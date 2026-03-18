/**
 * CEO Dashboard — Fase B, docs/cursor/02_dashboard_newbies_navigation.md
 * Vier blokken: Crew Status, Operationeel vandaag, Agent Health, Recente activiteit.
 * Auto-refresh 60s. Groen = goed, amber = aandacht, rood = actie.
 */
import { useState, useEffect, useCallback } from 'react'
import PageLayout from './PageLayout'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8090'

function MetricCard({ title, items, loading }) {
  const statusColor = (label, value) => {
    if (value === undefined || value === null) return 'text-slate-600'
    if (typeof value !== 'number') return 'text-slate-600'
    if (label.toLowerCase().includes('failed') || label.toLowerCase().includes('suspended')) return value > 0 ? 'text-red-600' : 'text-green-600'
    if (label.toLowerCase().includes('running') || label.toLowerCase().includes('awaiting')) return value > 0 ? 'text-amber-600' : 'text-slate-600'
    return 'text-green-600'
  }
  return (
    <div className="panel-card">
      <h3 className="font-semibold text-slate-800 mb-3">{title}</h3>
      {loading ? (
        <p className="text-sm text-slate-500">Laden…</p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {items.map(({ label, value }) => (
            <li key={label} className="flex justify-between gap-2">
              <span className="text-slate-600">{label}</span>
              <span className={`font-medium ${statusColor(label, value)}`}>{value}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function CEODashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchData = useCallback(async () => {
    try {
      setError(null)
      const r = await fetch(`${API_BASE}/api/dashboard/ceo`, { credentials: 'include' })
      if (!r.ok) throw new Error(r.statusText)
      const j = await r.json()
      setData(j)
    } catch (e) {
      setError(e.message || 'Fout bij laden dashboard')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 60_000)
    return () => clearInterval(interval)
  }, [fetchData])

  if (error) {
    return (
      <PageLayout size="wide" padded>
        <div className="panel-card border-red-200 bg-red-50">
          <p className="text-red-700">{error}</p>
          <button onClick={fetchData} className="mt-2 px-3 py-1 bg-red-100 rounded text-red-800 text-sm">Opnieuw proberen</button>
        </div>
      </PageLayout>
    )
  }

  const crew = data?.crew_status ?? {}
  const operational = data?.operational ?? {}
  const health = data?.agent_health ?? {}
  const recent = data?.recent_activity ?? {}

  return (
    <PageLayout size="wide" padded>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">CEO Dashboard</h1>
        <p className="text-slate-600 text-sm">Auto-refresh elke 60 seconden</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Crew Status"
          loading={loading}
          items={[
            { label: 'Actieve agents', value: crew.active_agents },
            { label: 'NewBies in training', value: crew.newbies_in_training },
            { label: 'NewBies klaar', value: crew.newbies_ready },
            { label: 'Gesuspendeerd', value: crew.suspended_agents },
          ]}
        />
        <MetricCard
          title="Operationeel vandaag"
          loading={loading}
          items={[
            { label: 'Jobs lopend', value: operational.jobs_running },
            { label: 'Jobs voltooid vandaag', value: operational.jobs_completed_today },
            { label: 'Wachten op goedkeuring', value: operational.jobs_awaiting_approval },
            { label: 'Fouten', value: operational.jobs_failed },
          ]}
        />
        <MetricCard
          title="Agent Health"
          loading={loading}
          items={[
            { label: 'Open development points', value: health.open_development_points },
            { label: 'Training verzoeken open', value: health.training_requests_open },
            { label: 'Agents met >3 open points', value: (health.high_retry_agents || []).length },
          ]}
        />
        <div className="panel-card">
          <h3 className="font-semibold text-slate-800 mb-3">Recente activiteit</h3>
          {loading ? (
            <p className="text-sm text-slate-500">Laden…</p>
          ) : (
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-slate-600 font-medium mb-1">Laatste 5 jobs</p>
                <ul className="text-slate-600">
                  {(recent.recent_jobs || []).slice(0, 5).map((j) => (
                    <li key={j.id}>{j.job_number || j.id} — {j.status}</li>
                  ))}
                  {(!recent.recent_jobs || recent.recent_jobs.length === 0) && <li>Geen</li>}
                </ul>
              </div>
              <div>
                <p className="text-slate-600 font-medium mb-1">Laatste 3 dev points</p>
                <ul className="text-slate-600">
                  {(recent.recent_development_points || []).slice(0, 3).map((d) => (
                    <li key={d.point_id}>{d.agent_role || d.agent_id}: {d.issue_description?.slice(0, 30)}…</li>
                  ))}
                  {(!recent.recent_development_points || recent.recent_development_points.length === 0) && <li>Geen</li>}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </PageLayout>
  )
}
