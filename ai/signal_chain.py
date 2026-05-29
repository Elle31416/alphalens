"""
ai/signal_chain.py
Four Grok signal chains — one per data source.
Each takes structured data and returns a JSON signal dict.

Model: grok-3-mini  ~$0.003/ticker/night at typical data volumes.
"""
import os
import json
import re
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── xAI / Grok client ─────────────────────────────────────────
client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

MODEL     = "grok-3-mini"
MAX_TOKENS = 800


def _call_grok(system: str, user: str) -> dict:
    """
    Single call to Grok. Returns parsed JSON dict.
    Falls back to an error dict on failure.
    """
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        
        # Robust extraction of JSON from potential markdown fences
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        clean_json = json_match.group(1) if json_match else raw
        return json.loads(clean_json)
    except json.JSONDecodeError as exc:
        logger.error(f"[Grok] JSON parse error: {exc}\nRaw: {resp.choices[0].message.content[:200]}")
        return {"signal": "neutral", "confidence": 0, "reasoning": "parse error", "key_evidence": []}
    except Exception as exc:
        logger.error(f"[Grok] API error: {exc}")
        return {"signal": "neutral", "confidence": 0, "reasoning": str(exc), "key_evidence": []}


# ─────────────────────────────────────────────────────────────
#  Chain 1 — Hiring velocity
# ─────────────────────────────────────────────────────────────
HIRING_SYSTEM = """You are a quantitative analyst who specialises in interpreting
corporate hiring patterns as leading indicators for earnings surprises.

Given structured LinkedIn job-posting data for a public company, analyse:
1. Total posting volume vs expected baseline
2. Which job categories are surging or collapsing (engineering, sales, ops, data_center, etc.)
3. Seniority mix shift (a surge in senior hires = scaling; junior = cost-cutting)
4. What the pattern historically predicts about the next earnings report

Return ONLY valid JSON — no markdown, no extra text:
{
  "signal":       "bullish" | "bearish" | "neutral",
  "confidence":   <float 0.0–1.0>,
  "reasoning":    "<2–3 sentence explanation>",
  "key_evidence": ["<evidence point 1>", "<evidence point 2>", "<evidence point 3>"]
}"""


def analyze_hiring(ticker: str, job_data: dict) -> dict:
    user = f"Ticker: {ticker}\nJob posting velocity data:\n{json.dumps(job_data, indent=2)}"
    result = _call_grok(HIRING_SYSTEM, user)
    logger.info(f"[Grok/Hiring] {ticker}: signal={result.get('signal')}, conf={result.get('confidence')}")
    return result


# ─────────────────────────────────────────────────────────────
#  Chain 2 — Amazon pricing velocity
# ─────────────────────────────────────────────────────────────
PRICING_SYSTEM = """You are a pricing intelligence analyst who interprets Amazon
product price movements as leading indicators for corporate earnings.

Given daily price history for a company's key Amazon SKUs, analyse:
1. Price velocity (% change) and acceleration over the last 7 and 14 days
2. Whether discounting has accelerated — a warning sign for demand weakness
3. Price increases that signal supply constraints or strong demand
4. What this pricing pattern typically predicts about upcoming earnings

Return ONLY valid JSON — no markdown, no extra text:
{
  "signal":       "bullish" | "bearish" | "neutral",
  "confidence":   <float 0.0–1.0>,
  "reasoning":    "<2–3 sentence explanation>",
  "key_evidence": ["<evidence point 1>", "<evidence point 2>", "<evidence point 3>"],
  "price_trend":  "up" | "down" | "flat"
}"""


def analyze_pricing(ticker: str, price_data: dict) -> dict:
    user = f"Ticker: {ticker}\nAmazon pricing velocity data:\n{json.dumps(price_data, indent=2)}"
    result = _call_grok(PRICING_SYSTEM, user)
    logger.info(f"[Grok/Pricing] {ticker}: signal={result.get('signal')}, conf={result.get('confidence')}")
    return result


# ─────────────────────────────────────────────────────────────
#  Chain 3 — App Store ratings delta
# ─────────────────────────────────────────────────────────────
RATINGS_SYSTEM = """You are a consumer-sentiment analyst who interprets mobile app
rating movements as leading indicators for consumer-facing company earnings.

Given app store rating history (iOS + Android) for a company's key app, analyse:
1. 30-day rating delta and momentum
2. Whether rating change is broad-based (both platforms) or isolated
3. Velocity: is the trend accelerating or reversing?
4. What consumer sentiment shift predicts about engagement metrics in earnings

Return ONLY valid JSON — no markdown, no extra text:
{
  "signal":        "bullish" | "bearish" | "neutral",
  "confidence":    <float 0.0–1.0>,
  "reasoning":     "<2–3 sentence explanation>",
  "key_evidence":  ["<evidence point 1>", "<evidence point 2>", "<evidence point 3>"],
  "sentiment_trend": "improving" | "deteriorating" | "stable"
}"""


def analyze_ratings(ticker: str, ratings_data: dict) -> dict:
    user = f"Ticker: {ticker}\nApp store ratings data:\n{json.dumps(ratings_data, indent=2)}"
    result = _call_grok(RATINGS_SYSTEM, user)
    logger.info(f"[Grok/Ratings] {ticker}: signal={result.get('signal')}, conf={result.get('confidence')}")
    return result


# ─────────────────────────────────────────────────────────────
#  Chain 4 — SEC filings
# ─────────────────────────────────────────────────────────────
FILINGS_SYSTEM = """You are a regulatory filings analyst who interprets SEC 8-K
and 10-Q filing patterns as context signals around upcoming earnings.

Given recent SEC filing data, analyse:
1. Frequency and recency of 8-K (material event) filings
2. Whether the quiet period before earnings has started (sudden silence = normal)
3. Any disclosure patterns that historically precede positive or negative surprises
4. Risk language changes or guidance update hints

Return ONLY valid JSON — no markdown, no extra text:
{
  "signal":       "bullish" | "bearish" | "neutral",
  "confidence":   <float 0.0–1.0>,
  "reasoning":    "<2–3 sentence explanation>",
  "key_evidence": ["<evidence point 1>", "<evidence point 2>", "<evidence point 3>"],
  "quiet_period": true | false
}"""


def analyze_filings(ticker: str, filings_data: dict) -> dict:
    user = f"Ticker: {ticker}\nSEC EDGAR filings data:\n{json.dumps(filings_data, indent=2)}"
    result = _call_grok(FILINGS_SYSTEM, user)
    logger.info(f"[Grok/Filings] {ticker}: signal={result.get('signal')}, conf={result.get('confidence')}")
    return result
