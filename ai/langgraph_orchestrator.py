"""
ai/langgraph_orchestrator.py
LangGraph pipeline that runs all 4 signal chains and synthesises
a composite earnings-surprise probability score (0–100).

Graph topology:
  START → [hiring, pricing, ratings, filings] → synthesize → END
         (4 parallel nodes)
"""
import os
import re
import json
import logging
from typing import TypedDict, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# ── State definition ──────────────────────────────────────────
class SignalState(TypedDict):
    ticker:          str
    hiring_data:     dict
    pricing_data:    dict
    ratings_data:    dict
    filings_data:    dict
    hiring_signal:   Optional[dict]
    pricing_signal:  Optional[dict]
    rating_signal:   Optional[dict]
    filing_signal:   Optional[dict]
    composite_score:  Optional[int]
    confidence_low:   Optional[int]
    confidence_high:  Optional[int]
    overall_signal:   Optional[str]
    analyst_bullets:  Optional[list]


# ── Grok client ───────────────────────────────────────────────
client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

SYNTH_SYSTEM = """You are the chief quant analyst at AlphaLens. You receive four
independent alternative-data signals about a public company and must synthesise
them into one composite earnings-surprise probability score.

Weights (rough guidance — use your judgement):
  Hiring velocity  : 35%
  Pricing velocity : 30%
  App ratings      : 20%
  SEC filings      : 15%

Return ONLY valid JSON — no markdown, no extra text:
{
  "score":               <integer 0–100>,
  "confidence_interval": [<low_int>, <high_int>],
  "overall_signal":      "strong_buy" | "buy" | "neutral" | "sell" | "strong_sell",
  "analyst_bullets":     [
    "<most important evidence point>",
    "<second most important evidence point>",
    "<third evidence point or key risk>"
  ],
  "summary": "<one sentence investment thesis>"
}"""


# ── Node functions ────────────────────────────────────────────
def analyze_hiring_node(state: SignalState) -> SignalState:
    from ai.signal_chain import analyze_hiring
    state["hiring_signal"] = analyze_hiring(state["ticker"], state["hiring_data"])
    return state


def analyze_pricing_node(state: SignalState) -> SignalState:
    from ai.signal_chain import analyze_pricing
    state["pricing_signal"] = analyze_pricing(state["ticker"], state["pricing_data"])
    return state


def analyze_ratings_node(state: SignalState) -> SignalState:
    from ai.signal_chain import analyze_ratings
    state["rating_signal"] = analyze_ratings(state["ticker"], state["ratings_data"])
    return state


def analyze_filings_node(state: SignalState) -> SignalState:
    from ai.signal_chain import analyze_filings
    state["filing_signal"] = analyze_filings(state["ticker"], state["filings_data"])
    return state


def synthesize_signals(state: SignalState) -> SignalState:
    """Composite Grok call that combines the 4 individual signals."""
    signals_payload = {
        "ticker":          state["ticker"],
        "hiring_signal":   state.get("hiring_signal",  {}),
        "pricing_signal":  state.get("pricing_signal", {}),
        "rating_signal":   state.get("rating_signal",  {}),
        "filing_signal":   state.get("filing_signal",  {}),
    }

    user_msg = f"Synthesise these four alternative-data signals:\n{json.dumps(signals_payload, indent=2)}"

    try:
        resp = client.chat.completions.create(
            model="grok-3-mini",
            max_tokens=1000,
            messages=[
                {"role": "system", "content": SYNTH_SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        clean_json = json_match.group(1) if json_match else raw
        result = json.loads(clean_json)
    except Exception as exc:
        logger.error(f"[LangGraph/Synthesize] {state['ticker']}: {exc}")
        result = {
            "score": 50, "confidence_interval": [40, 60],
            "overall_signal": "neutral",
            "analyst_bullets": ["Synthesis failed — check logs"],
            "summary": "Error during synthesis",
        }

    state["composite_score"]  = result.get("score", 50)
    ci = result.get("confidence_interval", [40, 60])
    state["confidence_low"]   = ci[0] if len(ci) > 0 else 40
    state["confidence_high"]  = ci[1] if len(ci) > 1 else 60
    state["overall_signal"]   = result.get("overall_signal", "neutral")
    state["analyst_bullets"]  = result.get("analyst_bullets", [])

    logger.info(
        f"[LangGraph] {state['ticker']} composite={state['composite_score']} "
        f"signal={state['overall_signal']}"
    )
    return state


# ── Graph builder ─────────────────────────────────────────────
def build_graph():
    """
    Compile the LangGraph signal graph.
    Returns a callable graph that accepts a SignalState dict.
    """
    from langgraph.graph import StateGraph, START, END

    g = StateGraph(SignalState)

    g.add_node("hiring",     analyze_hiring_node)
    g.add_node("pricing",    analyze_pricing_node)
    g.add_node("ratings",    analyze_ratings_node)
    g.add_node("filings",    analyze_filings_node)
    g.add_node("synthesize", synthesize_signals)

    # Correct Fan-out: All analysis nodes start in parallel from START
    g.add_edge(START, "hiring")
    g.add_edge(START, "pricing")
    g.add_edge(START, "ratings")
    g.add_edge(START, "filings")

    # Fan-in: All nodes must reach synthesize before END
    g.add_edge("hiring",  "synthesize")
    g.add_edge("pricing", "synthesize")
    g.add_edge("ratings", "synthesize")
    g.add_edge("filings", "synthesize")
    g.add_edge("synthesize", END)

    return g.compile()


# ── Main entry point ──────────────────────────────────────────
def run_ticker(
    ticker: str,
    hiring_data:  dict,
    pricing_data: dict,
    ratings_data: dict,
    filings_data: dict,
) -> SignalState:
    """
    Run the full graph for one ticker and return the final state.
    """
    graph = build_graph()
    initial_state: SignalState = {
        "ticker":         ticker,
        "hiring_data":    hiring_data,
        "pricing_data":   pricing_data,
        "ratings_data":   ratings_data,
        "filings_data":   filings_data,
        "hiring_signal":  None,
        "pricing_signal": None,
        "rating_signal":  None,
        "filing_signal":  None,
        "composite_score": None,
        "confidence_low":  None,
        "confidence_high": None,
        "overall_signal":  None,
        "analyst_bullets": None,
    }
    result = graph.invoke(initial_state)
    return result
