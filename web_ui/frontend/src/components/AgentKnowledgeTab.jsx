import { useEffect, useState } from 'react'
import { apiFetch } from '../apiClient'

export default function AgentKnowledgeTab({ agentId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [removingUrl, setRemovingUrl] = useState(null)
  const [selectedSource, setSelectedSource] = useState(null)

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
              <button
                type="button"
                onClick={() => setSelectedSource(source)}
                className="text-sm text-indigo-600 hover:underline break-all text-left"
              >
                {source.source_url}
              </button>
              <p className="text-xs text-slate-500 mt-1">
                {source.chunk_count} chunks •{' '}
                {source.last_added
                  ? new Date(source.last_added).toLocaleDateString('nl-NL')
                  : '—'}
                {!source.all_active && <span className="text-amber-600"> • Inactief</span>}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <a
                href={source.source_url}
                target="_blank"
                rel="noreferrer"
                className="shrink-0 px-3 py-1.5 text-sm font-medium rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Open
              </a>
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
          </div>
        ))}
      </div>

      {selectedSource && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-labelledby="knowledge-source-detail-title"
          onClick={() => setSelectedSource(null)}
        >
          <div
            className="bg-white rounded-xl shadow-lg max-w-lg w-full p-6 border border-slate-200"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="knowledge-source-detail-title" className="text-lg font-semibold text-slate-900 mb-4">
              Kennisbron details
            </h2>
            <div className="space-y-3 text-sm text-slate-700">
              <div>
                <p className="text-slate-500 text-xs uppercase tracking-wide mb-1">Bron URL</p>
                <p className="break-all">{selectedSource.source_url || '—'}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs uppercase tracking-wide mb-1">Aantal chunks</p>
                <p>{selectedSource.chunk_count ?? 0}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs uppercase tracking-wide mb-1">Aanmaakdatum</p>
                <p>{selectedSource.last_added ? new Date(selectedSource.last_added).toLocaleString('nl-NL') : '—'}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs uppercase tracking-wide mb-1">Agent waarvoor getraind</p>
                <p>{agentId || '—'}</p>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <a
                href={selectedSource.source_url}
                target="_blank"
                rel="noreferrer"
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50"
              >
                Open bron
              </a>
              <button
                type="button"
                onClick={() => setSelectedSource(null)}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700"
              >
                Sluiten
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
