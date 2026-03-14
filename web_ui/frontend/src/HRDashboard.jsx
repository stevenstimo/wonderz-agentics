import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from './apiClient'
import PageLayout from './PageLayout'
import { RefreshCw } from 'lucide-react'
import { useAuthReady } from './useAuthReady'

const TABS = [
  { id: 'points', label: 'Development Points' },
  { id: 'training', label: 'Training Requests' },
  { id: 'cross', label: 'Cross-Training' },
]

const IMPACT_COLOR = { high: '#E74C3C', medium: '#E67E22', low: '#95A5A6' }
const IMPACT_BADGE = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-orange-100 text-orange-700',
  low: 'bg-gray-100 text-gray-500',
}

const STATUS_BADGE = {
  OPEN: 'bg-blue-100 text-blue-700',
  IN_TRAINING: 'bg-purple-100 text-purple-700',
  RESOLVED: 'bg-green-100 text-green-700',
  DISMISSED: 'bg-gray-100 text-gray-500',
  AWAITING_APPROVAL: 'bg-orange-100 text-orange-700',
}

export default function HRDashboard() {
  const authReady = useAuthReady()
  const [tab, setTab] = useState('points')
  const [points, setPoints] = useState([])
  const [trainingRequests, setTrainingRequests] = useState([])
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [scanMessage, setScanMessage] = useState('')
  const [scanStep, setScanStep] = useState(0)
  const [scanOutcome, setScanOutcome] = useState(null)
  const [scanResultText, setScanResultText] = useState('')
  const [error, setError] = useState('')
  const [trainingUrlInput, setTrainingUrlInput] = useState({})
  const [crossProposals, setCrossProposals] = useState([])
  const [crossUrlInput, setCrossUrlInput] = useState({})
  const [filterImpact, setFilterImpact] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [report, setReport] = useState(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [approveModal, setApproveModal] = useState(null)
  const [approveUrl, setApproveUrl] = useState('')
  const [approvingId, setApprovingId] = useState(null)
  const [resolveInput, setResolveInput] = useState({})
  const [expandedPointId, setExpandedPointId] = useState(null)

  const loadPoints = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/hr/development-points')
      if (res.ok) {
        const data = await res.json()
        setPoints(data.development_points ?? (Array.isArray(data) ? data : []))
      }
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadTrainingRequests = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/hr/training-requests?status=pending')
      if (res.ok) {
        const data = await res.json()
        setTrainingRequests(Array.isArray(data) ? data : [])
      }
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadReport = useCallback(async () => {
    setReportLoading(true)
    try {
      const res = await apiFetch('/api/hr/report')
      if (res.ok) {
        const data = await res.json()
        setReport(data.agents != null ? data : { agents: {} })
      }
    } catch {
      setReport({ agents: {} })
    } finally {
      setReportLoading(false)
    }
  }, [])

  const loadCrossProposals = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/hr/cross-training-proposals?status=pending')
      if (res.ok) {
        const data = await res.json()
        setCrossProposals(Array.isArray(data) ? data : [])
      }
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!authReady) return
    if (tab === 'points') loadPoints()
    else if (tab === 'training') loadTrainingRequests()
    else if (tab === 'cross') loadCrossProposals()
  }, [authReady, tab, loadPoints, loadTrainingRequests, loadCrossProposals])

  // Mark CEO notifications as read when user lands on HR dashboard
  useEffect(() => {
    if (!authReady) return
    let cancelled = false
    const markAllRead = async () => {
      try {
        const res = await apiFetch('/api/hr/notifications')
        if (!res.ok || cancelled) return
        const list = await res.json()
        if (!Array.isArray(list) || cancelled) return
        for (const n of list) {
          if (n.notification_id) {
            await apiFetch(`/api/hr/notifications/${n.notification_id}/read`, { method: 'POST' })
          }
        }
      } catch {
        // ignore
      }
    }
    markAllRead()
    return () => { cancelled = true }
  }, [authReady])

  const SCAN_STEP_LABELS = ['Scannen van job steps...', 'Development points aanmaken...', 'Scan afgerond']

  async function triggerScan() {
    setScanning(true)
    setScanMessage('')
    setScanOutcome(null)
    setScanResultText('')
    setScanStep(0)
    setError('')

    const stepInterval = setInterval(() => {
      setScanStep((prev) => Math.min(prev + 1, 2))
    }, 1200)

    try {
      const res = await apiFetch('/api/hr/scan', { method: 'POST' })
      clearInterval(stepInterval)
      setScanStep(2)

      const data = res.ok ? await res.json().catch(() => ({})) : {}
      const created = data.created ?? 0
      const incremented = data.incremented ?? 0
      const total = created + incremented

      setScanOutcome('success')
      setScanResultText(total > 0
        ? `${created} nieuwe development point${created !== 1 ? 's' : ''} gevonden${incremented > 0 ? `, ${incremented} bijgewerkt` : ''}`
        : 'Geen nieuwe patronen gevonden')
      await loadPoints()

      setTimeout(() => {
        setScanning(false)
        setScanOutcome(null)
        setScanResultText('')
        setScanMessage('')
      }, 3000)
    } catch {
      clearInterval(stepInterval)
      setScanStep(2)
      setScanOutcome('error')
      setScanResultText('Scan mislukt')
      setError('Scan mislukt')
      setTimeout(() => {
        setScanning(false)
        setScanOutcome(null)
        setScanResultText('')
      }, 3000)
    }
  }

  async function updatePointStatus(pointId, status) {
    try {
      await apiFetch(`/api/hr/development-points/${pointId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, approved_by: 'hr-dashboard' }),
      })
      await loadPoints()
    } catch {
      setError('Status update mislukt')
    }
  }

  const handleApprove = async (id, url) => {
    setApprovingId(id)
    try {
      const res = await apiFetch('/api/hr/approve-training', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          point_id: id,
          approved: true,
          source_url: url || undefined,
          approved_by: 'hr-dashboard'
        })
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`)
      setApproveModal(null)
      setApproveUrl('')
      if (tab === 'training') loadTrainingRequests()
      else loadPoints()
    } catch (err) {
      setError(err.message || 'Goedkeuren mislukt')
    } finally {
      setApprovingId(null)
    }
  }

  /** Development Points tab only: dismiss point via dedicated endpoint. */
  async function handleDismiss(pointId) {
    if (tab !== 'points') return
    try {
      const res = await apiFetch(`/api/hr/development-points/${pointId}/dismiss`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      })
      if (res?.status === 404) {
        setApproveModal(null)
        await loadPoints()
        return
      }
      setApproveModal(null)
      await loadPoints()
    } catch {
      setError('Afwijzen mislukt')
    }
  }

  async function approveTraining(id) {
    setApprovingId(id)
    const sourceUrl = trainingUrlInput[id] || approveUrl || ''
    const body = tab === 'training'
      ? { request_id: id, approved: true, source_url: sourceUrl || undefined, approved_by: 'hr-dashboard' }
      : { point_id: id, approved: true, source_url: sourceUrl || undefined, approved_by: 'hr-dashboard' }
    try {
      const res = await apiFetch('/api/hr/approve-training', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Request failed')
      setTrainingUrlInput((prev) => { const n = { ...prev }; delete n[id]; return n })
      setApproveModal(null)
      setApproveUrl('')
      if (tab === 'training') await loadTrainingRequests()
      else await loadPoints()
    } catch (err) {
      setError(err?.message || 'Goedkeuren mislukt')
    } finally {
      setApprovingId(null)
    }
  }

  /** Training Requests tab only: reject request via approve-training with approved: false. */
  async function dismissTrainingRequest(requestId) {
    if (tab !== 'training') return
    try {
      await apiFetch('/api/hr/approve-training', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: requestId, approved: false, approved_by: 'hr-dashboard' }),
      })
      await loadTrainingRequests()
    } catch {
      setError('Afwijzen mislukt')
    }
  }

  async function approveCrossTrain(proposalId) {
    const sourceUrl = crossUrlInput[proposalId] || null
    try {
      await apiFetch('/api/hr/cross-train', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal_id: proposalId, approved: true, source_url: sourceUrl || undefined }),
      })
      setCrossUrlInput((prev) => { const n = { ...prev }; delete n[proposalId]; return n })
      await loadCrossProposals()
    } catch {
      setError('Goedkeuren mislukt')
    }
  }

  async function resolvePoint(pointId, resolution) {
    try {
      const res = await apiFetch(`/api/hr/development-points/${pointId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolution: resolution || 'Opgelost via HR Dashboard' }),
      })
      setResolveInput((prev) => { const n = { ...prev }; delete n[pointId]; return n })
      if (res?.status === 404) {
        await loadPoints()
        return
      }
      await loadPoints()
    } catch {
      setError('Opgelost markeren mislukt')
    }
  }

  async function rejectCrossTrain(proposalId) {
    try {
      await apiFetch('/api/hr/cross-train', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal_id: proposalId, approved: false }),
      })
      await loadCrossProposals()
    } catch {
      setError('Afwijzen mislukt')
    }
  }

  if (!authReady) return null

  return (
    <PageLayout size="wide" padded>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">HR Dashboard</h1>
        <div className="flex flex-col items-end gap-2">
          <button
            type="button"
            onClick={triggerScan}
            disabled={scanning}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-white font-medium disabled:opacity-50 text-sm"
            style={{
              background: scanning ? 'var(--color-text-muted)' : 'var(--color-brand-primary)',
            }}
          >
            <RefreshCw className={`w-4 h-4 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? 'Scannen...' : 'Scan nu'}
          </button>
          {(scanning || scanOutcome) && (
            <div
              className="w-64 rounded-[var(--radius-sm)] overflow-hidden border text-sm"
              style={{
                borderColor: scanOutcome === 'error' ? 'var(--color-status-error)' : scanOutcome === 'success' ? 'var(--color-status-success)' : 'var(--color-border)',
              }}
            >
              <div
                className="h-2 w-full overflow-hidden"
                style={{ background: 'var(--color-bg-input)' }}
              >
                <div
                  className="h-full w-full"
                  style={{
                    background: scanOutcome === 'error'
                      ? 'var(--color-status-error)'
                      : scanOutcome === 'success'
                        ? 'var(--color-status-success)'
                        : 'repeating-linear-gradient(90deg, var(--color-brand-primary), var(--color-brand-primary) 8px, var(--color-brand-primary-light) 8px, var(--color-brand-primary-light) 16px)',
                    backgroundSize: scanOutcome ? '100% 100%' : '32px 100%',
                    animation: scanOutcome ? 'none' : 'hr-scan-progress 0.8s linear infinite',
                  }}
                />
              </div>
              <div
                className="px-2 py-1.5"
                style={{
                  background: scanOutcome === 'error' ? 'var(--color-status-error-bg)' : scanOutcome === 'success' ? 'var(--color-status-success-bg)' : 'var(--color-bg-subtle)',
                  color: scanOutcome === 'error' ? '#991B1B' : scanOutcome === 'success' ? '#065F46' : 'var(--color-text-secondary)',
                }}
              >
                {scanOutcome ? scanResultText : SCAN_STEP_LABELS[scanStep]}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-2 mb-6">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              tab === t.id ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">{error}</div>
      )}
      {scanMessage && (
        <div className="mb-4 p-4 rounded-lg bg-green-50 text-green-700 border border-green-200 text-sm">{scanMessage}</div>
      )}

      {/* Weekly Report */}
      <section className="mb-8 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-slate-900">Weekly Report</h2>
          <button
            type="button"
            onClick={loadReport}
            disabled={reportLoading}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${reportLoading ? 'animate-spin' : ''}`} />
            Refresh rapport
          </button>
        </div>
        {report && report.agents && Object.keys(report.agents).length > 0 ? (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(report.agents).map(([agentId, data]) => (
              <div key={agentId} className="rounded-lg border border-slate-200 p-3 text-sm">
                <strong className="text-slate-900">{data.agent_name ?? agentId ?? '—'}</strong>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs">
                    {data.open_points_count != null ? data.open_points_count : '—'} open
                  </span>
                  <span className="text-slate-600">
                    Retry: {data.performance?.retry_rate != null ? ((data.performance.retry_rate) * 100).toFixed(1) : '—'}%
                  </span>
                  <span className="text-slate-600">
                    Jobs (7d): {data.performance?.jobs_touched_7d != null ? data.performance.jobs_touched_7d : '—'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : report ? (
          <p className="text-slate-500 text-sm">Geen data beschikbaar.</p>
        ) : (
          <p className="text-slate-500 text-sm">Klik "Refresh rapport" om te laden.</p>
        )}
      </section>

      {approveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
          <div className="rounded-xl bg-white p-6 shadow-xl max-w-md mx-4">
            {approveUrl ? (
              <p className="text-slate-500 text-xs mb-1">Aanbevolen door HR scan</p>
            ) : null}
            <p className="text-slate-700 mb-2">Trainings-URL (optioneel):</p>
            <input
              type="url"
              value={approveUrl}
              onChange={(e) => setApproveUrl(e.target.value)}
              placeholder="https://..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm mb-4"
            />
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => handleApprove(approveModal, approveUrl)}
                disabled={approvingId === approveModal}
                className="rounded-lg px-4 py-2 bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
              >
                {approvingId === approveModal ? (
                  <>
                    <span className="inline-block w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Verwerken...
                  </>
                ) : (
                  'Goedkeuren'
                )}
              </button>
              <button
                type="button"
                onClick={() => setApproveModal(null)}
                disabled={approvingId === approveModal}
                className="rounded-lg px-4 py-2 border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
              >
                Annuleren
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tab 1: Development Points */}
      {tab === 'points' && (
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <select
              value={filterImpact}
              onChange={(e) => setFilterImpact(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Alle impact</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Alle statussen</option>
              <option value="OPEN">Open</option>
              <option value="AWAITING_APPROVAL">Wacht op goedkeuring</option>
              <option value="IN_TRAINING">In training</option>
              <option value="RESOLVED">Opgelost</option>
              <option value="DISMISSED">Afgewezen</option>
            </select>
          </div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : (() => {
            const filtered = points.filter((p) => {
              if (filterImpact && (p.impact || '').toLowerCase() !== filterImpact) return false
              if (filterStatus && (p.status || '').toUpperCase() !== filterStatus) return false
              return true
            })
            return filtered.length === 0 ? (
            <div className="p-8 rounded-xl border border-slate-200 bg-slate-50 text-center">
              <p className="text-slate-600">Geen development points gevonden.</p>
              <p className="text-slate-400 text-sm mt-1">Klik "Scan nu" om job_steps te analyseren.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Agent</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Issue</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Frequency</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Impact</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Status</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Acties</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {filtered.map((p) => {
                    const impactKey = (p.impact || 'medium').toLowerCase()
                    const statusKey = (p.status || 'OPEN').toUpperCase()
                    const pointId = p.point_id || p.id
                    const showTrainingInput = trainingUrlInput[pointId] !== undefined && statusKey === 'AWAITING_APPROVAL'
                    const showResolveInput = resolveInput[pointId] !== undefined && (statusKey === 'IN_TRAINING' || statusKey === 'AWAITING_APPROVAL')
                    const isExpanded = expandedPointId === pointId
                    return (
                      <React.Fragment key={pointId}>
                        <tr className="hover:bg-slate-50">
                          <td className="px-4 py-2">{p.agent_name || p.agent_id || p.agent_role || '—'}</td>
                          <td
                            className="px-4 py-2 max-w-xs cursor-pointer hover:bg-slate-100 rounded"
                            role="button"
                            tabIndex={0}
                            onClick={() => setExpandedPointId(isExpanded ? null : pointId)}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpandedPointId(isExpanded ? null : pointId) } }}
                          >
                            {p.issue_description || '—'}
                          </td>
                          <td className="px-4 py-2">{p.frequency ?? '—'}</td>
                          <td className="px-4 py-2">
                            <span style={{ color: IMPACT_COLOR[impactKey] || IMPACT_COLOR.medium, fontWeight: 600 }} className={`px-2 py-0.5 text-xs font-medium rounded ${IMPACT_BADGE[impactKey] || IMPACT_BADGE.medium}`}>
                              {(p.impact || impactKey)}
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            <span className={`px-2 py-0.5 text-xs font-medium rounded ${STATUS_BADGE[statusKey] || 'bg-gray-100 text-gray-500'}`}>
                              {statusKey}
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <Link
                                to={`/hr/issues/${pointId}`}
                                className="text-xs font-medium text-indigo-600 hover:underline"
                              >
                                Detail →
                              </Link>
                              {statusKey === 'OPEN' && (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => { setApproveModal(p.id ?? pointId); setApproveUrl(p.suggested_url || '') }}
                                    className="text-xs font-medium text-indigo-600 hover:underline"
                                  >
                                    Goedkeuren
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleDismiss(pointId)}
                                    className="text-xs font-medium text-red-600 hover:underline"
                                  >
                                    Afwijzen
                                  </button>
                                </>
                              )}
                              {statusKey === 'AWAITING_APPROVAL' && !showTrainingInput && !showResolveInput && (
                                <button
                                  type="button"
                                  onClick={() => setTrainingUrlInput((prev) => ({ ...prev, [pointId]: p.suggested_url || '' }))}
                                  className="text-xs font-medium text-purple-600 hover:underline"
                                >
                                  Start Training
                                </button>
                              )}
                              {showTrainingInput && (
                                <div className="flex items-center gap-1">
                                  <input
                                    type="url"
                                    placeholder="Source URL (optioneel)"
                                    className="border border-slate-300 rounded px-2 py-1 text-xs w-48"
                                    value={trainingUrlInput[pointId] || ''}
                                    onChange={(e) => setTrainingUrlInput((prev) => ({ ...prev, [pointId]: e.target.value }))}
                                  />
                                  <button
                                    type="button"
                                    onClick={() => approveTraining(pointId)}
                                    disabled={approvingId === pointId}
                                    className="text-xs font-medium text-green-600 hover:underline disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-1"
                                  >
                                    {approvingId === pointId ? (
                                      <>
                                        <span className="inline-block w-3 h-3 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
                                        Verwerken...
                                      </>
                                    ) : (
                                      'Bevestig'
                                    )}
                                  </button>
                                <button
                                  type="button"
                                  onClick={() => setTrainingUrlInput((prev) => { const n = { ...prev }; delete n[pointId]; return n })}
                                  className="text-xs font-medium text-slate-400 hover:underline"
                                >
                                  Annuleer
                                </button>
                              </div>
                            )}
                            {(statusKey === 'IN_TRAINING' || statusKey === 'AWAITING_APPROVAL') && !showResolveInput && !showTrainingInput && (
                                <button
                                  type="button"
                                  onClick={() => setResolveInput((prev) => ({ ...prev, [pointId]: '' }))}
                                  className="text-xs font-medium text-slate-600 hover:underline"
                                >
                                  Opgelost markeren
                                </button>
                              )}
                              {showResolveInput && (
                                <div className="flex items-center gap-1">
                                  <input
                                    type="text"
                                    placeholder="Oplossing (optioneel)"
                                    className="border border-slate-300 rounded px-2 py-1 text-xs w-48"
                                    value={resolveInput[pointId] ?? ''}
                                    onChange={(e) => setResolveInput((prev) => ({ ...prev, [pointId]: e.target.value }))}
                                  />
                                  <button
                                    type="button"
                                    onClick={() => resolvePoint(pointId, resolveInput[pointId])}
                                    className="text-xs font-medium text-green-600 hover:underline"
                                  >
                                    Bevestig
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setResolveInput((prev) => { const n = { ...prev }; delete n[pointId]; return n })}
                                    className="text-xs font-medium text-slate-400 hover:underline"
                                  >
                                    Annuleer
                                  </button>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr className="bg-slate-50">
                            <td colSpan={6} className="px-4 py-3 align-top">
                              <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm">
                                <p className="font-medium text-slate-700 mb-1">Issue</p>
                                <p className="text-slate-600 mb-3">{p.issue_description || '—'}</p>
                                <p className="font-medium text-slate-700 mb-1">Root cause</p>
                                <p className="text-slate-600 mb-3 whitespace-pre-wrap">{p.root_cause || 'Geen root cause beschikbaar'}</p>
                                <p className="font-medium text-slate-700 mb-1">Evidence</p>
                                <div className="text-slate-600 mb-3 rounded bg-slate-100 p-2 overflow-x-auto max-h-40 overflow-y-auto">
                                  {p.evidence_example == null ? (
                                    '—'
                                  ) : typeof p.evidence_example === 'string' ? (
                                    p.evidence_example
                                  ) : (
                                    <pre className="text-xs whitespace-pre-wrap m-0">{JSON.stringify(p.evidence_example, null, 2)}</pre>
                                  )}
                                </div>
                                <p className="text-slate-600 mb-2">
                                  Confidence: {p.confidence_score != null ? `${Math.round(Number(p.confidence_score) * 100)}%` : '—'}
                                  {' · '}
                                  Frequency: {p.frequency != null ? p.frequency : '—'}
                                  {' · '}
                                  Impact: {(p.impact || '—').toUpperCase()}
                                </p>
                                <p className="font-medium text-slate-700 mb-1">Aanbevolen trainings-URL</p>
                                <p className="text-slate-600 mb-3">
                                  {p.suggested_url ? (
                                    <a href={p.suggested_url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline break-all">
                                      {p.suggested_url}
                                    </a>
                                  ) : (
                                    'Geen URL beschikbaar'
                                  )}
                                </p>
                                <div className="flex justify-end">
                                  <button
                                    type="button"
                                    onClick={() => setExpandedPointId(null)}
                                    className="rounded-lg px-3 py-1.5 border border-slate-300 text-slate-700 text-xs font-medium hover:bg-slate-50"
                                  >
                                    Sluiten
                                  </button>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          );
          })()}
        </div>
      )}

      {/* Tab 2: Training Requests */}
      {tab === 'training' && (
        <div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : trainingRequests.length === 0 ? (
            <div className="p-8 rounded-xl border border-slate-200 bg-slate-50 text-center">
              <p className="text-slate-600">Geen training requests in de wachtrij.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Agent</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Reden</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Confidence</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Voorgestelde URL</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Acties</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {trainingRequests.map((r) => {
                    const id = r.request_id || r.point_id || r.id
                    const showInput = trainingUrlInput[id] !== undefined
                    return (
                      <tr key={id} className="hover:bg-slate-50">
                        <td className="px-4 py-2">{r.agent_name || r.agent_id || r.agent_role || '—'}</td>
                        <td className="px-4 py-2 max-w-xs">{r.issue_description || r.reason || '—'}</td>
                        <td className="px-4 py-2">
                          {r.confidence_score != null ? (
                            <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                              r.confidence_score >= 0.80 ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'
                            }`}>
                              {Number(r.confidence_score).toFixed(2)}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-4 py-2 text-xs text-slate-500 max-w-xs truncate">{r.suggested_url || '—'}</td>
                        <td className="px-4 py-2">
                          <div className="flex flex-wrap items-center gap-2">
                            {!showInput ? (
                              <>
                                <button
                                  type="button"
                                  onClick={() => setTrainingUrlInput((prev) => ({ ...prev, [id]: r.suggested_url || '' }))}
                                  className="text-xs font-medium text-green-600 hover:underline"
                                >
                                  Goedkeuren
                                </button>
                                <button
                                  type="button"
                                  onClick={() => dismissTrainingRequest(id)}
                                  className="text-xs font-medium text-red-600 hover:underline"
                                >
                                  Afwijzen
                                </button>
                              </>
                            ) : (
                              <div className="flex items-center gap-1">
                                <input
                                  type="url"
                                  placeholder="Source URL override"
                                  className="border border-slate-300 rounded px-2 py-1 text-xs w-48"
                                  value={trainingUrlInput[id] || ''}
                                  onChange={(e) => setTrainingUrlInput((prev) => ({ ...prev, [id]: e.target.value }))}
                                />
                                <button
                                  type="button"
                                  onClick={() => approveTraining(id)}
                                  className="text-xs font-medium text-green-600 hover:underline"
                                >
                                  Bevestig
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setTrainingUrlInput((prev) => { const n = { ...prev }; delete n[id]; return n })}
                                  className="text-xs font-medium text-slate-400 hover:underline"
                                >
                                  Annuleer
                                </button>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Cross-Training */}
      {tab === 'cross' && (
        <div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : crossProposals.length === 0 ? (
            <div className="p-8 rounded-xl border border-slate-200 bg-slate-50 text-center">
              <p className="text-slate-600">Geen cross-training voorstellen.</p>
              <p className="text-slate-400 text-sm mt-1">HR Manager detecteert automatisch nieuwe kansen.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Lesson</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Bron agent</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Doel agents</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Reden</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Acties</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {crossProposals.map((p) => {
                    const showInput = crossUrlInput[p.proposal_id] !== undefined
                    const targets = Array.isArray(p.target_agent_ids) ? p.target_agent_ids : []
                    return (
                      <tr key={p.proposal_id} className="hover:bg-slate-50">
                        <td className="px-4 py-2 max-w-xs">{p.lesson_id}</td>
                        <td className="px-4 py-2">{p.source_agent_id || '—'}</td>
                        <td className="px-4 py-2">
                          <div className="flex flex-wrap gap-1">
                            {targets.map((id) => (
                              <span key={id} className="px-2 py-0.5 text-xs font-medium rounded bg-slate-100 text-slate-700">
                                {id}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-4 py-2 max-w-xs text-slate-600">{p.reason || '—'}</td>
                        <td className="px-4 py-2">
                          {!showInput ? (
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                onClick={() => setCrossUrlInput((prev) => ({ ...prev, [p.proposal_id]: '' }))}
                                className="text-xs font-medium text-green-600 hover:underline"
                              >
                                Goedkeuren
                              </button>
                              <button
                                type="button"
                                onClick={() => rejectCrossTrain(p.proposal_id)}
                                className="text-xs font-medium text-red-600 hover:underline"
                              >
                                Afwijzen
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1">
                              <input
                                type="url"
                                placeholder="Source URL (optioneel)"
                                className="border border-slate-300 rounded px-2 py-1 text-xs w-48"
                                value={crossUrlInput[p.proposal_id] || ''}
                                onChange={(e) => setCrossUrlInput((prev) => ({ ...prev, [p.proposal_id]: e.target.value }))}
                              />
                              <button
                                type="button"
                                onClick={() => approveCrossTrain(p.proposal_id)}
                                className="text-xs font-medium text-green-600 hover:underline"
                              >
                                Bevestig
                              </button>
                              <button
                                type="button"
                                onClick={() => setCrossUrlInput((prev) => { const n = { ...prev }; delete n[p.proposal_id]; return n })}
                                className="text-xs font-medium text-slate-400 hover:underline"
                              >
                                Annuleer
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </PageLayout>
  )
}
