import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import PageLayout from './PageLayout'
import { apiUrl } from './apiClient'

function parseContext(ctx) {
  if (!ctx) return {}
  if (typeof ctx === 'object') return ctx
  try {
    const parsed = JSON.parse(ctx)
    if (typeof parsed === 'string') return JSON.parse(parsed)
    return parsed
  } catch {
    return {}
  }
}

function getOutputContent(job, context) {
  // Alleen tonen bij JOB_READY of COMPLETED
  if (!['JOB_READY', 'COMPLETED'].includes(job?.status)) return null

  const ctx = context || (job ? parseContext(job.context) : {})
  const content = ctx?.final_content
    || ctx?.proposed_data?.content
    || job?.proposed_data?.content
    || null

  // Zorg dat het een string is, niet een object
  if (!content || typeof content !== 'string') return null

  return content
}

function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="w-full rounded-xl my-4" loading="lazy" />')
    .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-4 mb-2">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-xl font-bold mt-5 mb-2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-5 mb-3">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '</p><p class="mb-3 leading-relaxed">')
    .replace(/^/, '<p class="mb-3 leading-relaxed">')
    + '</p>'
}

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

export default function JobSplitView() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(!!jobId)
  const [error, setError] = useState(null)
  const [optimisticMessages, setOptimisticMessages] = useState([])
  const [approvingPlan, setApprovingPlan] = useState(false)
  const [approvingDeploy, setApprovingDeploy] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [sendingChat, setSendingChat] = useState(false)
  const [ceoTyping, setCeoTyping] = useState(false)
  const chatEndRef = useRef(null)
  const chatHistoryLengthRef = useRef(0)
  const runIntakeTriggeredRef = useRef(null)
  const [runningIntake, setRunningIntake] = useState(false)

  const fetchJob = useCallback(async () => {
    if (!jobId) return null
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
      return json
    } catch (err) {
      setError(err.message || 'Failed to load job')
      return null
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    if (jobId) fetchJob()
  }, [jobId, fetchJob])

  // When background tasks don't run (e.g. exe.xyz): trigger intake synchronously when user opens job in INTAKE_CLARIFICATION with no plan yet
  useEffect(() => {
    if (!jobId || !data?.job) return
    if (data.job.status !== 'INTAKE_CLARIFICATION') return
    const ctx = parseContext(data.job.context)
    if (ctx.plan && (ctx.plan.steps?.length ?? 0) > 0) return
    if (runIntakeTriggeredRef.current === jobId) return
    runIntakeTriggeredRef.current = jobId
    setRunningIntake(true)
    fetch(apiUrl(`/api/jobs/${jobId}/run-intake`), { method: 'POST' })
      .then(async (res) => {
        if (!res.ok) {
          const j = await res.json().catch(() => ({}))
          setError(j.detail || 'Intake start mislukt')
          return
        }
        await fetchJob()
      })
      .catch((err) => setError(err.message || 'Intake request failed'))
      .finally(() => setRunningIntake(false))
  }, [jobId, data?.job?.id, data?.job?.status, data?.job?.context, fetchJob])

  // Poll while intake is running (so we pick up CEO's first reply) or while job is executing.
  // When INTAKE_CLARIFICATION with empty chat_history, poll every 2s until Mr. Klein responds.
  useEffect(() => {
    if (!data?.job) return
    const status = data.job.status
    if (status !== 'RUNNING' && status !== 'INTAKE_CLARIFICATION') return
    const ms = status === 'INTAKE_CLARIFICATION' ? 2000 : 5000
    const interval = setInterval(fetchJob, ms)
    return () => clearInterval(interval)
  }, [data?.job?.status, data?.job?.context, fetchJob])

  useEffect(() => {
    if (!sendingChat && ceoTyping) {
      const t = setTimeout(() => setCeoTyping(false), 8000)
      return () => clearTimeout(t)
    }
  }, [sendingChat, ceoTyping])

  // Derived values before any early return so hook count is stable (React #310)
  const job = data?.job
  const steps = data?.steps ?? []
  const artifacts = data?.artifacts ?? []
  const context = job ? parseContext(job.context) : {}
  const imageUrl = context.image_url
  const plan = context.plan || {}
  const planSteps = Array.isArray(plan.steps) ? plan.steps : []
  const chatHistory = Array.isArray(context.chat_history) ? context.chat_history : []
  const statusStr = job?.status != null ? String(job.status) : ''
  const statusUpper = statusStr.toUpperCase()
  const isIntake = statusUpper === 'INTAKE_CLARIFICATION'
  const displayChatHistory = [...chatHistory, ...optimisticMessages]
  const inputDisabled = sendingChat
  useEffect(() => {
    if (isIntake && chatHistory.length) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [isIntake, chatHistory.length])

  const handleApprovePlan = async () => {
    setApprovingPlan(true)
    setError(null)
    try {
      const latest = await fetchJob()
      if (latest?.job?.status !== 'PLAN_PROPOSED') {
        setError(`Job status is "${latest?.job?.status || 'unknown'}". Refresh the page and try again when the plan is ready.`)
        return
      }
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 180000)
      const res = await fetch(apiUrl(`/api/jobs/${jobId}/approve-plan`), { method: 'POST', signal: controller.signal })
      clearTimeout(timeoutId)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const msg = body.detail || (res.status === 400 ? 'Job is not in PLAN_PROPOSED state.' : 'Failed to approve plan')
        setError(msg)
        await fetchJob()
        return
      }
      await fetchJob()
    } catch (err) {
      setError(err.message)
    } finally {
      setApprovingPlan(false)
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

  const handleSendMessage = async (e) => {
    e?.preventDefault()
    const msg = chatInput.trim()
    if (!msg || sendingChat) return

    if (!jobId) {
      setSendingChat(true)
      setChatInput('')
      try {
        const res = await fetch(apiUrl('/api/jobs'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: '00000000-0000-0000-0000-000000000001',
            job_post: msg,
            source_platform: 'web'
          })
        })
        if (!res.ok) {
          const j = await res.json().catch(() => ({}))
          throw new Error(j.detail || 'Failed to create job')
        }
        const d = await res.json()
        navigate(`/jobs/${d.job_id}`)
      } catch (err) {
        setError(err.message)
      } finally {
        setSendingChat(false)
      }
      return
    }

    setOptimisticMessages((prev) => [...prev, { role: 'user', content: msg }])
    setChatInput('')
    setSendingChat(true)
    if (statusUpper === 'INTAKE_CLARIFICATION' || statusUpper === 'RUNNING') {
      setCeoTyping(true)
    }
    const status = job?.status
    try {
      let res
      if (status === 'INTAKE_CLARIFICATION' || status === 'RUNNING') {
        res = await fetch(apiUrl(`/api/jobs/${jobId}/chat`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg })
        })
      } else if (status === 'PLAN_PROPOSED') {
        res = await fetch(apiUrl(`/api/jobs/${jobId}/request-changes`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ feedback: msg })
        })
      } else if (status === 'JOB_READY' || status === 'AWAITING_APPROVAL' || status === 'COMPLETED') {
        res = await fetch(apiUrl(`/api/jobs/${jobId}/feedback`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ feedback: msg })
        })
      } else {
        setError('Chat not available for this status. Refresh the page.')
        setOptimisticMessages((prev) => prev.filter((m) => m.content !== msg))
        return
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to send message')
      }
      await fetchJob()
      setOptimisticMessages([])
      if (status === 'INTAKE_CLARIFICATION' || status === 'RUNNING') {
        ;[2000, 4500, 7000].forEach((ms) => setTimeout(fetchJob, ms))
      }
    } catch (err) {
      setError(err.message)
      setOptimisticMessages((prev) => prev.filter((m) => m.content !== msg))
      setCeoTyping(false)
    } finally {
      setSendingChat(false)
    }
  }

  const handleKeyDown = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSendMessage(e)
    }
  }

  if (jobId && loading && !data) {
    return (
      <PageLayout size="wide" padded className="!max-w-none">
        <div className="grid grid-cols-1 md:grid-cols-[55%_45%] gap-4 min-h-[calc(100vh-8rem)]">
          <div className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden min-h-0">
            <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200">
              <h2 className="text-lg font-semibold text-slate-900">Loading…</h2>
            </div>
            <div className="flex-1 flex items-center justify-center p-8">
              <p className="text-slate-500 text-sm">Loading job…</p>
            </div>
          </div>
          <div className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden min-h-0">
            <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200">
              <h3 className="text-lg font-semibold text-slate-900">Output</h3>
            </div>
            <div className="flex-1 flex items-center justify-center p-8">
              <p className="text-slate-500 text-sm">—</p>
            </div>
          </div>
        </div>
      </PageLayout>
    )
  }

  if (jobId && error && !data) {
    return (
      <PageLayout size="wide" padded className="!max-w-none">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm text-red-500">{error}</div>
        <div className="mt-4 flex gap-2 flex-wrap">
          <button type="button" onClick={() => { setError(null); fetchJob(); }} className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700">Retry</button>
          <button type="button" onClick={() => navigate('/job-center')} className="px-4 py-2 border border-slate-300 rounded-lg font-medium">Back to Job Center</button>
        </div>
      </PageLayout>
    )
  }

  if (jobId && data && !data.job) {
    return (
      <PageLayout size="wide" padded className="!max-w-none">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm text-amber-700">Job not found.</div>
        <button type="button" onClick={() => navigate('/job-center')} className="mt-4 px-4 py-2 border border-slate-300 rounded-lg font-medium">Back to Job Center</button>
      </PageLayout>
    )
  }

  if (job) chatHistoryLengthRef.current = displayChatHistory.length

  const title = job ? (typeof job.job_post === 'string' ? job.job_post.slice(0, 60).trim() + (job.job_post.length > 60 ? '…' : '') : 'Job') : 'New Job'

  return (
    <PageLayout size="wide" padded className="!max-w-none">
      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800 flex items-center justify-between gap-2 flex-wrap">
          <span className="text-sm">{error}</span>
          <button type="button" onClick={() => { setError(null); fetchJob(); }} className="text-sm font-medium text-red-600 hover:text-red-800 underline">Dismiss & refresh</button>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-[55%_45%] gap-4 min-h-[calc(100vh-8rem)]">
        {/* Left: Chat */}
        <div className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden min-h-0">
          <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200 flex items-center justify-between gap-2">
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-slate-900 truncate">{title}</h2>
              {!job && <p className="text-xs text-slate-500 mt-0.5">Chat with Mr. Klein — describe your project</p>}
            </div>
            {job && <StatusBadge status={job.status} />}
          </div>
          <div className="flex-1 overflow-y-auto space-y-4 p-4 min-h-[10rem]">
            {displayChatHistory.length === 0 && !ceoTyping && !jobId && (
              <p className="text-slate-500 text-sm">Describe your task below. Mr. Klein will create a plan for you.</p>
            )}
            {displayChatHistory.length === 0 && !ceoTyping && jobId && isIntake && (
              <div className="thinking-indicator flex items-center gap-1.5 text-slate-500 text-sm">
                <span>Mr. Klein is thinking</span>
                <span className="thinking-dots inline-flex gap-0.5">
                  <span className="thinking-dot">.</span>
                  <span className="thinking-dot">.</span>
                  <span className="thinking-dot">.</span>
                </span>
              </div>
            )}
            {statusUpper === 'RUNNING' && (
              <p className="text-slate-600 text-sm bg-slate-100 px-3 py-2 rounded-lg">Job is running; your message will be applied after completion.</p>
            )}
            {displayChatHistory.map((msg, i) => (
              <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'ceo' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 text-xs font-semibold">MK</div>
                )}
                <div className="flex flex-col gap-0.5 max-w-[80%]">
                  {msg.role === 'ceo' && <span className="text-xs text-slate-500">Mr. Klein</span>}
                  <div
                    className={`px-4 py-2.5 rounded-xl ${
                      msg.role === 'ceo' ? 'bg-slate-100 text-slate-800 rounded-tl-none' : 'bg-indigo-600 text-white rounded-tr-none'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{msg.content || ''}</p>
                  </div>
                </div>
              </div>
            ))}
            {ceoTyping && (
              <div className="flex gap-2 justify-start items-center text-slate-500 text-sm">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 text-xs font-semibold">MK</div>
                <div className="px-4 py-2.5 rounded-xl rounded-tl-none bg-slate-100 text-slate-600 flex items-center gap-1">
                  <span>Mr. Klein is thinking</span>
                  <span className="thinking-dots inline-flex">
                    <span className="thinking-dot">.</span>
                    <span className="thinking-dot">.</span>
                    <span className="thinking-dot">.</span>
                  </span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <form onSubmit={handleSendMessage} className="flex-shrink-0 flex gap-2 p-3 border-t border-slate-200 bg-white">
            <textarea
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={jobId ? 'Type your message...' : 'Beschrijf je opdracht...'}
              className="flex-1 px-4 py-2.5 border border-slate-300 rounded-xl text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none min-h-[44px] max-h-32"
              disabled={inputDisabled}
              rows={1}
            />
            <button
              type="submit"
              disabled={inputDisabled || !chatInput.trim()}
              className="px-5 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition self-end"
            >
              {sendingChat ? 'Sending…' : 'Send'}
            </button>
          </form>
        </div>

        {/* Right: Output */}
        <div className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden min-h-0">
          <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200">
            <h3 className="text-lg font-semibold text-slate-900">{context.job_number ? `Output — #${context.job_number}` : 'Output'}</h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {!job && (
              <div className="text-slate-500 text-sm py-8">
                Describe your task on the left. Mr. Klein will create a plan for you.
              </div>
            )}

            {job?.status === 'INTAKE_CLARIFICATION' && (() => {
              const briefCtx = context.brief?.context
              const briefStr = typeof briefCtx === 'string' ? briefCtx : (briefCtx != null ? JSON.stringify(briefCtx) : '')
              const isApiCreditError = /credit balance|API error/i.test(briefStr) || /credit balance|API error/i.test(context.error || context.execution_error || '')
              return (
                <div className="space-y-2">
                  {isApiCreditError && (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                      Dit kan een eerdere fout zijn. Controleer of de juiste API-key op de server staat (Status → Keys; na herstart backend moet de fingerprint kloppen). Stuur daarna een nieuw bericht om opnieuw te proberen.
                      {briefCtx && typeof briefCtx === 'object' && briefCtx.key_fingerprint && (
                        <span className="block mt-2 text-xs font-mono text-amber-900">Key fingerprint bij fout: {briefCtx.key_fingerprint} (vergelijk met /api/status/keys)</span>
                      )}
                    </div>
                  )}
                  {runningIntake && <p className="text-amber-700 text-sm font-medium">Intake wordt uitgevoerd… (kan 20–30 sec duren)</p>}
                  {!isApiCreditError && !runningIntake && (
                    <p className="text-slate-500 text-sm">Wacht op Mr. Klein…</p>
                  )}
                </div>
              )
            })()}

            {job?.status === 'PLAN_PROPOSED' && (
              <div className="space-y-4">
                <h3 className="text-base font-semibold text-slate-900">Execution Plan</h3>
                {planSteps.length > 0 ? (
                  <ul className="space-y-3">
                    {planSteps.map((step, i) => (
                      <li key={i} className="flex items-center gap-3 p-3 rounded-lg border border-slate-200">
                        <span className="text-slate-500 font-mono text-sm">{step.step_index}</span>
                        <span className="font-medium text-slate-800">{step.agent_role || 'step'}</span>
                        <span className="text-sm text-slate-600 flex-1">{step.description || step.step_name || ''}</span>
                        {step.requires_approval && <span className="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-800">Approval</span>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-slate-500 text-sm">Wacht op Mr. Klein…</p>
                )}
                <div className="flex flex-col sm:flex-row gap-2 flex-wrap">
                  <button type="button" onClick={handleApprovePlan} disabled={approvingPlan} className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50">
                    {approvingPlan ? 'Starting…' : 'Start Execution'}
                  </button>
                </div>
              </div>
            )}

            {job?.status === 'RUNNING' && (() => {
              const updatedAt = job?.updated_at ? new Date(job.updated_at).getTime() : 0
              const isStuck = updatedAt > 0 && (Date.now() - updatedAt) > 5 * 60 * 1000
              const stepList = (steps && steps.length) > 0 ? steps : (planSteps.length > 0 ? planSteps.map((p, i) => ({ id: `plan-${i}`, step_index: p.step_index ?? i + 1, step_name: p.description, agent_role: p.agent_role, status: 'pending' })) : [])
              const completedCount = stepList.filter((s) => s.status === 'completed').length
              const totalCount = stepList.length || 1
              const progressPct = totalCount ? (completedCount / totalCount) * 100 : 0
              const allPending = stepList.length > 0 && stepList.every((s) => (s.status || 'pending') === 'pending')
              const agentLabel = (role) => {
                if (!role) return '—'
                const r = String(role).toLowerCase()
                if (r === 'copywriter') return 'Copywriter'
                if (r === 'reviewer') return 'Reviewer'
                if (r === 'image_generator' || r === 'image_generation') return 'Image generator'
                if (r === 'seo' || r === 'seo_specialist') return 'SEO'
                if (r.includes('gtm:director')) return 'Marcus (GTM Director)'
                if (r.includes('ads:meta')) return 'Sophie (Meta Ads)'
                if (r.includes('ads:google')) return 'Tom (Google Ads)'
                if (r.includes('email:specialist')) return 'Anna (Email)'
                if (r.includes('social:specialist')) return 'Daan (Social)'
                if (r.includes('seo:strategist')) return 'Eva (SEO)'
                return role
              }
              return (
                <div className="space-y-4">
                  <h3 className="text-base font-semibold text-slate-900">Execution in Progress</h3>
                  {isStuck && (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                      Dit job duurt langer dan verwacht. De backend werkt mogelijk nog aan een grote campagne. Blijf de pagina verversen — bij een crash is tussentijdse content opgeslagen.
                    </div>
                  )}
                  <p className="text-sm text-slate-600">
                    {allPending ? 'Execution is starting… Steps will show "In progress" and "Done" as they run. You can keep chatting with Mr. Klein on the left.' : 'Assigned agents run each step in order. Status updates every 5 seconds.'}
                  </p>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-sm font-medium text-slate-700">Overall</span>
                      <span className="text-xs text-slate-500">{completedCount} of {totalCount} steps done</span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
                      <div className="bg-indigo-600 h-3 rounded-full transition-all duration-500" style={{ width: `${progressPct}%` }} />
                    </div>
                  </div>
                  <ul className="space-y-2">
                    {stepList.map((s, idx) => {
                      const status = s.status || 'pending'
                      const isDone = status === 'completed'
                      const isRunning = status === 'running'
                      const isFailed = status === 'failed'
                      return (
                        <li key={s.id} className="rounded-xl border border-slate-200 overflow-hidden bg-white">
                          <div className="flex items-stretch gap-0 min-h-[52px]">
                            <div className={`w-1 flex-shrink-0 ${isDone ? 'bg-green-500' : isRunning ? 'bg-amber-500 animate-pulse' : isFailed ? 'bg-red-500' : 'bg-slate-200'}`} aria-hidden />
                            <div className="flex-1 flex items-center gap-3 p-3 min-w-0 flex-wrap">
                              <span className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium bg-slate-100 text-slate-600">
                                {isDone ? '✓' : isRunning ? '…' : idx + 1}
                              </span>
                              <span className="text-sm font-medium text-slate-800 flex-1 min-w-0 truncate" title={s.step_name || s.agent_role || s.step_index}>
                                {s.step_name || s.agent_role || `Step ${s.step_index}`}
                              </span>
                              <span className="flex-shrink-0 text-xs px-2 py-1 rounded bg-indigo-50 text-indigo-700 font-medium" title="Assigned agent">
                                {agentLabel(s.agent_role)}
                              </span>
                              <span className={`flex-shrink-0 text-xs px-2 py-1 rounded-full font-medium ${isDone ? 'bg-green-100 text-green-800' : isRunning ? 'bg-amber-100 text-amber-800' : isFailed ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-600'}`}>
                                {isDone ? 'Done' : isRunning ? 'In progress' : isFailed ? 'Failed' : 'Pending'}
                              </span>
                            </div>
                          </div>
                          {isDone && s.output && (
                            <div className="border-t border-slate-100 px-3 pb-2 pt-1">
                              {s.output.image_url && (
                                <div className="mb-2">
                                  <img src={s.output.image_url} alt="Step image" className="w-full max-h-32 object-cover rounded-lg shadow-sm" loading="lazy" />
                                </div>
                              )}
                              <StepOutputExpand output={s.output} />
                            </div>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                  {allPending && (
                    <div className="space-y-2">
                      <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                        Steps nog niet gestart of wacht op backend. Als er na een paar seconden nog niets verandert: controleer of de backend draait en of er een 500-fout in het netwerk-tabblad staat; bij falen verschijnt hier een Error log of gaat de job naar Failed.
                      </div>
                      {context.execution_error && (
                        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm">
                          <h4 className="font-semibold text-red-800 mb-1">Last error (debug)</h4>
                          <pre className="text-xs text-slate-800 whitespace-pre-wrap break-words overflow-auto max-h-32">{context.execution_error}</pre>
                        </div>
                      )}
                    </div>
                  )}
                  <p className="text-xs text-slate-500">Refreshing every 5 seconds.</p>
                </div>
              )
            })()}

            {job?.status === 'JOB_READY' && (() => {
              const content = getOutputContent(job, context)
              const contentStr = typeof content === 'string' ? content : (content != null ? String(content) : '')
              return (
              <div className="space-y-4">
                <div className="rounded-lg bg-green-100 text-green-800 px-4 py-3 font-medium">Content Ready!</div>
                {imageUrl && (
                  <div className="mb-4 rounded-xl overflow-hidden bg-slate-100 min-h-[200px] relative">
                    <img
                      src={imageUrl}
                      alt="Generated illustration"
                      className="w-full rounded-xl"
                      loading="eager"
                    />
                  </div>
                )}
                <div className="rounded-xl border border-slate-200 p-4 bg-white">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <h3 className="text-sm font-medium text-slate-500">Final content</h3>
                    <button
                      type="button"
                      onClick={() => {
                        const text = typeof content === 'string' ? content : (content != null ? JSON.stringify(content) : '')
                        if (text) navigator.clipboard.writeText(text)
                      }}
                      className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
                    >
                      Copy
                    </button>
                  </div>
                  <div className="prose prose-slate max-w-none text-slate-800 max-h-96 overflow-y-auto">
                    <div dangerouslySetInnerHTML={{ __html: renderMarkdown(contentStr) || '<p class="text-slate-500">No content yet.</p>' }} />
                  </div>
                </div>
                {artifacts?.length > 0 && (
                  <ul className="space-y-2">
                    {artifacts.map((a) => (
                      <li key={a.id} className="p-3 rounded-lg border border-slate-200">
                        <span className="text-sm font-medium text-slate-700">{a.artifact_type || a.name || 'Artifact'}</span>
                        <pre className="mt-2 text-xs text-slate-600 overflow-auto max-h-32 whitespace-pre-wrap">{typeof (a.proposed_data?.content ?? a.content) === 'string' ? (a.proposed_data?.content ?? a.content) : JSON.stringify(a.proposed_data ?? a.content ?? {}, null, 2)}</pre>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="flex gap-2 flex-wrap">
                  <button type="button" onClick={handleApproveDeploy} disabled={approvingDeploy} className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50">
                    {approvingDeploy ? 'Deploying…' : 'Approve & Publish'}
                  </button>
                </div>
              </div>
              )
            })()}

            {job?.status === 'COMPLETED' && (() => {
              const content = getOutputContent(job, context)
              const contentStr = typeof content === 'string' ? content : (content != null ? String(content) : '')
              return (
              <div className="space-y-4">
                <div className="rounded-lg bg-green-100 text-green-800 px-4 py-3 font-medium">Job Completed</div>
                {imageUrl && (
                  <div className="mb-4 rounded-xl overflow-hidden bg-slate-100 min-h-[200px] relative">
                    <img
                      src={imageUrl}
                      alt="Generated illustration"
                      className="w-full rounded-xl"
                      loading="eager"
                    />
                  </div>
                )}
                <div className="rounded-xl border border-slate-200 p-4 bg-white">
                  <h3 className="text-sm font-medium text-slate-500 mb-2">Final content</h3>
                  <div className="prose prose-slate max-w-none text-slate-800 max-h-96 overflow-y-auto">
                    <div dangerouslySetInnerHTML={{ __html: renderMarkdown(contentStr) || '<p class="text-slate-500">No content.</p>' }} />
                  </div>
                </div>
                {context.deployment && (
                  <div className="rounded-xl border border-slate-200 p-4 bg-slate-50">
                    <h3 className="text-sm font-medium text-slate-600 mb-2">Deployment</h3>
                    <pre className="text-xs text-slate-700 overflow-auto">{JSON.stringify(context.deployment, null, 2)}</pre>
                  </div>
                )}
                <button type="button" onClick={() => navigate('/job-center')} className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700">Back to Job Center</button>
              </div>
              )
            })()}

            {job?.status === 'FAILED' && (
              <div className="space-y-4">
                <div className="rounded-lg bg-red-100 text-red-800 px-4 py-3 font-medium">Job Failed</div>
                {(context.execution_error || context.error || context.message) && (
                  <div className="rounded-xl border border-red-200 bg-red-50 p-4">
                    <h4 className="text-sm font-semibold text-red-800 mb-2">Error log</h4>
                    <pre className="text-sm text-slate-800 whitespace-pre-wrap break-words overflow-auto max-h-48">
                      {context.execution_error || context.error || context.message}
                    </pre>
                  </div>
                )}
                <pre className="text-sm text-slate-700 bg-slate-50 p-4 rounded overflow-auto max-h-48 whitespace-pre-wrap">
                  {(typeof context.error === 'string' && context.error) || (typeof context.message === 'string' && context.message) || context.execution_error || JSON.stringify(context, null, 2)}
                </pre>
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const res = await fetch(apiUrl('/api/jobs'), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: '00000000-0000-0000-0000-000000000001', job_post: job?.job_post || '', source_platform: job?.source_platform || 'custom' })
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

            {job?.status && !['INTAKE_CLARIFICATION', 'PLAN_PROPOSED', 'RUNNING', 'JOB_READY', 'COMPLETED', 'FAILED'].includes(job.status) && (
              <p className="text-slate-600 text-sm">Status: <strong>{job.status}</strong>. No specific view for this status.</p>
            )}
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
