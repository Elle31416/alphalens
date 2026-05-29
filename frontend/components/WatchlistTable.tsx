// frontend/components/WatchlistTable.tsx
import { useRouter } from "next/router"
import { LineChart, Line, ResponsiveContainer, Tooltip } from "recharts"
import { TrendingUp, TrendingDown, Minus, RefreshCw } from "lucide-react"
import { Signal, scoreColor, signalLabel, signalBg } from "../lib/api"

interface Props {
  signals:    Signal[]
  onRefresh?: () => void
  loading?:   boolean
}

export default function WatchlistTable({ signals, onRefresh, loading }: Props) {
  const router = useRouter()

  return (
    <div className="rounded-xl border border-zinc-800 overflow-hidden">
      {/* Table header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-900/40">
        <span className="text-sm font-semibold text-zinc-300">Watchlist</span>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[80px_60px_120px_90px_90px_90px_90px_1fr] gap-3 px-4 py-2
                      text-[11px] font-semibold uppercase tracking-wider text-zinc-600
                      border-b border-zinc-800">
        <span>Ticker</span>
        <span className="text-right">Score</span>
        <span className="text-center">Signal</span>
        <span className="text-center">Hiring</span>
        <span className="text-center">Pricing</span>
        <span className="text-center">Ratings</span>
        <span className="text-center">Filings</span>
        <span>Analyst Summary</span>
      </div>

      {/* Rows */}
      {signals.length === 0 && (
        <div className="px-4 py-12 text-center text-zinc-600 text-sm">
          No signals yet — run the pipeline to generate data.
        </div>
      )}

      {signals.map((s) => (
        <div
          key={s.ticker}
          onClick={() => router.push(`/ticker/${s.ticker}`)}
          className="grid grid-cols-[80px_60px_120px_90px_90px_90px_90px_1fr] gap-3
                     px-4 py-3 border-b border-zinc-800/60 hover:bg-zinc-800/30
                     cursor-pointer transition-colors items-center"
        >
          {/* Ticker */}
          <span className="font-mono font-semibold text-white text-sm">{s.ticker}</span>

          {/* Score */}
          <div className="flex justify-end">
            <div
              className="score-badge text-sm"
              style={{
                background: `${scoreColor(s.composite_score)}22`,
                color:       scoreColor(s.composite_score),
                border:      `1.5px solid ${scoreColor(s.composite_score)}55`,
              }}
            >
              {s.composite_score}
            </div>
          </div>

          {/* Overall signal */}
          <div className="flex justify-center">
            <span className={`signal-pill ${signalBg(s.overall_signal)}`}>
              {signalLabel(s.overall_signal)}
            </span>
          </div>

          {/* Individual source signals */}
          {[s.hiring_signal, s.pricing_signal, s.rating_signal, s.filing_signal].map((sig, i) => (
            <div key={i} className="flex justify-center">
              {sig ? (
                <MiniSignal signal={sig.signal} confidence={sig.confidence} />
              ) : (
                <span className="text-zinc-700 text-xs">—</span>
              )}
            </div>
          ))}

          {/* Analyst bullets */}
          <div className="min-w-0">
            {(s.analyst_bullets ?? []).slice(0, 2).map((b, i) => (
              <p key={i} className="text-xs text-zinc-400 truncate leading-5">{b}</p>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function MiniSignal({ signal, confidence }: { signal: string; confidence: number }) {
  const Icon = signal === "bullish" ? TrendingUp
             : signal === "bearish" ? TrendingDown
             : Minus
  const color = signal === "bullish" ? "#3B6D11"
              : signal === "bearish" ? "#993556"
              : "#BA7517"
  return (
    <div className="flex flex-col items-center gap-0.5">
      <Icon size={14} style={{ color }} />
      <span className="text-[10px] font-mono" style={{ color }}>
        {Math.round(confidence * 100)}%
      </span>
    </div>
  )
}
