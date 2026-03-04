import { useEffect, useMemo, useState } from 'react'
import { MessageSquare, RefreshCw, ChevronDown, ChevronUp, X } from 'lucide-react'
import PageLayout from './PageLayout';
import { ToastContainer, useToast } from './Toast'

const commandList = new Set([
  'laat verbeter punten zien',
  'laat verbeterpunten zien',
])

export default function HRImprovements() {
  const [command, setCommand] = useState('')
  const [commandMessage, setCommandMessage] = useState('')
  const [improvements, setImprovements] = useState([])
  const [loading, setLoading] = useState(false)
  const [trainingLoading, setTrainingLoading] = useState(null)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState({})
  const [submittedById, setSubmittedById] = useState({})
  const [logItem, setLogItem] = useState(null)
  const toast = useToast()

  const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

  const grouped = useMemo(() => {
    return improvements.reduce((acc, item) => {
      if (!acc[item.agent_id]) {
        acc[item.agent_id] = {
          agent_id: item.agent_id,
          agent_name: item.agent_name,
          items: [],
        }
      }
      acc[item.agent_id].items.push(item)
      return acc
    }, {})
  }, [improvements])

  const fetchImprovements = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiBase}/api/hr/improvements`)
      if (!res.ok) throw new Error('Failed to fetch improvements')
      const data = await res.json()
      setImprovements(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchImprovements()
  }, [])

  const onSubmitCommand = (e) => {
    e.preventDefault()
    const normalized = command.trim().toLowerCase().replace(/\s+/g, ' ')
    if (commandList.has(normalized)) {
      setCommandMessage('HR manager: verbeterpunten worden getoond.')
      fetchImprovements()
    } else if (!normalized) {
      setCommandMessage('')
    } else {
      setCommandMessage('HR manager: commando niet herkend.')
    }
  }

  const toggleItem = (id) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const handleAuthorizeTraining = async (item) => {
    setTrainingLoading(item.id)
    setError(null)
    try {
      const res = await fetch(`${apiBase}/api/ceo/approval/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request_type: 'training',
          details: {
            agent: item.agent_name || item.agent_id,
            agent_id: item.agent_id,
            improvement_id: item.id,
            title: item.title,
            summary: item.summary,
            proposed_action: item.proposed_action,
            source: 'hr_improvements'
          }
        })
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to request training approval')
      }

      setSubmittedById(prev => ({ ...prev, [item.id]: true }))
      toast.success('Training request submitted for approval')
    } catch (err) {
      const errorMsg = err.message || 'Failed to request training approval'
      setError(errorMsg)
      toast.error(errorMsg)
    } finally {
      setTrainingLoading(null)
    }
  }

  const openLog = (item) => {
    setLogItem(item)
  }

  const closeLog = () => {
    setLogItem(null)
  }

  const groupList = Object.values(grouped)
  const flatItems = groupList.flatMap(group => group.items.map(item => ({
    ...item,
    agent_name: group.agent_name,
  })))

  const criticalCount = flatItems.filter(item => {
    const severity = String(item.severity || '').toLowerCase()
    return severity.includes('critical') || severity.includes('high')
  }).length

  const getImpactClass = (severity) => {
    const level = String(severity || '').toLowerCase()
    if (level.includes('high') || level.includes('critical')) return 'hr-pill hr-pill-high'
    if (level.includes('medium')) return 'hr-pill hr-pill-medium'
    return 'hr-pill hr-pill-low'
  }

  const getImpactLabel = (severity) => {
    const level = String(severity || '').toLowerCase()
    if (level.includes('high') || level.includes('critical')) return 'High Impact'
    if (level.includes('medium')) return 'Medium Impact'
    return 'Low Impact'
  }

  return (
    <PageLayout size="medium" padded>
          <div className="panel-card mb-8">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <h2 className="page-title">HR Improvements</h2>
                <p className="page-subtitle">Performance backlog identified by HR QA Analyst.</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="hr-pill hr-pill-high">{criticalCount} Critical Issues</span>
                <button
                  onClick={fetchImprovements}
                  className="btn-manage gap-2"
                >
                  <RefreshCw className="w-4 h-4" />
                  Refresh
                </button>
              </div>
            </div>
            <form onSubmit={onSubmitCommand} className="mt-6 flex gap-3 flex-wrap">
              <div className="flex-1 min-w-[240px] relative">
                <MessageSquare className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  placeholder="Typ: laat verbeter punten zien"
                  className="w-full pl-9 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
              <button
                type="submit"
                className="btn-manage"
              >
                Stuur naar HR
              </button>
            </form>
            {commandMessage && (
              <div className="mt-3 text-sm text-indigo-700">{commandMessage}</div>
            )}
          </div>

          <div className="panel-card">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-semibold text-gray-800">Issues by agent</h3>
              {loading && <span className="text-sm text-gray-400">Loading...</span>}
            </div>
            {error && <div className="text-sm text-red-600">Error: {error}</div>}
            {!error && !loading && flatItems.length === 0 && (
              <div className="text-sm text-gray-500">Geen verbeterpunten gevonden.</div>
            )}
            <div className="grid gap-6 md:grid-cols-1 lg:grid-cols-2">
              {flatItems.map(item => {
                const isOpen = !!expanded[item.id]
                return (
                  <div key={item.id} className="hr-card">
                    <div className="flex items-start justify-between">
                      <div className="text-sm text-gray-400">Issue</div>
                      <div className="flex items-center gap-2">
                        {submittedById[item.id] && (
                          <span className="hr-pill hr-pill-submitted">Submitted</span>
                        )}
                        <span className={getImpactClass(item.severity)}>{getImpactLabel(item.severity)}</span>
                      </div>
                    </div>
                    <div>
                      <div className="text-lg font-semibold text-gray-900">{item.title}</div>
                      <div className="text-sm text-gray-500 mt-1">
                        {item.summary || item.agent_name || 'Agent review'}
                      </div>
                    </div>

                    <div>
                      <div className="hr-section-title">Evidence</div>
                      <div className="hr-evidence mt-2">
                        <span>{item.details || item.evidence || 'Log excerpt unavailable.'}</span>
                        <button
                          className="text-xs font-semibold text-indigo-600"
                          onClick={() => openLog(item)}
                          type="button"
                        >
                          View Log
                        </button>
                      </div>
                    </div>

                    <div className="hr-action">
                      <div className="hr-action-title">Proposed Action</div>
                      <div className="text-sm text-white">
                        {item.proposed_action || 'Injecteer transactielogs in de vector store.'}
                      </div>
                      <button
                        className="btn-secondary w-full justify-center"
                        onClick={() => handleAuthorizeTraining(item)}
                        disabled={trainingLoading !== null || submittedById[item.id]}
                      >
                        {submittedById[item.id]
                          ? 'Submitted'
                          : trainingLoading === item.id
                          ? 'Authorizing...'
                          : 'Authorize Training'}
                      </button>
                      <button
                        className="text-xs text-indigo-200 flex items-center gap-2"
                        onClick={() => toggleItem(item.id)}
                        type="button"
                      >
                        {isOpen ? 'Hide details' : 'View details'}
                        {isOpen ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </button>
                    </div>

                    {isOpen && (
                      <div className="text-sm text-gray-600 whitespace-pre-line">
                        {item.details || 'Geen extra details beschikbaar.'}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
      {logItem && (
        <div className="modal-overlay" onClick={closeLog}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-gray-400">Evidence Log</div>
                <div className="text-lg font-semibold text-gray-900">{logItem.title}</div>
              </div>
              <button className="btn-icon-only" onClick={closeLog} type="button">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="text-sm text-gray-700 whitespace-pre-line">
              {logItem.details || logItem.evidence || 'Log excerpt unavailable.'}
            </div>
          </div>
        </div>
      )}
      <ToastContainer toasts={toast.toasts} onRemove={toast.removeToast} />
    </PageLayout>
  )
}
