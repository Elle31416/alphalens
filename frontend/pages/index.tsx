// frontend/pages/index.tsx
import { useState, useEffect, useCallback } from "react"
import Head from "next/head"
import { BarChart2, Download, Play, TrendingUp, Activity, Zap } from "lucide-react"
import WatchlistTable from "../components/WatchlistTable"
import { fetchSignals, exportCSV, triggerPipeline, Signal, scoreColor } from "../lib/api"

export default function Dashboard() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchSignals()
      setSignals(data)
      setLastUpdate(new Date().toLocaleTimeString())
    } catch (err) {
      console.error("Failed to load signals:", err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleRun = async () => {
    setRunning(true)
    try {
      await triggerPipeline()
      setTimeout(load, 3000)  // reload after 3s
    } finally {
      setRunning(false)
    }
  }

  // Stats
  const avgScore    = signals.length ? Math.round(signals.reduce((s, x) => s + x.composite_score, 0) / signals.length) : 0
  const bullish     = signals.filter(s => ["strong_buy","buy"].includes(s.overall_signal)).length
  const bearish     = signals.filter(s => ["sell","strong_sell"].includes(s.overall_signal)).length

  return (
    <>
      <Head>
        <title>AlphaLens — Alternative Data Signals</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="min-h-screen" style={{ background: "#0d0f14" }}>
        {/* ── Top nav ─────────────────────────────────────── */}
        <nav className="border-b border-zinc-800 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap size={18} className="text-emerald-400" />
            <span className="font-semibold text-white">AlphaLens</span>
            <span className="text-xs text-zinc-600 ml-1">alt-data · Bright Data + Grok</span>
          </div>
          <div className="flex items-center gap-3">
            {lastUpdate && (
              <span className="text-xs text-zinc-600">Updated {lastUpdate}</span>
            )}
            <button
              onClick={() => exportCSV()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-700
                         text-zinc-300 hover:border-zinc-500 hover:text-white text-sm transition-colors"
            >
              <Download size={13} />
              Export CSV
            </button>
            <button
              onClick={handleRun}
              disabled={running}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-900/60
                         text-emerald-300 hover:bg-emerald-900 text-sm transition-colors disabled:opacity-50"
            >
              <Play size={13} className={running ? "animate-pulse" : ""} />
              {running ? "Running…" : "Run Pipeline"}
            </button>
          </div>
        </nav>

        <div className="px-6 py-6 max-w-screen-xl mx-auto">
          {/* ── Stats row ──────────────────────────────────── */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <StatCard icon={<BarChart2 size={16} />} label="Tickers tracked" value={signals.length} color="#185FA5" />
            <StatCard icon={<Activity size={16} />} label="Avg signal score" value={avgScore} color={scoreColor(avgScore)} />
            <StatCard icon={<TrendingUp size={16} />} label="Bullish signals" value={bullish} color="#3B6D11" />
            <StatCard icon={<TrendingUp size={16} className="rotate-180" />} label="Bearish signals" value={bearish} color="#993556" />
          </div>

          {/* ── Watchlist ───────────────────────────────────── */}
          <WatchlistTable signals={signals} onRefresh={load} loading={loading} />

          {/* ── Footer ─────────────────────────────────────── */}
          <p className="text-xs text-zinc-700 mt-6 text-center">
            AlphaLens · Built with Bright Data (Residential Proxies, Web Unlocker, Scraper API) + Grok xAI
            · For educational / hackathon use only — not financial advice
          </p>
        </div>
      </div>
    </>
  )
}

function StatCard({
  icon, label, value, color
}: {
  icon: React.ReactNode
  label: string
  value: number
  color: string
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-4">
      <div className="flex items-center gap-2 mb-2" style={{ color }}>
        {icon}
        <span className="text-xs font-medium text-zinc-500">{label}</span>
      </div>
      <div className="text-2xl font-bold" style={{ color }}>
        {value}
      </div>
    </div>
  )
}
