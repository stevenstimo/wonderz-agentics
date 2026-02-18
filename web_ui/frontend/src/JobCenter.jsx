import { apiBase } from './apiBase'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageLayout from './PageLayout'

const STATUS_COLORS = {
  INTAKE_CLARIFICATION: 'bg-yellow-100 text-yellow-800',
  PLAN_PROPOSED: 'bg-blue-100 text-blue-800',
  RUNNING: 'bg-indigo-100 text-indigo-800',
  JOB_READY: 'bg-green-100 text-green-800',
  COMPLETED: 'bg-green-200 text-green-900',
  FAILED: 'bg-red-100 text-red-800',
}

export default function JobCenter() {
  const [jobs, setJobs] = useState([])
  const [expandedJob, setExpandedJob] = useState(null)
  const [jobDetail, setJobDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchJobs = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiBase}/api/jobs`)
      if (!res.ok) throw new Error('Failed to load jobs')
      const data = await res.json()
      setJobs(data.jobs || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchJobs() }, [])

  const loadDetail = async (jobId) => {
    if (expandedJob === jobId) {
      setExpandedJob(null)
      setJobDetail(null)
      return
    }
    setExpandedJob(jobId)
    try {
      const res = await fetch(`${apiBase}/api/jobs/${jobId}`)
      const data = await res.json()
      setJobDetail(data)
    } catch {
      setJobDetail(null)
    }
  }

  const getArtifactText = () => {
    if (!jobDetail) return null
    const arts = jobDetail.artifacts || []
    for (const a of arts) {
      let pd = a.proposed_data
      if (typeof pd === 'string') try { pd = JSON.parse(pd) } catch { continue }
      if (pd?.text) return pd.text
    }
    return null
  }

  return (
    <PageLayout size="wide" padded className="space-y-6">
      <div className="panel-card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="page-title">Job Center</h2>
            <p className="page-subtitle">Alle jobs en hun output.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={fetchJobs} className="px-3 py-1.5 text-sm bg-slate-100 hover:bg-slate-200 rounded-lg">↻ Refresh</button>
            <Link to="/jobs/new" className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">+ Nieuwe Job</Link>
          </div>
        </div>
      </div>

      {loading && <div className="panel-card text-slate-500">Laden...</div>}
      {error && <div className="panel-card text-red-500">{error}</div>}

      {!loading && jobs.length === 0 && (
        <div className="panel-card text-center py-12">
          <p className="text-slate-400 text-lg">Nog geen jobs.</p>
          <Link to="/jobs/new" className="mt-4 inline-block px-4 py-2 bg-indigo-600 text-white rounded-lg">Maak je eerste job</Link>
        </div>
      )}

      {jobs.map(job => (
        <div key={job.job_id} className="panel-card">
          <div className="flex items-center justify-between cursor-pointer" onClick={() => loadDetail(job.job_id)}>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3">
                <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${STATUS_COLORS[job.status] || 'bg-slate-100 text-slate-600'}`}>
                  {job.status}
                </span>
                <span className="text-sm font-medium text-slate-800 truncate">{job.job_post}</span>
              </div>
              <div className="mt-1 text-xs text-slate-400">
                {new Date(job.created_at).toLocaleString('nl-NL')} · {job.source_platform || 'custom'}
              </div>
            </div>
            <span className="text-slate-400 ml-4">{expandedJob === job.job_id ? '▲' : '▼'}</span>
          </div>

          {expandedJob === job.job_id && jobDetail && (
            <div className="mt-4 border-t border-slate-100 pt-4 space-y-4">
              {/* Artifacts / Output */}
              {(() => {
                const text = getArtifactText()
                if (text) return (
                  <div>
                    <h4 className="text-sm font-semibold text-slate-700 mb-2">📝 Output</h4>
                    <div className="bg-slate-50 rounded-lg p-4 text-sm text-slate-800 whitespace-pre-wrap leading-relaxed">
                      {text}
                    </div>
                    <div className="mt-2 text-xs text-slate-400">{text.split(/\s+/).length} woorden</div>
                  </div>
                )
                return null
              })()}

              {/* Steps */}
              {jobDetail.steps && jobDetail.steps.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-slate-700 mb-2">🔄 Workflow Steps</h4>
                  <div className="space-y-1">
                    {jobDetail.steps.map((s, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-slate-600">
                        <span className="w-5 h-5 rounded-full bg-green-100 text-green-700 flex items-center justify-center text-[10px] font-bold">{s.step_index}</span>
                        <span className="font-medium">{s.agent_name}</span>
                        <span className="text-slate-400">·</span>
                        <span className="text-slate-400">{s.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Plan */}
              {(() => {
                let ctx = jobDetail.job?.context
                if (typeof ctx === 'string') try { ctx = JSON.parse(ctx) } catch { return null }
                const plan = ctx?.plan
                if (!plan) return null
                return (
                  <div>
                    <h4 className="text-sm font-semibold text-slate-700 mb-2">📋 Plan</h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                      {plan.steps?.map((s, i) => (
                        <div key={i} className="text-xs bg-slate-50 rounded p-2">
                          <span className="font-medium">{s.step_index}. {s.agent_role}</span>
                          <p className="text-slate-500 mt-0.5">{s.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}
            </div>
          )}
        </div>
      ))}
    </PageLayout>
  )
}
