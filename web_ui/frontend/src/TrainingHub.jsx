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
        setChunksProcessed(data.chunks)
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
      <div style={{ maxWidth: '960px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div className="wz-card" style={{ padding: '20px' }}>
          <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--color-text-primary)' }}>Training Hub</h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '12px', marginTop: '6px' }}>
            Train agents met URL-bronnen om hun kennis te vergroten.
          </p>
        </div>

        <div className="wz-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <label style={{ fontSize: '11px', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>
            Agent kiezen
          </label>
          <select
            className="wz-input"
            value={selectedAgentId}
            onChange={e => setSelectedAgentId(e.target.value)}
            style={{ width: '100%', fontSize: '12px' }}
          >
            <option value="">Selecteer een agent...</option>
            {agents.map(agent => (
              <option key={agent.agent_id} value={agent.agent_id}>
                {agent.name || agent.agent_name || agent.agent_id} {agent.role ? `(${agent.role})` : ''}
              </option>
            ))}
          </select>
          {selectedAgent && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{displayName}</div>
                {displayRole && (
                  <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>{displayRole}</div>
                )}
              </div>
              <span className="wz-badge" style={{ color: 'var(--color-brand-primary)' }}>{selectedAgentId}</span>
            </div>
          )}
        </div>

        <form onSubmit={startTraining} className="wz-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <label style={{ fontSize: '11px', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>
            Training URL
          </label>
          <div style={{ position: 'relative' }}>
            <Link2 style={{ position: 'absolute', left: '12px', top: '11px', width: '16px', height: '16px', color: 'var(--color-text-muted)' }} />
            <input
              className="wz-input"
              type="url"
              placeholder="https://example.com/bron"
              value={url}
              onChange={e => setUrl(e.target.value)}
              required
              style={{ width: '100%', paddingLeft: '38px', fontSize: '12px' }}
            />
          </div>
          <button
            type="submit"
            className="wz-btn-primary"
            disabled={training || !selectedAgentId}
            style={{ alignSelf: 'flex-start', fontSize: '12px', fontWeight: 600 }}
          >
            {training ? 'Training...' : 'Start training'}
          </button>
          {error && (
            <div className="wz-card" style={{ padding: '10px', borderColor: 'var(--color-status-error)', color: 'var(--color-status-error)', fontSize: '12px' }}>
              {error}
            </div>
          )}
          {(training || chunksProcessed !== null) && (
            <div className="wz-card" style={{ padding: '12px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Loader2 style={{ width: '16px', height: '16px', color: 'var(--color-brand-primary)' }} />
              <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                {training ? 'Bezig met verwerken...' : `${chunksProcessed} chunks verwerkt`}
              </div>
            </div>
          )}
        </form>

        <div className="wz-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text-primary)' }}>Trainingsgeschiedenis</h2>
            <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>{history.length} bronnen</span>
          </div>
          {history.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Nog geen trainingsbronnen toegevoegd.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {history.map((item, idx) => (
                <div key={`${item.url || item.source_url || idx}`} className="wz-card" style={{ padding: '12px' }}>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                    {item.url || item.source_url}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '6px' }}>
                    {item.status ? `Status: ${item.status}` : 'Status: onbekend'}
                  </div>
                  {item.added_at && (
                    <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Toegevoegd: {item.added_at}</div>
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
