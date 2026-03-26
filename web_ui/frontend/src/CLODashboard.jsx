import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { GraduationCap, Loader2 } from 'lucide-react'
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

function agentPath(agentId) {
  if (!agentId) return '/agents'
  return `/agents/${encodeURIComponent(agentId)}`
}

function newbiePath(id) {
  if (!id) return '/newbies'
  return `/newbies/${encodeURIComponent(id)}`
}

export default function CLODashboard() {
  const toast = useToast()
  const [periodDays, setPeriodDays] = useState(30)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['clo', 'dashboard', periodDays],
    queryFn: () => fetchJson(`/api/clo/dashboard?period_days=${periodDays}`),
  })

  const devPoints = Array.isArray(data?.dev_points) ? data.dev_points : []
  const newbiePipeline = Array.isArray(data?.newbie_pipeline) ? data.newbie_pipeline : []
  const promotionReady = Array.isArray(data?.promotion_ready) ? data.promotion_ready : []
  const lowReadiness = Array.isArray(data?.low_readiness_agents) ? data.low_readiness_agents : []

  const totalOpenDevPoints = useMemo(
    () => devPoints.reduce((s, r) => s + (Number(r.open_points) || 0), 0),
    [devPoints],
  )

  const agentsInTraining = useMemo(() => {
    const row = newbiePipeline.find(
      (r) => String(r.status || '').toLowerCase() === 'in_training',
    )
    return row ? Number(row.count) || 0 : 0
  }, [newbiePipeline])

  const trainingChart = useMemo(() => {
    const rows = Array.isArray(data?.training_activity) ? [...data.training_activity] : []
    return rows.reverse().map((r) => ({
      dag: r.dag ? String(r.dag).slice(0, 10) : '',
      chunks: Number(r.chunks_added) || 0,
      agents: Number(r.agents_trained) || 0,
    }))
  }, [data?.training_activity])

  useEffect(() => {
    if (isError && error) {
      toast.error(error.message || 'Kon CLO-data niet laden')
    }
  }, [isError, error, toast])

  return (
    <PageLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">CLO Dashboard</h1>
          <p className="text-sm text-slate-600 mt-1">
            Learning &amp; development — strategisch overzicht (monitoring)
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-slate-600">
            <GraduationCap className="w-5 h-5 text-indigo-600" />
            <span className="text-sm">Periode (dev points &amp; signalen)</span>
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

        {/* 1. Overzicht kaarten */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Open dev points
            </div>
            <div className="mt-2 text-2xl font-bold text-slate-900">{numFmt(totalOpenDevPoints)}</div>
            <div className="mt-1 text-xs text-slate-500">top-10 agents, periode {periodDays}d</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Newbies in training
            </div>
            <div className="mt-2 text-2xl font-bold text-slate-900">{numFmt(agentsInTraining)}</div>
            <div className="mt-1 text-xs text-slate-500">status in_training</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Klaar voor promotie
            </div>
            <div className="mt-2 text-2xl font-bold text-emerald-700">{numFmt(promotionReady.length)}</div>
            <div className="mt-1 text-xs text-slate-500">readiness ≥ 70 (max 10 in lijst)</div>
          </div>
        </div>

        {/* 2. Newbie pipeline */}
        <section>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Newbie pipeline</h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium text-right">Aantal</th>
                    <th className="px-4 py-3 font-medium text-right">Gem. readiness</th>
                  </tr>
                </thead>
                <tbody>
                  {newbiePipeline.length === 0 && (
                    <tr>
                      <td colSpan={3} className="px-4 py-6 text-center text-slate-500">
                        Geen newbie-data.
                      </td>
                    </tr>
                  )}
                  {newbiePipeline.map((row) => (
                    <tr key={row.status} className="border-t border-slate-100">
                      <td className="px-4 py-2.5 font-mono text-xs">{row.status}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.count)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">
                        {row.avg_readiness != null ? Number(row.avg_readiness).toFixed(1) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* 3. Klaar voor promotie */}
        <section>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Klaar voor promotie</h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3 font-medium">Newbie</th>
                    <th className="px-4 py-3 font-medium">Rol</th>
                    <th className="px-4 py-3 font-medium text-right">Readiness</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {promotionReady.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                        Geen newbies in promotievenster.
                      </td>
                    </tr>
                  )}
                  {promotionReady.map((row) => (
                    <tr key={row.newbie_id} className="border-t border-slate-100">
                      <td className="px-4 py-2.5 font-medium text-slate-800">{row.newbie_name}</td>
                      <td className="px-4 py-2.5 font-mono text-xs">{row.suggested_role || '—'}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.readiness_score)}</td>
                      <td className="px-4 py-2.5 text-xs">{row.status}</td>
                      <td className="px-4 py-2.5">
                        <Link
                          to={newbiePath(row.newbie_id)}
                          className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                        >
                          Open
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* 4. Agents met meeste open dev points */}
        <section>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Agents met meeste open dev points</h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3 font-medium">Agent</th>
                    <th className="px-4 py-3 font-medium text-right">Open</th>
                    <th className="px-4 py-3 font-medium text-right">Totaal</th>
                    <th className="px-4 py-3 font-medium">Laatste punt</th>
                    <th className="px-4 py-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {devPoints.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                        Geen dev points in deze periode.
                      </td>
                    </tr>
                  )}
                  {devPoints.map((row) => (
                    <tr key={row.agent_id} className="border-t border-slate-100">
                      <td className="px-4 py-2.5 font-mono text-xs break-all">{row.agent_id}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.open_points)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.total_points)}</td>
                      <td className="px-4 py-2.5 text-xs text-slate-600">
                        {row.last_point_at ? String(row.last_point_at).slice(0, 16) : '—'}
                      </td>
                      <td className="px-4 py-2.5">
                        <Link
                          to={agentPath(row.agent_id)}
                          className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                        >
                          Agent
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* 5. Agents met laagste readiness */}
        <section>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">
            Agents met laagste readiness
            <span className="font-normal text-slate-500 text-sm ml-2">(performance_score)</span>
          </h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3 font-medium">Agent</th>
                    <th className="px-4 py-3 font-medium">Naam</th>
                    <th className="px-4 py-3 font-medium">Rol</th>
                    <th className="px-4 py-3 font-medium text-right">Score</th>
                    <th className="px-4 py-3 font-medium text-right">Open punten</th>
                    <th className="px-4 py-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {lowReadiness.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                        Geen actieve agents.
                      </td>
                    </tr>
                  )}
                  {lowReadiness.map((row) => (
                    <tr key={row.agent_id} className="border-t border-slate-100">
                      <td className="px-4 py-2.5 font-mono text-xs break-all max-w-[12rem] truncate" title={row.agent_id}>
                        {row.agent_id}
                      </td>
                      <td className="px-4 py-2.5">{row.name}</td>
                      <td className="px-4 py-2.5 text-xs">{row.role}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">
                        {row.readiness_score != null ? Number(row.readiness_score).toFixed(1) : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{numFmt(row.open_dev_points)}</td>
                      <td className="px-4 py-2.5">
                        <Link
                          to={agentPath(row.agent_id)}
                          className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                        >
                          Agent
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* 6. Training activiteit */}
        <section>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Training activiteit (14 dagen)</h2>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm h-72">
            {trainingChart.length === 0 ? (
              <div className="flex h-full items-center justify-center text-slate-500 text-sm">
                Geen kennis-chunks in deze periode.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trainingChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="dag" tick={{ fontSize: 11 }} stroke="#64748b" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#64748b" allowDecimals={false} />
                  <Tooltip contentStyle={{ borderRadius: 8 }} />
                  <Bar dataKey="chunks" name="Chunks toegevoegd" fill="#6366f1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        <p className="text-xs text-slate-500">Read-only; geen wijzigingen aan HR-werkstromen.</p>
      </div>
    </PageLayout>
  )
}
