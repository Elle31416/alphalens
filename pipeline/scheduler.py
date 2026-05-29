"""
pipeline/scheduler.py
Nightly pipeline: runs all 4 scrapers in parallel for each ticker,
then sends data through the Grok/LangGraph AI pipeline.

Schedule: weeknights Mon–Fri at 23:00 EST.
Run manually: python -m pipeline.scheduler
"""
import os
import logging
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Ticker configuration ──────────────────────────────────────
# Loaded from DB at runtime; this is the fallback config for testing.
TICKER_CONFIG = {
    "AAPL":  {
        "company":     "Apple",
        "asins":       ["B0BDHB9Y8H", "B0CHX2QNKQ"],
        "ios_app_id":  "284417350",     # App Store app
        "android_pkg": "com.apple.android.music",
        "sec_cik":     "0000320193",
    },
    "MSFT":  {
        "company":     "Microsoft",
        "asins":       ["B09DKJ3WPJ"],
        "ios_app_id":  "469263332",
        "android_pkg": "com.microsoft.office.word",
        "sec_cik":     "0000789019",
    },
    "AMZN":  {
        "company":     "Amazon",
        "asins":       ["B08H75RTZ8"],
        "ios_app_id":  "297606951",
        "android_pkg": "com.amazon.mShop.android.shopping",
        "sec_cik":     "0001018724",
    },
    "GOOGL": {
        "company":     "Google",
        "asins":       ["B09CXSBSQX"],
        "ios_app_id":  "544007664",
        "android_pkg": "com.google.android.googlequicksearchbox",
        "sec_cik":     "0001652044",
    },
    "META":  {
        "company":     "Meta",
        "asins":       ["B0BZZ3NFKB"],
        "ios_app_id":  "284882215",
        "android_pkg": "com.facebook.katana",
        "sec_cik":     "0001326801",
    },
    "NVDA":  {
        "company":     "NVIDIA",
        "asins":       ["B07QP84KLQ"],
        "ios_app_id":  None,
        "android_pkg": None,
        "sec_cik":     "0001045810",
    },
}

USE_MOCK = os.getenv("USE_MOCK_DATA", "false").lower() == "true"

def get_active_config() -> dict:
    """Fetch ticker configuration from database, falling back to TICKER_CONFIG."""
    from pipeline.db import get_tickers
    try:
        db_rows = get_tickers()
        if not db_rows:
            return TICKER_CONFIG
        
        config = {}
        for row in db_rows:
            # Map DB columns to the format expected by runners
            config[row['symbol']] = {
                "company":     row['company'],
                "asins":       [a.strip() for a in (row.get('amazon_asins') or "").split(",") if a.strip()],
                "ios_app_id":  row.get('ios_app_id'),
                "android_pkg": row.get('android_pkg'),
                "sec_cik":     row.get('sec_cik'),
            }
        return config
    except Exception as exc:
        logger.error(f"[Pipeline] Failed to fetch config from DB, using fallback: {exc}")
        return TICKER_CONFIG


# ── Scraper runners ───────────────────────────────────────────
def run_linkedin(ticker: str, cfg: dict) -> dict:
    if USE_MOCK:
        from scrapers.linkedin_jobs import mock_fetch
        return mock_fetch(ticker)
    from scrapers.linkedin_jobs import fetch_linkedin_jobs
    return fetch_linkedin_jobs(cfg["company"], ticker)


def run_amazon(ticker: str, cfg: dict) -> dict:
    if USE_MOCK:
        from scrapers.amazon_pricing import mock_fetch
        return {"prices": mock_fetch(ticker), "avg_price": 150.0}
    from scrapers.amazon_pricing import fetch_amazon_prices
    return {"prices": fetch_amazon_prices(ticker, cfg["asins"])}


def run_appstore(ticker: str, cfg: dict) -> dict:
    if USE_MOCK:
        from scrapers.appstore_ratings import mock_fetch
        return mock_fetch(ticker)
    from scrapers.appstore_ratings import fetch_app_ratings
    return fetch_app_ratings(ticker, cfg.get("ios_app_id"), cfg.get("android_pkg"))


