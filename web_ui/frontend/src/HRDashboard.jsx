import { useEffect, useState, useCallback } from 'react'
import { apiFetch } from './apiClient'
import PageLayout from './PageLayout'
import { RefreshCw } from 'lucide-react'
import { useAuthReady } from './useAuthReady'

const TABS = [
  { id: 'points', label: 'Development Points' },
  { id: 'training', label: 'Training Requests' },
]

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
  const [error, setError] = useState('')
  const [trainingUrlInput, setTrainingUrlInput] = useState({})

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

  useEffect(() => {
    if (!authReady) return
    if (tab === 'points') loadPoints()
    else if (tab === 'training') loadTrainingRequests()
  }, [authReady, tab, loadPoints, loadTrainingRequests])

  async function triggerScan() {
    setScanning(true)
    try {
      await apiFetch('/api/hr/scan', { method: 'POST' })
      await loadPoints()
    } catch {
      setError('Scan mislukt')
    }
    setScanning(false)
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

  async function approveTraining(pointId) {
    const sourceUrl = trainingUrlInput[pointId] || ''
    try {
      await apiFetch('/api/hr/approve-training', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ point_id: pointId, approved: true, source_url: sourceUrl || undefined }),
      })
      setTrainingUrlInput((prev) => { const n = { ...prev }; delete n[pointId]; return n })
      if (tab === 'training') await loadTrainingRequests()
      else await loadPoints()
    } catch {
      setError('Goedkeuren mislukt')
    }
  }

  async function dismissTrainingRequest(pointId) {
    try {
      await apiFetch(`/api/hr/development-points/${pointId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'DISMISSED', approved_by: 'hr-dashboard' }),
      })
      await loadTrainingRequests()
    } catch {
      setError('Afwijzen mislukt')
    }
  }

  if (!authReady) return null

  return (
    <PageLayout size="wide" padded>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">HR Dashboard</h1>
        <button
          type="button"
          onClick={triggerScan}
          disabled={scanning}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 text-sm"
        >
          <RefreshCw className={`w-4 h-4 ${scanning ? 'animate-spin' : ''}`} />
          {scanning ? 'Scannen...' : 'Scan nu'}
        </button>
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

      {/* Tab 1: Development Points */}
      {tab === 'points' && (
        <div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : points.length === 0 ? (
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
                  {points.map((p) => {
                    const impactKey = (p.impact || 'medium').toLowerCase()
                    const statusKey = (p.status || 'OPEN').toUpperCase()
                    const showTrainingInput = trainingUrlInput[p.point_id] !== undefined && statusKey === 'AWAITING_APPROVAL'
                    return (
                      <tr key={p.point_id || p.id} className="hover:bg-slate-50">
                        <td className="px-4 py-2">{p.agent_name || p.agent_id || p.agent_role || '—'}</td>
                        <td className="px-4 py-2 max-w-xs">{p.issue_description || '—'}</td>
                        <td className="px-4 py-2">{p.frequency ?? '—'}</td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${IMPACT_BADGE[impactKey] || IMPACT_BADGE.medium}`}>
                            {impactKey}
                          </span>
                        </td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${STATUS_BADGE[statusKey] || 'bg-gray-100 text-gray-500'}`}>
                            {statusKey}
                          </span>
                        </td>
                        <td className="px-4 py-2">
                          <div className="flex flex-wrap items-center gap-2">
                            {statusKey === 'OPEN' && (
                              <>
                                <button
                                  type="button"
                                  onClick={() => updatePointStatus(p.point_id, 'AWAITING_APPROVAL')}
                                  className="text-xs font-medium text-indigo-600 hover:underline"
                                >
                                  Goedkeuren
                                </button>
                                <button
                                  type="button"
                                  onClick={() => updatePointStatus(p.point_id, 'DISMISSED')}
                                  className="text-xs font-medium text-red-600 hover:underline"
                                >
                                  Afwijzen
                                </button>
                              </>
                            )}
                            {statusKey === 'AWAITING_APPROVAL' && !showTrainingInput && (
                              <button
                                type="button"
                                onClick={() => setTrainingUrlInput((prev) => ({ ...prev, [p.point_id]: p.suggested_url || '' }))}
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
                                  value={trainingUrlInput[p.point_id] || ''}
                                  onChange={(e) => setTrainingUrlInput((prev) => ({ ...prev, [p.point_id]: e.target.value }))}
                                />
                                <button
                                  type="button"
                                  onClick={() => approveTraining(p.point_id)}
                                  className="text-xs font-medium text-green-600 hover:underline"
                                >
                                  Bevestig
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setTrainingUrlInput((prev) => { const n = { ...prev }; delete n[p.point_id]; return n })}
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
                    const id = r.point_id || r.id
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
    </PageLayout>
  )
}
