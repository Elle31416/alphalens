"""
pipeline/db.py
PostgreSQL connection pool and query helpers.
"""
import os
import json
import logging
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Connection pool ───────────────────────────────────────────
_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        conn_str = os.getenv("DATABASE_URL")
        if conn_str:
            # Support Render's unified connection string
            _pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=conn_str)
        else:
            _pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", 5432)),
                dbname=os.getenv("POSTGRES_DB", "alphalens"),
                user=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", "alpha123"),
            )
    return _pool


@contextmanager
def get_conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ── Generic helpers ───────────────────────────────────────────
def query(sql: str, params: tuple = (), dict_cursor: bool = True) -> list[dict]:
    """Execute SELECT and return list of row dicts."""
    with get_conn() as conn:
        cur_cls = psycopg2.extras.RealDictCursor if dict_cursor else psycopg2.extras.DictCursor
        with conn.cursor(cursor_factory=cur_cls) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def execute(sql: str, params: tuple = ()) -> None:
    """Execute INSERT / UPDATE / DELETE."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


def execute_returning(sql: str, params: tuple = ()) -> dict | None:
    """Execute INSERT RETURNING and return the row."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None


# ── Domain helpers ────────────────────────────────────────────
def get_tickers() -> list[dict]:
    return query("SELECT * FROM tickers ORDER BY symbol")


def insert_raw_signal(ticker: str, source: str, payload: dict) -> None:
    execute(
        "INSERT INTO raw_signals (ticker, source, payload) VALUES (%s, %s, %s)",
        (ticker, source, json.dumps(payload)),
    )
    logger.debug(f"Stored raw signal: {ticker}/{source}")


def upsert_processed_signal(
    ticker: str,
    hiring_signal: dict,
    pricing_signal: dict,
    rating_signal: dict,
    filing_signal: dict,
    composite_score: int,
    confidence_low: int,
    confidence_high: int,
    overall_signal: str,
    analyst_bullets: list[str],
) -> None:
    execute(
        """
        INSERT INTO processed_signals
            (ticker, hiring_signal, pricing_signal, rating_signal, filing_signal,
             composite_score, confidence_low, confidence_high, overall_signal, analyst_bullets)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, run_date)
        DO UPDATE SET
            hiring_signal   = EXCLUDED.hiring_signal,
            pricing_signal  = EXCLUDED.pricing_signal,
            rating_signal   = EXCLUDED.rating_signal,
            filing_signal   = EXCLUDED.filing_signal,
            composite_score = EXCLUDED.composite_score,
            confidence_low  = EXCLUDED.confidence_low,
            confidence_high = EXCLUDED.confidence_high,
            overall_signal  = EXCLUDED.overall_signal,
            analyst_bullets = EXCLUDED.analyst_bullets,
            created_at      = NOW()
        """,
        (
            ticker,
            json.dumps(hiring_signal),
            json.dumps(pricing_signal),
            json.dumps(rating_signal),
            json.dumps(filing_signal),
            composite_score,
            confidence_low,
            confidence_high,
            overall_signal,
            analyst_bullets,
        ),
    )


def get_latest_signals() -> list[dict]:
    return query(
        """
        SELECT DISTINCT ON (ticker)
            ticker, run_date, composite_score, confidence_low, confidence_high,
            overall_signal, analyst_bullets,
            hiring_signal, pricing_signal, rating_signal, filing_signal
        FROM processed_signals
        ORDER BY ticker, run_date DESC
        """
    )


def get_ticker_history(ticker: str, days: int = 30) -> list[dict]:
    return query(
        """
        SELECT * FROM raw_signals
        WHERE ticker = %s
        ORDER BY scraped_at DESC
        LIMIT %s
        """,
        (ticker.upper(), days),
    )


def get_ticker_signals(ticker: str) -> list[dict]:
    return query(
        """
        SELECT * FROM processed_signals
        WHERE ticker = %s
        ORDER BY run_date DESC
        LIMIT 30
        """,
        (ticker.upper(),),
    )
