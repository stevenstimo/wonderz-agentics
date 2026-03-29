import { useEffect, useState } from 'react'
import { BookOpen, CheckCircle, AlertCircle, ExternalLink } from 'lucide-react'

export default function TrainingPanel({ agentId }) {
  const [url, setUrl] = useState('')
  const [training, setTraining] = useState(false)
  const [result, setResult] = useState(null)
  const [sessions, setSessions] = useState([])
  const [loadingSessions, setLoadingSessions] = useState(false)

  useEffect(() => {
    if (agentId) loadSessions()
  }, [agentId])

  async function loadSessions() {
    setLoadingSessions(true)
    try {
      const res = await fetch(`/api/agents/${agentId}/training-sessions`)
      if (!res.ok) throw new Error('Failed to load training sessions')
      const data = await res.json()
      setSessions(data.sessions || [])
    } catch (err) {
      console.error('Load sessions error:', err)
    } finally {
      setLoadingSessions(false)
    }
  }

  async function handleTrain(e) {
    e.preventDefault()
    setTraining(true)
    setResult(null)

    try {
      const res = await fetch(`/api/agents/${agentId}/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || 'Training failed')
      }

      setResult({ success: true, data })
      setUrl('')
      await loadSessions()
    } catch (err) {
      setResult({ success: false, error: err.message })
    } finally {
      setTraining(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center gap-2 mb-6">
        <BookOpen className="text-indigo-600" size={24} />
        <h2 className="text-xl font-bold text-gray-900">Training</h2>
      </div>

      <form onSubmit={handleTrain} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Training Source URL</label>
          <input
            type="url"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://example.com/training-content"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            required
            disabled={training}
          />
          <p className="text-xs text-gray-500 mt-1">Agent will learn from the content at this URL</p>
        </div>

        <button
          type="submit"
          disabled={training || !url}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
        >
          {training ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              Training in progress...
            </>
          ) : (
            <>
              <BookOpen size={18} />
              Start Training
            </>
          )}
        </button>
      </form>

      {result && (
        <div className={`mt-4 p-4 rounded-lg ${result.success ? 'bg-green-50' : 'bg-red-50'}`}>
          <div className="flex items-start gap-2">
            {result.success ? (
              <CheckCircle className="text-green-600 flex-shrink-0" size={20} />
            ) : (
              <AlertCircle className="text-red-600 flex-shrink-0" size={20} />
            )}
            <div>
              <p className={`font-medium ${result.success ? 'text-green-900' : 'text-red-900'}`}>
                {result.success ? 'Training started!' : 'Training failed'}
              </p>
              {result.success && result.data && (
                <p className="text-sm text-green-700 mt-1">
                  Session {result.data.session_id} queued for {result.data.source_url}
                </p>
              )}
              {!result.success && (
                <p className="text-sm text-red-700 mt-1">{result.error}</p>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="mt-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-700">Recent Training Sessions</h3>
          <button
            type="button"
            onClick={loadSessions}
            className="text-xs text-indigo-600 hover:text-indigo-800"
            disabled={loadingSessions}
          >
            {loadingSessions ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        {loadingSessions ? (
          <div className="text-xs text-gray-400">Loading sessions...</div>
        ) : sessions.length === 0 ? (
          <div className="text-xs text-gray-400">No sessions yet.</div>
        ) : (
          <div className="space-y-2">
            {sessions.map(session => (
              <div key={session.session_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-900 truncate">{session.source_url}</p>
                  <p className="text-xs text-gray-500">
                    {session.status} • {session.chunks_processed || 0}/{session.chunks_total || 0} chunks
                  </p>
                </div>
                {session.source_url && (
                  <a
                    href={session.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-indigo-600 hover:text-indigo-800"
                  >
                    <ExternalLink size={16} />
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
