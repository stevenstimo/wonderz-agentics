import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageLayout from './PageLayout'

const apiBase = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')

function initials(name) {
  if (!name || typeof name !== 'string') return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  return (name[0] || '?').toUpperCase()
}

function StatusBadge({ status, isSuspended }) {
  const active = !isSuspended && (status === 'active' || status === 'hired' || !status)
  const cls = active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {active ? 'Active' : 'Suspended'}
    </span>
  )
}

export default function AgentsOverview() {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function loadAgents() {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${apiBase}/api/agents`)
      const data = await res.json().catch(() => [])
      if (!res.ok) {
        throw new Error('Agents ophalen mislukt')
      }
      setAgents(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message || 'Onbekende fout')
      setAgents([])
    } finally {
      setLoading(false)
    }
  }

  async function deactivateAgent(agentId) {
    if (!window.confirm('Agent deactiveren?')) return
    try {
      const res = await fetch(`${apiBase}/api/agents/${encodeURIComponent(agentId)}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Deactiveren mislukt')
      setAgents((prev) => prev.filter((agent) => agent.agent_id !== agentId))
    } catch (err) {
      alert(err.message || 'Onbekende fout')
    }
  }

  useEffect(() => {
    loadAgents()
  }, [])

  return (
    <PageLayout>
      <div className="panel-card">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="page-title mb-1">Crew Members</h1>
            <p className="page-subtitle">Overzicht van actieve hired agents.</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-icon-only" type="button" onClick={loadAgents} aria-label="Refresh">
              ↻
            </button>
            <Link to="/agents/new" className="btn-manage">
              + Nieuwe Agent
            </Link>
          </div>
        </div>

        {error && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        {loading ? (
          <div className="text-sm text-gray-500">Laden...</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 gap-4 w-full">
            {agents.map((agent) => (
              <Link
                key={agent.agent_id}
                to={`/agents/${encodeURIComponent(agent.agent_id)}`}
                className="block rounded-lg border border-slate-200 p-4 hover:border-indigo-300 hover:bg-slate-50/50 transition"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-700 font-semibold text-sm">
                    {initials(agent.name)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-slate-800">{agent.name || '—'}</span>
                      <StatusBadge status={agent.status} isSuspended={agent.is_suspended} />
                    </div>
                    <div className="text-xs text-slate-600 mt-0.5">{agent.role || '—'}</div>
                    {agent.specialization && (
                      <div className="text-xs text-slate-500 mt-1">{agent.specialization}</div>
                    )}
                    {typeof agent.performance_score === 'number' && (
                      <div className="mt-2">
                        <div className="text-xs text-slate-500 mb-1">Performance</div>
                        <div className="h-2 rounded-full bg-slate-100">
                          <div
                            className="h-2 rounded-full bg-indigo-500"
                            style={{ width: `${Math.min(100, Math.max(0, agent.performance_score))}%` }}
                          />
                        </div>
                      </div>
                    )}
                    <div className="mt-3 flex items-center gap-3">
                      <span className="text-blue-600 text-sm">View</span>
                      <button
                        type="button"
                        className="text-red-600 hover:underline text-sm"
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          deactivateAgent(agent.agent_id)
                        }}
                      >
                        Deactiveren
                      </button>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
            {!agents.length && (
              <div className="col-span-full py-8 text-center text-sm text-slate-500">
                Geen actieve agents gevonden.
              </div>
            )}
          </div>
        )}
      </div>
    </PageLayout>
  )
}
