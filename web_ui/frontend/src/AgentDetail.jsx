import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, User } from 'lucide-react'
import PageLayout from './PageLayout'
import TrainingPanel from './components/TrainingPanel'

export default function AgentDetail() {
  const { agentId } = useParams()
  const [agent, setAgent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadAgent()
  }, [agentId])

  async function loadAgent() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/agents/${agentId}`)
      if (!res.ok) throw new Error('Agent not found')
      const data = await res.json()
      setAgent(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <PageLayout title="Agent Detail">
        <div className="text-center py-12 text-gray-500">Loading agent...</div>
      </PageLayout>
    )
  }

  if (error || !agent) {
    return (
      <PageLayout title="Agent Detail">
        <div className="text-center py-12">
          <p className="text-red-500 mb-4">{error || 'Agent not found'}</p>
          <Link to="/agents" className="text-indigo-600 hover:underline">← Back to Agents</Link>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout title={agent.name || 'Agent Detail'}>
      <div className="max-w-5xl mx-auto px-4 py-8">
        <Link to="/agents" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-indigo-600 mb-6">
          <ArrowLeft className="w-4 h-4" /> Back to Agents
        </Link>
        <Link to={`/agents/${agentId}/analytics`} className="inline-flex items-center gap-2 text-sm text-indigo-600 hover:underline mb-6 ml-4">
          View Analytics
        </Link>

        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center">
              <User className="text-indigo-600" size={24} />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-2xl font-bold text-gray-900">{agent.name}</h1>
                <span className={`text-xs font-semibold px-2 py-1 rounded-full ${
                  agent.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                }`}>
                  {agent.status}
                </span>
              </div>
              <p className="text-sm text-gray-500 capitalize">{agent.role}</p>
              <div className="flex gap-6 text-sm mt-3">
                <div>
                  <span className="text-gray-400">Performance</span>
                  <span className="ml-2 font-semibold">{Math.round((agent.performance_score || 0) * 100)}%</span>
                </div>
                <div>
                  <span className="text-gray-400">Completed Tasks</span>
                  <span className="ml-2 font-semibold">{agent.completed_tasks || 0}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-3">System Instructions</h2>
            <pre className="text-sm text-gray-600 whitespace-pre-wrap font-sans leading-relaxed bg-gray-50 p-4 rounded-lg max-h-64 overflow-y-auto">
              {agent.system_instructions || 'No instructions provided.'}
            </pre>
          </div>

          <TrainingPanel agentId={agentId} />
        </div>
      </div>
    </PageLayout>
  )
}
