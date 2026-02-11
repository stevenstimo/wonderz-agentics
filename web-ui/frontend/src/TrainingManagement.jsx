import { useEffect, useState } from 'react'
import { BookOpen, Send, Check, Clock, AlertCircle, RefreshCw } from 'lucide-react'
import Sidebar from './Sidebar'

export default function TrainingManagement() {
  const [trainingSessions, setTrainingSessions] = useState([])
  const [crew, setCrew] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showRequestForm, setShowRequestForm] = useState(false)
  const [expandedSession, setExpandedSession] = useState(null)
  const [formData, setFormData] = useState({
    crew_id: '',
    agent_name: '',
    training_url: '',
    training_title: '',
    training_summary: '',
  })
  const [knowledgeBases, setKnowledgeBases] = useState({})

  const fetchTrainingSessions = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/training/sessions`)
      if (!res.ok) throw new Error('Failed to fetch training sessions')
      const data = await res.json()
      setTrainingSessions(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message)
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

  useEffect(() => {
    fetchTrainingSessions()
    fetchCrew()
  }, [])

  const handleSubmitRequest = async (e) => {
    e.preventDefault()
    if (!formData.crew_id || !formData.training_url) {
      setError('Agent and Training URL are required')
      return
    }

    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/training/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })

      if (!res.ok) throw new Error('Failed to request training')
      
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
      setError(err.message)
    }
  }

  const handleCrewSelect = (e) => {
    const selected = crew.find(c => c.id === e.target.value)
    if (selected) {
      setFormData({
        ...formData,
        crew_id: selected.id,
        agent_name: selected.name,
      })
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex">
      <Sidebar />
      <main className="flex-1 px-8 py-8">
        <div className="max-w-6xl mx-auto">
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
                    Agent
                  </label>
                  <select
                    value={formData.crew_id}
                    onChange={handleCrewSelect}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  >
                    <option value="">Select an agent</option>
                    {crew.map(c => <option key={c.id} value={c.id}>{c.name} ({c.role})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Training URL
                  </label>
                  <input
                    type="url"
                    value={formData.training_url}
                    onChange={(e) => setFormData({ ...formData, training_url: e.target.value })}
                    placeholder="https://example.com/training"
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
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
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
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
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <div className="flex gap-2 pt-4">
                  <button
                    type="submit"
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
                  >
                    Request Training
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowRequestForm(false)}
                    className="px-4 py-2 border rounded-lg hover:bg-gray-100 transition"
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
            {loading && <div className="text-sm text-gray-400">Loading...</div>}
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
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold px-2 py-1 rounded-full bg-white">
                          {session.status || 'pending'}
                        </span>
                        <span className="text-xs font-semibold px-2 py-1 rounded-full bg-white">
                          {session.approval_status || 'pending'}
                        </span>
                      </div>
                    </div>
                  </div>
                  {expandedSession === session.session_id && (
                    <div className="mt-4 pt-4 border-t space-y-3">
                      {session.training_summary && (
                        <div>
                          <div className="text-xs font-medium text-gray-600 mb-1">Summary</div>
                          <div className="text-sm text-gray-700">{session.training_summary}</div>
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
                          {session.completed_at && ` • Completed: ${new Date(session.completed_at).toLocaleDateString()}`}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
