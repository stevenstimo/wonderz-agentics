import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Search, Plus, AlertTriangle } from 'lucide-react'

import { apiFetch } from './apiClient'
import { useAuthReady } from './useAuthReady'

const TARGET_AGENTS_PLACEHOLDER = [
  { value: 'agent:seo-specialist', label: 'agent:seo-specialist' },
  { value: 'agent:copywriter', label: 'agent:copywriter' },
  { value: 'agent:gtm-strategist', label: 'agent:gtm-strategist' },
  { value: 'agent:sales-enablement', label: 'agent:sales-enablement' },
]

const SCOPES = ['all', 'agency_wide', 'client_specific', 'per_job']
const STATUSES = ['all', 'draft', 'approved', 'stale']

const SCOPE_BADGE = {
  agency_wide: 'wz-badge-running',
  client_specific: 'wz-badge-warning',
  per_job: 'wz-tag',
}

const STATUS_BADGE = {
  draft: 'wz-tag',
  approved: 'wz-badge-success',
  stale: 'wz-badge-warning',
}

function formatRelative(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now - d
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins} min ago`
  if (diffHours < 24) return `${diffHours} hours ago`
  if (diffDays < 7) return `${diffDays} days ago`
  return d.toLocaleDateString()
}

export default function SkillFactory() {
  const authReady = useAuthReady()
  const navigate = useNavigate()
  const location = useLocation()
  const [skills, setSkills] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [targetAgent, setTargetAgent] = useState('all')
  const [scope, setScope] = useState('all')
  const [status, setStatus] = useState('approved')
  const [targetAgentOptions, setTargetAgentOptions] = useState(TARGET_AGENTS_PLACEHOLDER)

  const fetchAgents = useCallback(async () => {
    try {
      const res = await apiFetch('/api/agents')
      if (res.ok) {
        const data = await res.json()
        const agents = data?.agents || []
        if (agents.length > 0) {
          const opts = agents.map((a) => ({
            value: a.agent_id || a.role || a.name,
            label: a.agent_id || a.role || a.name,
          }))
          setTargetAgentOptions((prev) => {
            const seen = new Set(prev.map((p) => p.value))
            const newOpts = opts.filter((o) => !seen.has(o.value))
            return newOpts.length ? [...prev, ...newOpts] : prev
          })
        }
      }
    } catch {
      // Keep placeholder options
    }
  }, [])

  const fetchSkills = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      params.set('doc_type', 'skill_spec')
      if (search.trim()) params.set('search', search.trim())
      if (targetAgent !== 'all') params.set('function_tag', targetAgent.replace(/^agent:/, ''))
      if (scope !== 'all') params.set('scope', scope)
      if (status !== 'all') params.set('status', status)
      params.set('limit', '50')
      const res = await apiFetch(`/api/knowledge?${params}`)
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setSkills(data)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      console.error('Failed to load skills:', err)
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [search, targetAgent, scope, status, navigate, location])

  useEffect(() => {
    if (!authReady) return
    fetchAgents()
  }, [authReady, fetchAgents])

  useEffect(() => {
    if (!authReady) return
    fetchSkills()
  }, [authReady, fetchSkills])

  return (
    <PageLayout size="wide" padded>
      <div className="flex gap-6">
        {/* Filters sidebar */}
        <aside className="w-56 flex-shrink-0 space-y-4">
          <h2 className="wz-label block mb-2">
            Filters
          </h2>
          <div>
            <label className="wz-label block mb-1">Zoeken</label>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onBlur={fetchSkills}
                onKeyDown={(e) => e.key === 'Enter' && fetchSkills()}
                placeholder="title, summary"
                className="wz-input w-full pl-9"
              />
            </div>
          </div>
          <div>
            <label className="wz-label block mb-1">Target agent</label>
            <select
              value={targetAgent}
              onChange={(e) => setTargetAgent(e.target.value)}
              className="wz-input w-full"
            >
              <option value="all">All</option>
              {targetAgentOptions.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="wz-label block mb-1">Scope</label>
            <div className="flex flex-wrap gap-1">
              {SCOPES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setScope(s)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-full transition-colors ${
                    scope === s
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {s === 'all' ? 'All' : s.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="wz-label block mb-1">Status</label>
            <div className="flex flex-wrap gap-1">
              {STATUSES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStatus(s)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-full transition-colors ${
                    status === s
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {s === 'all' ? 'All' : s}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* Skill list */}
        <main className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-bold text-slate-900">Skill Factory</h1>
            <Link
              to="/knowledge/upload?doc_type=skill_spec"
              className="wz-btn-primary inline-flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Nieuwe Skill Spec
            </Link>
          </div>

          {error && (
            <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
              {error}
            </div>
          )}

          {loading ? (
            <div className="wz-card p-8">
              Skills laden...
            </div>
          ) : skills.length === 0 ? (
            <div className="wz-card p-12 text-center text-slate-500">
              Geen skill specs gevonden. Upload een document om te beginnen.
            </div>
          ) : (
            <div className="grid gap-4">
              {skills.map((doc) => (
                <Link
                  key={doc.document_id}
                  to={`/knowledge/${doc.document_id}`}
                  className="wz-card block p-4 wz-lift relative"
                >
                  {doc.status === 'stale' && (
                    <div className="absolute top-0 left-0 right-0 rounded-t-xl bg-orange-50 border-b border-orange-200 px-4 py-2 flex items-center gap-2 text-orange-800 text-sm">
                      <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                      Brondocument gewijzigd — herziening vereist
                    </div>
                  )}
                  <div className={doc.status === 'stale' ? 'pt-12' : ''}>
                    <h3 className="font-semibold text-slate-900 truncate">{doc.title || 'Untitled'}</h3>
                    {doc.function_tag && (
                      <p className="wz-mono text-xs mt-0.5">agent:{doc.function_tag}</p>
                    )}
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      <span className="px-2 py-0.5 text-xs font-medium rounded bg-pink-100 text-pink-700">
                        skill_spec
                      </span>
                      <span className={`px-2 py-0.5 text-xs font-medium rounded ${SCOPE_BADGE[doc.scope] || 'wz-tag'}`}>
                        {doc.scope || 'agency_wide'}
                      </span>
                      <span className={`px-2 py-0.5 text-xs font-medium rounded ${STATUS_BADGE[doc.status] || 'wz-tag'}`}>
                        {doc.status}
                      </span>
                    </div>
                    {doc.summary && (
                      <p className="mt-2 text-sm text-slate-600 line-clamp-2">{doc.summary}</p>
                    )}
                    <p className="mt-2 text-xs text-slate-400">
                      {formatRelative(doc.updated_at)}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </main>
      </div>
    </PageLayout>
  )
}