def run_edgar(ticker: str, cfg: dict) -> dict:
    if USE_MOCK:
        from scrapers.sec_edgar import mock_fetch
        return mock_fetch(ticker)
    from scrapers.sec_edgar import fetch_sec_filings
    return fetch_sec_filings(ticker, cfg["sec_cik"])


# ── Per-ticker pipeline ───────────────────────────────────────
def process_ticker(ticker: str, cfg: dict) -> bool:
    """
    Run all 4 scrapers concurrently for one ticker,
    then run the AI pipeline to produce composite signal.
    """
    logger.info(f"[Pipeline] ── Starting {ticker} ──")
    start = datetime.now(timezone.utc)

    # Parallel scrape
    scrapers = {
        "hiring":  (run_linkedin,  ticker, cfg),
        "pricing": (run_amazon,    ticker, cfg),
        "ratings": (run_appstore,  ticker, cfg),
        "filings": (run_edgar,     ticker, cfg),
    }
    results: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=4) as ex:
        future_map = {
            ex.submit(fn, t, c): name
            for name, (fn, t, c) in scrapers.items()
        }
        for fut in as_completed(future_map):
            name = future_map[fut]
            try:
                results[name] = fut.result()
                logger.info(f"[Pipeline] {ticker}/{name} ✓")
            except Exception as exc:
                logger.error(f"[Pipeline] {ticker}/{name} ✗ {exc}")
                results[name] = {}

    # AI signal generation
    try:
        from ai.langgraph_orchestrator import run_ticker
        state = run_ticker(
            ticker,
            hiring_data  = results.get("hiring",  {}),
            pricing_data = results.get("pricing", {}),
            ratings_data = results.get("ratings", {}),
            filings_data = results.get("filings", {}),
        )

        from pipeline.db import upsert_processed_signal
        upsert_processed_signal(
            ticker         = ticker,
            hiring_signal  = state.get("hiring_signal",  {}),
            pricing_signal = state.get("pricing_signal", {}),
            rating_signal  = state.get("rating_signal",  {}),
            filing_signal  = state.get("filing_signal",  {}),
            composite_score = state.get("composite_score", 50),
            confidence_low  = state.get("confidence_low",  40),
            confidence_high = state.get("confidence_high", 60),
            overall_signal  = state.get("overall_signal",  "neutral"),
            analyst_bullets = state.get("analyst_bullets", []),
        )

        elapsed = (datetime.now(timezone.utc) - start).seconds
        logger.info(
            f"[Pipeline] {ticker} DONE ✓ score={state.get('composite_score')} "
            f"signal={state.get('overall_signal')} in {elapsed}s"
        )
        return True

    except Exception as exc:
        logger.error(f"[Pipeline] {ticker} AI pipeline failed: {exc}")
        return False


def verify_environment() -> bool:
    """Check if required Bright Data credentials are present in non-mock mode."""
    if USE_MOCK:
        return True
    if not os.getenv("BD_UNLOCKER_USER") or not os.getenv("BD_UNLOCKER_PASS"):
        logger.error("[Pipeline] Missing Bright Data credentials (BD_UNLOCKER_USER/PASS) in environment.")
        return False
    return True


# ── Nightly batch ─────────────────────────────────────────────
def run_nightly():
    logger.info("═══════════════════════════════════════")
    config = get_active_config()
    
    logger.info(f"AlphaLens nightly run — {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"Tickers: {list(config.keys())}")
    logger.info(f"Mode: {'MOCK' if USE_MOCK else 'LIVE'}")
    logger.info("═══════════════════════════════════════")

    if not verify_environment():
        return

    success, failed = [], []
    for ticker, cfg in config.items():
        ok = process_ticker(ticker, cfg)
        (success if ok else failed).append(ticker)

    logger.info(f"Nightly run complete. ✓ {success} | ✗ {failed}")


# ── Scheduler setup ───────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if "--now" in sys.argv:
        # Run immediately (for testing)
        run_nightly()
    else:
        from apscheduler.schedulers.blocking import BlockingScheduler
        scheduler = BlockingScheduler(timezone="America/New_York")
        scheduler.add_job(run_nightly, "cron", day_of_week="mon-fri", hour=23, minute=0)
        logger.info("Scheduler started — runs Mon–Fri at 23:00 EST. Ctrl+C to stop.")
        try:
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped.")
