import { useEffect, useState } from 'react'
import { Loader2, X } from 'lucide-react'
import { apiFetch } from '../apiClient'

export default function AgentKnowledgeTab({ agentId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [removingUrl, setRemovingUrl] = useState(null)
  const [detailSourceUrl, setDetailSourceUrl] = useState(null)
  const [chunks, setChunks] = useState([])
  const [chunksLoading, setChunksLoading] = useState(false)

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

  const openKnowledgeDetail = async (sourceUrl) => {
    if (!sourceUrl || !agentId) return
    setDetailSourceUrl(sourceUrl)
    setChunksLoading(true)
    setChunks([])
    try {
      const res = await apiFetch(
        `/api/agents/${encodeURIComponent(agentId)}/knowledge?source_url=${encodeURIComponent(sourceUrl)}`
      )
      if (!res.ok) {
        setChunks([])
        return
      }
      const json = await res.json()
      setChunks(Array.isArray(json.chunks) ? json.chunks : [])
    } catch {
      setChunks([])
    } finally {
      setChunksLoading(false)
    }
  }

  const closeKnowledgeDetail = () => {
    setDetailSourceUrl(null)
    setChunks([])
  }

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
    <div
      className="rounded-xl border p-6 shadow-sm"
      style={{
        backgroundColor: 'var(--color-bg-card)',
        borderColor: 'var(--color-border)',
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
          Kennisbank
        </h3>
        <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          {data.total_chunks} chunks totaal
        </span>
      </div>

      {(!data.sources || data.sources.length === 0) && (
        <p style={{ color: 'var(--color-text-muted)' }}>Deze agent heeft nog geen getrainde kennisbronnen.</p>
      )}

      <div className="space-y-3">
        {data.sources?.map((source) => (
          <div
            key={source.source_url}
            className={`flex items-start justify-between gap-4 rounded-lg border p-3 ${
              !source.all_active ? 'opacity-80' : ''
            }`}
            style={{
              backgroundColor: !source.all_active ? 'var(--color-bg-subtle)' : 'transparent',
              borderColor: 'var(--color-border)',
            }}
          >
            <div className="min-w-0 flex-1">
              <button
                type="button"
                onClick={() => openKnowledgeDetail(source.source_url)}
                className="text-sm text-indigo-600 hover:underline break-all text-left"
              >
                {source.source_url}
              </button>
              <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                {source.chunk_count} chunks •{' '}
                {source.last_added
                  ? new Date(source.last_added).toLocaleDateString('nl-NL')
                  : '—'}
                {!source.all_active && <span className="text-amber-600"> • Inactief</span>}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => openKnowledgeDetail(source.source_url)}
                className="shrink-0 px-3 py-1.5 text-sm font-medium rounded-lg border text-slate-700 hover:bg-slate-50"
                style={{ borderColor: 'var(--color-border)' }}
              >
                Open
              </button>
              {source.all_active && (
                <button
                  type="button"
                  onClick={() => handleDeactivate(source.source_url)}
                  disabled={removingUrl === source.source_url}
                  className="shrink-0 px-3 py-1.5 text-sm font-medium rounded-lg border text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  style={{ borderColor: 'var(--color-border)' }}
                >
                  {removingUrl === source.source_url ? 'Verwijderen...' : 'Verwijder'}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {detailSourceUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-labelledby="knowledge-chunks-title"
          onClick={closeKnowledgeDetail}
        >
          <div
            className="rounded-xl shadow-lg max-w-2xl w-full max-h-[85vh] flex flex-col border"
            style={{
              backgroundColor: 'var(--color-bg-card)',
              borderColor: 'var(--color-border)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className="flex items-start justify-between gap-4 p-4 border-b shrink-0"
              style={{ borderColor: 'var(--color-border)' }}
            >
              <h2
                id="knowledge-chunks-title"
                className="text-lg font-semibold pr-8"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Geleerde kennis
              </h2>
              <button
                type="button"
                onClick={closeKnowledgeDetail}
                className="p-1 rounded-lg hover:bg-slate-100 shrink-0"
                aria-label="Sluiten"
              >
                <X className="w-5 h-5" style={{ color: 'var(--color-text-secondary)' }} />
              </button>
            </div>
            <div className="px-4 pt-3 pb-2 shrink-0">
              <a
                href={detailSourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-indigo-600 hover:underline break-all"
              >
                {detailSourceUrl}
              </a>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto px-4 pb-4">
              {chunksLoading ? (
                <div className="flex items-center gap-2 py-8 justify-center" style={{ color: 'var(--color-text-muted)' }}>
                  <Loader2 className="w-6 h-6 animate-spin shrink-0" aria-hidden />
                  <span>Chunks laden...</span>
                </div>
              ) : chunks.length === 0 ? (
                <p className="py-6 text-center" style={{ color: 'var(--color-text-muted)' }}>
                  Geen chunks gevonden voor deze bron.
                </p>
              ) : (
                <div className="space-y-4 pt-2">
                  <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                    {chunks.length} chunks geïndexeerd
                  </p>
                  {chunks.map((chunk) => (
                    <div
                      key={chunk.knowledge_id ?? `${chunk.chunk_index}-${chunk.source_url}`}
                      className="rounded-lg border p-3 text-sm"
                      style={{
                        borderColor: 'var(--color-border)',
                        backgroundColor: 'var(--color-bg-subtle)',
                      }}
                    >
                      <span
                        className="text-xs font-medium mb-2 inline-block"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        #{Number(chunk.chunk_index ?? 0) + 1}
                      </span>
                      <p className="whitespace-pre-wrap" style={{ color: 'var(--color-text-primary)' }}>
                        {chunk.chunk_text}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
