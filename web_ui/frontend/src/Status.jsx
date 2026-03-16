import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { Activity, CheckCircle2, AlertTriangle, Bot, Settings as SettingsIcon, RefreshCw } from 'lucide-react'
import PageLayout from './PageLayout'
import { apiUrl, apiFetch } from './apiClient'
import { getCurrentUserRole, isSuperAdmin } from './authz'
import PipelineMetricsTab from './components/status/PipelineMetricsTab'
import StorageCostsTab from './components/status/StorageCostsTab'
import EdgeIntelligenceTab from './components/status/EdgeIntelligenceTab'

function StatusRow({ label, ok, detail }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-gray-100 last:border-b-0">
      <div>
        <div className="font-semibold text-gray-800">{label}</div>
        <div className="text-sm text-gray-500">{detail}</div>
      </div>
      <div className={`inline-flex items-center gap-1.5 text-sm font-semibold ${ok ? 'text-emerald-600' : 'text-amber-600'}`}>
        {ok ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
        <span>{ok ? 'OK' : 'Check'}</span>
      </div>
    </div>
  )
}

export default function Status() {
  const [daveInfo, setDaveInfo] = useState(null)
  const [settingsOk, setSettingsOk] = useState(null)
  const [settingsDetail, setSettingsDetail] = useState('Onbekend')
  const [healthOk, setHealthOk] = useState(null)
  const [healthDetail, setHealthDetail] = useState('Onbekend')
  const [dbOk, setDbOk] = useState(null)
  const [dbDetail, setDbDetail] = useState('Onbekend')
  const [healthLatencyMs, setHealthLatencyMs] = useState(null)
  const [daveLatencyMs, setDaveLatencyMs] = useState(null)
  const [settingsLatencyMs, setSettingsLatencyMs] = useState(null)
  const [recentCommits, setRecentCommits] = useState([])
  const [recentChanges, setRecentChanges] = useState([])
  const [lastUpdated, setLastUpdated] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [loading, setLoading] = useState(false)
  const [userRole, setUserRole] = useState('member')
  const [activeTab, setActiveTab] = useState('overview') // 'overview' | 'pipeline' | 'storage' | 'edge'

  const isSuper = useMemo(() => isSuperAdmin(userRole), [userRole])

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const summaryStart = performance.now()
      const summaryRes = await apiFetch('/api/status/summary')
      const summaryElapsed = Math.round(performance.now() - summaryStart)
      setHealthLatencyMs(summaryElapsed)

      if (summaryRes.ok) {
        const summary = await summaryRes.json()
        const healthData = summary?.health || {}
        setHealthOk(healthData?.status === 'ok')
        setHealthDetail(`Backend: ${healthData?.status || 'unknown'}`)
        setDbOk(Boolean(healthData?.checks?.database?.ok))
        setDbDetail(healthData?.checks?.database?.detail || 'Onbekend')

        setDaveInfo({
          status: summary?.dave_dev?.status || 'unknown',
          specialization: summary?.dave_dev?.specialization || 'Geen data ontvangen',
          id: summary?.dave_dev?.ok ? 'dave-dev' : null,
        })
        setDaveLatencyMs(summaryElapsed)

        const providers = Array.isArray(summary?.settings?.active_providers)
          ? summary.settings.active_providers
          : []
        setSettingsOk(Boolean(summary?.settings?.ok))
        setSettingsDetail(providers.length > 0 ? `Actief: ${providers.join(', ')}` : 'Geen LLM sleutel gevonden')
        setSettingsLatencyMs(summaryElapsed)

        setRecentCommits(Array.isArray(summary?.recent?.recent_commits) ? summary.recent.recent_commits : [])
        setRecentChanges(Array.isArray(summary?.recent?.working_tree_top) ? summary.recent.working_tree_top : [])
      } else {
        setLoadError('Status summary endpoint reageert niet.')
      }
      setLastUpdated(new Date())
    } catch (_err) {
      setLoadError('Status data laden is mislukt.')
      setHealthOk(false)
      setHealthDetail('Onbekend')
      setDbOk(false)
      setDbDetail('Onbekend')
      setDaveInfo(null)
      setSettingsOk(false)
      setSettingsDetail('Onbekend')
      setRecentCommits([])
      setRecentChanges([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // Haal huidige user role op voor tab-visibility (super_admin only voor intelligence tabs)
    getCurrentUserRole()
      .then((ctx) => setUserRole(ctx.role || 'member'))
      .catch(() => setUserRole('member'))

    load()
    const timer = setInterval(load, 30_000)
    return () => clearInterval(timer)
  }, [load])

  return (
    <PageLayout size="medium" padded className="space-y-6">
      <div className="panel-card">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Activity className="w-6 h-6 text-indigo-600" />
            <div>
              <h1 className="page-title">Status</h1>
              <p className="page-subtitle">Overzicht van systeemstatus, pipeline en intelligence.</p>
              {lastUpdated && (
                <p className="text-xs text-gray-400 mt-1">
                  Laatst bijgewerkt: {lastUpdated.toLocaleTimeString()}
                </p>
              )}
            </div>
          </div>
          <button
            onClick={load}
            className="btn-manage gap-2"
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
        <div className="mt-4 border-t border-slate-100 pt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setActiveTab('overview')}
            className={`px-3 py-1.5 text-sm rounded-full border ${
              activeTab === 'overview'
                ? 'bg-indigo-600 text-white border-indigo-600'
                : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
            }`}
          >
            Overzicht
          </button>
          {isSuper && (
            <>
              <button
                type="button"
                onClick={() => setActiveTab('pipeline')}
                className={`px-3 py-1.5 text-sm rounded-full border ${
                  activeTab === 'pipeline'
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                }`}
              >
                Pipeline Metrics
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('storage')}
                className={`px-3 py-1.5 text-sm rounded-full border ${
                  activeTab === 'storage'
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                }`}
              >
                Storage &amp; Costs
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('edge')}
                className={`px-3 py-1.5 text-sm rounded-full border ${
                  activeTab === 'edge'
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                }`}
              >
                Edge Intelligence
              </button>
            </>
          )}
        </div>
      </div>

      {activeTab === 'overview' && (
        <>
          <div className="panel-card">
            <div className="flex items-center gap-2 mb-3">
              <Bot className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-800">Agent Services</h2>
            </div>
            <StatusRow
              label="Backend Health Endpoint"
              ok={Boolean(healthOk)}
              detail={`${healthDetail}${healthLatencyMs !== null ? ` (${healthLatencyMs} ms)` : ''}`}
            />
            <StatusRow
              label="Database Check"
              ok={Boolean(dbOk)}
              detail={dbDetail}
            />
            <StatusRow
              label="Dave Dev Endpoint"
              ok={Boolean(daveInfo?.id)}
              detail={`${daveInfo?.specialization || 'Geen data ontvangen'}${daveLatencyMs !== null ? ` (${daveLatencyMs} ms)` : ''}`}
            />
            <StatusRow
              label="Dave Dev Status"
              ok={daveInfo?.status === 'active'}
              detail={`Status: ${daveInfo?.status || 'unknown'}`}
            />
          </div>

          <div className="panel-card">
            <div className="flex items-center gap-2 mb-3">
              <SettingsIcon className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-800">Configuratie</h2>
            </div>
            <StatusRow
              label="LLM sleutel in settings"
              ok={Boolean(settingsOk)}
              detail={`${settingsDetail}${settingsLatencyMs !== null ? ` (${settingsLatencyMs} ms)` : ''}`}
            />
          </div>

          <div className="panel-card">
            <div className="flex items-center gap-2 mb-3">
              <Activity className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-800">Recente Updates</h2>
            </div>
            <div className="space-y-4">
              <div>
                <div className="text-sm font-semibold text-gray-700 mb-1">Commits</div>
                {recentCommits.length === 0 ? (
                  <div className="text-sm text-gray-500">Geen commit data beschikbaar.</div>
                ) : (
                  <ul className="text-sm text-gray-600 space-y-1">
                    {recentCommits.map((item, idx) => (
                      <li key={`commit-${idx}`}>- {item}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-700 mb-1">Working tree</div>
                {recentChanges.length === 0 ? (
                  <div className="text-sm text-gray-500">Geen open wijzigingen.</div>
                ) : (
                  <ul className="text-sm text-gray-600 space-y-1">
                    {recentChanges.map((item, idx) => (
                      <li key={`change-${idx}`}>- {item}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === 'pipeline' && isSuper && <PipelineMetricsTab />}
      {activeTab === 'storage' && isSuper && <StorageCostsTab />}
      {activeTab === 'edge' && isSuper && <EdgeIntelligenceTab />}

      {loadError && (
        <div className="panel-card border-amber-200 bg-amber-50 text-amber-800">
          {loadError}
        </div>
      )}
    </PageLayout>
  )
}
