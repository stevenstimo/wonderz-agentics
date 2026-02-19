import { useState, useEffect } from 'react'
import PageLayout from './PageLayout'
import { AlertTriangle, CheckCircle, XCircle, BarChart3, RefreshCw, Filter } from 'lucide-react'

const IMPACT_COLORS = {
  HIGH: { bg: 'bg-red-50', border: 'border-red-200', badge: 'bg-red-100 text-red-800' },
  MEDIUM: { bg: 'bg-amber-50', border: 'border-amber-200', badge: 'bg-amber-100 text-amber-800' },
  LOW: { bg: 'bg-blue-50', border: 'border-blue-200', badge: 'bg-blue-100 text-blue-800' },
}

export default function HRDashboard() {
  const [points, setPoints] = useState([])
  const [report, setReport] = useState(null)
  const [filter, setFilter] = useState({ impact: '', agent: '' })
  const [scanning, setScanning] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAll()
  }, [filter])

  async function loadAll() {
    setLoading(true)
    await Promise.all([loadPoints(), loadReport()])
    setLoading(false)
  }

  async function loadPoints() {
    try {
      const params = new URLSearchParams({ status: 'OPEN' })
      if (filter.impact) params.append('impact', filter.impact)
      if (filter.agent) params.append('agent_role', filter.agent)
      const res = await fetch(`/api/hr/development-points?${params}`)
      const data = await res.json()
      setPoints(data.development_points || [])
    } catch (e) {
      console.error('Failed to load points:', e)
    }
  }

  async function loadReport() {
    try {
      const res = await fetch('/api/hr/report')
      setReport(await res.json())
    } catch (e) {
      console.error('Failed to load report:', e)
    }
  }

  async function triggerScan() {
    setScanning(true)
    try {
      await fetch('/api/hr/scan', { method: 'POST' })
      await loadAll()
    } catch (e) {
      console.error('Scan failed:', e)
    }
    setScanning(false)
  }

  async function resolvePoint(pointId) {
    const resolution = prompt('Hoe is dit opgelost?')
    if (!resolution) return
    try {
      await fetch(`/api/hr/development-points/${pointId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolution })
      })
      await loadPoints()
    } catch (e) {
      console.error('Resolve failed:', e)
    }
  }

  async function dismissPoint(pointId) {
    if (!confirm('Weet je zeker dat je dit punt wilt afwijzen?')) return
    try {
      await fetch(`/api/hr/development-points/${pointId}/dismiss`, { method: 'POST' })
      await loadPoints()
    } catch (e) {
      console.error('Dismiss failed:', e)
    }
  }

  const agentRoles = report ? Object.keys(report) : []

  return (
    <PageLayout title="HR Manager Dashboard">
      <div className="max-w-5xl mx-auto">
        {/* Header actions */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">HR Manager</h1>
            <p className="text-gray-500 text-sm mt-1">Agent performance monitoring & development points</p>
          </div>
          <button
            onClick={triggerScan}
            disabled={scanning}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm font-medium"
          >
            <RefreshCw className={`w-4 h-4 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? 'Scanning...' : 'Run Scan'}
          </button>
        </div>

        {/* Performance Overview */}
        {report && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-indigo-500" />
              Performance Overview (7 dagen)
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(report).map(([role, data]) => (
                <div key={role} className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-gray-900 capitalize">{role.replace('_', ' ')}</h3>
                    {data.open_points.length > 0 && (
                      <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                        {data.open_points.length} issue{data.open_points.length !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-gray-500">Total steps</div>
                      <div className="font-semibold text-gray-900">{data.total_steps}</div>
                    </div>
                    <div>
                      <div className="text-gray-500">Failed</div>
                      <div className={`font-semibold ${data.failed_steps > 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {data.failed_steps}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-500">Success rate</div>
                      <div className={`font-semibold ${data.success_rate >= 0.9 ? 'text-green-600' : data.success_rate >= 0.7 ? 'text-amber-600' : 'text-red-600'}`}>
                        {(data.success_rate * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-500">Retry rate</div>
                      <div className={`font-semibold ${data.retry_rate > 1 ? 'text-amber-600' : 'text-gray-900'}`}>
                        {data.retry_rate.toFixed(1)}x
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-3 mb-4">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={filter.impact}
            onChange={e => setFilter({ ...filter, impact: e.target.value })}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white"
          >
            <option value="">Alle impacts</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
          <select
            value={filter.agent}
            onChange={e => setFilter({ ...filter, agent: e.target.value })}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white"
          >
            <option value="">Alle agents</option>
            {agentRoles.map(role => (
              <option key={role} value={role}>{role}</option>
            ))}
          </select>
        </div>

        {/* Development Points */}
        <div>
          <h2 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            Open Development Points
          </h2>

          {loading ? (
            <div className="text-center py-8 text-gray-400">Laden...</div>
          ) : points.length === 0 ? (
            <div className="text-center py-12 bg-green-50 rounded-xl border border-green-200">
              <CheckCircle className="w-8 h-8 text-green-500 mx-auto mb-2" />
              <p className="text-green-700 font-medium">Geen open development points</p>
              <p className="text-green-600 text-sm">Alle agents presteren naar verwachting \uD83C\uDF89</p>
            </div>
          ) : (
            <div className="space-y-3">
              {points.map(point => {
                const colors = IMPACT_COLORS[point.impact] || IMPACT_COLORS.LOW
                return (
                  <div key={point.point_id} className={`rounded-xl border p-4 ${colors.bg} ${colors.border}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${colors.badge}`}>
                            {point.impact}
                          </span>
                          <span className="text-xs font-mono text-gray-500">{point.point_id}</span>
                          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">
                            {point.agent_role?.replace('_', ' ')}
                          </span>
                          <span className="text-xs text-gray-500">×{point.frequency}</span>
                        </div>
                        <p className="text-sm text-gray-800">{point.issue_description}</p>
                        {point.created_at && (
                          <p className="text-xs text-gray-400 mt-1">
                            Aangemaakt: {new Date(point.created_at).toLocaleDateString('nl-NL')}
                          </p>
                        )}
                      </div>
                      <div className="flex gap-2 flex-shrink-0">
                        <button
                          onClick={() => resolvePoint(point.point_id)}
                          className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700"
                        >
                          <CheckCircle className="w-3.5 h-3.5" /> Opgelost
                        </button>
                        <button
                          onClick={() => dismissPoint(point.point_id)}
                          className="flex items-center gap-1 px-3 py-1.5 bg-gray-200 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-300"
                        >
                          <XCircle className="w-3.5 h-3.5" /> Afwijzen
                        </button>
                      </div>
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
