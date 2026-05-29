"""
scrapers/appstore_ratings.py
Scrapes App Store / Play Store ratings via Bright Data Scraping Browser.
Scraping Browser = real Chrome in the cloud via CDP — handles JS rendering.

Cost estimate: ~$20/month for 5 tickers × 2 platforms scraped daily.
"""
import os
import re
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from pipeline.db import insert_raw_signal

load_dotenv()

logger = logging.getLogger(__name__)

# ── Bright Data Scraping Browser endpoint (CDP) ───────────────
_USER  = os.getenv("BD_UNLOCKER_USER", "")
_PASS  = os.getenv("BD_UNLOCKER_PASS", "")
_HOST  = os.getenv("BRIGHTDATA_UNLOCKER_HOST", "brd.superproxy.io")
SBR_CDP = f"wss://{_USER}:{_PASS}@{_HOST}:9222"


# ── Core scrape ───────────────────────────────────────────────
def scrape_app_rating(app_id: str, platform: str = "ios") -> dict | None:
    """
    Connect to Scraping Browser via CDP and extract the app's star rating,
    review count, and title.

    platform: "ios"     → apps.apple.com  (App Store)
              "android" → play.google.com  (Play Store)
    """
    from playwright.sync_api import sync_playwright

    if platform == "ios":
        url = f"https://apps.apple.com/us/app/id{app_id}"
    else:
        url = f"https://play.google.com/store/apps/details?id={app_id}"

    logger.info(f"[AppStore] Scraping {platform} app {app_id} via Scraping Browser")

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(SBR_CDP)
        ctx     = browser.new_context()
        page    = ctx.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(3000)   # let JS settle

            # ── iOS App Store selectors ───────────────────────
            if platform == "ios":
                rating_el  = page.query_selector("span.we-rating-count-stars-bar-value") \
                          or page.query_selector("span[class*='rating']")               \
                          or page.query_selector("div.we-customer-ratings__averages")
                rating_str = rating_el.inner_text().strip() if rating_el else None

                count_el   = page.query_selector("div.we-customer-ratings__count")
                count_str  = count_el.inner_text().strip() if count_el else None

                title_el   = page.query_selector("h1.product-header__title")
                title      = title_el.inner_text().strip() if title_el else None

            # ── Google Play Store selectors ───────────────────
            else:
                rating_el  = page.query_selector("div[itemprop='starRating'] meta[itemprop='ratingValue']")
                rating_str = rating_el.get_attribute("content") if rating_el else None
                if not rating_str:
                    rating_el  = page.query_selector("div.TT9eCd")
                    rating_str = rating_el.inner_text().strip() if rating_el else None

                count_el   = page.query_selector("div.g1rdde")
                count_str  = count_el.inner_text().strip() if count_el else None

                title_el   = page.query_selector("h1.Fd93Bb")
                title      = title_el.inner_text().strip() if title_el else None

            rating = _parse_rating(rating_str)
            count  = _parse_count(count_str)

            result = {
                "app_id":       app_id,
                "platform":     platform,
                "title":        title,
                "rating":       rating,
                "review_count": count,
                "raw_rating":   rating_str,
                "scraped_at":   datetime.now(timezone.utc).isoformat(),
            }
            logger.info(f"[AppStore] {platform}/{app_id}: ★{rating} ({count} reviews)")
            return result

        except Exception as exc:
            logger.error(f"[AppStore] Failed to scrape {platform}/{app_id}: {exc}")
            return {"app_id": app_id, "platform": platform, "error": str(exc)}
        finally:
            page.close()
            ctx.close()
            browser.close()


# ── Fetch ratings for a ticker ────────────────────────────────
def fetch_app_ratings(ticker: str, ios_app_id: str | None, android_pkg: str | None) -> dict:
    """
    Scrape iOS and/or Android ratings, store in DB, return combined result.
    """
    results = {}

    if ios_app_id:
        results["ios"] = scrape_app_rating(ios_app_id, "ios")
    if android_pkg:
        results["android"] = scrape_app_rating(android_pkg, "android")

    insert_raw_signal(ticker, "appstore", results)
    logger.info(f"[AppStore] Stored ratings for {ticker}")
    return results


# ── Compute rating delta ──────────────────────────────────────
def compute_rating_delta(history: list[dict]) -> dict:
    """
    Given a list of {scraped_at, rating} records (oldest→newest),
    compute 30d delta and recent trend.
    """
    import pandas as pd

    if len(history) < 2:
        return {}

    df = pd.DataFrame(history)
    df["rating"]     = pd.to_numeric(df["rating"], errors="coerce")
    df["scraped_at"] = pd.to_datetime(df["scraped_at"])
    df = df.sort_values("scraped_at")

    current   = float(df["rating"].iloc[-1])
    prev_30d  = float(df["rating"].iloc[0]) if len(df) >= 1 else current
    delta_30d = round(current - prev_30d, 3)

    return {
        "current_rating": current,
        "delta_30d":       delta_30d,
        "trend":           "up"     if delta_30d >  0.05 else
                           "down"   if delta_30d < -0.05 else "flat",
        "volatility":      float(df["rating"].std()),
    }


# ── Parse helpers ─────────────────────────────────────────────
def _parse_rating(raw: str | None) -> float | None:
    if not raw:
        return None
    match = re.search(r"[\d.]+", raw)
    if match:
        try:
            v = float(match.group())
            return v if v <= 5 else None
        except ValueError:
            return None
    return None


def _parse_count(raw: str | None) -> int | None:
    if not raw:
        return None
    raw = raw.replace(",", "").replace(".", "").strip()
    match = re.search(r"\d+", raw)
    if match:
        try:
            return int(match.group())
        except ValueError:
            return None
    return None


# ── Dev mock ──────────────────────────────────────────────────
def mock_fetch(ticker: str) -> dict:
    import random
    rating = round(random.uniform(3.8, 4.9), 1)
    return {
        "ios": {"app_id": "000000", "platform": "ios", "rating": rating,
                "review_count": random.randint(10_000, 2_000_000), "title": f"{ticker} App"},
        "android": {"app_id": "com.example", "platform": "android", "rating": round(rating + random.uniform(-0.2, 0.2), 1),
                    "review_count": random.randint(5_000, 1_000_000)},
    }
