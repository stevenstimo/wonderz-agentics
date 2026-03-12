import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from './PageLayout'
import { apiUrl, apiFetch } from './apiClient'
import { useAuthReady } from './useAuthReady'

const STATUS_BADGE = {
  INTAKE_CLARIFICATION: 'bg-amber-100 text-amber-800',
  PLAN_PROPOSED: 'bg-purple-100 text-purple-800',
  RUNNING: 'bg-blue-100 text-blue-800',
  JOB_READY: 'bg-emerald-100 text-emerald-800',
  AWAITING_APPROVAL: 'bg-slate-100 text-slate-800',
  COMPLETED: 'bg-emerald-100 text-emerald-800',
  FAILED: 'bg-red-100 text-red-800',
  CANCELLED: 'bg-slate-100 text-slate-600',
}

const STATUS_LABEL = {
  INTAKE_CLARIFICATION: 'Intake',
  PLAN_PROPOSED: 'Planning',
  RUNNING: 'Running',
  JOB_READY: 'Ready',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
  AWAITING_APPROVAL: 'Awaiting approval',
}

function StatusBadge({ status }) {
  const cls = STATUS_BADGE[status] || 'bg-slate-100 text-slate-700'
  const label = STATUS_LABEL[status] ?? status
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}

function relativeTime(dateStr) {
  const d = new Date(dateStr)
  const now = new Date()
  const s = Math.floor((now - d) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  const days = Math.floor(s / 86400)
  if (days === 1) return 'yesterday'
  if (s < 604800) return `${days} d ago`
  return d.toLocaleDateString()
}

function parseJobContext(ctx) {
  if (!ctx) return {}
  if (typeof ctx === 'object') return ctx
  try {
    const parsed = JSON.parse(ctx)
    if (typeof parsed === 'string') return JSON.parse(parsed)
    return parsed
  } catch { return {} }
}

function getJobNumber(job) {
  const ctx = parseJobContext(job?.context)
  return ctx?.job_number ?? '—'
}

const AGENT_INITIALS = {
  copywriter: 'CW',
  reviewer: 'RV',
  image_generator: 'IG',
  image_generation: 'IG',
  seo: 'SEO',
  seo_specialist: 'SEO',
}

function getAgentInitials(role) {
  if (!role) return '—'
  const r = String(role).toLowerCase().replace(/\s+/g, '_')
  return AGENT_INITIALS[r] || (role.length >= 2 ? role.slice(0, 2).toUpperCase() : role[0].toUpperCase())
}

function getAssignedAgents(job) {
  const ctx = parseJobContext(job?.context)
  const steps = ctx?.plan?.steps
  if (!Array.isArray(steps) || steps.length === 0) return []
  const roles = [...new Set(steps.map((s) => s.agent_role).filter(Boolean))]
  return roles.map((role) => ({ role, initials: getAgentInitials(role) }))
}

const COLORS = ['bg-indigo-500', 'bg-emerald-500', 'bg-amber-500', 'bg-slate-600', 'bg-purple-500']

const IN_PROGRESS_STATUSES = ['INTAKE_CLARIFICATION', 'PLAN_PROPOSED', 'RUNNING', 'JOB_READY', 'AWAITING_APPROVAL']
const COMPLETED_STATUSES = ['COMPLETED']
const FAILED_STATUSES = ['FAILED', 'CANCELLED']

export default function JobCenter() {
  const navigate = useNavigate()
  const authReady = useAuthReady()
  const [jobs, setJobs] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [crew, setCrew] = useState([])
  const [sections, setSections] = useState([])
  const [meta, setMeta] = useState(null)
  const [crewLoading, setCrewLoading] = useState(true)
  const [crewError, setCrewError] = useState(null)

  const fetchJobs = useCallback(async () => {
    try {
      const res = await apiFetch('/api/jobs')
      if (!res.ok) throw new Error('Failed to load jobs')
      const data = await res.json()
      setJobs(Array.isArray(data) ? data : [])
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!authReady) return
    fetchJobs()
    const interval = setInterval(fetchJobs, 10000)
    return () => clearInterval(interval)
  }, [authReady, fetchJobs])

  useEffect(() => {
    if (!authReady) return
    let active = true
    const fetchCrew = async () => {
      setCrewLoading(true)
      setCrewError(null)
      try {
        const [crewRes, explainerRes] = await Promise.all([
          apiFetch('/api/crew'),
          apiFetch('/api/explainer/sections'),
        ])
        if (!crewRes.ok) throw new Error('Failed to load crew status')
        if (!explainerRes.ok) throw new Error('Failed to load updates')
        const crewData = await crewRes.json()
        const explainerData = await explainerRes.json()
        if (!active) return
        setCrew(Array.isArray(crewData) ? crewData : [])
        setSections(Array.isArray(explainerData.sections) ? explainerData.sections : [])
        setMeta(explainerData.meta || null)
      } catch (err) {
        if (active) setCrewError(err.message || 'Failed to load job center data')
      } finally {
        if (active) setCrewLoading(false)
      }
    }
    fetchCrew()
    return () => { active = false }
  }, [authReady])

  const filteredJobs = jobs.filter((j) => {
    if (filter === 'active') { if (!IN_PROGRESS_STATUSES.includes(j.status)) return false }
    else if (filter === 'completed') { if (!COMPLETED_STATUSES.includes(j.status)) return false }
    else if (filter === 'failed') { if (!FAILED_STATUSES.includes(j.status)) return false }
    const q = (searchQuery || '').trim().toLowerCase()
    if (q && !(j.job_post || '').toLowerCase().includes(q)) return false
    return true
  })

  const updates = sections.map((s) => ({
    slug: s.slug,
    title: s.title,
    updated_at: s.updated_at,
  }))

  return (
    <PageLayout size="wide" padded className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Jobs Overview</h1>
          <p className="text-slate-600 mt-0.5">Track and manage your automated AI jobs and delivered assets.</p>
        </div>
        <button
          type="button"
          onClick={() => navigate('/jobs/new')}
          className="rounded-lg px-4 py-2.5 bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition shadow-sm flex-shrink-0"
        >
          Create New Job
        </button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex flex-col sm:flex-row gap-3 flex-wrap">
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search jobs..."
            className="flex-1 min-w-[200px] px-3 py-2 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
          />
          <div className="flex gap-1 flex-wrap">
            {[
              { key: 'all', label: 'All' },
              { key: 'active', label: 'Active' },
              { key: 'completed', label: 'Completed' },
              { key: 'failed', label: 'Failed' },
            ].map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => setFilter(key)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                  filter === key
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {loading && (
          <div className="p-8 text-center text-slate-500 text-sm">Loading jobs...</div>
        )}
        {!loading && error && (
          <div className="p-8 text-center text-red-500 text-sm">{error}</div>
        )}
        {!loading && !error && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/80">
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Job Title</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Status</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Assigned Agents</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Date</th>
                    <th className="text-right py-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredJobs.map((job) => {
                    const agents = getAssignedAgents(job)
                    const title = (job.job_post || '—').length > 80 ? `${(job.job_post || '').slice(0, 80)}…` : (job.job_post || '—')
                    return (
                      <tr
                        key={job.id}
                        onClick={() => navigate(`/jobs/${job.id}`)}
                        className="border-b border-slate-100 hover:bg-slate-50 transition cursor-pointer"
                      >
                        <td className="py-3 px-4">
                          <div className="font-medium text-slate-900">{title}</div>
                          <div className="text-xs text-slate-400 mt-0.5">#{getJobNumber(job)}</div>
                        </td>
                        <td className="py-3 px-4">
                          <StatusBadge status={job.status} />
                          {job.intake_source === 'email' && (
                            <span style={{
                              background: '#EBF5FB', color: '#1A5276',
                              borderRadius: '4px', padding: '2px 8px',
                              fontSize: '11px', marginLeft: '6px'
                            }}>✉ Via Email</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex -space-x-2">
                            {agents.length === 0 ? (
                              <span className="text-xs text-slate-400">—</span>
                            ) : (
                              agents.slice(0, 5).map((a, i) => (
                                <span
                                  key={a.role}
                                  className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-semibold text-white border-2 border-white ${COLORS[i % COLORS.length]}`}
                                  title={a.role}
                                >
                                  {a.initials}
                                </span>
                              ))
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-sm text-slate-600">
                          {relativeTime(job.created_at)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); navigate(`/jobs/${job.id}`); }}
                            className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                          >
                            View Details
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {filteredJobs.length === 0 && (
              <div className="py-12 text-center">
                <p className="text-slate-600 mb-4">No jobs match the filter. Create one to get started.</p>
                <button
                  type="button"
                  onClick={() => navigate('/jobs/new')}
                  className="rounded-lg px-4 py-2 bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition"
                >
                  Create New Job
                </button>
              </div>
            )}
            {filteredJobs.length > 0 && (
              <div className="px-4 py-3 border-t border-slate-200 text-sm text-slate-500">
                Showing {filteredJobs.length} of {jobs.length} jobs
              </div>
            )}
          </>
        )}
      </div>

      {/* Crew status section */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Crew status</h3>
            <p className="text-sm text-slate-500">Current active crew members.</p>
          </div>
          {meta && (
            <div className="text-xs text-slate-400">
              <div>Env: {meta.deploy_env}</div>
              <div>SHA: {meta.build_sha}</div>
              <div>Data: {new Date(meta.data_refreshed_at).toLocaleString()}</div>
            </div>
          )}
        </div>
        {crewLoading && <div className="mt-4 text-slate-500 text-sm">Loading...</div>}
        {!crewLoading && crewError && <div className="mt-4 text-red-500 text-sm">{crewError}</div>}
        {!crewLoading && !crewError && (
          <>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
              {updates.map((item) => (
                <div key={item.slug} className="rounded-lg border border-slate-200 p-4">
                  <div className="text-sm font-semibold text-slate-800">{item.title}</div>
                  <div className="text-xs text-slate-500 mt-2">
                    Updated: {item.updated_at ? new Date(item.updated_at).toLocaleString() : 'Unknown'}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              {crew.map((member) => (
                <div key={member.id} className="rounded-lg border border-slate-200 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-800">{member.name}</div>
                      <div className="text-xs text-slate-500">{member.role}</div>
                    </div>
                    <span className="text-xs uppercase tracking-wide text-slate-400">{member.status}</span>
                  </div>
                  <div className="mt-3 text-xs text-slate-500">{member.current_task || 'No active task'}</div>
                  {typeof member.progress === 'number' && (
                    <div className="mt-2 h-2 rounded-full bg-slate-100 overflow-hidden">
                      <div className="h-2 rounded-full bg-indigo-600 transition-all" style={{ width: `${member.progress}%` }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </PageLayout>
  )
}
