import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, User } from 'lucide-react'
import PageLayout from './PageLayout'
import TrainingPanel from './components/TrainingPanel'
import { getErrorMessage } from './utils/errorMessage'

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
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <PageLayout title="Agent Detail">
        <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-muted)' }}>
          Loading agent...
        </div>
      </PageLayout>
    )
  }

  if (error || !agent) {
    return (
      <PageLayout title="Agent Detail">
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <p style={{ color: 'var(--color-status-error)', marginBottom: '16px' }}>
            {error || 'Agent not found'}
          </p>
          <Link to="/agents" className="wz-btn-ghost">
            ← Back to Agents
          </Link>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout title={agent.name || 'Agent Detail'}>
      <div style={{ maxWidth: '1024px', margin: '0 auto', padding: '32px 16px' }}>
        <Link
          to="/agents"
          className="wz-btn-ghost"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '12px', marginBottom: '24px' }}
        >
          <ArrowLeft style={{ width: '16px', height: '16px' }} /> Back to Agents
        </Link>
        <Link
          to={`/agents/${agentId}/analytics`}
          className="wz-btn-ghost"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '12px', marginBottom: '24px', marginLeft: '16px' }}
        >
          View Analytics
        </Link>

        <div className="wz-card" style={{ padding: '24px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                backgroundColor: 'var(--color-bg-subtle)',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid var(--color-border)'
              }}
            >
              <User style={{ color: 'var(--color-brand-primary)' }} size={24} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                  {agent.name}
                </h1>
                <span
                  className={`wz-badge ${agent.status === 'active' ? 'wz-badge-success' : 'wz-badge-running'}`}
                  style={{ fontSize: '12px', fontWeight: 600, textTransform: 'capitalize' }}
                >
                  {agent.status}
                </span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                {agent.role}
              </p>
              <div style={{ display: 'flex', gap: '24px', fontSize: '12px', marginTop: '12px' }}>
                <div>
                  <span style={{ color: 'var(--color-text-muted)' }}>Performance</span>
                  <span style={{ marginLeft: '8px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                    {Math.round((agent.performance_score || 0) * 100)}%
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)' }}>Completed Tasks</span>
                  <span style={{ marginLeft: '8px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                    {agent.completed_tasks || 0}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '24px'
          }}
        >
          <div className="wz-card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '12px' }}>
              System Instructions
            </h2>
            <pre
              className="wz-mono"
              style={{
                fontSize: '12px',
                color: 'var(--color-text-muted)',
                whiteSpace: 'pre-wrap',
                lineHeight: 1.6,
                backgroundColor: 'var(--color-bg-subtle)',
                padding: '16px',
                borderRadius: '12px',
                maxHeight: '256px',
                overflowY: 'auto',
                border: '1px solid var(--color-border)'
              }}
            >
              {agent.system_instructions || 'No instructions provided.'}
            </pre>
          </div>

          <TrainingPanel agentId={agentId} />
        </div>
      </div>
    </PageLayout>
  )
}
