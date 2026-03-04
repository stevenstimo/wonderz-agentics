import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import PageLayout from './PageLayout'
import { apiUrl } from './apiClient'
import { IntakeChatView } from './components/IntakeChatView'

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
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  )
}

export default function JobDetail() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [requestChangesOpen, setRequestChangesOpen] = useState(false)
  const [requestChangesText, setRequestChangesText] = useState('')
  const [submittingRequest, setSubmittingRequest] = useState(false)
  const [approvingPlan, setApprovingPlan] = useState(false)
  const [approvingDeploy, setApprovingDeploy] = useState(false)

  const fetchJob = useCallback(async () => {
    if (!jobId) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(apiUrl(`/api/jobs/${jobId}`))
      if (!res.ok) {
        if (res.status === 404) throw new Error('Job not found')
        throw new Error('Failed to load job')
      }
      const json = await res.json()
      setData(json)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    fetchJob()
  }, [fetchJob])

  useEffect(() => {
    if (!data?.job || data.job.status !== 'RUNNING') return
    const interval = setInterval(fetchJob, 5000)
    return () => clearInterval(interval)
  }, [data?.job?.status, fetchJob])

  const handleApprovePlan = async () => {
    setApprovingPlan(true)
    try {
      const res = await fetch(apiUrl(`/api/jobs/${jobId}/approve-plan`), { method: 'POST' })
      if (!res.ok) throw new Error('Failed to approve plan')
      await fetchJob()
    } catch (err) {
      setError(err.message)
    } finally {
      setApprovingPlan(false)
    }
  }

  const handleRequestChanges = async (e) => {
    e.preventDefault()
    if (!requestChangesText.trim()) return
    setSubmittingRequest(true)
    try {
      const res = await fetch(apiUrl(`/api/jobs/${jobId}/request-changes`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback: requestChangesText.trim() })
      })
      if (!res.ok) throw new Error('Failed to submit feedback')
      setRequestChangesOpen(false)
      setRequestChangesText('')
      await fetchJob()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmittingRequest(false)
    }
  }

  const handleApproveDeploy = async () => {
    setApprovingDeploy(true)
    try {
      const res = await fetch(apiUrl(`/api/jobs/${jobId}/approve`), { method: 'POST' })
      if (!res.ok) throw new Error('Failed to approve and deploy')
      await fetchJob()
    } catch (err) {
      setError(err.message)
    } finally {
      setApprovingDeploy(false)
    }
  }

  if (!jobId) {
    return (
      <PageLayout size="wide" padded>
        <div className="panel-card text-red-500">Missing job ID</div>
      </PageLayout>
    )
  }

  if (loading && !data) {
    return (
      <PageLayout size="wide" padded>
        <div className="panel-card">Loading job...</div>
      </PageLayout>
    )
  }

  if (error && !data) {
    return (
      <PageLayout size="wide" padded>
        <div className="panel-card text-red-500">{error}</div>
        <button type="button" onClick={() => navigate('/job-center')} className="mt-4 px-4 py-2 border border-slate-300 rounded-lg">
          Back to Job Center
        </button>
      </PageLayout>
    )
  }

  const { job, clarifications = [], steps = [], artifacts = [] } = data
  const context = typeof job.context === 'string' ? (() => { try { return JSON.parse(job.context); } catch { return {}; } })() : (job.context || {})
  const plan = context.plan || {}
  const planSteps = plan.steps || []
  const unansweredClarifications = clarifications.filter((c) => !c.user_answer && c.answered_at == null)

  return (
    <PageLayout size="wide" padded className="space-y-6">
      <div className="panel-card">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <button type="button" onClick={() => navigate('/job-center')} className="text-sm text-slate-500 hover:text-slate-700 mb-2">
              ← Back to Job Center
            </button>
            <h2 className="page-title">Job</h2>
            <div className="flex items-center gap-2 mt-2">
              <StatusBadge status={job.status} />
              <span className="text-sm text-slate-500">{job.source_platform || '—'}</span>
            </div>
          </div>
        </div>
        <div className="mt-4">
          <p className="text-sm font-medium text-slate-600">Description</p>
          <p className="mt-1 text-slate-800 whitespace-pre-wrap">{job.job_post || '—'}</p>
        </div>
      </div>

      {error && <div className="panel-card text-red-500">{error}</div>}

      {/* INTAKE_CLARIFICATION: unanswered clarifications → IntakeChatView */}
      {job.status === 'INTAKE_CLARIFICATION' && unansweredClarifications.length > 0 && (
        <div className="panel-card">
          <IntakeChatView
            jobId={jobId}
            clarifications={unansweredClarifications}
            onAnswersSubmitted={fetchJob}
          />
        </div>
      )}

      {/* PLAN_PROPOSED: show plan, Approve Plan, Request Changes */}
      {job.status === 'PLAN_PROPOSED' && (
        <div className="panel-card space-y-4">
          <h3 className="text-lg font-semibold text-slate-900">Proposed plan</h3>
          {planSteps.length > 0 ? (
            <ul className="list-decimal list-inside space-y-2 text-slate-700">
              {planSteps.map((step, i) => (
                <li key={i}>
                  {step.step_name || step.name || step.agent_role || 'Step'} {step.agent_role && `(${step.agent_role})`}
                </li>
              ))}
            </ul>
          ) : (
            <pre className="text-sm text-slate-600 bg-slate-50 p-4 rounded overflow-auto max-h-48">
              {JSON.stringify(plan, null, 2)}
            </pre>
          )}
          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={handleApprovePlan}
              disabled={approvingPlan}
              className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
            >
              {approvingPlan ? 'Approving...' : 'Approve Plan'}
            </button>
            {!requestChangesOpen ? (
              <button
                type="button"
                onClick={() => setRequestChangesOpen(true)}
                className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
              >
                Request Changes
              </button>
            ) : (
              <form onSubmit={handleRequestChanges} className="flex flex-col gap-2">
                <textarea
                  value={requestChangesText}
                  onChange={(e) => setRequestChangesText(e.target.value)}
                  placeholder="Describe requested changes..."
                  className="w-full max-w-md px-3 py-2 border border-slate-300 rounded-lg resize-none"
                  rows={3}
                />
                <div className="flex gap-2">
                  <button type="submit" disabled={submittingRequest || !requestChangesText.trim()} className="px-4 py-2 bg-amber-600 text-white rounded-lg disabled:opacity-50">
                    {submittingRequest ? 'Sending...' : 'Submit'}
                  </button>
                  <button type="button" onClick={() => { setRequestChangesOpen(false); setRequestChangesText(''); }} className="px-4 py-2 border border-slate-300 rounded-lg">
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* RUNNING: job_steps with status, auto-refresh */}
      {job.status === 'RUNNING' && (
        <div className="panel-card">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Steps</h3>
          <ul className="space-y-2">
            {(steps || []).map((s) => (
              <li key={s.id} className="flex items-center gap-3 p-3 rounded-lg border border-slate-200">
                <span className="text-sm font-medium text-slate-700">{s.step_name || s.step_index}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${s.status === 'completed' ? 'bg-green-100 text-green-800' : s.status === 'running' ? 'bg-purple-100 text-purple-800' : 'bg-slate-100 text-slate-600'}`}>
                  {s.status || 'pending'}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-500">Refreshing every 5 seconds.</p>
        </div>
      )}

      {/* JOB_READY / COMPLETED: results/artifacts; JOB_READY: Approve & Deploy */}
      {(job.status === 'JOB_READY' || job.status === 'COMPLETED') && (
        <div className="panel-card space-y-4">
          <h3 className="text-lg font-semibold text-slate-900">Results</h3>
          {artifacts && artifacts.length > 0 ? (
            <ul className="space-y-2">
              {artifacts.map((a) => (
                <li key={a.id} className="p-3 rounded-lg border border-slate-200">
                  <span className="text-sm font-medium text-slate-700">{a.artifact_type || a.name || 'Artifact'}</span>
                  {a.content && <pre className="mt-2 text-xs text-slate-600 overflow-auto max-h-32">{typeof a.content === 'string' ? a.content : JSON.stringify(a.content)}</pre>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-slate-500">No artifacts yet.</p>
          )}
          {job.status === 'JOB_READY' && (
            <button
              type="button"
              onClick={handleApproveDeploy}
              disabled={approvingDeploy}
              className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
            >
              {approvingDeploy ? 'Deploying...' : 'Approve & Deploy'}
            </button>
          )}
        </div>
      )}

      {/* FAILED: error from context */}
      {job.status === 'FAILED' && (
        <div className="panel-card">
          <h3 className="text-lg font-semibold text-red-800 mb-2">Job failed</h3>
          <pre className="text-sm text-slate-700 bg-slate-50 p-4 rounded overflow-auto max-h-48">
            {context.error || context.message || JSON.stringify(context, null, 2)}
          </pre>
        </div>
      )}
    </PageLayout>
  )
}
