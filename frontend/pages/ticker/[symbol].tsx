// frontend/pages/ticker/[symbol].tsx
import { useRouter } from "next/router"
import { useEffect, useState } from "react"
import Head from "next/head"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts"
import { ArrowLeft, TrendingUp, TrendingDown, DollarSign, Star, FileText } from "lucide-react"
import { fetchTickerSignals, Signal, SignalDetail, signalBg, signalLabel, scoreColor } from "../../lib/api"

export default function TickerDetail() {
  const router      = useRouter()
  const { symbol }  = router.query as { symbol: string }
  const [data, setData]     = useState<{ signals: Signal[]; raw: unknown[] } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!symbol) return
    setLoading(true)
    fetchTickerSignals(symbol)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [symbol])

  const latest = data?.signals?.[0]

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#0d0f14" }}>
        <div className="text-zinc-500 text-sm">Loading {symbol}…</div>
      </div>
    )
  }

  if (!latest) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#0d0f14" }}>
        <div className="text-center">
          <div className="text-zinc-400 mb-4">No signals found for {symbol}</div>
          <button onClick={() => router.back()} className="text-sm text-emerald-400 hover:underline">← Back</button>
        </div>
      </div>
    )
  }

  const scoreHistory = (data?.signals ?? [])
    .slice(0, 14)
    .reverse()
    .map((s, i) => ({ day: `D-${14 - i}`, score: s.composite_score }))

  return (
    <>
      <Head>
        <title>{symbol} — AlphaLens</title>
      </Head>

      <div className="min-h-screen px-6 py-6 max-w-screen-xl mx-auto" style={{ background: "#0d0f14" }}>
        {/* ── Header ───────────────────────────────────── */}
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={() => router.back()}
            className="p-2 rounded-lg border border-zinc-800 hover:border-zinc-600 text-zinc-500 hover:text-white transition-colors"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-white font-mono">{symbol}</h1>
            <p className="text-xs text-zinc-500">Signal date: {latest.run_date}</p>
          </div>
          <div className="ml-auto flex items-center gap-4">
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center text-xl font-bold border-2"
              style={{
                background: `${scoreColor(latest.composite_score)}20`,
                color:       scoreColor(latest.composite_score),
                borderColor: scoreColor(latest.composite_score),
              }}
            >
              {latest.composite_score}
            </div>
            <div>
              <span className={`signal-pill ${signalBg(latest.overall_signal)}`}>
                {signalLabel(latest.overall_signal)}
              </span>
              <p className="text-xs text-zinc-600 mt-1">
                CI: [{latest.confidence_low}–{latest.confidence_high}]
              </p>
            </div>
          </div>
        </div>

        {/* ── Analyst bullets ────────────────────────── */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 px-5 py-4 mb-6">
          <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Grok Analyst Summary</p>
          <ul className="space-y-1.5">
            {(latest.analyst_bullets ?? []).map((b, i) => (
              <li key={i} className="text-sm text-zinc-300 flex items-start gap-2">
                <span className="text-emerald-500 mt-0.5 shrink-0">›</span>
                {b}
              </li>
            ))}
          </ul>
        </div>

        {/* ── Score history chart ─────────────────── */}
        {scoreHistory.length > 1 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 px-5 py-4 mb-6">
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">14-Day Score History</p>
            <ResponsiveContainer width="100%" height={100}>
              <LineChart data={scoreHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2230" />
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#555" }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#555" }} width={28} />
                <Tooltip
                  contentStyle={{ background: "#141720", border: "1px solid #1e2230", fontSize: 12 }}
                  labelStyle={{ color: "#8892a4" }}
                />
                <Line type="monotone" dataKey="score" stroke="#185FA5" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* ── 4 signal panels ────────────────────────── */}
        <div className="grid grid-cols-2 gap-4">
          <SignalPanel
            title="Hiring Velocity"
            icon={<TrendingUp size={15} />}
            color="#185FA5"
            signal={latest.hiring_signal}
          />
          <SignalPanel
            title="Amazon Pricing"
            icon={<DollarSign size={15} />}
            color="#BA7517"
            signal={latest.pricing_signal}
          />
          <SignalPanel
            title="App Store Ratings"
            icon={<Star size={15} />}
            color="#0F6E56"
            signal={latest.rating_signal}
          />
          <SignalPanel
            title="SEC Filings"
            icon={<FileText size={15} />}
            color="#534AB7"
            signal={latest.filing_signal}
          />
        </div>
      </div>
    </>
  )
}

function SignalPanel({
  title, icon, color, signal
}: {
  title:  string
  icon:   React.ReactNode
  color:  string
  signal: SignalDetail | null
}) {
  if (!signal) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 px-5 py-4">
        <div className="flex items-center gap-2 mb-3" style={{ color }}>
          {icon}
          <span className="text-sm font-semibold">{title}</span>
        </div>
        <p className="text-xs text-zinc-600">No data available</p>
      </div>
    )
  }

  const direction = signal.signal === "bullish" ? TrendingUp
                  : signal.signal === "bearish" ? TrendingDown
                  : null
  const signalColor = signal.signal === "bullish" ? "#3B6D11"
                    : signal.signal === "bearish" ? "#993556"
                    : "#BA7517"

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 px-5 py-4">
      {/* Panel header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2" style={{ color }}>
          {icon}
          <span className="text-sm font-semibold">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-mono px-2 py-0.5 rounded-full"
            style={{ background: `${signalColor}22`, color: signalColor, border: `1px solid ${signalColor}44` }}
          >
            {signal.signal}
          </span>
          <span className="text-xs text-zinc-600 font-mono">
            {Math.round(signal.confidence * 100)}%
          </span>
        </div>
      </div>

      {/* Confidence bar */}
      <div className="h-1 bg-zinc-800 rounded-full mb-3">
        <div
          className="h-1 rounded-full transition-all"
          style={{ width: `${signal.confidence * 100}%`, background: signalColor }}
        />
      </div>

      {/* Reasoning */}
      <p className="text-xs text-zinc-400 leading-relaxed mb-3">{signal.reasoning}</p>

      {/* Evidence bullets */}
      <ul className="space-y-1">
        {(signal.key_evidence ?? []).map((e, i) => (
          <li key={i} className="text-xs text-zinc-500 flex items-start gap-1.5">
            <span style={{ color }} className="mt-0.5 shrink-0">·</span>
            {e}
          </li>
        ))}
      </ul>
    </div>
  )
}
