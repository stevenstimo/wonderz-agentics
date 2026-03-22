/**
 * Quality checklist and agent performance above job delivery content.
 */
import { useEffect, useState } from 'react'
import { CheckCircle, XCircle, AlertTriangle, Loader2 } from 'lucide-react'
import { apiFetch } from '../apiClient'

export default function JobQualityReport({ jobId }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!jobId) return undefined
    let cancelled = false
    setLoading(true)
    setError(null)
    ;(async () => {
      try {
        const res = await apiFetch(`/api/jobs/${jobId}/quality-report`)
        if (cancelled) return
        if (!res.ok) {
          const j = await res.json().catch(() => ({}))
          setError(j.detail || `HTTP ${res.status}`)
          setReport(null)
          return
        }
        const data = await res.json()
        if (!cancelled) setReport(data)
      } catch (e) {
        if (!cancelled) {
          setError(e?.message || 'Laden mislukt')
          setReport(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [jobId])

  if (!jobId) return null
  if (loading) {
    return (
      <div className="mb-4 flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        <Loader2 className="h-4 w-4 animate-spin shrink-0" aria-hidden />
        Kwaliteit controleren…
      </div>
    )
  }
  if (error) {
    return (
      <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Kwaliteitsrapport: {error}
      </div>
    )
  }
  if (!report) return null

  const allPassed = report.checks_passed === report.checks_total
  const agents = Array.isArray(report.agents) ? report.agents : []

  return (
    <div className="job-quality-report mb-5 rounded-lg border border-slate-200 bg-slate-50/80 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold text-slate-900">Kwaliteitscontrole</span>
        <span
          className={`text-sm font-semibold ${allPassed ? 'text-emerald-700' : 'text-red-700'}`}
        >
          {report.checks_passed}/{report.checks_total} checks geslaagd
        </span>
      </div>

      <div className="mb-4 flex flex-col gap-1.5">
        {(report.checks || []).map((check) => (
          <div
            key={check.id}
            className={`flex flex-wrap items-center gap-2 rounded-md px-2.5 py-1.5 text-sm ${
              check.passed ? 'bg-emerald-50 text-emerald-900' : 'bg-red-50 text-red-900'
            }`}
          >
            {check.passed ? (
              <CheckCircle className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
            ) : (
              <XCircle className="h-4 w-4 shrink-0 text-red-600" aria-hidden />
            )}
            <span className="font-medium min-w-[8rem]">{check.label}</span>
            <span className="text-xs opacity-80">{check.detail}</span>
          </div>
        ))}
      </div>

      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600">
          Betrokken agents
        </div>
        {agents.length === 0 ? (
          <p className="text-xs text-slate-500">Geen stapdata voor deze job.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {agents.map((agent) => {
              const reason = (agent.performance_reason || '').trim()
              return (
                <div
                  key={agent.agent_id}
                  title={reason || undefined}
                  className={`inline-flex max-w-full flex-col gap-0.5 rounded-lg border px-3 py-1.5 text-xs ${
                    agent.performance === 'good'
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                      : agent.performance === 'warning'
                        ? 'border-amber-200 bg-amber-50 text-amber-900'
                        : 'border-red-200 bg-red-50 text-red-900'
                  }`}
                >
                  <div className="flex min-w-0 max-w-full items-center gap-1.5">
                    {agent.performance === 'good' ? (
                      <CheckCircle className="h-3.5 w-3.5 shrink-0" aria-hidden />
                    ) : agent.performance === 'warning' ? (
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
                    ) : (
                      <XCircle className="h-3.5 w-3.5 shrink-0" aria-hidden />
                    )}
                    <span className="font-medium truncate">{agent.agent_id}</span>
                    <span className="opacity-75 shrink-0">
                      {agent.total_steps} stap{agent.total_steps !== 1 ? 'pen' : ''}
                      {agent.retries > 0
                        ? ` · ${agent.retries} retr${agent.retries !== 1 ? 'ies' : 'y'}`
                        : ''}
                      {agent.failed_steps > 0
                        ? ` · ${agent.failed_steps} fout${agent.failed_steps !== 1 ? 'en' : ''}`
                        : ''}
                    </span>
                  </div>
                  {reason ? (
                    <span className="block max-w-full pl-5 text-[0.7rem] leading-snug opacity-90">
                      {reason}
                    </span>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
