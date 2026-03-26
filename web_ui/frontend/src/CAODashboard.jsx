import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Loader2, TrendingUp } from 'lucide-react'
import PageLayout from './PageLayout.jsx'
import { fetchJson } from './apiClient'
import { useToast } from './Toast'

const PERIODS = [
  { value: 7, label: '7 dagen' },
  { value: 30, label: '30 dagen' },
  { value: 90, label: '90 dagen' },
]

function numFmt(n) {
  if (n == null) return '—'
  return new Intl.NumberFormat('nl-NL').format(Number(n))
}

function pctFmt(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return `${Number(n).toFixed(1)}%`
}

export default function CAODashboard() {
  const toast = useToast()
  const [periodDays, setPeriodDays] = useState(30)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['cao', 'dashboard', periodDays],
    queryFn: () => fetchJson(`/api/cao/dashboard?period_days=${periodDays}`),
  })

  const js = data?.job_stats || {}
  const total = Number(js.total_jobs) || 0
  const completed = Number(js.completed) || 0
  const failed = Number(js.failed) || 0
  const blocked = Number(js.blocked) || 0
  const completionRate = total > 0 ? (100 * completed) / total : 0
  const failedRate = total > 0 ? (100 * failed) / total : 0

  const perPreset = Array.isArray(data?.per_preset) ? data.per_preset : []
  const perAgent = Array.isArray(data?.per_agent) ? data.per_agent : []
  const blockedRoles = Array.isArray(data?.blocked_roles) ? data.blocked_roles : []

  const dailyTrend = useMemo(() => {
    const rows = Array.isArray(data?.daily_trend) ? [...data.daily_trend] : []
    return rows.reverse().map((r) => ({
      dag: r.dag ? String(r.dag).slice(0, 10) : '',
      completed: Number(r.completed) || 0,
      failed: Number(r.failed) || 0,
    }))
  }, [data?.daily_trend])

  useEffect(() => {
    if (isError && error) {
      toast.error(error.message || 'Kon CAO-data niet laden')
    }
  }, [isError, error, toast])

  return (
    <PageLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">CAO Dashboard</h1>
          <p className="text-sm text-slate-600 mt-1">
            Crew performance en job-doorstroming (monitoring)
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-slate-600">
            <TrendingUp className="w-5 h-5 text-indigo-600" />
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

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Jobs</div>
            <div className="mt-2 text-2xl font-bold text-slate-900">{numFmt(total)}</div>
            <div className="mt-1 text-xs text-slate-500">in periode</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Completion rate</div>
            <div className="mt-2 text-2xl font-bold text-emerald-700">{pctFmt(completionRate)}</div>
            <div className="mt-1 text-xs text-slate-500">{numFmt(completed)} JOB_READY</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Failed rate</div>
            <div className="mt-2 text-2xl font-bold text-red-700">{pctFmt(failedRate)}</div>
            <div className="mt-1 text-xs text-slate-500">{numFmt(failed)} FAILED</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Geblokkeerd</div>
            <div className="mt-2 text-2xl font-bold text-amber-700">{numFmt(blocked)}</div>
            <div className="mt-1 text-xs text-slate-500">BLOCKED jobs</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Gem. doorlooptijd</div>
            <div className="mt-2 text-2xl font-bold text-slate-900">
              {js.avg_duration_minutes != null ? `${numFmt(js.avg_duration_minutes)} min` : '—'}
            </div>
            <div className="mt-1 text-xs text-slate-500">create → update</div>
          </div>
        </div>

        <section>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Meest geblokkeerde rollen (HR)</h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3 font-medium">Rol-key</th>
                    <th className="px-4 py-3 font-medium">Titel (voorbeeld)</th>
                    <th className="px-4 py-3 font-medium text-right">Open punten</th>
                  </tr>
                </thead>
                <tbody>
                  {blockedRoles.length === 0 && (
                    <tr>
                      <td colSpan={3} className="px-4 py-6 text-center text-slate-500">
                        Geen open HR-blocked punten in deze periode.
                      </td>
                    </tr>
                  )}
                  {blockedRoles.map((row) => (
                    <tr key={row.role_key || row.role_label} className="border-t border-slate-100">
                      <td className="px-4 py-2.5 font-mono text-xs">{row.role_key || '—'}</td>
                      <td className="px-4 py-2.5 text-slate-700 max-w-md truncate" title={row.role_label}>
                        {row.role_label || '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.blocked_count)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Performance per preset</h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3 font-medium">Preset</th>
                    <th className="px-4 py-3 font-medium text-right">Totaal</th>
                    <th className="px-4 py-3 font-medium text-right">Completed</th>
                    <th className="px-4 py-3 font-medium text-right">Failed</th>
                    <th className="px-4 py-3 font-medium text-right">Approval %</th>
                  </tr>
                </thead>
                <tbody>
                  {perPreset.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                        Geen jobs in deze periode.
                      </td>
                    </tr>
                  )}
                  {perPreset.map((row) => (
                    <tr key={row.preset} className="border-t border-slate-100">
                      <td className="px-4 py-2.5 font-mono text-xs">{row.preset}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.total)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.completed)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.failed)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{pctFmt(row.approval_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Performance per agent (job_steps)</h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3 font-medium">Agent</th>
                    <th className="px-4 py-3 font-medium">Rol</th>
                    <th className="px-4 py-3 font-medium text-right">Stappen</th>
                    <th className="px-4 py-3 font-medium text-right">Success %</th>
                  </tr>
                </thead>
                <tbody>
                  {perAgent.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                        Geen gelabelde agent-stappen in deze periode.
                      </td>
                    </tr>
                  )}
                  {perAgent.map((row) => (
                    <tr
                      key={`${row.agent_id}-${row.agent_role}`}
                      className="border-t border-slate-100"
                    >
                      <td className="px-4 py-2.5 font-mono text-xs">{row.agent_id || '—'}</td>
                      <td className="px-4 py-2.5">{row.agent_role || '—'}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.total_steps)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{pctFmt(row.success_rate)}</td>
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
              <div className="flex h-full items-center justify-center text-slate-500 text-sm">
                Geen trenddata.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dailyTrend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="dag" tick={{ fontSize: 11 }} stroke="#64748b" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#64748b" allowDecimals={false} />
                  <Tooltip contentStyle={{ borderRadius: 8 }} />
                  <Legend />
                  <Bar dataKey="completed" name="JOB_READY" fill="#22c55e" stackId="jobs" />
                  <Bar dataKey="failed" name="FAILED" fill="#ef4444" stackId="jobs" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        <p className="text-xs text-slate-500">
          Alleen read-only aggregaties; geen impact op de pipeline.
        </p>
      </div>
    </PageLayout>
  )
}
