import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const apiBase = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')

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
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead>
              <tr className="border-b border-gray-200 text-left text-sm text-gray-600">
                <th className="py-2 pr-4 font-medium">Naam</th>
                <th className="py-2 pr-4 font-medium">Rol</th>
                <th className="py-2 pr-4 font-medium">Doel</th>
                <th className="py-2 pr-4 font-medium">Tools</th>
                <th className="py-2 pr-4 font-medium">Aangemaakt</th>
                <th className="py-2 pr-0 font-medium">Acties</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.agent_id} className="border-b border-gray-100 text-sm text-gray-800">
                  <td className="py-3 pr-4">{agent.agent_name}</td>
                  <td className="py-3 pr-4">{agent.role}</td>
                  <td className="py-3 pr-4">{agent.goal}</td>
                  <td className="py-3 pr-4">{agent.tool_whitelist?.length || 0} tools</td>
                  <td className="py-3 pr-4">
                    {agent.created_at ? new Date(agent.created_at).toLocaleDateString() : '-'}
                  </td>
                  <td className="py-3 pr-0">
                    <div className="flex items-center gap-3">
                      <Link className="text-blue-600 hover:underline" to={`/agents/${encodeURIComponent(agent.agent_id)}/edit`}>
                        Edit
                      </Link>
                      <button
                        type="button"
                        className="text-red-600 hover:underline"
                        onClick={() => deactivateAgent(agent.agent_id)}
                      >
                        Deactiveren
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!agents.length && (
                <tr>
                  <td className="py-4 text-sm text-gray-500" colSpan={6}>
                    Geen actieve agents gevonden.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
