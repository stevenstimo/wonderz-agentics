import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import PageLayout from './PageLayout'
import { SuccessRateChart } from './components/SuccessRateChart'
import { TokenUsageChart } from './components/TokenUsageChart'

export default function AgentAnalytics({ agentId: agentIdProp }) {
  const params = useParams()
  const agentId = agentIdProp || params.agentId
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!agentId) return

    async function fetchMetrics() {
      setLoading(true)
      setError(null)
      try {
        const response = await fetch(`/api/monitoring/agents/${agentId}/performance?days=30`)
        if (!response.ok) throw new Error('Failed to fetch metrics')
        const data = await response.json()
        setMetrics(data)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchMetrics()
  }, [agentId])

  if (!agentId) {
    return (
      <PageLayout title="Agent Analytics">
        <div className="text-center py-12 text-gray-500">No agent selected.</div>
      </PageLayout>
    )
  }

  if (loading) {
    return (
      <PageLayout title="Agent Analytics">
        <div className="text-center py-12 text-gray-500">Loading analytics...</div>
      </PageLayout>
    )
  }

  if (error || !metrics) {
    return (
      <PageLayout title="Agent Analytics">
        <div className="text-center py-12 text-red-500">{error || 'Failed to load analytics.'}</div>
      </PageLayout>
    )
  }

  return (
    <PageLayout title="Agent Analytics">
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Agent Analytics</h1>
            <p className="text-sm text-gray-500">Agent: {metrics.agent_id}</p>
          </div>
          <Link to={`/agents/${agentId}`} className="text-sm text-indigo-600 hover:underline">
            Back to Agent
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm text-gray-500">Success Rate</div>
            <div className="text-3xl font-bold text-green-600">
              {(metrics.success_rate * 100).toFixed(1)}%
            </div>
          </div>

          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm text-gray-500">Jobs Worked</div>
            <div className="text-3xl font-bold text-blue-600">
              {metrics.jobs_worked}
            </div>
          </div>

          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm text-gray-500">Avg Latency</div>
            <div className="text-3xl font-bold text-purple-600">
              {metrics.avg_latency_ms}ms
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <SuccessRateChart data={metrics.trend_data} />
          <TokenUsageChart data={metrics.token_data} labelKey="label" />
        </div>
      </div>
    </PageLayout>
  )
}
