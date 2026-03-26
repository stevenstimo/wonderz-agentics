import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2, PackageCheck } from 'lucide-react'
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

function dtFmt(v) {
  if (v == null) return '—'
  const d = typeof v === 'string' ? new Date(v) : v
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('nl-NL', { dateStyle: 'short', timeStyle: 'short' })
}

export default function CDODashboard() {
  const toast = useToast()
  const [periodDays, setPeriodDays] = useState(30)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['cdo', 'dashboard', periodDays],
    queryFn: () => fetchJson(`/api/cdo/dashboard?period_days=${periodDays}`),
  })

  const stats = data?.delivery_stats && typeof data.delivery_stats === 'object' ? data.delivery_stats : {}
  const perClient = Array.isArray(data?.per_client) ? data.per_client : []
  const deliveredJobs = Array.isArray(data?.delivered_jobs) ? data.delivered_jobs : []
  const revisionJobs = Array.isArray(data?.revision_jobs) ? data.revision_jobs : []

  useEffect(() => {
    if (isError && error) {
      toast.error(error.message || 'Kon CDO-data niet laden')
    }
  }, [isError, error, toast])

  return (
    <PageLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">CDO Dashboard</h1>
          <p className="text-sm text-slate-600 mt-1">
            Leveringen, revisies en first-time-right (monitoring)
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-slate-600">
            <PackageCheck className="w-5 h-5 text-indigo-600" />
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

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Delivery overzicht</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Geleverd</div>
              <div className="mt-2 text-2xl font-bold text-emerald-700">{numFmt(stats.delivered)}</div>
              <div className="mt-1 text-xs text-slate-500">JOB_READY in periode</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Revisies</div>
              <div className="mt-2 text-2xl font-bold text-amber-700">{numFmt(stats.revisions)}</div>
              <div className="mt-1 text-xs text-slate-500">NEEDS_CHANGES</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Mislukt</div>
              <div className="mt-2 text-2xl font-bold text-red-700">{numFmt(stats.failed)}</div>
              <div className="mt-1 text-xs text-slate-500">FAILED</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">First-time-right</div>
              <div className="mt-2 text-2xl font-bold text-slate-900">{pctFmt(stats.first_time_right_rate)}</div>
              <div className="mt-1 text-xs text-slate-500">vs delivered + revisies + failed</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Gem. doorlooptijd</div>
              <div className="mt-2 text-2xl font-bold text-slate-900">
                {stats.avg_delivery_minutes != null ? `${numFmt(stats.avg_delivery_minutes)} min` : '—'}
              </div>
              <div className="mt-1 text-xs text-slate-500">alleen JOB_READY</div>
            </div>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Per client delivery rate</h2>
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Client</th>
                  <th className="px-4 py-3 text-right">Totaal</th>
                  <th className="px-4 py-3 text-right">Geleverd</th>
                  <th className="px-4 py-3 text-right">Revisies</th>
                  <th className="px-4 py-3 text-right">Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {perClient.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-slate-500 text-center">
                      Geen jobs met clientnaam in deze periode
                    </td>
                  </tr>
                ) : (
                  perClient.map((row) => (
                    <tr key={String(row.client_name)} className="hover:bg-slate-50/80">
                      <td className="px-4 py-3 font-medium text-slate-800">{row.client_name}</td>
                      <td className="px-4 py-3 text-right">{numFmt(row.total)}</td>
                      <td className="px-4 py-3 text-right text-emerald-700">{numFmt(row.delivered)}</td>
                      <td className="px-4 py-3 text-right text-amber-700">{numFmt(row.revisions)}</td>
                      <td className="px-4 py-3 text-right">{pctFmt(row.delivery_rate)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Recente leveringen</h2>
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Job</th>
                  <th className="px-4 py-3">Client</th>
                  <th className="px-4 py-3">Preset</th>
                  <th className="px-4 py-3 text-right">Minuten</th>
                  <th className="px-4 py-3">Afgerond</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {deliveredJobs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-slate-500 text-center">
                      Geen JOB_READY in deze periode
                    </td>
                  </tr>
                ) : (
                  deliveredJobs.map((row) => (
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
                      <td className="px-4 py-3 text-right text-slate-700">
                        {row.duration_minutes != null ? numFmt(Math.round(Number(row.duration_minutes))) : '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-600">{dtFmt(row.updated_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Jobs in revisie</h2>
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Job</th>
                  <th className="px-4 py-3">Client</th>
                  <th className="px-4 py-3">Preset</th>
                  <th className="px-4 py-3">Laatste update</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {revisionJobs.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-slate-500 text-center">
                      Geen NEEDS_CHANGES in deze periode
                    </td>
                  </tr>
                ) : (
                  revisionJobs.map((row) => (
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
                      <td className="px-4 py-3 text-slate-600">{dtFmt(row.updated_at)}</td>
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
