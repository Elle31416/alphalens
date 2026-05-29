// frontend/lib/api.ts
// API client for the AlphaLens FastAPI backend

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export interface Signal {
  ticker:          string
  run_date:        string
  composite_score: number
  confidence_low:  number
  confidence_high: number
  overall_signal:  "strong_buy" | "buy" | "neutral" | "sell" | "strong_sell"
  analyst_bullets: string[]
  hiring_signal:   SignalDetail | null
  pricing_signal:  SignalDetail | null
  rating_signal:   SignalDetail | null
  filing_signal:   SignalDetail | null
}

export interface SignalDetail {
  signal:      "bullish" | "bearish" | "neutral"
  confidence:  number
  reasoning:   string
  key_evidence: string[]
  // optional extra fields per chain
  price_trend?:      string
  sentiment_trend?:  string
  quiet_period?:     boolean
}

export interface Ticker {
  id:      number
  symbol:  string
  company: string
  sec_cik: string | null
}

export interface BacktestResult {
  ticker:            string
  signal_date:       string
  alphalens_signal:  string
  composite_score:   number
  key_evidence:      string[]
  actual_result:     string
  actual_move_pct:   number
}

// ── Fetchers ────────────────────────────────────────────────
export async function fetchSignals(): Promise<Signal[]> {
  const r = await fetch(`${API_URL}/signals`, { cache: "no-store" })
  if (!r.ok) throw new Error(`API error ${r.status}`)
  const data = await r.json()
  return data.signals ?? []
}

export async function fetchTickerSignals(ticker: string): Promise<{
  ticker:  string
  signals: Signal[]
  raw:     unknown[]
}> {
  const r = await fetch(`${API_URL}/signals/${ticker}`, { cache: "no-store" })
  if (!r.ok) throw new Error(`API error ${r.status}`)
  return r.json()
}

export async function fetchTickers(): Promise<Ticker[]> {
  const r = await fetch(`${API_URL}/tickers`, { cache: "no-store" })
  if (!r.ok) throw new Error(`API error ${r.status}`)
  const data = await r.json()
  return data.tickers ?? []
}

export async function fetchBacktest(): Promise<BacktestResult[]> {
  const r = await fetch(`${API_URL}/backtest`, { cache: "no-store" })
  if (!r.ok) throw new Error(`API error ${r.status}`)
  const data = await r.json()
  return data.results ?? []
}

export async function triggerPipeline(ticker?: string): Promise<void> {
  const url = ticker ? `${API_URL}/pipeline/run?ticker=${ticker}` : `${API_URL}/pipeline/run`
  await fetch(url, { method: "POST" })
}

export async function exportCSV(): Promise<void> {
  const r    = await fetch(`${API_URL}/signals/export/csv`)
  const blob = await r.blob()
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement("a")
  const name = `alphalens_signals_${new Date().toISOString().slice(0,10)}.csv`
  a.href     = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ── Score → colour ───────────────────────────────────────────
export function scoreColor(score: number): string {
  if (score >= 75) return "#0F6E56"
  if (score >= 60) return "#3B6D11"
  if (score >= 45) return "#BA7517"
  if (score >= 30) return "#993556"
  return "#8B1A1A"
}

export function signalLabel(signal: string): string {
  return {
    strong_buy:  "Strong Buy",
    buy:         "Buy",
    neutral:     "Neutral",
    sell:        "Sell",
    strong_sell: "Strong Sell",
    bullish:     "Bullish",
    bearish:     "Bearish",
  }[signal] ?? signal
}

export function signalBg(signal: string): string {
  return {
    strong_buy:  "bg-emerald-900/60 text-emerald-300",
    buy:         "bg-green-900/60 text-green-300",
    neutral:     "bg-amber-900/60 text-amber-300",
    sell:        "bg-rose-900/60 text-rose-300",
    strong_sell: "bg-red-950/80 text-red-300",
    bullish:     "bg-green-900/60 text-green-300",
    bearish:     "bg-rose-900/60 text-rose-300",
  }[signal] ?? "bg-zinc-800 text-zinc-300"
}
