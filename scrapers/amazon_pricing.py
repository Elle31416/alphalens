"""
scrapers/amazon_pricing.py
Scrapes Amazon product prices via Bright Data Web Unlocker proxy.
Web Unlocker handles bot-detection + rotating residential IPs automatically.

Cost estimate: ~$25/month for 5 tickers × ~3 ASINs each scraped daily.
"""
import os
import logging
import requests
import urllib3
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pipeline.db import insert_raw_signal

load_dotenv()

# Suppress noisy SSL warnings in terminal when using residential proxies
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# ── Proxy config (Web Unlocker zone) ─────────────────────────
_USER = os.getenv("BD_UNLOCKER_USER", "")
_PASS = os.getenv("BD_UNLOCKER_PASS", "")
_HOST = os.getenv("BRIGHTDATA_UNLOCKER_HOST", "brd.superproxy.io")
_PORT = os.getenv("BRIGHTDATA_UNLOCKER_PORT", "22225")

PROXY = {
    "http":  f"http://{_USER}:{_PASS}@{_HOST}:{_PORT}",
    "https": f"http://{_USER}:{_PASS}@{_HOST}:{_PORT}",
}

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


# ── Single ASIN scrape ────────────────────────────────────────
def scrape_amazon_price(asin: str, ticker: str) -> dict:
    """
    Fetch current price + title for a single Amazon ASIN.
    Returns dict with price, title, rating, review_count, availability.
    """
    url = f"https://www.amazon.com/dp/{asin}"
    logger.info(f"[Amazon] Scraping ASIN {asin} for {ticker}")

    try:
        r = requests.get(url, proxies=PROXY, headers=HEADERS, timeout=30, verify=False)
        r.raise_for_status()
    except requests.RequestException as exc:
        logger.error(f"[Amazon] Request failed for {asin}: {exc}")
        return {"asin": asin, "ticker": ticker, "error": str(exc)}

    soup = BeautifulSoup(r.text, "html.parser")

    # Price — try multiple selectors
    price = None
    for sel in [
        "span.a-price-whole",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "span[data-a-color='price'] span.a-offscreen",
    ]:
        tag = soup.select_one(sel)
        if tag:
            raw = tag.get_text(strip=True).replace(",", "").replace("$", "")
            try:
                price = float(raw)
            except ValueError:
                pass
            if price:
                break

    # Title
    title_tag = soup.find("span", id="productTitle")
    title = title_tag.get_text(strip=True) if title_tag else None

    # Star rating
    rating_tag = soup.find("span", {"data-hook": "rating-out-of-text"})
    if not rating_tag:
        rating_tag = soup.find("span", {"class": "a-icon-alt"})
    rating = rating_tag.get_text(strip=True)[:3] if rating_tag else None

    # Review count
    reviews_tag = soup.find("span", id="acrCustomerReviewText")
    review_count = reviews_tag.get_text(strip=True) if reviews_tag else None

    # Availability
    avail_tag = soup.find("div", id="availability")
    availability = avail_tag.get_text(strip=True)[:60] if avail_tag else None

    result = {
        "asin":         asin,
        "ticker":       ticker,
        "title":        title,
        "price":        price,
        "rating":       rating,
        "review_count": review_count,
        "availability": availability,
        "scraped_at":   datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"[Amazon] {ticker}/{asin}: ${price}")
    return result


# ── Multi-ASIN batch ──────────────────────────────────────────
def fetch_amazon_prices(ticker: str, asins: list[str]) -> list[dict]:
    """
    Scrape all ASINs for a ticker, store in DB, return price list.
    """
    results = []
    for asin in asins:
        data = scrape_amazon_price(asin, ticker)
        results.append(data)

    # Compute velocity vs last snapshot
    payload = {
        "prices":      results,
        "avg_price":   _safe_avg([r.get("price") for r in results if r.get("price")]),
        "asin_count":  len([r for r in results if not r.get("error")]),
    }
    insert_raw_signal(ticker, "amazon", payload)
    logger.info(f"[Amazon] Stored {len(results)} price points for {ticker}")
    return results


def _safe_avg(vals: list) -> float | None:
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


# ── Compute pricing velocity from history ─────────────────────
def compute_pricing_velocity(price_history: list[dict]) -> dict:
    """
    Given a list of {date, avg_price} records (oldest→newest),
    compute pct_change, 7-day rolling velocity, and acceleration.
    """
    import pandas as pd

    if not price_history:
        return {}

    df = pd.DataFrame(price_history)
    df = df.sort_values("scraped_at")
    df["price"] = pd.to_numeric(df.get("avg_price", df.get("price", 0)), errors="coerce")
    df["pct_change"]  = df["price"].pct_change()
    df["velocity_7d"] = df["pct_change"].rolling(7).mean()
    df["accel"]       = df["velocity_7d"].diff()

    tail = df.tail(14)
    return {
        "current_avg_price":    float(df["price"].iloc[-1]) if not df.empty else None,
        "14d_price_change_pct": float(df["pct_change"].tail(14).sum() * 100),
        "7d_velocity_avg":      float(tail["velocity_7d"].mean() * 100),
        "acceleration":         float(tail["accel"].mean() * 100),
        "trend":                "down" if tail["velocity_7d"].mean() < -0.002 else
                                "up"   if tail["velocity_7d"].mean() >  0.002 else "flat",
        "records":              tail[["price", "pct_change", "velocity_7d"]].to_dict("records"),
    }


# ── Dev / test mock ───────────────────────────────────────────
def mock_fetch(ticker: str) -> list[dict]:
    import random
    base = random.uniform(50, 500)
    return [
        {"asin": f"B0{i:08d}", "ticker": ticker, "price": round(base * random.uniform(0.85, 1.15), 2),
         "title": f"{ticker} Product {i}", "availability": "In Stock"}
        for i in range(1, 4)
    ]
