import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageLayout from './PageLayout'
import { RefreshCw, MessageCircle } from 'lucide-react'
import { buildAuthHeaders } from './authz'

const IMPACT_STYLES = {
  high: { className: 'wz-badge', color: 'var(--color-status-error)' },
  medium: { className: 'wz-badge', color: 'var(--color-status-warning)' },
  low: { className: 'wz-badge', color: 'var(--color-status-success)' }
}

export default function HRDashboard() {
  const [points, setPoints] = useState([])
  const [report, setReport] = useState([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)

  useEffect(() => {
    loadAll()
  }, [])

  async function loadAll() {
    setLoading(true)
    await Promise.all([loadPoints(), loadReport()])
    setLoading(false)
  }

  async function loadPoints() {
    try {
      const res = await fetch('/api/hr/development-points')
      const data = await res.json()
      setPoints(data.development_points ?? (Array.isArray(data) ? data : []))
    } catch (err) {
      console.error('Failed to load development points:', err)
    }
  }

  async function loadReport() {
    try {
      const res = await fetch('/api/hr/report', { headers: await buildAuthHeaders() })
      const data = await res.json()
      const agents = data.agents ?? {}
      setReport(Object.entries(agents).map(([agent_id, a]) => ({
        agent_id,
        agent_name: a.agent_name ?? a.name,
        agent_role: a.role,
        jobs_completed: a.performance?.jobs_touched_7d ?? 0,
        avg_retry_rate: a.performance?.retry_rate ?? 0,
        open_points: a.open_points_count ?? a.open_points ?? 0,
        in_training: 0,
        resolved_last_30_days: 0
      })))
    } catch (err) {
      console.error('Failed to load report:', err)
    }
  }

  async function triggerScan() {
    setScanning(true)
    try {
      await fetch('/api/hr/scan', { method: 'POST' })
      await loadAll()
    } catch (err) {
      console.error('Scan failed:', err)
    }
    setScanning(false)
  }

  async function updatePoint(pointId, status) {
    try {
      await fetch(`/api/hr/development-points/${pointId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, approved_by: 'hr-dashboard' })
      })
      await loadPoints()
    } catch (err) {
      console.error('Update failed:', err)
    }
  }

  const reportEntries = Array.isArray(report) ? report : []

  return (
    <PageLayout title="HR Dashboard">
      <div style={{ maxWidth: '1040px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div className="wz-card" style={{ padding: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--color-text-primary)' }}>HR Dashboard</h1>
            <p style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Development points en agent stats</p>
          </div>
          <button
            className="wz-btn-primary"
            onClick={triggerScan}
            disabled={scanning}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: 600 }}
          >
            <RefreshCw style={{ width: '16px', height: '16px' }} />
            {scanning ? 'Scannen...' : 'Scan nu'}
          </button>
        </div>

        <div className="wz-card" style={{ padding: '20px' }}>
          <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '12px' }}>Agent stats</h2>
          {loading && reportEntries.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Laden...</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
              {reportEntries.map((data) => (
                <div key={data.agent_id} className="wz-card" style={{ padding: '14px' }}>
                  <div style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>
                    {data.agent_name || data.agent_id}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                    {data.agent_role || data.agent_id}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '10px', marginTop: '12px', fontSize: '12px' }}>
                    <div>
                      <div style={{ color: 'var(--color-text-muted)' }}>Jobs (30d)</div>
                      <div style={{ fontWeight: 600 }}>{data.jobs_completed}</div>
                    </div>
                    <div>
                      <div style={{ color: 'var(--color-text-muted)' }}>Avg retry (7d)</div>
                      <div style={{ fontWeight: 600 }}>{Number(data.avg_retry_rate || 0).toFixed(2)}</div>
                    </div>
                    <div>
                      <div style={{ color: 'var(--color-text-muted)' }}>Open points</div>
                      <div style={{ fontWeight: 600 }}>{data.open_points}</div>
                    </div>
                    <div>
                      <div style={{ color: 'var(--color-text-muted)' }}>In training</div>
                      <div style={{ fontWeight: 600 }}>{data.in_training}</div>
                    </div>
                    <div>
                      <div style={{ color: 'var(--color-text-muted)' }}>Resolved (30d)</div>
                      <div style={{ fontWeight: 600 }}>{data.resolved_last_30_days}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="wz-card" style={{ padding: '20px' }}>
          <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '12px' }}>Development points</h2>
          {loading && points.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Laden...</div>
          ) : points.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Geen development points gevonden.</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
              {points.map(point => {
                const impactKey = (point.impact || 'medium').toLowerCase()
                const impactStyle = IMPACT_STYLES[impactKey] || IMPACT_STYLES.medium
                return (
                  <div key={point.point_id} className="wz-card" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{point.issue_description}</div>
                      <span className={impactStyle.className} style={{ color: impactStyle.color }}>
                        {impactKey}
                      </span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Agent: {point.agent_name || point.agent_id}</div>
                    <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                      Frequentie: {point.frequency}
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '4px', alignItems: 'center' }}>
                      <Link
                        to={`/agents/${encodeURIComponent(point.agent_id || '')}?tab=chat`}
                        className="wz-btn-ghost"
                        style={{ fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                      >
                        <MessageCircle style={{ width: '14px', height: '14px' }} />
                        Bespreek direct met {point.agent_name || point.agent_id || 'agent'}
                      </Link>
                      <select
                        value={point.status || 'OPEN'}
                        onChange={(e) => updatePoint(point.point_id, e.target.value)}
                        style={{ fontSize: '12px', padding: '4px 8px', borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)', color: 'var(--color-text-primary)' }}
                      >
                        <option value="OPEN">OPEN</option>
                        <option value="AWAITING_APPROVAL">AWAITING_APPROVAL</option>
                        <option value="IN_TRAINING">IN_TRAINING</option>
                        <option value="RESOLVED">RESOLVED</option>
                        <option value="DISMISSED">DISMISSED</option>
                      </select>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </PageLayout>
  )
}
