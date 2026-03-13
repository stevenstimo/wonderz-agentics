import { useEffect, useMemo, useState } from 'react'
import PageLayout from './PageLayout'
import { Loader2, Link2 } from 'lucide-react'
import { getErrorMessage } from './utils/errorMessage'

export default function TrainingHub() {
  const [agents, setAgents] = useState([])
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [url, setUrl] = useState('')
  const [training, setTraining] = useState(false)
  const [chunksProcessed, setChunksProcessed] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    loadAgents()
  }, [])

  async function loadAgents() {
    try {
      const res = await fetch('/api/agents')
      const data = await res.json()
      const list = Array.isArray(data) ? data : (data.agents || [])
      setAgents(list)
    } catch (err) {
      console.error('Failed to load agents:', err)
    }
  }

  const selectedAgent = useMemo(
    () => agents.find(a => a.agent_id === selectedAgentId),
    [agents, selectedAgentId]
  )

  const history = useMemo(() => {
    if (!selectedAgent) return []
    return selectedAgent.knowledge_sources || selectedAgent.knowledge_base_sources || []
  }, [selectedAgent])

  async function startTraining(e) {
    e.preventDefault()
    setError('')
    setChunksProcessed(null)

    if (!selectedAgentId || !url.trim()) return

    setTraining(true)
    try {
      const res = await fetch(`/api/agents/${selectedAgentId}/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() })
      })
      const data = await res.json()
      if (!res.ok) {
        setError(getErrorMessage(data) || 'Training mislukt')
      } else {
        setChunksProcessed(data.chunks_processed ?? data.chunks)
        setUrl('')
        await loadAgents()
      }
    } catch (err) {
      console.error('Training failed:', err)
      setError(getErrorMessage(err) || 'Training mislukt')
    }
    setTraining(false)
  }

  const displayName = selectedAgent?.name || selectedAgent?.agent_name || selectedAgent?.agent_id
  const displayRole = selectedAgent?.role || ''

  return (
    <PageLayout title="Training Hub">
      <div className="max-w-[960px] mx-auto flex flex-col gap-5">
        <div className="wz-card p-5">
          <h1 className="wz-title text-[22px]">Training Hub</h1>
          <p className="wz-label mt-1.5 normal-case">
            Train agents met URL-bronnen om hun kennis te vergroten.
          </p>
        </div>

        <div className="wz-card p-5 flex flex-col gap-3">
          <label className="wz-label">
            Agent kiezen
          </label>
          <select
            className="wz-input w-full text-sm"
            value={selectedAgentId}
            onChange={e => setSelectedAgentId(e.target.value)}
          >
            <option value="">Selecteer een agent...</option>
            {agents.map(agent => (
              <option key={agent.agent_id} value={agent.agent_id}>
                {agent.name || agent.agent_name || agent.agent_id} {agent.role ? `(${agent.role})` : ''}
              </option>
            ))}
          </select>
          {selectedAgent && (
            <div className="flex justify-between items-center">
              <div>
                <div className="font-semibold text-[var(--color-text-primary)]">{displayName}</div>
                {displayRole && (
                  <div className="wz-mono text-xs">{displayRole}</div>
                )}
              </div>
              <span className="wz-badge wz-mono">{selectedAgentId}</span>
            </div>
          )}
        </div>

        <form onSubmit={startTraining} className="wz-card p-5 flex flex-col gap-3">
          <label className="wz-label">
            Training URL
          </label>
          <div className="relative">
            <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)]" />
            <input
              className="wz-input w-full pl-10 text-sm"
              type="url"
              placeholder="https://example.com/bron"
              value={url}
              onChange={e => setUrl(e.target.value)}
              required
            />
          </div>
          <button
            type="submit"
            className="wz-btn-primary self-start text-sm font-semibold"
            disabled={training || !selectedAgentId}
          >
            {training ? 'Training...' : 'Start training'}
          </button>
          {error && (
            <div className="wz-card p-2.5 border-2 border-[var(--color-status-error)] text-[var(--color-status-error)] text-sm">
              {error}
            </div>
          )}
          {(training || chunksProcessed !== null) && (
            <div className="wz-card-subtle p-3 flex items-center gap-2.5">
              <Loader2 className="w-4 h-4 text-[var(--color-brand-primary)] flex-shrink-0" />
              <div className="wz-mono text-sm">
                {training ? 'Bezig met verwerken...' : `${chunksProcessed} chunks verwerkt`}
              </div>
            </div>
          )}
        </form>

        <div className="wz-card p-5">
          <div className="flex justify-between items-center mb-3">
            <h2 className="wz-subtitle text-sm">Trainingsgeschiedenis</h2>
            <span className="wz-label normal-case">{history.length} bronnen</span>
          </div>
          {history.length === 0 ? (
            <div className="wz-mono text-sm">
              Nog geen trainingsbronnen toegevoegd.
            </div>
          ) : (
            <div className="flex flex-col gap-2.5">
              {history.map((item, idx) => (
                <div key={`${item.url || item.source_url || idx}`} className="wz-card-subtle p-3">
                  <div className="text-sm font-semibold text-[var(--color-text-primary)]">
                    {item.url || item.source_url}
                  </div>
                  <div className="wz-mono text-xs mt-1.5">
                    {item.status ? `Status: ${item.status}` : 'Status: onbekend'}
                  </div>
                  {item.added_at && (
                    <div className="wz-mono text-xs">Toegevoegd: {item.added_at}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </PageLayout>
  )
}
