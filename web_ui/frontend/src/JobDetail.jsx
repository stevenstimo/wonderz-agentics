/**
 * Replaced by JobSplitView (Claude-style split: chat left, output right).
 * Route /jobs/:jobId now renders JobSplitView. This file is kept for reference.
 */
import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import PageLayout from './PageLayout'
import { apiUrl, apiFetch } from './apiClient'

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

function getOutputContent(job, context) {
  // Alleen tonen bij JOB_READY of COMPLETED
  if (!['JOB_READY', 'COMPLETED'].includes(job?.status)) return null

  const ctx = context || {}
  const content = ctx?.final_content
    || ctx?.proposed_data?.content
    || job?.proposed_data?.content
    || null

  // Zorg dat het een string is, niet een object
  if (!content || typeof content !== 'string') return null

  return content
}

function StatusBadge({ status }) {
  const cls = STATUS_BADGE[status] || 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  )
}

function ChatHistoryReadOnly({ chatHistory, className = '' }) {
  if (!chatHistory?.length) return null
  return (
    <div className={`rounded-xl border border-slate-200 bg-slate-50/50 p-4 ${className}`}>
      <h3 className="text-sm font-medium text-slate-500 mb-3">Conversation</h3>
      <div className="space-y-3 max-h-48 overflow-y-auto">
        {chatHistory.map((msg, i) => (
          <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'ceo' && (
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-slate-200 flex items-center justify-center text-slate-500 text-xs">W</div>
            )}
            <div
              className={`max-w-[85%] px-3 py-2 rounded-xl text-sm ${
                msg.role === 'ceo' ? 'bg-slate-200/80 text-slate-700' : 'bg-indigo-100 text-indigo-900'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content || ''}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function StepOutputExpand({ output }) {
  const [open, setOpen] = useState(false)
  if (!output || typeof output !== 'object') return null
  const text = output.content || output.review || output.optimized_content || JSON.stringify(output, null, 2)
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
      >
        {open ? 'Hide output' : 'View output'}
      </button>
      {open && (
        <pre className="mt-1 p-3 bg-slate-50 rounded text-xs overflow-auto max-h-48 whitespace-pre-wrap">
          {typeof text === 'string' ? text : JSON.stringify(text, null, 2)}
        </pre>
      )}
    </div>
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
  const [chatInput, setChatInput] = useState('')
  const [sendingChat, setSendingChat] = useState(false)
  const [ceoTyping, setCeoTyping] = useState(false)
  const chatEndRef = useRef(null)
  const chatHistoryLengthRef = useRef(0)

  const fetchJob = useCallback(async () => {
    if (!jobId) return
    setLoading(true)
    setError(null)
    try {
      const url = apiUrl(`/api/jobs/${jobId}`)
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 15000)
      const res = await fetch(url, { signal: controller.signal })
      clearTimeout(timeoutId)
      if (!res.ok) {
        if (res.status === 404) throw new Error('Job not found')
        const text = await res.text()
        let detail = `Failed to load job (${res.status})`
        try {
          const j = JSON.parse(text)
          if (j.detail) detail = typeof j.detail === 'string' ? j.detail : detail
        } catch (_) {}
        throw new Error(detail)
      }
      const contentType = (res.headers.get('content-type') || '').toLowerCase()
      const text = await res.text()
      if (!contentType.includes('application/json')) {
        setError('Server returned non-JSON; check if /api is proxied to the backend.')
        return
      }
      const json = JSON.parse(text)
      setData(json)
    } catch (err) {
      if (err.name === 'AbortError') setError('Request timed out. Check your connection.')
      else setError(err.message || 'Failed to load job')
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

  useEffect(() => {
    if (!sendingChat && ceoTyping) {
      const t = setTimeout(() => setCeoTyping(false), 8000)
      return () => clearTimeout(t)
    }
  }, [sendingChat, ceoTyping])


  const handleApprovePlan = async () => {
    setApprovingPlan(true)
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 180000)
      const res = await apiFetch(`/api/jobs/${jobId}/approve-plan`, { method: 'POST', signal: controller.signal })
      clearTimeout(timeoutId)
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
      const res = await apiFetch(`/api/jobs/${jobId}/request-changes`, {
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
      const res = await apiFetch(`/api/jobs/${jobId}/approve`, { method: 'POST' })
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
        <div className="mt-4 flex gap-2 flex-wrap">
          <button type="button" onClick={() => { setError(null); fetchJob(); }} className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
            Opnieuw proberen
          </button>
          <button type="button" onClick={() => navigate('/job-center')} className="px-4 py-2 border border-slate-300 rounded-lg">
            Back to Job Center
          </button>
        </div>
      </PageLayout>
    )
  }

  if (data && !data.job) {
    return (
      <PageLayout size="wide" padded>
        <div className="panel-card text-amber-700">Job not found or invalid response.</div>
        <button type="button" onClick={() => navigate('/job-center')} className="mt-4 px-4 py-2 border border-slate-300 rounded-lg">
          Back to Job Center
        </button>
      </PageLayout>
    )
  }

  const job = data?.job
  const clarifications = data?.clarifications ?? []
  const steps = data?.steps ?? []
  const artifacts = data?.artifacts ?? []
  const context = (() => {
    let raw = job?.context
    if (raw == null) return {}
    if (typeof raw === 'object') return raw
    try {
      const parsed = JSON.parse(String(raw))
      return typeof parsed === 'string' ? (() => { try { return JSON.parse(parsed); } catch { return {}; } })() : (parsed || {})
    } catch {
      return {}
    }
  })()
  const plan = context.plan || {}
  const planSteps = plan.steps || []
  const chatHistory = Array.isArray(context.chat_history) ? context.chat_history : []

  const scrollChatToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }
  useEffect(() => {
    if (job?.status === 'INTAKE_CLARIFICATION' && chatHistory.length) scrollChatToBottom()
  }, [job?.status, chatHistory.length])

  const handleSendChat = async (e) => {
    e?.preventDefault()
    const msg = chatInput.trim()
    if (!msg || sendingChat) return
    setCeoTyping(true)
    setSendingChat(true)
    setChatInput('')
    try {
      const res = await apiFetch(`/api/jobs/${jobId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      })
      if (!res.ok) throw new Error('Failed to send message')
      await fetchJob()
      ;[2000, 4500, 7000].forEach((ms) => setTimeout(fetchJob, ms))
    } catch (err) {
      setError(err.message)
    } finally {
      setSendingChat(false)
    }
  }
  useEffect(() => {
    if (chatHistory.length > chatHistoryLengthRef.current && ceoTyping) setCeoTyping(false)
    chatHistoryLengthRef.current = chatHistory.length
  }, [chatHistory.length, ceoTyping])

  useEffect(() => {
    if (!sendingChat && ceoTyping) {
      const t = setTimeout(() => setCeoTyping(false), 1500)
      return () => clearTimeout(t)
    }
  }, [sendingChat, ceoTyping])

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
              <StatusBadge status={job?.status} />
              <span className="text-sm text-slate-500">{job?.source_platform || '—'}</span>
            </div>
          </div>
        </div>
        <div className="mt-4">
          <p className="text-sm font-medium text-slate-600">Description</p>
          <p className="mt-1 text-slate-800 whitespace-pre-wrap">{job?.job_post || '—'}</p>
        </div>
      </div>

      {error && <div className="panel-card text-red-500">{error}</div>}

      {/* INTAKE_CLARIFICATION: chat UI with chat_history */}
      {job?.status === 'INTAKE_CLARIFICATION' && (
        <div className="panel-card flex flex-col rounded-xl border border-slate-200 overflow-hidden max-h-[32rem] w-full min-w-0">
          <h3 className="text-lg font-semibold text-slate-900 mb-3 px-1">Clarify your request</h3>
          <div className="flex-1 overflow-y-auto space-y-4 min-h-[10rem] px-1 pb-2 transition-all">
            {chatHistory.length === 0 && !ceoTyping && (
              <p className="text-slate-500 text-sm">Mr. Klein is thinking…</p>
            )}
            {chatHistory.map((msg, i) => (
              <div
                key={i}
                className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'ceo' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 text-xs font-semibold">
                    MK
                  </div>
                )}
                <div
                  className={`max-w-[80%] px-4 py-2.5 rounded-2xl transition-all ${
                    msg.role === 'ceo'
                      ? 'bg-slate-100 text-slate-800 rounded-tl-none'
                      : 'bg-indigo-600 text-white rounded-tr-none'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.content || ''}</p>
                </div>
              </div>
            ))}
            {ceoTyping && (
              <div className="flex gap-2 justify-start items-center text-slate-500 text-sm">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 text-xs font-semibold">MK</div>
                <div className="px-4 py-2.5 rounded-2xl rounded-tl-none bg-slate-100 text-slate-600 flex items-center gap-1">
                  Mr. Klein is typing
                  <span className="inline-flex gap-0.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse" style={{ animationDelay: '300ms' }} />
                  </span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <form onSubmit={handleSendChat} className="sticky bottom-0 flex flex-col sm:flex-row gap-2 w-full min-w-0 p-3 bg-white border-t border-slate-200">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Type your message..."
              className="flex-1 px-4 py-2.5 border border-slate-300 rounded-xl text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              disabled={sendingChat}
            />
            <button
              type="submit"
              disabled={sendingChat || !chatInput.trim()}
              className="px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {sendingChat ? 'Sending…' : 'Send'}
            </button>
          </form>
        </div>
      )}

      {/* PLAN_PROPOSED: chat read-only, Execution Plan card, Start Execution / Request Changes */}
      {job?.status === 'PLAN_PROPOSED' && (
        <>
          <ChatHistoryReadOnly chatHistory={chatHistory} />
          <div className="panel-card space-y-4">
            <h3 className="text-lg font-semibold text-slate-900">Execution Plan</h3>
            {planSteps.length > 0 ? (
              <ul className="space-y-3">
                {planSteps.map((step, i) => (
                  <li key={i} className="flex items-center gap-3 p-3 rounded-lg border border-slate-200">
                    <span className="text-slate-500 font-mono text-sm">{step.step_index}</span>
                    <span className="font-medium text-slate-800">{step.agent_role || 'step'}</span>
                    <span className="text-sm text-slate-600 flex-1">{step.description || step.step_name || ''}</span>
                    {step.requires_approval && (
                      <span className="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-800">Approval</span>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <pre className="text-sm text-slate-600 bg-slate-50 p-4 rounded overflow-auto max-h-48">
                {JSON.stringify(plan, null, 2)}
              </pre>
            )}
            <div className="flex flex-col sm:flex-row gap-2 flex-wrap">
              <button
                type="button"
                onClick={handleApprovePlan}
                disabled={approvingPlan}
                className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
              >
                {approvingPlan ? 'Starting…' : 'Start Execution'}
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
        </>
      )}

      {/* RUNNING: chat read-only, progress bar, step cards with View Output, 5s refresh */}
      {job?.status === 'RUNNING' && (
        <>
          <ChatHistoryReadOnly chatHistory={chatHistory} />
          <div className="panel-card">
            <h3 className="text-lg font-semibold text-slate-900 mb-2">Execution in Progress</h3>
            <div className="w-full bg-slate-200 rounded-full h-2 mb-4">
              <div
                className="bg-indigo-600 h-2 rounded-full transition-all"
                style={{ width: `${steps?.length ? (steps.filter((s) => s.status === 'completed').length / steps.length) * 100 : 0}%` }}
              />
            </div>
            <ul className="space-y-3">
              {(steps || []).map((s) => (
                <li key={s.id} className="p-3 rounded-lg border border-slate-200">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-sm font-medium text-slate-700">{s.step_name || s.agent_role || s.step_index}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${
                        s.status === 'completed' ? 'bg-green-100 text-green-800' :
                        s.status === 'running' ? 'bg-amber-100 text-amber-800 animate-pulse' :
                        s.status === 'failed' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {s.status || 'pending'}
                    </span>
                  </div>
                  {s.status === 'completed' && s.output && <StepOutputExpand output={s.output} />}
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-slate-500">Refreshing every 5 seconds.</p>
          </div>
        </>
      )}

      {/* JOB_READY: chat read-only, Content Ready! banner, final_content, Approve & Request Revisions */}
      {job?.status === 'JOB_READY' && (() => {
        const content = getOutputContent(job, context)
        const contentStr = typeof content === 'string' ? content : (content != null ? String(content) : '')
        return (
        <>
          <ChatHistoryReadOnly chatHistory={chatHistory} />
          <div className="panel-card space-y-4">
            <div className="rounded-lg bg-green-100 text-green-800 px-4 py-3 font-medium">Content Ready!</div>
            <div className="rounded-lg border border-slate-200 p-4 bg-white">
              <h3 className="text-sm font-medium text-slate-500 mb-2">Final content</h3>
              <div className="text-slate-800 whitespace-pre-wrap">{contentStr || 'No content yet.'}</div>
            </div>
            {artifacts?.length > 0 && (
              <ul className="space-y-2">
                {artifacts.map((a) => (
                  <li key={a.id} className="p-3 rounded-lg border border-slate-200">
                    <span className="text-sm font-medium text-slate-700">{a.artifact_type || a.name || 'Artifact'}</span>
                    <pre className="mt-2 text-xs text-slate-600 overflow-auto max-h-32 whitespace-pre-wrap">
                      {(() => {
                        const c = a.proposed_data?.content ?? a.content
                        return typeof c === 'string' ? c : (c != null ? JSON.stringify(c, null, 2) : (typeof a.proposed_data === 'object' ? JSON.stringify(a.proposed_data, null, 2) : ''))
                      })()}
                    </pre>
                  </li>
                ))}
              </ul>
            )}
            <div className="flex gap-2 flex-wrap">
              <button
                type="button"
                onClick={handleApproveDeploy}
                disabled={approvingDeploy}
                className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
              >
                {approvingDeploy ? 'Deploying…' : 'Approve & Publish'}
              </button>
              <button
                type="button"
                onClick={() => setRequestChangesOpen(true)}
                className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
              >
                Request Revisions
              </button>
            </div>
            {requestChangesOpen && (
              <form onSubmit={handleRequestChanges} className="flex flex-col gap-2">
                <textarea
                  value={requestChangesText}
                  onChange={(e) => setRequestChangesText(e.target.value)}
                  placeholder="Describe revisions..."
                  className="w-full max-w-md px-3 py-2 border border-slate-300 rounded-lg resize-none"
                  rows={3}
                />
                <div className="flex gap-2">
                  <button type="submit" disabled={submittingRequest || !requestChangesText.trim()} className="px-4 py-2 bg-amber-600 text-white rounded-lg disabled:opacity-50">Submit</button>
                  <button type="button" onClick={() => { setRequestChangesOpen(false); setRequestChangesText(''); }} className="px-4 py-2 border border-slate-300 rounded-lg">Cancel</button>
                </div>
              </form>
            )}
          </div>
        </>
        )
      })()}

      {/* COMPLETED: Job Completed banner, final content, deployment info */}
      {job?.status === 'COMPLETED' && (() => {
        const content = getOutputContent(job, context)
        const contentStr = typeof content === 'string' ? content : (content != null ? String(content) : '')
        return (
        <>
          <ChatHistoryReadOnly chatHistory={chatHistory} />
          <div className="panel-card space-y-4">
            <div className="rounded-lg bg-green-100 text-green-800 px-4 py-3 font-medium">Job Completed</div>
            <div className="rounded-lg border border-slate-200 p-4 bg-white">
              <h3 className="text-sm font-medium text-slate-500 mb-2">Final content</h3>
              <div className="text-slate-800 whitespace-pre-wrap">{contentStr}</div>
            </div>
            {context.deployment && (
              <div className="rounded-lg border border-slate-200 p-4 bg-slate-50">
                <h3 className="text-sm font-medium text-slate-600 mb-2">Deployment</h3>
                <pre className="text-xs text-slate-700 overflow-auto">{JSON.stringify(context.deployment, null, 2)}</pre>
              </div>
            )}
          </div>
        </>
        )
      })()}

      {/* FAILED: error, Retry button */}
      {job?.status === 'FAILED' && (
        <div className="panel-card space-y-4">
          <h3 className="text-lg font-semibold text-red-800">Job failed</h3>
          {context?.token_budget_exceeded && (
            <div className="rounded-lg bg-red-100 text-red-800 px-4 py-3 font-medium">
              Token budget exceeded: {context.tokens_used ?? job?.tokens_used ?? '?'} / {context.token_budget ?? job?.token_budget ?? 50000} tokens used.
            </div>
          )}
          <pre className="text-sm text-slate-700 bg-slate-50 p-4 rounded overflow-auto max-h-48">
            {(typeof context.error === 'string' && context.error) || (typeof context.message === 'string' && context.message) || JSON.stringify(context, null, 2)}
          </pre>
          <button
            type="button"
            onClick={async () => {
              try {
                const res = await apiFetch('/api/jobs', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    user_id: '00000000-0000-0000-0000-000000000001',
                    job_post: job?.job_post || '',
                    source_platform: job?.source_platform || 'custom',
                  }),
                })
                if (!res.ok) throw new Error('Failed to create job')
                const d = await res.json()
                navigate(`/jobs/${d.job_id}`)
              } catch (e) {
                setError(e.message)
              }
            }}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700"
          >
            Retry (new job)
          </button>
        </div>
      )}

      {/* Fallback: onbekende status */}
      {job?.status && !['INTAKE_CLARIFICATION', 'PLAN_PROPOSED', 'RUNNING', 'JOB_READY', 'COMPLETED', 'FAILED'].includes(job.status) && (
        <div className="panel-card text-slate-600">
          Status: <strong>{job.status}</strong>. Geen specifieke weergave voor deze status.
        </div>
      )}
    </PageLayout>
  )
}
