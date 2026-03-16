import React, { useEffect, useState } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { apiFetch } from '../../apiClient'

function formatDuration(seconds) {
  if (!seconds || Number.isNaN(seconds)) return '—'
  const s = Math.max(0, Math.round(seconds))
  const m = Math.floor(s / 60)
  const rem = s % 60
  if (m === 0) return `${rem}s`
  return `${m}m ${rem}s`
}

function kpiColorFromSuccessRate(rate) {
  if (rate >= 90) return 'text-emerald-600'
  if (rate >= 70) return 'text-amber-500'
  return 'text-rose-500'
}

function phaseColor(ms) {
  if (ms < 10_000) return '#16a34a' // <10s
  if (ms < 30_000) return '#eab308' // 10–30s
  return '#ef4444' // >30s
}

export default function PipelineMetricsTab() {
  const [metrics, setMetrics] = useState(null)
  const [days, setDays] = useState(7)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    const fetchMetrics = async () => {
      setLoading(true)
      setError('')
      try {
        const res = await apiFetch(`/api/status/pipeline-metrics?days=${days}`)
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || `Kon pipeline-metrics niet laden (${res.status})`)
        }
        const data = await res.json()
        if (active) setMetrics(data)
      } catch (err) {
        if (active) {
          setError(err.message || 'Pipeline metrics laden mislukt')
          setMetrics(null)
        }
      } finally {
        if (active) setLoading(false)
      }
    }
    fetchMetrics()
    return () => {
      active = false
    }
  }, [days])

  const summary = metrics?.summary || {}
  const nexusPhases = Array.isArray(metrics?.nexus_phases) ? metrics.nexus_phases : []
  const agentPerformance = Array.isArray(metrics?.agent_performance) ? metrics.agent_performance : []
  const dailyTrend = Array.isArray(metrics?.daily_trend) ? metrics.daily_trend : []
  const errors = Array.isArray(metrics?.errors) ? metrics.errors : []
  const recentJobs = Array.isArray(metrics?.recent_jobs) ? metrics.recent_jobs : []

  const bottleneckCount = agentPerformance.filter((a) => a.is_bottleneck).length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-900">Pipeline Metrics</h2>
        <div className="inline-flex items-center gap-1 text-xs text-slate-500">
          Periode:
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDays(d)}
              className={`ml-1 px-2 py-0.5 rounded-full border text-[11px] ${
                days === d
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
              }`}
            >
              {d}d
            </button>
          ))}
          {loading && <Loader2 className="w-3 h-3 ml-1 animate-spin text-slate-400" />}
        </div>
      </div>

      {error && (
        <div className="panel-card border-amber-200 bg-amber-50 text-amber-800 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {/* Blok 1: KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="panel-card">
          <div className="text-xs font-medium text-slate-500 mb-1">Total Jobs ({days}d)</div>
          <div className="text-2xl font-semibold text-slate-900">
            {summary.total_jobs != null ? summary.total_jobs : '—'}
          </div>
        </div>
        <div className="panel-card">
          <div className="text-xs font-medium text-slate-500 mb-1">Success Rate</div>
          <div className={`text-2xl font-semibold ${kpiColorFromSuccessRate(summary.success_rate || 0)}`}>
            {summary.success_rate != null ? `${summary.success_rate.toFixed(1)}%` : '—'}
          </div>
        </div>
        <div className="panel-card">
          <div className="text-xs font-medium text-slate-500 mb-1">Avg Duration</div>
          <div className="text-2xl font-semibold text-slate-900">
            {formatDuration(summary.avg_duration_seconds)}
          </div>
        </div>
        <div className="panel-card">
          <div className="text-xs font-medium text-slate-500 mb-1">Bottlenecks (agents &gt; 60s)</div>
          <div className={`text-2xl font-semibold ${bottleneckCount > 0 ? 'text-rose-500' : 'text-emerald-600'}`}>
            {bottleneckCount}
          </div>
        </div>
      </div>

      {/* Blok 2: Dagelijkse trend */}
      <div className="panel-card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-800">Dagelijkse trend</h3>
        </div>
        {dailyTrend.length === 0 ? (
          <p className="text-sm text-slate-500">Nog geen jobs in deze periode.</p>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={dailyTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="completed" stackId="1" stroke="#16a34a" fill="#bbf7d0" name="Completed" />
                <Area type="monotone" dataKey="failed" stackId="1" stroke="#ef4444" fill="#fecaca" name="Failed" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Blok 3: NEXUS Fase Timings */}
      <div className="panel-card">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">NEXUS Fase Timings</h3>
        {nexusPhases.length === 0 ? (
          <p className="text-sm text-slate-500">Nog geen fase-data beschikbaar.</p>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={nexusPhases} layout="vertical" margin={{ left: 80 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tickFormatter={(v) => `${Math.round(v / 1000)}s`} />
                <YAxis dataKey="phase" type="category" />
                <Tooltip
                  formatter={(value, key) => {
                    if (key === 'avg_timing_ms') return [`${Math.round(value / 1000)}s`, 'Avg']
                    if (key === 'p95_timing_ms') return [`${Math.round(value / 1000)}s`, 'p95']
                    return [value, key]
                  }}
                />
                <Bar
                  dataKey="avg_timing_ms"
                  name="Avg timing"
                  fill="#6366f1"
                  label={false}
                  radius={[0, 4, 4, 0]}
                >
                  {nexusPhases.map((entry, index) => (
                    <cell // eslint-disable-line react/no-array-index-key
                      key={`cell-${index}`}
                      fill={phaseColor(entry.avg_timing_ms || 0)}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Blok 4: Agent Performance tabel */}
      <div className="panel-card">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">Agent Performance</h3>
        {agentPerformance.length === 0 ? (
          <p className="text-sm text-slate-500">Nog geen agent executies in deze periode.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-100">
                  <th className="py-2 pr-4">Agent</th>
                  <th className="py-2 pr-4">Avg Time</th>
                  <th className="py-2 pr-4">Executions</th>
                  <th className="py-2 pr-4">Failure Rate</th>
                  <th className="py-2 pr-4">Bottleneck</th>
                </tr>
              </thead>
              <tbody>
                {agentPerformance.map((a) => (
                  <tr
                    key={a.agent_id}
                    className={`border-b last:border-b-0 ${
                      a.is_bottleneck ? 'bg-rose-50/60' : 'hover:bg-slate-50'
                    }`}
                  >
                    <td className="py-2 pr-4 font-medium text-slate-800">{a.agent_id || '—'}</td>
                    <td className="py-2 pr-4 text-slate-700">
                      {a.avg_timing_ms != null ? `${Math.round(a.avg_timing_ms / 1000)}s` : '—'}
                    </td>
                    <td className="py-2 pr-4 text-slate-700">{a.total_executions}</td>
                    <td className="py-2 pr-4 text-slate-700">
                      {a.failure_rate != null ? `${a.failure_rate.toFixed(1)}%` : '—'}
                    </td>
                    <td className="py-2 pr-4">
                      {a.is_bottleneck && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-700">
                          Bottleneck
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Blok 5: Errors */}
      <div className="panel-card">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">Errors</h3>
        {errors.length === 0 ? (
          <p className="text-sm text-slate-500">Geen error-events in deze periode.</p>
        ) : (
          <div className="divide-y divide-slate-100">
            {errors.map((e, idx) => (
              <details key={`${e.event_type}-${e.agent_id}-${idx}`} className="py-2 group">
                <summary className="flex items-center justify-between cursor-pointer">
                  <div>
                    <div className="text-sm font-medium text-slate-800">
                      {e.event_type}{' '}
                      {e.agent_id && (
                        <span className="text-xs text-slate-500 font-normal">({e.agent_id})</span>
                      )}
                    </div>
                    <div className="text-xs text-slate-500">
                      {e.count}x · laatste: {e.last_seen || 'onbekend'}
                    </div>
                  </div>
                  <span className="text-xs text-slate-400 group-open:rotate-180 transition-transform">▼</span>
                </summary>
              </details>
            ))}
          </div>
        )}
      </div>

      {/* Blok 6: Recent Jobs tabel */}
      <div className="panel-card">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">Recent Jobs</h3>
        {recentJobs.length === 0 ? (
          <p className="text-sm text-slate-500">Nog geen jobs beschikbaar.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-100">
                  <th className="py-2 pr-4">Title</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Duration</th>
                  <th className="py-2 pr-4">Client</th>
                  <th className="py-2 pr-4">Datum</th>
                </tr>
              </thead>
              <tbody>
                {recentJobs.map((j) => (
                  <tr key={j.id} className="border-b last:border-b-0 hover:bg-slate-50">
                    <td className="py-2 pr-4 text-slate-800 max-w-xs truncate" title={j.title}>
                      {j.title || '—'}
                    </td>
                    <td className="py-2 pr-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                        {j.status || '—'}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-slate-700">
                      {j.duration_seconds != null ? formatDuration(j.duration_seconds) : '—'}
                    </td>
                    <td className="py-2 pr-4 text-slate-700">{j.company_id || '—'}</td>
                    <td className="py-2 pr-4 text-slate-700">
                      {j.created_at ? new Date(j.created_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

