import { useEffect, useState } from 'react'
import { apiFetch } from '../apiClient'

export default function AgentKnowledgeTab({ agentId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [removingUrl, setRemovingUrl] = useState(null)

  const fetchKnowledge = async () => {
    if (!agentId) return
    try {
      const res = await apiFetch(`/api/agents/${encodeURIComponent(agentId)}/knowledge`)
      if (res.ok) {
        const json = await res.json()
        setData(json)
      } else {
        setData(null)
      }
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setLoading(true)
    fetchKnowledge()
  }, [agentId])

  const handleDeactivate = async (sourceUrl) => {
    if (!confirm(`Bron verwijderen uit kennisbank?\n${sourceUrl}`)) return
    setRemovingUrl(sourceUrl)
    try {
      const res = await apiFetch(
        `/api/agents/${encodeURIComponent(agentId)}/knowledge?source_url=${encodeURIComponent(sourceUrl)}`,
        { method: 'DELETE' }
      )
      if (res.ok) await fetchKnowledge()
    } catch {
      // keep list as is
    }
    setRemovingUrl(null)
  }

  if (loading) return <p className="text-slate-500">Laden...</p>
  if (!data) return <p className="text-slate-500">Kon kennisbank niet laden.</p>

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-900">Kennisbank</h3>
        <span className="text-sm text-slate-500">{data.total_chunks} chunks totaal</span>
      </div>

      {(!data.sources || data.sources.length === 0) && (
        <p className="text-slate-500">Deze agent heeft nog geen getrainde kennisbronnen.</p>
      )}

      <div className="space-y-3">
        {data.sources?.map((source) => (
          <div
            key={source.source_url}
            className={`flex items-start justify-between gap-4 rounded-lg border p-3 ${
              !source.all_active ? 'bg-slate-50 border-slate-200 opacity-80' : 'border-slate-200'
            }`}
          >
            <div className="min-w-0 flex-1">
              <a
                href={source.source_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-indigo-600 hover:underline break-all"
              >
                {source.source_url}
              </a>
              <p className="text-xs text-slate-500 mt-1">
                {source.chunk_count} chunks •{' '}
                {source.last_added
                  ? new Date(source.last_added).toLocaleDateString('nl-NL')
                  : '—'}
                {!source.all_active && <span className="text-amber-600"> • Inactief</span>}
              </p>
            </div>
            {source.all_active && (
              <button
                type="button"
                onClick={() => handleDeactivate(source.source_url)}
                disabled={removingUrl === source.source_url}
                className="shrink-0 px-3 py-1.5 text-sm font-medium rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                {removingUrl === source.source_url ? 'Verwijderen...' : 'Verwijder'}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
