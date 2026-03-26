import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Factory, Loader2 } from 'lucide-react'
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

function dtFmt(v) {
  if (v == null) return '—'
  const d = typeof v === 'string' ? new Date(v) : v
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('nl-NL', { dateStyle: 'short', timeStyle: 'short' })
}

export default function COODashboard() {
  const toast = useToast()
  const [periodDays, setPeriodDays] = useState(30)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['coo', 'dashboard', periodDays],
    queryFn: () => fetchJson(`/api/coo/dashboard?period_days=${periodDays}`),
  })

  const activeJobs = Array.isArray(data?.active_jobs) ? data.active_jobs : []
  const statusBreakdown = Array.isArray(data?.status_breakdown) ? data.status_breakdown : []
  const stepPerformance = Array.isArray(data?.step_performance) ? data.step_performance : []
  const recentFailures = Array.isArray(data?.recent_failures) ? data.recent_failures : []

  useEffect(() => {
    if (isError && error) {
      toast.error(error.message || 'Kon COO-data niet laden')
    }
  }, [isError, error, toast])

  return (
    <PageLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">COO Dashboard</h1>
          <p className="text-sm text-slate-600 mt-1">
            Productie en RUNNING-fase (monitoring)
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-slate-600">
            <Factory className="w-5 h-5 text-indigo-600" />
            <span className="text-sm">Periode (stats)</span>
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

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Actieve jobs</h2>
          <p className="text-xs text-slate-500">RUNNING — huidige momentopname (niet gefilterd op periode hierboven)</p>
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Job</th>
                  <th className="px-4 py-3">Client</th>
                  <th className="px-4 py-3">Preset</th>
                  <th className="px-4 py-3">Gestart</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {activeJobs.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-slate-500 text-center">
                      Geen RUNNING jobs
                    </td>
                  </tr>
                ) : (
                  activeJobs.map((row) => (
                    <tr key={row.id} className="hover:bg-slate-50/80">
                      <td className="px-4 py-3">
                        <Link
                          to={`/jobs/${row.id}`}
                          className="font-medium text-indigo-600 hover:text-indigo-800"
                        >
                          {row.title || row.id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-slate-700">{row.client_name || '—'}</td>
                      <td className="px-4 py-3 text-slate-600">{row.preset_id || '—'}</td>
                      <td className="px-4 py-3 text-slate-600">{dtFmt(row.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Status breakdown</h2>
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Aantal</th>
                  <th className="px-4 py-3 text-right">Gem. minuten</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {statusBreakdown.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-4 py-6 text-slate-500 text-center">
                      Geen jobs in deze periode
                    </td>
                  </tr>
                ) : (
                  statusBreakdown.map((row) => (
                    <tr key={String(row.status)} className="hover:bg-slate-50/80">
                      <td className="px-4 py-3 font-mono text-xs">{row.status || '—'}</td>
                      <td className="px-4 py-3 text-right">{numFmt(row.count)}</td>
                      <td className="px-4 py-3 text-right">{row.avg_minutes ?? '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Stap performance per rol</h2>
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Agent-rol</th>
                  <th className="px-4 py-3 text-right">Totaal stappen</th>
                  <th className="px-4 py-3 text-right">Voltooid</th>
                  <th className="px-4 py-3 text-right">Mislukt</th>
                  <th className="px-4 py-3 text-right">Gem. tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {stepPerformance.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-slate-500 text-center">
                      Geen stappen in deze periode
                    </td>
                  </tr>
                ) : (
                  stepPerformance.map((row) => (
                    <tr key={String(row.agent_role)} className="hover:bg-slate-50/80">
                      <td className="px-4 py-3 font-medium text-slate-800">{row.agent_role}</td>
                      <td className="px-4 py-3 text-right">{numFmt(row.total_steps)}</td>
                      <td className="px-4 py-3 text-right text-emerald-700">{numFmt(row.completed)}</td>
                      <td className="px-4 py-3 text-right text-red-700">{numFmt(row.failed)}</td>
                      <td className="px-4 py-3 text-right">{numFmt(row.avg_tokens)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Recente fouten</h2>
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Job</th>
                  <th className="px-4 py-3">Stap</th>
                  <th className="px-4 py-3">Rol</th>
                  <th className="px-4 py-3">Fout</th>
                  <th className="px-4 py-3">Tijdstip</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recentFailures.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-slate-500 text-center">
                      Geen mislukte stappen in deze periode
                    </td>
                  </tr>
                ) : (
                  recentFailures.map((row, i) => (
                    <tr key={`${row.job_id}-${row.created_at}-${i}`} className="hover:bg-slate-50/80">
                      <td className="px-4 py-3">
                        <Link
                          to={`/jobs/${row.job_id}`}
                          className="font-medium text-indigo-600 hover:text-indigo-800"
                        >
                          {row.job_id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-slate-700">{row.step_name || '—'}</td>
                      <td className="px-4 py-3 text-slate-600">{row.agent_role || '—'}</td>
                      <td className="px-4 py-3 text-slate-700 max-w-md truncate" title={row.error_message}>
                        {row.error_message || '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{dtFmt(row.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </PageLayout>
  )
}
