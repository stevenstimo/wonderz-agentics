import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import PageLayout from './PageLayout'
import { fetchJson } from './apiClient'
import { queryKeys } from './queryKeys'

function initials(name) {
  if (!name || typeof name !== 'string') return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  return (name[0] || '?').toUpperCase()
}

function StatusBadge({ isActive }) {
  const cls = isActive ? 'bg-green-100 text-green-800' : 'bg-slate-200 text-slate-600'
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${cls}`}>
      {isActive ? 'Actief' : 'Inactief'}
    </span>
  )
}

export default function AgentsOverview() {
  // Filter: 'all' | true (actief) | false (inactief)
  const [activeFilter, setActiveFilter] = useState('all')
  const params = new URLSearchParams()
  if (activeFilter === true) params.set('is_active', 'true')
  if (activeFilter === false) params.set('is_active', 'false')
  const qs = params.toString()
  const endpoint = qs ? `/api/agents?${qs}` : '/api/agents'
  const { data: agents = [], isLoading: loading, error, refetch } = useQuery({
    queryKey: queryKeys.agents({ activeFilter }),
    queryFn: async () => {
      const data = await fetchJson(endpoint)
      const list = Array.isArray(data) ? data : (data?.agents || [])
      return [...list].sort((a, b) => {
        if ((a.role || '').toLowerCase() === 'ceo') return -1
        if ((b.role || '').toLowerCase() === 'ceo') return 1
        return (a.name || '').localeCompare(b.name || '')
      })
    },
    refetchInterval: 30_000,
  })

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
              onClick={() => refetch()}
              className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition"
              aria-label="Refresh"
            >
              ↻
            </button>
            <Link
              to="/agents/new"
              className="rounded-lg px-4 py-2.5 bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition"
            >
              + Nieuwe agent
            </Link>
          </div>
        </div>

        {/* Filter: actief / inactief */}
        <div className="mx-6 mt-4 flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-slate-600">Status:</span>
          <div className="inline-flex rounded-lg border border-slate-200 p-0.5 bg-slate-50/80">
            <button
              type="button"
              onClick={() => setActiveFilter('all')}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${activeFilter === 'all' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
            >
              Alles
            </button>
            <button
              type="button"
              onClick={() => setActiveFilter(true)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${activeFilter === true ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
            >
              Actief
            </button>
            <button
              type="button"
              onClick={() => setActiveFilter(false)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${activeFilter === false ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
            >
              Inactief
            </button>
          </div>
        </div>

        {error && (
          <div className="mx-6 mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 border border-red-100">
            {error.message || 'Unknown error'}
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
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Rol</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Categorie</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Status</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Tools</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Performance</th>
                    <th className="text-right py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Acties</th>
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
                      <td className="py-3 px-4 text-sm text-slate-600">{agent.category || '—'}</td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center gap-1.5">
                          <StatusBadge isActive={agent.is_active !== false} />
                          {agent.is_suspended && (
                            <span
                              style={{
                                background: '#FDEDEC',
                                color: '#922B21',
                                borderRadius: '4px',
                                padding: '2px 8px',
                                fontSize: '11px',
                                marginLeft: '6px',
                                fontWeight: 600,
                              }}
                            >
                              Gesuspendeerd
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm text-slate-600">
                        {(Array.isArray(agent.tool_access_whitelist) ? agent.tool_access_whitelist : agent.tool_whitelist || []).length}
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
                          to={`/agents/${encodeURIComponent(agent.agent_id)}?tab=chat`}
                          className="text-indigo-600 hover:text-indigo-800 text-sm font-medium mr-3"
                        >
                          Open chat
                        </Link>
                        <Link
                          to={`/agents/${encodeURIComponent(agent.agent_id)}/edit`}
                          className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                        >
                          Bewerken
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!agents.length && (
              <div className="py-16 text-center">
                <p className="text-slate-600 mb-4">Nog geen agents in je crew. Maak je eerste agent aan om te beginnen.</p>
                <Link
                  to="/agents/new"
                  className="inline-flex rounded-lg px-4 py-2.5 bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition"
                >
                  Maak eerste agent aan
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </PageLayout>
  )
}
