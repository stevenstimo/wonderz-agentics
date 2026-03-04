import { useEffect, useState } from 'react'
import { BookOpen, Send, Check, Clock, AlertCircle, RefreshCw, Loader } from 'lucide-react'
import PageLayout from './PageLayout';
import { ToastContainer, useToast } from './Toast'

export default function TrainingManagement() {
  const [trainingSessions, setTrainingSessions] = useState([])
  const [crew, setCrew] = useState([])
  const [loading, setLoading] = useState(false)
  const [submitLoading, setSubmitLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showRequestForm, setShowRequestForm] = useState(false)
  const [expandedSession, setExpandedSession] = useState(null)
  const [formValidation, setFormValidation] = useState({})
  const toast = useToast()
  
  const [formData, setFormData] = useState({
    crew_id: '',
    agent_name: '',
    training_url: '',
    training_title: '',
    training_summary: '',
  })
  const [knowledgeBases, setKnowledgeBases] = useState({})
  const [decisionLoading, setDecisionLoading] = useState(null)
  const [completionLoading, setCompletionLoading] = useState(null)
  const [completionData, setCompletionData] = useState({})
  const [approvalsById, setApprovalsById] = useState({})

  const fetchTrainingSessions = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/training/sessions`)
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to fetch training sessions')
      }
      const data = await res.json()
      setTrainingSessions(Array.isArray(data) ? data : [])
    } catch (err) {
      const errorMsg = err.message || 'Failed to load training sessions'
      setError(errorMsg)
      toast.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const fetchCrew = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/crew`)
      if (!res.ok) throw new Error('Failed to fetch crew')
      const data = await res.json()
      setCrew(Array.isArray(data) ? data : [])
    } catch (err) {
      console.error('Error fetching crew:', err)
    }
  }

  const fetchKnowledgeBase = async (crew_id) => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/training/${crew_id}/knowledge-base`)
      if (!res.ok) throw new Error('Failed to fetch knowledge base')
      const data = await res.json()
      setKnowledgeBases(prev => ({ ...prev, [crew_id]: data }))
    } catch (err) {
      console.error('Error fetching knowledge base:', err)
    }
  }

  const fetchApprovals = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/ceo/approvals`)
      if (!res.ok) {
        return
      }
      const data = await res.json()
      const map = Array.isArray(data)
        ? data.reduce((acc, approval) => {
            acc[approval.id] = approval
            return acc
          }, {})
        : {}
      setApprovalsById(map)
    } catch (err) {
      console.error('Error fetching approvals:', err)
    }
  }

  const validateForm = () => {
    const errors = {}
    
    if (!formData.crew_id) {
      errors.crew_id = 'Please select an agent'
    }
    
    if (!formData.training_url) {
      errors.training_url = 'Training URL is required'
    } else if (!formData.training_url.startsWith('http://') && !formData.training_url.startsWith('https://')) {
      errors.training_url = 'URL must start with http:// or https://'
    } else if (formData.training_url.length > 2048) {
      errors.training_url = 'URL is too long (max 2048 characters)'
    }
    
    if (formData.training_title && formData.training_title.length > 200) {
      errors.training_title = 'Title must be 200 characters or less'
    }
    
    setFormValidation(errors)
    return Object.keys(errors).length === 0
  }

  useEffect(() => {
    fetchTrainingSessions()
    fetchCrew()
    fetchApprovals()
  }, [])

  const handleSubmitRequest = async (e) => {
    e.preventDefault()
    
    if (!validateForm()) {
      toast.warning('Please fix the validation errors')
      return
    }

    setSubmitLoading(true)
    setError(null)

    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/training/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || errorData.error || 'Failed to request training')
      }
      
      toast.success(`Training request submitted for ${formData.agent_name}. Awaiting CEO approval.`)
      setFormData({
        crew_id: '',
        agent_name: '',
        training_url: '',
        training_title: '',
        training_summary: '',
      })
      setShowRequestForm(false)
      setError(null)
      fetchTrainingSessions()
    } catch (err) {
      const errorMsg = err.message || 'Failed to request training'
      setError(errorMsg)
      toast.error(errorMsg)
    } finally {
      setSubmitLoading(false)
    }
  }

  const handleCrewSelect = (e) => {
    const selectedId = e.target.value
    const selected = crew.find(c => String(c.id) === selectedId)

    setFormData(prev => ({
      ...prev,
      crew_id: selected ? selected.id : '',
      agent_name: selected ? selected.name : '',
    }))
  }

  const handleApprovalDecision = async (approvalId, approved) => {
    setDecisionLoading(approvalId)
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/api/ceo/approval/${approvalId}/decide?approved=${approved}`,
        { method: 'POST' }
      )

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || errorData.error || 'Failed to process approval')
      }

      toast.success(`Training request ${approved ? 'approved' : 'rejected'}`)
      fetchTrainingSessions()
      fetchApprovals()
    } catch (err) {
      const errorMsg = err.message || 'Failed to process approval'
      toast.error(errorMsg)
    } finally {
      setDecisionLoading(null)
    }
  }

  const updateCompletionData = (sessionId, field, value) => {
    setCompletionData(prev => ({
      ...prev,
      [sessionId]: {
        ...prev[sessionId],
        [field]: value,
      }
    }))
  }

  const handleCompleteTraining = async (sessionId) => {
    const payload = completionData[sessionId] || {}
    if (!payload.knowledge_base || !payload.knowledge_base.trim()) {
      toast.warning('Knowledge base content is required')
      return
    }

    setCompletionLoading(sessionId)
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/api/training/${sessionId}/complete`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            knowledge_base: payload.knowledge_base,
            summary: payload.summary || null,
          })
        }
      )

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || errorData.error || 'Failed to complete training')
      }

      toast.success('Training marked as completed')
      setCompletionData(prev => ({ ...prev, [sessionId]: { knowledge_base: '', summary: '' } }))
      fetchTrainingSessions()
      fetchApprovals()
    } catch (err) {
      const errorMsg = err.message || 'Failed to complete training'
      toast.error(errorMsg)
    } finally {
      setCompletionLoading(null)
    }
  }

  const toggleExpandSession = (sessionId) => {
    if (expandedSession === sessionId) {
      setExpandedSession(null)
    } else {
      setExpandedSession(sessionId)
      const session = trainingSessions.find(s => s.session_id === sessionId)
      if (session && !knowledgeBases[session.crew_id]) {
        fetchKnowledgeBase(session.crew_id)
      }
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <Check className="w-5 h-5 text-green-600" />
      case 'in_progress':
        return <Clock className="w-5 h-5 text-blue-600" />
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-600" />
      default:
        return <Clock className="w-5 h-5 text-gray-600" />
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-50'
      case 'in_progress':
        return 'bg-blue-50'
      case 'failed':
        return 'bg-red-50'
      default:
        return 'bg-gray-50'
    }
  }

  const getApprovalBadgeClass = (status) => {
    switch (status) {
      case 'approved':
        return 'bg-green-100 text-green-800'
      case 'rejected':
        return 'bg-red-100 text-red-800'
      case 'completed':
        return 'bg-emerald-100 text-emerald-800'
      default:
        return 'bg-gray-100 text-gray-700'
    }
  }

  return (
    <PageLayout variant="inner" size="wide">
          <div className="bg-white rounded-xl shadow-lg p-8 mb-8">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <h2 className="text-2xl font-bold text-gray-800">Training Management</h2>
                <p className="text-sm text-gray-500">Train agents with URLs and build their knowledge bases</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={fetchTrainingSessions}
                  className="flex items-center gap-2 px-4 py-2 text-sm bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition"
                >
                  <RefreshCw className="w-4 h-4" />
                  Refresh
                </button>
                <button
                  onClick={() => {
                    setShowRequestForm(true)
                    setError(null)
                  }}
                  className="flex items-center gap-2 px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
                >
                  <Send className="w-4 h-4" />
                  Request Training
                </button>
              </div>
            </div>

            {error && (
              <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            )}
          </div>

          {showRequestForm && (
            <div className="bg-white rounded-xl shadow-lg p-8 mb-8">
              <h3 className="text-lg font-semibold mb-6 text-gray-800">Request Training</h3>
              <form onSubmit={handleSubmitRequest} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Agent <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={formData.crew_id === '' ? '' : String(formData.crew_id)}
                    onChange={handleCrewSelect}
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                      formValidation.crew_id ? 'border-red-500 bg-red-50' : ''
                    }`}
                  >
                    <option value="">Select an agent</option>
                    {crew.map(c => <option key={c.id} value={c.id}>{c.name} ({c.role})</option>)}
                  </select>
                  {formValidation.crew_id && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      {formValidation.crew_id}
                    </div>
                  )}
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Training URL <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="url"
                    value={formData.training_url}
                    onChange={(e) => setFormData({ ...formData, training_url: e.target.value })}
                    placeholder="https://example.com/training"
                    maxLength="2048"
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                      formValidation.training_url ? 'border-red-500 bg-red-50' : ''
                    }`}
                  />
                  {formValidation.training_url && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      {formValidation.training_url}
                    </div>
                  )}
                  <div className="text-xs text-gray-500 mt-1">{formData.training_url.length}/2048</div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Training Title
                  </label>
                  <input
                    type="text"
                    value={formData.training_title}
                    onChange={(e) => setFormData({ ...formData, training_title: e.target.value })}
                    placeholder="e.g., Advanced Python Techniques"
                    maxLength="200"
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                      formValidation.training_title ? 'border-red-500 bg-red-50' : ''
                    }`}
                  />
                  {formValidation.training_title && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      {formValidation.training_title}
                    </div>
                  )}
                  <div className="text-xs text-gray-500 mt-1">{formData.training_title.length}/200</div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Summary (optional)
                  </label>
                  <textarea
                    value={formData.training_summary}
                    onChange={(e) => setFormData({ ...formData, training_summary: e.target.value })}
                    placeholder="Brief summary of what the agent will learn"
                    rows={3}
                    maxLength="1000"
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                  <div className="text-xs text-gray-500 mt-1">{formData.training_summary.length}/1000</div>
                </div>
                
                <div className="flex gap-2 pt-4">
                  <button
                    type="submit"
                    disabled={submitLoading}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {submitLoading ? (
                      <>
                        <Loader className="w-4 h-4 animate-spin" />
                        Requesting...
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4" />
                        Request Training
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowRequestForm(false)
                      setFormValidation({})
                    }}
                    disabled={submitLoading}
                    className="px-4 py-2 border rounded-lg hover:bg-gray-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          <div className="bg-white rounded-xl shadow-lg p-8">
            <h3 className="text-lg font-semibold mb-6 text-gray-800 flex items-center gap-2">
              <BookOpen className="w-5 h-5" />
              Training Sessions ({trainingSessions.length})
            </h3>
            {loading && (
              <div className="flex items-center justify-center py-8">
                <Loader className="w-5 h-5 animate-spin text-indigo-600 mr-2" />
                <span className="text-sm text-gray-500">Loading training sessions...</span>
              </div>
            )}
            {!loading && trainingSessions.length === 0 && (
              <div className="text-sm text-gray-500">No training sessions yet. Create one to get started!</div>
            )}
            <div className="space-y-3">
              {trainingSessions.map(session => (
                <div key={session.session_id} className={`border rounded-lg p-4 ${getStatusColor(session.status)}`}>
                  <div
                    className="cursor-pointer"
                    onClick={() => toggleExpandSession(session.session_id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 flex-1">
                        {getStatusIcon(session.status)}
                        <div>
                          <div className="font-semibold text-gray-800">{session.agent_name}</div>
                          <div className="text-sm text-gray-600">{session.training_title || session.training_url}</div>
                          {session.metadata?.approval_id && approvalsById[session.metadata.approval_id]?.details?.decision_note && (
                            <div className="text-xs text-gray-500 mt-1">
                              CEO note: {approvalsById[session.metadata.approval_id].details.decision_note}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold px-2 py-1 rounded-full bg-white">
                          {session.status || 'pending'}
                        </span>
                        <span className={`text-xs font-semibold px-2 py-1 rounded-full ${getApprovalBadgeClass(session.approval_status)}`}>
                          {session.approval_status || 'pending'}
                        </span>
                        {session.status === 'completed' && (
                          <span className="text-xs font-semibold px-2 py-1 rounded-full bg-emerald-100 text-emerald-800">
                            Completed
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  {expandedSession === session.session_id && (
                    <div className="mt-4 pt-4 border-t space-y-3">
                      {session.status === 'completed' && (
                        <div className="px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800">
                          Knowledge base updated and training completed.
                        </div>
                      )}
                      {session.metadata?.approval_id && approvalsById[session.metadata.approval_id]?.details?.decision_note && (
                        <div className="text-xs text-gray-600">
                          CEO note: {approvalsById[session.metadata.approval_id].details.decision_note}
                        </div>
                      )}
                      {session.approval_status === 'pending' && session.metadata?.approval_id && (
                        <div className="flex flex-wrap gap-2">
                          <button
                            onClick={() => handleApprovalDecision(session.metadata.approval_id, true)}
                            disabled={decisionLoading !== null}
                            className="flex items-center gap-2 px-3 py-2 text-xs bg-green-600 text-white rounded hover:bg-green-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {decisionLoading === session.metadata.approval_id ? (
                              <Loader className="w-3 h-3 animate-spin" />
                            ) : (
                              <Check className="w-3 h-3" />
                            )}
                            Approve Training
                          </button>
                          <button
                            onClick={() => handleApprovalDecision(session.metadata.approval_id, false)}
                            disabled={decisionLoading !== null}
                            className="flex items-center gap-2 px-3 py-2 text-xs bg-red-600 text-white rounded hover:bg-red-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {decisionLoading === session.metadata.approval_id ? (
                              <Loader className="w-3 h-3 animate-spin" />
                            ) : (
                              <AlertCircle className="w-3 h-3" />
                            )}
                            Reject Training
                          </button>
                        </div>
                      )}
                      {session.training_summary && (
                        <div>
                          <div className="text-xs font-medium text-gray-600 mb-1">Summary</div>
                          <div className="text-sm text-gray-700">{session.training_summary}</div>
                        </div>
                      )}
                      {session.approval_status === 'approved' && session.status !== 'completed' && (
                        <div className="bg-white border rounded-lg p-3 space-y-2">
                          <div className="text-xs font-semibold text-gray-700">Complete Training</div>
                          <textarea
                            value={completionData[session.session_id]?.knowledge_base || ''}
                            onChange={(e) => updateCompletionData(session.session_id, 'knowledge_base', e.target.value)}
                            placeholder="Paste the knowledge base content here"
                            rows={3}
                            className="w-full px-3 py-2 text-sm border rounded"
                          />
                          <input
                            type="text"
                            value={completionData[session.session_id]?.summary || ''}
                            onChange={(e) => updateCompletionData(session.session_id, 'summary', e.target.value)}
                            placeholder="Optional summary"
                            className="w-full px-3 py-2 text-sm border rounded"
                          />
                          <button
                            onClick={() => handleCompleteTraining(session.session_id)}
                            disabled={completionLoading !== null}
                            className="flex items-center gap-2 px-3 py-2 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {completionLoading === session.session_id ? (
                              <Loader className="w-3 h-3 animate-spin" />
                            ) : (
                              <Check className="w-3 h-3" />
                            )}
                            Mark Completed
                          </button>
                        </div>
                      )}
                      <div>
                        <div className="text-xs font-medium text-gray-600 mb-1">Training URL</div>
                        <a href={session.training_url} target="_blank" rel="noopener noreferrer" 
                           className="text-sm text-indigo-600 hover:underline">{session.training_url}</a>
                      </div>
                      {session.knowledge_base && (
                        <div>
                          <div className="text-xs font-medium text-gray-600 mb-1">Knowledge Base</div>
                          <div className="text-sm text-gray-700 bg-white p-2 rounded whitespace-pre-wrap max-h-32 overflow-auto">
                            {session.knowledge_base}
                          </div>
                        </div>
                      )}
                      {session.requested_at && (
                        <div className="text-xs text-gray-500">
                          Requested: {new Date(session.requested_at).toLocaleDateString()}
                          {session.approved_at && ` • Approved: ${new Date(session.approved_at).toLocaleDateString()}`}
                          {session.completed_at && ` • Completed: ${new Date(session.completed_at).toLocaleDateString()}`}
                        </div>
                      )}
                      {session.approval_status === 'rejected' && (
                        <div className="text-xs text-red-600">
                          Training request rejected by CEO.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
      <ToastContainer toasts={toast.toasts} onRemove={toast.removeToast} />
    </PageLayout>
  )
}
