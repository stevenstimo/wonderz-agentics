import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from './PageLayout'
import { apiUrl } from './apiClient'

const STATUS_BADGE = {
  INTAKE_CLARIFICATION: 'bg-amber-100 text-amber-800',
  PLAN_PROPOSED: 'bg-blue-100 text-blue-800',
  RUNNING: 'bg-purple-100 text-purple-800',
  JOB_READY: 'bg-green-100 text-green-800',
  AWAITING_APPROVAL: 'bg-slate-100 text-slate-800',
  COMPLETED: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  CANCELLED: 'bg-gray-100 text-gray-600',
}

function StatusBadge({ status }) {
  const cls = STATUS_BADGE[status] || 'bg-gray-100 text-gray-700'
  const label = STATUS_LABEL[status] ?? status
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
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

const STATUS_LABEL = {
  INTAKE_CLARIFICATION: 'Intake',
  PLAN_PROPOSED: 'Planning',
  RUNNING: 'Running',
  JOB_READY: 'Ready',
  COMPLETED: 'Done',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
  AWAITING_APPROVAL: 'Awaiting approval',
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

function getCeoPreview(job) {
  const ctx = parseJobContext(job?.context)
  const msg = (typeof ctx.ceo_message === 'string' ? ctx.ceo_message : '') || ''
  const s = msg.slice(0, 60).trim()
  return s + (msg.length > 60 ? '…' : '')
}

const IN_PROGRESS_STATUSES = ['INTAKE_CLARIFICATION', 'PLAN_PROPOSED', 'RUNNING', 'JOB_READY', 'AWAITING_APPROVAL']
const COMPLETED_STATUSES = ['COMPLETED']
const FAILED_STATUSES = ['FAILED', 'CANCELLED']

export default function JobCenter() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState([])
  const [filter, setFilter] = useState('all') // all | in_progress | completed | failed
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
      const res = await fetch(apiUrl('/api/jobs'))
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
    fetchJobs()
    const interval = setInterval(fetchJobs, 10000)
    return () => clearInterval(interval)
  }, [fetchJobs])

  useEffect(() => {
    let active = true
    const fetchCrew = async () => {
      setCrewLoading(true)
      setCrewError(null)
      try {
        const [crewRes, explainerRes] = await Promise.all([
          fetch(apiUrl('/api/crew')),
          fetch(apiUrl('/api/explainer/sections'))
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
  }, [])

  const filteredJobs = jobs.filter((j) => {
    if (filter === 'all') {}
    else if (filter === 'in_progress') { if (!IN_PROGRESS_STATUSES.includes(j.status)) return false }
    else if (filter === 'completed') { if (!COMPLETED_STATUSES.includes(j.status)) return false }
    else if (filter === 'failed') { if (!FAILED_STATUSES.includes(j.status)) return false }
    const q = (searchQuery || '').trim().toLowerCase()
    if (q && !(j.job_post || '').toLowerCase().includes(q)) return false
    return true
  })

  const statusCounts = jobs.reduce((acc, j) => {
    acc[j.status] = (acc[j.status] || 0) + 1
    return acc
  }, {})

  const updates = sections.map((s) => ({
    slug: s.slug,
    title: s.title,
    updated_at: s.updated_at
  }))

  return (
    <PageLayout size="wide" padded className="space-y-6">
      <div className="panel-card">
        <h2 className="page-title">Job Center</h2>
        <p className="page-subtitle">
          Live status and updates from the backend. Create jobs and track the intake → plan → execution flow.
        </p>
      </div>

      {/* New Job button */}
      <div className="panel-card">
        <button
          type="button"
          onClick={() => navigate('/jobs/new')}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition"
        >
          New Job
        </button>
      </div>

      {/* Jobs overview */}
      <div className="panel-card">
        <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
          <h3 className="text-lg font-semibold text-slate-900">Jobs</h3>
          <div className="flex flex-wrap gap-2">
            <span className="text-sm text-slate-500">Total: {jobs.length}</span>
            {Object.entries(statusCounts).map(([status, count]) => (
              <span key={status} className="flex items-center gap-1">
                <StatusBadge status={status} />
                <span className="text-xs text-slate-500">{count}</span>
              </span>
            ))}
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2 mb-4">
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search jobs..."
            className="w-full sm:max-w-xs px-3 py-2 border border-slate-300 rounded-lg text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
          <div className="flex gap-2 flex-wrap">
          {['all', 'in_progress', 'completed', 'failed'].map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                filter === f ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {f === 'all' ? 'All' : f === 'in_progress' ? 'In Progress' : f === 'completed' ? 'Completed' : 'Failed'}
            </button>
          ))}
          </div>
        </div>

        {loading && <div className="text-slate-500">Loading jobs...</div>}
        {!loading && error && <div className="text-red-500">{error}</div>}
        {!loading && !error && (
          <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 gap-4 w-full">
            {filteredJobs.map((job) => (
              <button
                key={job.id}
                type="button"
                onClick={() => navigate(`/jobs/${job.id}`)}
                className="text-left rounded-lg border border-slate-200 p-4 hover:border-indigo-300 hover:bg-slate-50/50 transition"
              >
                <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={job.status} />
                    <span className="text-xs font-medium text-slate-600">#{parseJobContext(job.context)?.job_number ?? '—'}</span>
                  </div>
                  <span className="text-xs text-slate-400">{job.source_platform || '—'}</span>
                </div>
                <p className="text-sm text-slate-800 line-clamp-2">
                  {(job.job_post || '').length > 100 ? `${job.job_post.slice(0, 100)}…` : (job.job_post || '—')}
                </p>
                {getCeoPreview(job) && (
                  <p className="mt-1 text-xs text-slate-500 line-clamp-1">{getCeoPreview(job)}</p>
                )}
                <div className="mt-2 text-xs text-slate-500">{relativeTime(job.created_at)}</div>
              </button>
            ))}
          </div>
        )}
        {!loading && !error && filteredJobs.length === 0 && (
          <div className="py-8 text-center">
            <p className="text-slate-600 mb-4">No jobs match the filter. Create one to get started.</p>
            <button
              type="button"
              onClick={() => navigate('/jobs/new')}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition"
            >
              New Job
            </button>
          </div>
        )}
      </div>

      {/* Crew status (existing section) */}
      <div className="panel-card">
        <div className="flex items-center justify-between gap-4 flex-wrap">
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
        {crewLoading && <div className="mt-4 text-slate-500">Loading...</div>}
        {!crewLoading && crewError && <div className="mt-4 text-red-500">{crewError}</div>}
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
                    <div className="mt-2 h-2 rounded-full bg-slate-100">
                      <div className="h-2 rounded-full bg-indigo-500" style={{ width: `${member.progress}%` }} />
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
