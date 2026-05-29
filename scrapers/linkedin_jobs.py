"""
scrapers/linkedin_jobs.py
Scrapes LinkedIn job postings for a company via Bright Data Web Scraper API.
Dataset ID: gd_lpfll7v5hcjmq79k1 (LinkedIn Job Postings)

Cost estimate: ~$35/month for 5 tickers scraped daily.
"""
import os
import time
import logging
import requests
from dotenv import load_dotenv
from pipeline.db import insert_raw_signal

load_dotenv()

logger = logging.getLogger(__name__)

BD_API_TOKEN = os.getenv("BD_API_TOKEN")
DATASET_ID   = "gd_lpfll7v5hcjmq79k1"      # LinkedIn Job Postings dataset
BASE_URL     = "https://api.brightdata.com/datasets/v3"

HEADERS = {
    "Authorization": f"Bearer {BD_API_TOKEN}",
    "Content-Type":  "application/json",
}


# ── Trigger snapshot ─────────────────────────────────────────
def trigger_snapshot(company: str) -> str:
    """
    Submit a scrape job. Returns snapshot_id which you poll later.
    """
    payload = {
        "dataset_id": DATASET_ID,
        "include_errors": True,
        "inputs": [
            {"keyword": company, "location": "United States", "time_range": "Past month"}
        ],
    }
    r = requests.post(f"{BASE_URL}/trigger", headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    snapshot_id = r.json().get("snapshot_id")
    logger.info(f"[LinkedIn] Triggered snapshot {snapshot_id} for '{company}'")
    return snapshot_id


# ── Poll until ready ─────────────────────────────────────────
def wait_for_snapshot(snapshot_id: str, max_wait_sec: int = 300) -> list[dict]:
    """
    Poll the snapshot endpoint until status = 'ready', then return rows.
    """
    url = f"{BASE_URL}/snapshot/{snapshot_id}"
    elapsed = 0
    while elapsed < max_wait_sec:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        status = data.get("status", "running")

        if status == "ready":
            logger.info(f"[LinkedIn] Snapshot {snapshot_id} ready — {len(data.get('items', []))} rows")
            return data.get("items", [])

        if status == "failed":
            raise RuntimeError(f"Bright Data snapshot {snapshot_id} failed: {data}")

        logger.debug(f"[LinkedIn] Snapshot {snapshot_id} status={status}, waiting…")
        time.sleep(15)
        elapsed += 15

    raise TimeoutError(f"Snapshot {snapshot_id} not ready after {max_wait_sec}s")


# ── Compute hiring velocity ───────────────────────────────────
def compute_hiring_velocity(jobs: list[dict]) -> dict:
    """
    Aggregate raw job listings into a structured hiring-velocity payload
    suitable for the Grok signal chain.
    """
    from collections import Counter
    import re

    # Bucket job titles into broad categories
    category_map = {
        "engineering":  re.compile(r"engineer|developer|swe|sde|architect|ml|ai|data scientist", re.I),
        "sales":        re.compile(r"sales|account exec|business dev|revenue", re.I),
        "ops":          re.compile(r"operat|supply chain|logistics|warehouse|fulfillment", re.I),
        "finance":      re.compile(r"financ|accounti|fp&a|controller|treasury", re.I),
        "hr":           re.compile(r"recruiter|hr |human resour|people ops|talent", re.I),
        "data_center":  re.compile(r"data center|gpu|server|infra|cloud ops|network eng", re.I),
    }

    categories: Counter = Counter()
    locations:  Counter = Counter()
    seniority:  Counter = Counter()

    for job in jobs:
        title = job.get("title", "") or ""
        for cat, pattern in category_map.items():
            if pattern.search(title):
                categories[cat] += 1
        loc = job.get("location", "Unknown")
        locations[loc.split(",")[0].strip()] += 1

        title_lower = title.lower()
        if any(w in title_lower for w in ["senior", "sr.", "staff", "principal", "director"]):
            seniority["senior"] += 1
        elif any(w in title_lower for w in ["junior", "jr.", "associate", "entry"]):
            seniority["junior"] += 1
        else:
            seniority["mid"] += 1

    return {
        "total_postings":    len(jobs),
        "by_category":       dict(categories.most_common(10)),
        "top_locations":     dict(locations.most_common(5)),
        "seniority_mix":     dict(seniority),
        "sample_titles":     [j.get("title") for j in jobs[:10]],
    }


# ── Main entry point ─────────────────────────────────────────
def fetch_linkedin_jobs(company: str, ticker: str) -> dict:
    """
    Full flow: trigger → poll → aggregate → store in DB.
    Returns the velocity payload.
    """
    logger.info(f"[LinkedIn] Fetching jobs for {ticker} ({company})")
    snapshot_id = trigger_snapshot(company)
    jobs        = wait_for_snapshot(snapshot_id)
    velocity    = compute_hiring_velocity(jobs)

    insert_raw_signal(ticker, "linkedin", {"velocity": velocity, "raw_count": len(jobs)})
    logger.info(f"[LinkedIn] Stored hiring data for {ticker}: {velocity['total_postings']} postings")
    return velocity


# ── Dev / test helper ─────────────────────────────────────────
def mock_fetch(ticker: str) -> dict:
    """Returns synthetic data so you can develop offline without Bright Data credits."""
    import random
    base = random.randint(40, 300)
    return {
        "total_postings": base,
        "by_category": {
            "engineering": int(base * 0.45),
            "sales":       int(base * 0.20),
            "ops":         int(base * 0.15),
            "data_center": int(base * 0.10),
            "hr":          int(base * 0.05),
            "finance":     int(base * 0.05),
        },
        "top_locations": {"San Francisco": 12, "New York": 8, "Seattle": 6, "Austin": 4, "Remote": 10},
        "seniority_mix": {"senior": int(base * 0.3), "mid": int(base * 0.5), "junior": int(base * 0.2)},
        "sample_titles": [
            "Senior Software Engineer, ML Platform",
            "GPU Validation Engineer",
            "Data Center Operations Lead",
            "VP of Sales, Enterprise",
        ],
    }
