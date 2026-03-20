import { useState, useEffect, useCallback, useMemo } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Search, Plus } from 'lucide-react'

import { apiFetch } from './apiClient'
import { useAuthReady } from './useAuthReady'

const STATUSES = ['all', 'active', 'draft', 'inactive']

const STATUS_BADGE = {
  active: 'wz-badge-success',
  draft: 'wz-badge-warning',
  inactive: 'wz-tag',
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
  const { authReady } = useAuthReady()
  const navigate = useNavigate()
  const location = useLocation()
  const [skills, setSkills] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [expandedSkillId, setExpandedSkillId] = useState(null)

  const fetchSkills = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/skill-factory')
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setSkills(data?.skills || [])
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
  }, [navigate, location])

  useEffect(() => {
    if (!authReady) return
    fetchSkills()
  }, [authReady, fetchSkills])

  const filteredSkills = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (skills || []).filter((s) => {
      if (status !== 'all' && (s?.status || '').toLowerCase() !== status) return false
      if (!q) return true
      const haystack = [
        s?.display_name,
        s?.name,
        s?.skill_id,
        s?.description,
        s?.trigger_condition,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return haystack.includes(q)
    })
  }, [skills, search, status])

  function truncate(text, maxLen) {
    const t = (text || '').toString().trim()
    if (!t) return ''
    if (t.length <= maxLen) return t
    return t.slice(0, maxLen - 1) + '…'
  }

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
                placeholder="name, trigger, description"
                className="wz-input w-full pl-9"
              />
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
              to="/knowledge/skills/new"
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
          ) : filteredSkills.length === 0 ? (
            <div className="wz-card p-12 text-center text-slate-500">
              Geen skills geregistreerd. Maak je eerste skill aan.
            </div>
          ) : (
            <div className="grid gap-4">
              {filteredSkills.map((s) => {
                const sid = s?.skill_id || s?.name
                const expanded = expandedSkillId === sid
                const linkedCount = Number(s?.linked_agents_count ?? 0) || 0
                const triggerText = s?.trigger_condition || s?.description || ''

                return (
                  <button
                    key={sid}
                    type="button"
                    className="wz-card block p-4 wz-lift relative text-left"
                    aria-expanded={expanded}
                    onClick={() => setExpandedSkillId((prev) => (prev === sid ? null : sid))}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <h3 className="font-semibold text-slate-900 truncate">
                          {s?.display_name || s?.name || 'Untitled'}
                        </h3>
                        {sid && (
                          <p className="wz-mono text-xs mt-0.5">
                            {sid}
                          </p>
                        )}
                      </div>
                      <span className={`px-2 py-0.5 text-xs font-medium rounded ${STATUS_BADGE[s?.status] || 'wz-tag'}`}>
                        {s?.status || 'active'}
                      </span>
                    </div>

                    <div className="mt-2 flex items-start justify-between gap-3">
                      <p className="mt-0 text-sm text-slate-600 line-clamp-2">
                        {truncate(triggerText, 140)}
                      </p>
                      <p className="text-xs text-slate-500 whitespace-nowrap">
                        Agents: {linkedCount}
                      </p>
                    </div>

                    <p className="mt-2 text-xs text-slate-400">
                      {formatRelative(s?.updated_at)}
                    </p>

                    {expanded && (
                      <div className="mt-3 pt-3 border-t border-slate-200 space-y-2">
                        {s?.description && (
                          <div>
                            <div className="text-xs font-semibold text-slate-600">Description</div>
                            <div className="text-sm text-slate-800 whitespace-pre-wrap">{s.description}</div>
                          </div>
                        )}

                        {s?.trigger_condition && (
                          <div>
                            <div className="text-xs font-semibold text-slate-600">Trigger condition</div>
                            <div className="text-sm text-slate-800 whitespace-pre-wrap">{s.trigger_condition}</div>
                          </div>
                        )}

                        <div>
                          <div className="text-xs font-semibold text-slate-600">Requires tools</div>
                          <div className="flex flex-wrap gap-1.5 mt-1">
                            {(s?.requires_tools || []).length ? (
                              (s.requires_tools || []).map((t) => (
                                <span key={t} className="px-2 py-0.5 text-xs font-medium rounded bg-slate-100 text-slate-700">
                                  {t}
                                </span>
                              ))
                            ) : (
                              <span className="text-sm text-slate-500">None</span>
                            )}
                          </div>
                        </div>

                        <div>
                          <div className="text-xs font-semibold text-slate-600">Requires skills</div>
                          <div className="flex flex-wrap gap-1.5 mt-1">
                            {(s?.requires_skills || []).length ? (
                              (s.requires_skills || []).map((t) => (
                                <span key={t} className="px-2 py-0.5 text-xs font-medium rounded bg-slate-100 text-slate-700">
                                  {t}
                                </span>
                              ))
                            ) : (
                              <span className="text-sm text-slate-500">None</span>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </button>
                )
              ))}
            </div>
          )}
        </main>
      </div>
    </PageLayout>
  )
}
