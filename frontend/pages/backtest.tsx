// frontend/pages/backtest.tsx
import { useEffect, useState } from "react"
import Head from "next/head"
import { useRouter } from "next/router"
import { ArrowLeft, CheckCircle, XCircle, MinusCircle } from "lucide-react"
import { fetchBacktest, BacktestResult, signalBg, scoreColor } from "../lib/api"

const DEMO_DATA: BacktestResult[] = [
  {
    ticker:           "NVDA",
    signal_date:      "2024-10-15",
    alphalens_signal: "strong_buy",
    composite_score:  82,
    key_evidence: [
      "Hiring in 'GPU validation' roles up 340% YoY",
      "Amazon GPU SKU prices trending +12% (supply constraint)",
      "CUDA Toolkit app rating jumped 0.3 stars in 30 days",
    ],
    actual_result:  "+9.3% beat, stock +16% next day",
    actual_move_pct: 16.0,
  },
  {
    ticker:           "META",
    signal_date:      "2024-10-22",
    alphalens_signal: "buy",
    composite_score:  71,
    key_evidence: [
      "Engineering hires spiked 28% focused on AI/ML platform roles",
      "Instagram app rating delta +0.2 stars over 30 days",
      "No 8-K surprise filings — quiet period confirmed",
    ],
    actual_result:  "+8.9% beat, stock +9.5% next day",
    actual_move_pct: 9.5,
  },
  {
    ticker:           "AMZN",
    signal_date:      "2024-10-29",
    alphalens_signal: "buy",
    composite_score:  67,
    key_evidence: [
      "AWS infrastructure roles +45% YoY — capacity expansion signal",
      "Amazon Prime prices stable, no pre-earnings discounting",
      "Recent 8-K re: AWS region expansion (bullish capacity)",
    ],
    actual_result:  "+6.2% beat on AWS revenue, stock +8.0%",
    actual_move_pct: 8.0,
  },
  {
    ticker:           "MSFT",
    signal_date:      "2024-07-16",
    alphalens_signal: "neutral",
    composite_score:  53,
    key_evidence: [
      "Hiring growth slowing — 8% YoY vs 22% prior quarter",
      "Office pricing flat — no demand signal either way",
      "Teams app rating stable at 3.9 — no engagement spike",
    ],
    actual_result:  "+2.1% beat, mixed guide, stock -2.9% next day",
    actual_move_pct: -2.9,
  },
  {
    ticker:           "GOOGL",
    signal_date:      "2024-10-22",
    alphalens_signal: "buy",
    composite_score:  74,
    key_evidence: [
      "Search Ads product roles +55% — demand signal",
      "Google Maps app ratings up 0.4 stars (engagement surge)",
      "No negative 8-Ks — clean pre-earnings period",
    ],
    actual_result:  "+6.0% beat, stock +5.2% next day",
    actual_move_pct: 5.2,
  },
]

export default function BacktestPage() {
  const router  = useRouter()
  const [data, setData] = useState<BacktestResult[]>(DEMO_DATA)

  useEffect(() => {
    fetchBacktest().then(r => { if (r.length > 0) setData(r) }).catch(() => {})
  }, [])

  const correct = data.filter((r) => {
    const isPos = ["buy","strong_buy"].includes(r.alphalens_signal)
    return (isPos && r.actual_move_pct > 0) || (!isPos && r.actual_move_pct < 0)
  })
  const hitRate = Math.round((correct.length / data.length) * 100)

  return (
    <>
      <Head><title>Backtest — AlphaLens</title></Head>

      <div className="min-h-screen px-6 py-6 max-w-screen-xl mx-auto" style={{ background: "#0d0f14" }}>
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={() => router.push("/")}
            className="p-2 rounded-lg border border-zinc-800 hover:border-zinc-600 text-zinc-500 hover:text-white transition-colors"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-white">Historical Backtest</h1>
            <p className="text-xs text-zinc-500">What AlphaLens would have signalled — vs what actually happened</p>
          </div>
        </div>

        {/* Hit rate summary */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 px-5 py-4 text-center">
            <div className="text-3xl font-bold text-white mb-1">{hitRate}%</div>
            <div className="text-xs text-zinc-500">Signal hit rate</div>
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 px-5 py-4 text-center">
            <div className="text-3xl font-bold text-emerald-400 mb-1">{correct.length}/{data.length}</div>
            <div className="text-xs text-zinc-500">Correct signals</div>
          </div>
          <div className="rounded-xl border border-emerald-900/50 bg-emerald-900/10 px-5 py-4 flex items-center">
            <p className="text-xs text-emerald-300 leading-relaxed">
              Hedge funds pay quant teams millions for 55% accuracy on alt data.
              AlphaLens generates these signals autonomously every night.
            </p>
          </div>
        </div>

        {/* Results table */}
        <div className="rounded-xl border border-zinc-800 overflow-hidden">
          <div className="grid grid-cols-[80px_80px_100px_80px_1fr_140px] gap-4 px-4 py-2.5
                          text-[11px] font-semibold uppercase tracking-wider text-zinc-600
                          border-b border-zinc-800 bg-zinc-900/40">
            <span>Ticker</span>
            <span>Signal Date</span>
            <span>AlphaLens</span>
            <span>Score</span>
            <span>Key Evidence</span>
            <span>Actual Outcome</span>
          </div>

          {data.map((r) => {
            const isBull = ["buy","strong_buy"].includes(r.alphalens_signal)
            const correct = (isBull && r.actual_move_pct > 0) || (!isBull && r.actual_move_pct < 0)
            const isNeutral = r.alphalens_signal === "neutral"

            return (
              <div key={`${r.ticker}-${r.signal_date}`}
                   className="grid grid-cols-[80px_80px_100px_80px_1fr_140px] gap-4 px-4 py-4
                              border-b border-zinc-800/60 items-start">
                <span className="font-mono font-semibold text-white text-sm">{r.ticker}</span>
                <span className="text-xs text-zinc-500 font-mono mt-0.5">{r.signal_date}</span>
                <span className={`signal-pill mt-0.5 ${signalBg(r.alphalens_signal)}`}>
                  {r.alphalens_signal.replace("_", " ")}
                </span>
                <span className="text-sm font-bold mt-0.5" style={{ color: scoreColor(r.composite_score) }}>
                  {r.composite_score}
                </span>
                <ul className="space-y-1">
                  {r.key_evidence.map((e, i) => (
                    <li key={i} className="text-xs text-zinc-500 flex items-start gap-1.5">
                      <span className="text-zinc-700 mt-0.5 shrink-0">·</span>{e}
                    </li>
                  ))}
                </ul>
                <div className="flex items-start gap-2">
                  {isNeutral ? (
                    <MinusCircle size={14} className="text-amber-500 mt-0.5 shrink-0" />
                  ) : correct ? (
                    <CheckCircle size={14} className="text-emerald-500 mt-0.5 shrink-0" />
                  ) : (
                    <XCircle size={14} className="text-rose-500 mt-0.5 shrink-0" />
                  )}
                  <div>
                    <p className="text-xs text-zinc-300 leading-5">{r.actual_result}</p>
                    <p className="text-xs font-mono font-semibold"
                       style={{ color: r.actual_move_pct > 0 ? "#3B6D11" : "#993556" }}>
                      {r.actual_move_pct > 0 ? "+" : ""}{r.actual_move_pct}%
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        <p className="text-xs text-zinc-700 mt-6 text-center">
          Historical backtest for demonstration. Not financial advice.
          AlphaLens uses Bright Data proxies + Grok xAI — none of this pipeline runs without fresh data.
        </p>
      </div>
    </>
  )
}
