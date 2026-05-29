"""
api/main.py
FastAPI backend — exposes signal data to the Next.js dashboard.

Endpoints:
  GET  /signals              → latest composite signal for all tickers
  GET  /signals/{ticker}     → historical signals for a specific ticker
  GET  /signals/{ticker}/raw → raw scraper data (30 most recent)
  GET  /signals/export/csv   → downloadable CSV for Bloomberg / Excel
  GET  /tickers              → watchlist configuration
  POST /tickers              → add a new ticker
  POST /pipeline/run         → manually trigger the nightly pipeline
  GET  /health               → service health check
"""
import os
import io
import csv
import logging
from datetime import date
from dotenv import load_dotenv

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AlphaLens API",
    description="Alternative-data earnings signal platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict to your frontend domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "alphalens-api"}


# ── Signals ───────────────────────────────────────────────────
@app.get("/signals")
def get_signals():
    """Return the latest composite signal for all tickers, sorted by score descending."""
    try:
        from pipeline.db import get_latest_signals
        rows = get_latest_signals()
        return {"signals": rows, "count": len(rows)}
    except Exception as exc:
        logger.error(f"/signals error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/signals/{ticker}")
def get_ticker_signals(ticker: str):
    """Return the last 30 days of processed signals for a ticker."""
    try:
        from pipeline.db import get_ticker_signals, get_ticker_history
        signals = get_ticker_signals(ticker.upper())
        raw     = get_ticker_history(ticker.upper(), days=30)
        return {
            "ticker":   ticker.upper(),
            "signals":  signals,
            "raw":      raw,
        }
    except Exception as exc:
        logger.error(f"/signals/{ticker} error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ── CSV export ────────────────────────────────────────────────
@app.get("/signals/export/csv")
def export_csv():
    """
    Export all latest signals as CSV.
    Compatible with Bloomberg, Excel, and backtesting tools.
    """
    try:
        from pipeline.db import get_latest_signals
        rows = get_latest_signals()

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "ticker", "run_date", "composite_score",
            "confidence_low", "confidence_high", "overall_signal",
            "analyst_bullet_1", "analyst_bullet_2", "analyst_bullet_3",
            "hiring_signal", "pricing_signal", "rating_signal", "filing_signal",
        ])

        for row in rows:
            bullets  = row.get("analyst_bullets") or []
            writer.writerow([
                row.get("ticker"),
                row.get("run_date"),
                row.get("composite_score"),
                row.get("confidence_low"),
                row.get("confidence_high"),
                row.get("overall_signal"),
                bullets[0] if len(bullets) > 0 else "",
                bullets[1] if len(bullets) > 1 else "",
                bullets[2] if len(bullets) > 2 else "",
                (row.get("hiring_signal")  or {}).get("signal", ""),
                (row.get("pricing_signal") or {}).get("signal", ""),
                (row.get("rating_signal")  or {}).get("signal", ""),
                (row.get("filing_signal")  or {}).get("signal", ""),
            ])

        output.seek(0)
        filename = f"alphalens_signals_{date.today().isoformat()}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as exc:
        logger.error(f"/signals/export/csv error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Tickers ───────────────────────────────────────────────────
@app.get("/tickers")
def get_tickers():
    from pipeline.db import get_tickers
    return {"tickers": get_tickers()}


class TickerCreate(BaseModel):
    symbol:             str
    company:            str
    linkedin_company_id: str | None = None
    amazon_asins:        str | None = None
    ios_app_id:          str | None = None
    android_pkg:         str | None = None
    sec_cik:             str | None = None


@app.post("/tickers")
def add_ticker(body: TickerCreate):
    from pipeline.db import execute
    try:
        execute(
            """
            INSERT INTO tickers
                (symbol, company, linkedin_company_id, amazon_asins, ios_app_id, android_pkg, sec_cik)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE SET
                company              = EXCLUDED.company,
                linkedin_company_id  = EXCLUDED.linkedin_company_id,
                amazon_asins         = EXCLUDED.amazon_asins,
                ios_app_id           = EXCLUDED.ios_app_id,
                android_pkg          = EXCLUDED.android_pkg,
                sec_cik              = EXCLUDED.sec_cik
            """,
            (
                body.symbol.upper(), body.company,
                body.linkedin_company_id, body.amazon_asins,
                body.ios_app_id, body.android_pkg, body.sec_cik,
            ),
        )
        return {"status": "ok", "ticker": body.symbol.upper()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Manual pipeline trigger ───────────────────────────────────
@app.post("/pipeline/run")
def trigger_pipeline(background_tasks: BackgroundTasks, ticker: str | None = None):
    """
    Manually trigger a pipeline run. Optionally for a single ticker.
    Runs in the background; returns immediately.
    """
    def _run(t: str | None):
        from pipeline.scheduler import run_nightly, process_ticker, get_active_config, verify_environment
        
        if not verify_environment():
            return

        if t:
            config = get_active_config()
            cfg = config.get(t.upper())
            if cfg:
                process_ticker(t.upper(), cfg)
            else:
                logger.error(f"Unknown ticker {t}")
        else:
            run_nightly()

    background_tasks.add_task(_run, ticker)
    return {"status": "started", "ticker": ticker or "all"}


# ── Backtest ──────────────────────────────────────────────────
@app.get("/backtest")
def get_backtest():
    from pipeline.db import query
    rows = query("SELECT * FROM backtest_results ORDER BY signal_date DESC")
    return {"results": rows}


@app.post("/backtest")
def add_backtest(data: dict):
    from pipeline.db import execute
    try:
        execute(
            """
            INSERT INTO backtest_results
                (ticker, signal_date, alphalens_signal, composite_score, key_evidence, actual_result, actual_move_pct)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data["ticker"], data["signal_date"], data.get("alphalens_signal"),
                data.get("composite_score"), data.get("key_evidence", []),
                data.get("actual_result"), data.get("actual_move_pct"),
            ),
        )
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        # Render and other PaaS providers inject the PORT variable automatically
        port=int(os.getenv("PORT", os.getenv("API_PORT", 8000))),
        reload=os.getenv("API_RELOAD", "false").lower() == "true",
    )
