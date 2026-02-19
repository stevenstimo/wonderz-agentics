import { useState, useEffect, useRef } from 'react'
import PageLayout from './PageLayout'
import { GraduationCap, Play, CheckCircle, XCircle, Loader2, Link2, Clock } from 'lucide-react'

const STATUS_STYLES = {
  pending:    { bg: 'bg-gray-50',  border: 'border-gray-200', badge: 'bg-gray-100 text-gray-700',  icon: Clock },
  processing: { bg: 'bg-blue-50',  border: 'border-blue-200', badge: 'bg-blue-100 text-blue-700',  icon: Loader2 },
  completed:  { bg: 'bg-green-50', border: 'border-green-200',badge: 'bg-green-100 text-green-700', icon: CheckCircle },
  failed:     { bg: 'bg-red-50',   border: 'border-red-200',  badge: 'bg-red-100 text-red-700',    icon: XCircle },
}

export default function TrainingHub() {
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState('')
  const [sessions, setSessions] = useState([])
  const [training, setTraining] = useState(false)
  const [loading, setLoading] = useState(false)
  const pollRef = useRef(null)

  useEffect(() => {
    loadAgents()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  useEffect(() => {
    if (selectedAgent) loadSessions(selectedAgent)
    else setSessions([])
  }, [selectedAgent])

  // Poll active sessions
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current)

    const active = sessions.filter(s => s.status === 'processing' || s.status === 'pending')
    if (active.length > 0 && selectedAgent) {
      pollRef.current = setInterval(() => loadSessions(selectedAgent), 2000)
    }

    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [sessions, selectedAgent])

  async function loadAgents() {
    try {
      const res = await fetch('/api/agents')
      const data = await res.json()
      setAgents(data.agents || [])
    } catch (e) {
      console.error('Failed to load agents:', e)
    }
  }

  async function loadSessions(agentId) {
    try {
      const res = await fetch(`/api/agents/${agentId}/training-sessions`)
      const data = await res.json()
      setSessions(data.sessions || [])
    } catch (e) {
      console.error('Failed to load sessions:', e)
    }
  }

  async function startTraining(e) {
    e.preventDefault()
    const url = e.target.url.value.trim()
    if (!url || !selectedAgent) return

    setTraining(true)
    try {
      const res = await fetch(`/api/agents/${selectedAgent}/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: url })
      })
      if (res.ok) {
        e.target.reset()
        await loadSessions(selectedAgent)
      } else {
        const err = await res.json()
        alert('Training start mislukt: ' + (err.detail || 'Unknown error'))
      }
    } catch (err) {
      console.error('Training start failed:', err)
    }
    setTraining(false)
  }

  const selectedAgentObj = agents.find(a => a.agent_id === selectedAgent)

  return (
    <PageLayout title="Training Hub">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <GraduationCap className="w-7 h-7 text-indigo-500" />
            Training Hub
          </h1>
          <p className="text-gray-500 text-sm mt-1">Train agents met URL-bronnen om hun kennis te vergroten</p>
        </div>

        {/* Agent selector */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Selecteer agent om te trainen</label>
          <select
            value={selectedAgent}
            onChange={e => setSelectedAgent(e.target.value)}
            className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none"
          >
            <option value="">Kies een agent...</option>
            {agents.map(agent => (
              <option key={agent.agent_id} value={agent.agent_id}>
                {agent.name} ({agent.role})
              </option>
            ))}
          </select>

          {selectedAgentObj && (
            <div className="mt-3 p-3 bg-indigo-50 rounded-lg">
              <div className="text-sm">
                <span className="font-medium text-indigo-900">{selectedAgentObj.name}</span>
                <span className="text-indigo-600 ml-2 text-xs bg-indigo-100 px-2 py-0.5 rounded">
                  {selectedAgentObj.role}
                </span>
              </div>
              {selectedAgentObj.hiring_logic && (
                <p className="text-xs text-indigo-700 mt-1">{selectedAgentObj.hiring_logic}</p>
              )}
              <p className="text-xs text-indigo-500 mt-1 font-mono">{selectedAgentObj.agent_id}</p>
            </div>
          )}
        </div>

        {selectedAgent && (
          <>
            {/* Training form */}
            <form onSubmit={startTraining} className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
              <h2 className="text-sm font-semibold text-gray-800 mb-3">Nieuwe Training Starten</h2>
              <div className="flex gap-3">
                <div className="relative flex-1">
                  <Link2 className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                  <input
                    name="url"
                    type="url"
                    placeholder="https://example.com/article"
                    required
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none"
                  />
                </div>
                <button
                  type="submit"
                  disabled={training}
                  className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm font-medium whitespace-nowrap"
                >
                  {training ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  Start Training
                </button>
              </div>
            </form>

            {/* Training history */}
            <div>
              <h2 className="text-sm font-semibold text-gray-800 mb-3">Training Geschiedenis</h2>

              {sessions.length === 0 ? (
                <div className="text-center py-10 bg-gray-50 rounded-xl border border-gray-200">
                  <GraduationCap className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                  <p className="text-gray-500 text-sm">Nog geen trainingen voor deze agent</p>
                  <p className="text-gray-400 text-xs mt-1">Start een training hierboven</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {sessions.map(session => {
                    const style = STATUS_STYLES[session.status] || STATUS_STYLES.pending
                    const Icon = style.icon
                    const progress = session.chunks_total > 0
                      ? Math.round((session.chunks_processed / session.chunks_total) * 100)
                      : 0

                    return (
                      <div key={session.session_id} className={`rounded-xl border p-4 ${style.bg} ${style.border}`}>
                        <div className="flex items-center justify-between gap-3 mb-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <Icon className={`w-4 h-4 flex-shrink-0 ${session.status === 'processing' ? 'animate-spin text-blue-500' : ''}`} />
                            <span className={`text-xs font-semibold px-2 py-0.5 rounded uppercase ${style.badge}`}>
                              {session.status}
                            </span>
                            <span className="text-xs text-gray-500 truncate" title={session.source_url}>
                              {session.source_url}
                            </span>
                          </div>
                          <span className="text-xs text-gray-400 flex-shrink-0">
                            {session.started_at ? new Date(session.started_at).toLocaleString('nl-NL') : ''}
                          </span>
                        </div>

                        {session.status === 'processing' && (
                          <div className="mt-2">
                            <div className="h-2 bg-white/70 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                                style={{ width: `${progress}%` }}
                              />
                            </div>
                            <p className="text-xs text-blue-600 mt-1">
                              {session.chunks_processed} / {session.chunks_total} chunks verwerkt ({progress}%)
                            </p>
                          </div>
                        )}

                        {session.status === 'completed' && (
                          <p className="text-xs text-green-700 mt-1">
                            ✓ Voltooid — {session.chunks_total} chunks verwerkt
                          </p>
                        )}

                        {session.status === 'failed' && session.error_message && (
                          <p className="text-xs text-red-700 mt-1">
                            ✗ {session.error_message}
                          </p>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </PageLayout>
  )
}
