"""
scrapers/sec_edgar.py
Fetches recent SEC filings for a company via the free EDGAR public API.
No proxy needed — SEC provides open access.

Cost: $0 (free public API).
"""
import logging
import requests
from datetime import datetime, timezone
from pipeline.db import insert_raw_signal

logger = logging.getLogger(__name__)

EDGAR_BASE = "https://data.sec.gov"
HEADERS    = {"User-Agent": "AlphaLens contact@alphalens.dev"}   # SEC requires a User-Agent


# ── Filings fetch ─────────────────────────────────────────────
def get_recent_filings(cik: str, form_type: str = "8-K", limit: int = 5) -> list[dict]:
    """
    Return the most recent `limit` filings of `form_type` for a CIK.
    CIK can be provided with or without leading zeros.
    """
    cik_padded = cik.lstrip("0").zfill(10)
    url = f"{EDGAR_BASE}/submissions/CIK{cik_padded}.json"

    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except requests.RequestException as exc:
        logger.error(f"[EDGAR] Failed to fetch CIK {cik}: {exc}")
        return []

    data = r.json()
    filings = data.get("filings", {}).get("recent", {})

    forms         = filings.get("form", [])
    dates         = filings.get("filingDate", [])
    accessions    = filings.get("accessionNumber", [])
    descriptions  = filings.get("primaryDocument", [])
    reporting     = filings.get("reportDate", [])

    results = []
    for form, date, accn, doc, rep in zip(forms, dates, accessions, descriptions, reporting):
        if form == form_type:
            accn_clean = accn.replace("-", "")
            results.append({
                "form":        form,
                "filing_date": date,
                "report_date": rep,
                "accession":   accn,
                "doc_url":     f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accn_clean}/{doc}",
                "viewer_url":  f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_padded}&type={form_type}&dateb=&owner=include&count=10",
            })
            if len(results) >= limit:
                break

    logger.info(f"[EDGAR] Found {len(results)} {form_type} filings for CIK {cik}")
    return results


# ── Full filing scan ──────────────────────────────────────────
def fetch_sec_filings(ticker: str, cik: str) -> dict:
    """
    Fetch both 8-K (material events) and 10-Q (quarterly) filings.
    Store in DB and return structured payload.
    """
    eightk = get_recent_filings(cik, "8-K",  limit=3)
    tenq   = get_recent_filings(cik, "10-Q", limit=2)
    tenk   = get_recent_filings(cik, "10-K", limit=1)

    payload = {
        "ticker":    ticker,
        "cik":       cik,
        "filings_8k":  eightk,
        "filings_10q": tenq,
        "filings_10k": tenk,
        "total_events": len(eightk),
        "last_8k_date": eightk[0]["filing_date"] if eightk else None,
        "fetched_at":  datetime.now(timezone.utc).isoformat(),
    }
    insert_raw_signal(ticker, "sec", payload)
    logger.info(f"[EDGAR] Stored filing data for {ticker}")
    return payload


# ── Analyze filing cadence ────────────────────────────────────
def compute_filing_signal(filings: dict) -> dict:
    """
    Simple rule-based signal from filing frequency.
    Frequent 8-Ks close to earnings = material events (positive or negative).
    """
    from datetime import date, timedelta

    eightks = filings.get("filings_8k", [])
    recent  = [
        f for f in eightks
        if f.get("filing_date") and
           (date.today() - datetime.strptime(f["filing_date"], "%Y-%m-%d").date()).days <= 30
    ]

    signal   = "neutral"
    evidence = []

    if len(recent) >= 3:
        signal   = "bullish"
        evidence.append(f"{len(recent)} material event (8-K) filings in past 30 days — active disclosure period")
    elif len(recent) == 0 and eightks:
        signal   = "neutral"
        evidence.append("No 8-K filings in past 30 days — quiet period likely")

    last_10q = filings.get("filings_10q", [])
    if last_10q:
        evidence.append(f"Last 10-Q filed {last_10q[0].get('filing_date', 'unknown')}")

    return {
        "signal":              signal,
        "recent_8k_count":     len(recent),
        "last_8k_date":        eightks[0]["filing_date"] if eightks else None,
        "evidence":            evidence,
        "confidence":          0.4,    # SEC data alone has low alpha; high context value
    }


# ── Company info ──────────────────────────────────────────────
def get_company_info(cik: str) -> dict:
    """Return company name, SIC code, and fiscal year end from EDGAR."""
    cik_padded = cik.lstrip("0").zfill(10)
    url = f"{EDGAR_BASE}/submissions/CIK{cik_padded}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        return {
            "name":             data.get("name"),
            "sic":              data.get("sic"),
            "sic_description":  data.get("sicDescription"),
            "state":            data.get("stateOfIncorporation"),
            "fiscal_year_end":  data.get("fiscalYearEnd"),
            "ticker":           data.get("tickers", [None])[0],
        }
    except Exception as exc:
        logger.error(f"[EDGAR] Company info failed for CIK {cik}: {exc}")
        return {}


# ── Dev mock ──────────────────────────────────────────────────
def mock_fetch(ticker: str) -> dict:
    from datetime import date, timedelta
    today = date.today()
    return {
        "ticker": ticker, "cik": "0000000000",
        "filings_8k": [
            {"form": "8-K", "filing_date": str(today - timedelta(days=5)),
             "doc_url": "https://www.sec.gov/", "accession": "0000000-24-000001"},
            {"form": "8-K", "filing_date": str(today - timedelta(days=18)),
             "doc_url": "https://www.sec.gov/", "accession": "0000000-24-000002"},
        ],
        "filings_10q": [
            {"form": "10-Q", "filing_date": str(today - timedelta(days=45)),
             "doc_url": "https://www.sec.gov/", "accession": "0000000-24-000003"},
        ],
        "filings_10k": [],
        "total_events": 2,
        "last_8k_date": str(today - timedelta(days=5)),
    }
