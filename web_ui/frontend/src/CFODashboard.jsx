import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Coins, Loader2 } from 'lucide-react'
import PageLayout from './PageLayout.jsx'
import { fetchJson } from './apiClient'
import { useToast } from './Toast'

const PERIODS = [
  { value: 7, label: '7 dagen' },
  { value: 30, label: '30 dagen' },
  { value: 90, label: '90 dagen' },
]

function eurFmt(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' }).format(Number(n))
}

function numFmt(n) {
  if (n == null) return '—'
  return new Intl.NumberFormat('nl-NL').format(Number(n))
}

export default function CFODashboard() {
  const toast = useToast()
  const [periodDays, setPeriodDays] = useState(30)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['cfo', 'dashboard', periodDays],
    queryFn: () => fetchJson(`/api/cfo/dashboard?period_days=${periodDays}`),
  })

  const totals = data?.totals || {}
  const perAgent = Array.isArray(data?.per_agent) ? data.per_agent : []
  const perModel = Array.isArray(data?.per_model) ? data.per_model : []
  const dailyTrend = useMemo(() => {
    const rows = Array.isArray(data?.daily_trend) ? [...data.daily_trend] : []
    return rows.reverse().map((r) => ({
      dag: r.dag ? String(r.dag).slice(0, 10) : '',
      cost_eur: (r.cost_usd || 0) * (data?.usd_to_eur ?? 0.92),
      tokens: r.tokens ?? 0,
    }))
  }, [data?.daily_trend, data?.usd_to_eur])

  useEffect(() => {
    if (isError && error) {
      toast.error(error.message || 'Kon CFO-data niet laden')
    }
  }, [isError, error, toast])

  return (
    <PageLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">CFO Dashboard</h1>
          <p className="text-sm text-slate-600 mt-1">Tokenverbruik en geschatte kosten (monitoring)</p>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-slate-600">
            <Coins className="w-5 h-5 text-amber-600" />
            <span className="text-sm">Periode</span>
            <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setPeriodDays(p.value)}
                  className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                    periodDays === p.value
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          {isLoading && (
            <span className="inline-flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              Laden…
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Totale kosten</div>
            <div className="mt-2 text-2xl font-bold text-slate-900">{eurFmt(totals.total_cost_eur)}</div>
            <div className="mt-1 text-xs text-slate-500">USD→EUR × {data?.usd_to_eur ?? 0.92}</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tokens (in + out)</div>
            <div className="mt-2 text-2xl font-bold text-slate-900">{numFmt(totals.total_tokens)}</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Jobs (met logging)</div>
            <div className="mt-2 text-2xl font-bold text-slate-900">{numFmt(totals.total_jobs)}</div>
          </div>
        </div>

        <section>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Kosten per agent</h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3 font-medium">Agent</th>
                    <th className="px-4 py-3 font-medium text-right">Tokens</th>
                    <th className="px-4 py-3 font-medium text-right">Kosten (EUR)</th>
                    <th className="px-4 py-3 font-medium text-right">Jobs</th>
                  </tr>
                </thead>
                <tbody>
                  {perAgent.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                        Geen data in deze periode.
                      </td>
                    </tr>
                  )}
                  {perAgent.map((row) => (
                    <tr key={row.agent_id || 'unknown'} className="border-t border-slate-100">
                      <td className="px-4 py-2.5 font-mono text-xs">{row.agent_id || '—'}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.tokens)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{eurFmt(row.cost_eur)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.jobs)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Kosten per model</h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3 font-medium">Model</th>
                    <th className="px-4 py-3 font-medium text-right">Tokens</th>
                    <th className="px-4 py-3 font-medium text-right">Kosten (EUR)</th>
                  </tr>
                </thead>
                <tbody>
                  {perModel.length === 0 && (
                    <tr>
                      <td colSpan={3} className="px-4 py-6 text-center text-slate-500">
                        Geen data in deze periode.
                      </td>
                    </tr>
                  )}
                  {perModel.map((row) => (
                    <tr key={row.model} className="border-t border-slate-100">
                      <td className="px-4 py-2.5 font-mono text-xs">{row.model}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.tokens)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{eurFmt(row.cost_eur)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Dagelijkse trend (14 dagen)</h2>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm h-72">
            {dailyTrend.length === 0 ? (
              <div className="flex h-full items-center justify-center text-slate-500 text-sm">Geen trenddata.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dailyTrend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="dag" tick={{ fontSize: 11 }} stroke="#64748b" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#64748b" tickFormatter={(v) => `€${v.toFixed(2)}`} />
                  <Tooltip
                    formatter={(value) => [eurFmt(value), 'Kosten']}
                    labelFormatter={(label) => `dag ${label}`}
                    contentStyle={{ borderRadius: 8 }}
                  />
                  <Bar dataKey="cost_eur" fill="#6366f1" radius={[4, 4, 0, 0]} name="kosten (EUR)" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        <p className="text-xs text-slate-500">
          Indicatief op basis van vastgelegde LLM-usage en prijslijst per model. Geen pipeline-impact.
        </p>
      </div>
    </PageLayout>
  )
}
