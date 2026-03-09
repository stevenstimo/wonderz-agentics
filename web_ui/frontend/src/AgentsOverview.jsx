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
  const cls = active ? 'bg-blue-100 text-blue-800' : 'bg-red-100 text-red-800'
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${cls}`}>
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
      if (!res.ok) throw new Error('Failed to load agents')
      const list = Array.isArray(data) ? data : []
      const sorted = [...list].sort((a, b) => {
        if ((a.role || '').toLowerCase() === 'ceo') return -1
        if ((b.role || '').toLowerCase() === 'ceo') return 1
        return (a.name || '').localeCompare(b.name || '')
      })
      setAgents(sorted)
    } catch (err) {
      setError(err.message || 'Unknown error')
      setAgents([])
    } finally {
      setLoading(false)
    }
  }

  async function deactivateAgent(agentId, e) {
    e.preventDefault()
    e.stopPropagation()
    if (!window.confirm('Deactivate this agent?')) return
    try {
      const res = await fetch(`${apiBase}/api/agents/${encodeURIComponent(agentId)}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Deactivation failed')
      setAgents((prev) => prev.filter((agent) => agent.agent_id !== agentId))
    } catch (err) {
      alert(err.message || 'Unknown error')
    }
  }

  useEffect(() => {
    loadAgents()
  }, [])

  return (
    <PageLayout>
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="p-6 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Agents</h1>
            <p className="text-slate-600 mt-0.5">Manage your hired agents and their performance.</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={loadAgents}
              className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition"
              aria-label="Refresh"
            >
              ↻
            </button>
            <Link
              to="/agents/new"
              className="rounded-lg px-4 py-2.5 bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition"
            >
              New Agent
            </Link>
          </div>
        </div>

        {error && (
          <div className="mx-6 mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 border border-red-100">
            {error}
          </div>
        )}

        {loading ? (
          <div className="p-8 text-center text-slate-500 text-sm">Loading...</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/80">
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Agent</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Role</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Specialization</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Status</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Performance</th>
                    <th className="text-right py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {agents.map((agent) => (
                    <tr
                      key={agent.agent_id}
                      className="border-b border-slate-100 hover:bg-slate-50 transition"
                    >
                      <td className="py-3 px-4">
                        <Link
                          to={`/agents/${encodeURIComponent(agent.agent_id)}`}
                          className="flex items-center gap-3"
                        >
                          <div className="w-10 h-10 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-sm font-semibold flex-shrink-0">
                            {initials(agent.name)}
                          </div>
                          <span className="font-medium text-slate-900">{agent.name || '—'}</span>
                        </Link>
                      </td>
                      <td className="py-3 px-4 text-sm text-slate-600">{agent.role || '—'}</td>
                      <td className="py-3 px-4 text-sm text-slate-600">{agent.specialization || '—'}</td>
                      <td className="py-3 px-4">
                        <StatusBadge status={agent.status} isSuspended={agent.is_suspended} />
                      </td>
                      <td className="py-3 px-4">
                        {typeof agent.performance_score === 'number' ? (
                          <div className="flex items-center gap-2 min-w-[100px]">
                            <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden max-w-[80px]">
                              <div
                                className="h-2 rounded-full bg-indigo-600 transition-all"
                                style={{ width: `${Math.min(100, Math.max(0, agent.performance_score))}%` }}
                              />
                            </div>
                            <span className="text-xs text-slate-500 w-8">{Math.round(agent.performance_score)}%</span>
                          </div>
                        ) : (
                          <span className="text-slate-400 text-sm">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          to={`/agents/${encodeURIComponent(agent.agent_id)}`}
                          className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                        >
                          View Details
                        </Link>
                        <button
                          type="button"
                          onClick={(e) => deactivateAgent(agent.agent_id, e)}
                          className="ml-3 text-red-600 hover:text-red-800 text-sm font-medium"
                        >
                          Deactivate
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!agents.length && (
              <div className="py-12 text-center text-slate-500 text-sm">No agents found.</div>
            )}
          </>
        )}
      </div>
    </PageLayout>
  )
}
