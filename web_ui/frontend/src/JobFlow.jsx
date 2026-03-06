/**
 * Replaced by JobSplitView + NewJob. Route /jobs/new now renders NewJob (split view).
 * This file is kept for reference; do not delete yet.
 */
import { useState, useRef, useEffect } from 'react'
import { supabase } from './supabase'
import PageLayout from './PageLayout'
import { Sparkles, Play, CheckCircle, XCircle, Loader2, ChevronRight, Circle } from 'lucide-react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8090'

// Status mapping van backend naar UI fase
function getPhase(status) {
  if (!status) return 'intake'
  if (status === 'INTAKE_CLARIFICATION') return 'intake'
  if (status === 'PLAN_PROPOSED') return 'plan'
  if (status === 'RUNNING') return 'tracker'
  if (status === 'JOB_READY') return 'review'
  if (status === 'COMPLETED' || status === 'FAILED') return 'done'
  return 'intake'
}

function normalizeStepStatus(status) {
  if (status === 'success' || status === 'completed') return 'success'
  if (status === 'failed') return 'failed'
  if (status === 'in_progress' || status === 'running' || status === 'awaiting_user_input') return 'in_progress'
  return 'unknown'
}

function roleToStepName(role) {
  if (!role) return ''
  if (role === 'copywriter') return 'copy_agent'
  if (role === 'reviewer') return 'reviewer_agent'
  return role
}

function subtaskLabel(name) {
  if (name === 'prepare') return 'Voorbereiden'
  if (name === 'execute') return 'Uitvoeren'
  if (name === 'finalize') return 'Afronden'
  return name
}

function heartbeatMeta(level) {
  if (level === 'green') {
    return {
      label: 'Heartbeat: goed',
      dotClass: 'bg-green-500 animate-pulse',
      textClass: 'text-green-700'
    }
  }
  if (level === 'orange') {
    return {
      label: 'Heartbeat: zwak',
      dotClass: 'bg-orange-500 animate-pulse',
      textClass: 'text-orange-700'
    }
  }
  return {
    label: 'Heartbeat: geen signaal',
    dotClass: 'bg-gray-400',
    textClass: 'text-gray-500'
  }
}

export default function JobFlow() {
  const [jobData, setJobData] = useState(null)   // { job, clarifications, steps, artifacts }
  const [phase, setPhase] = useState('intake')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([{ from: 'ceo', text: 'Hallo. Beschrijf je job.' }])
  const [loading, setLoading] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [feedback, setFeedback] = useState('')
  const [showFeedback, setShowFeedback] = useState(false)
  const [nowMs, setNowMs] = useState(Date.now())
  const bottomRef = useRef(null)
  const pollRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  // Stop polling on unmount
  useEffect(() => { return () => { if (pollRef.current) clearInterval(pollRef.current) } }, [])
  useEffect(() => {
    const t = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  const loadJob = async (id) => {
    try {
      const r = await fetch(API + '/api/jobs/' + id)
      if (!r.ok) return
      const d = await r.json()
      setJobData(d)
      const unanswered = (d.clarifications || []).filter(c => !c.user_answer)
      const hasPendingClarifications = unanswered.length > 0
      const newPhase = hasPendingClarifications ? 'intake' : getPhase(d.job?.status)
      setPhase(newPhase)

      // Toon eerste onbeantwoorde clarification vraag in chat.
      const nextQuestion = unanswered[0]?.question || d.job?.context?.brief?.clarifications?.[0]?.question
      if (nextQuestion) {
        setMessages(p => {
          const lastMsg = p[p.length - 1]
          if (lastMsg?.from === 'ceo' && lastMsg?.text === nextQuestion) return p
          return [...p, { from: 'ceo', text: nextQuestion }]
        })
      }

      return d
    } catch {
      return null
    }
  }

  const startPolling = (id) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      const d = await loadJob(id)
      if (!d) return
      const status = d.job?.status
      const hasPendingClarifications = (d.clarifications || []).some(c => !c.user_answer)
      // Stop polling als we in een stabiele fase zitten
      if (!hasPendingClarifications && ['PLAN_PROPOSED', 'JOB_READY', 'COMPLETED', 'FAILED'].includes(status)) {
        clearInterval(pollRef.current)
        // Toon CEO vragen als die er zijn
        if (status === 'PLAN_PROPOSED') {
          setMessages(p => [...p, { from: 'ceo', text: 'Plan is klaar. Bekijk het hieronder.' }])
        }
      }
    }, 2000)
  }

  const send = async () => {
    if (!input.trim() || loading) return
    const text = input.trim()
    setInput('')
    setMessages(p => [...p, { from: 'user', text }])
    setLoading(true)

    try {
      if (!jobId) {
        // Nieuwe job aanmaken
        const r = await fetch(API + '/api/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_post: text, user_id: 'anonymous', source_platform: 'custom' })
        })
        if (!r.ok) {
          const err = await r.json().catch(() => ({}))
          throw new Error(err.detail || 'Server error ' + r.status)
        }
        const d = await r.json()
        const newId = d.job_id
        setJobId(newId)
        setMessages(p => [...p, { from: 'ceo', text: 'Job aangemaakt. Mr. Klein analyseert...' }])
        startPolling(newId)

        // Laad direct jobdata; loadJob toont eventuele clarification vraag.
        setTimeout(() => {
          loadJob(newId)
        }, 1500)
      } else {
        // Antwoord geven op clarification vragen
        const clars = jobData?.clarifications || []
        const unanswered = clars.filter(c => !c.user_answer)
        const answersMap = {}
        if (unanswered.length > 0) {
          answersMap[unanswered[0].question_id] = text
        } else {
          answersMap['general'] = text
        }

        const r = await fetch(API + '/api/jobs/' + jobId + '/answer', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ answers: answersMap })
        })
        if (!r.ok) {
          const err = await r.json().catch(() => ({}))
          throw new Error(err.detail || 'Server error ' + r.status)
        }
        setMessages(p => [...p, { from: 'ceo', text: 'Antwoord ontvangen. Opnieuw analyseren...' }])
        startPolling(jobId)
      }
    } catch (err) {
      setMessages(p => [...p, { from: 'ceo', text: 'Fout: ' + err.message }])
    }
    setLoading(false)
  }

  const approvePlan = async () => {
    setLoading(true)
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 180000)
      const r = await fetch(API + '/api/jobs/' + jobId + '/approve-plan', { method: 'POST', signal: controller.signal })
      clearTimeout(timeoutId)
      if (!r.ok) throw new Error('Plan goedkeuren mislukt')
      setPhase('tracker')
      startPolling(jobId)
    } catch (err) {
      alert(err.message)
    }
    setLoading(false)
  }

  const submitFeedback = async () => {
    if (!feedback.trim()) return
    setLoading(true)
    try {
      await fetch(API + '/api/jobs/' + jobId + '/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback })
      })
      setFeedback('')
      setShowFeedback(false)
      setPhase('tracker')
      startPolling(jobId)
    } catch {}
    setLoading(false)
  }

  const approveAndDeploy = async () => {
    setLoading(true)
    try {
      await fetch(API + '/api/jobs/' + jobId + '/approve', { method: 'POST' })
      setPhase('done')
    } catch {}
    setLoading(false)
  }

  const stepList = ['intake', 'plan', 'tracker', 'review']
  const labels = { intake: 'Intake', plan: 'Plan', tracker: 'Uitvoering', review: 'Review' }
  const ci = stepList.indexOf(phase)
  const job = jobData?.job
  const steps = jobData?.steps || []
  const rawPlan = job?.context?.plan ?? job?.context?.execution_plan ?? []
  const plan = Array.isArray(rawPlan) ? rawPlan : (Array.isArray(rawPlan?.steps) ? rawPlan.steps : [])

  // Group raw step events by step_name so UI shows one logical task with latest state.
  const groupedSteps = Object.values(
    steps.reduce((acc, step, idx) => {
      const key = step.step_name || `step_${idx}`
      if (!acc[key]) {
        acc[key] = {
          key,
          name: step.step_name || step.agent_role || `Stap ${idx + 1}`,
          records: [],
          firstIndex: Number.isFinite(step.step_index) ? step.step_index : idx + 1
        }
      }
      acc[key].records.push(step)
      if (Number.isFinite(step.step_index)) {
        acc[key].firstIndex = Math.min(acc[key].firstIndex, step.step_index)
      }
      return acc
    }, {})
  )
    .sort((a, b) => a.firstIndex - b.firstIndex)
    .map(group => {
      const latest = group.records[group.records.length - 1]
      return {
        ...group,
        latest,
        status: normalizeStepStatus(latest?.status)
      }
    })

  const doneCount = groupedSteps.filter(s => s.status === 'success').length
  const latestActivityMs = steps.reduce((acc, s) => {
    const ts = new Date(s.created_at || s.started_at || s.completed_at || 0).getTime()
    return Number.isFinite(ts) ? Math.max(acc, ts) : acc
  }, 0)
  const idleSeconds = latestActivityMs ? (nowMs - latestActivityMs) / 1000 : Number.POSITIVE_INFINITY
  const heartbeatLevel = !latestActivityMs ? 'gray' : idleSeconds <= 8 ? 'green' : idleSeconds <= 25 ? 'orange' : 'gray'
  const hb = heartbeatMeta(heartbeatLevel)
  const planRoleTotals = plan.reduce((acc, step) => {
    const role = step?.agent_role || step?.role || step?.name || 'agent'
    acc[role] = (acc[role] || 0) + 1
    return acc
  }, {})

  const planTasks = plan.map((step, index) => {
    const role = step?.agent_role || step?.role || step?.name || 'agent'
    const roleStepName = roleToStepName(role)
    const roleOccurrence = plan.slice(0, index + 1).filter(s => (s?.agent_role || s?.role || s?.name || 'agent') === role).length
    const roleTotal = planRoleTotals[role] || 1

    const relatedEvents = steps.filter(s => s.step_name === roleStepName)
    const relatedSubEvents = steps.filter(s => typeof s.step_name === 'string' && s.step_name.startsWith(`${roleStepName}::`))
    const successCount = relatedEvents.filter(s => normalizeStepStatus(s.status) === 'success').length
    const inProgressCount = relatedEvents.filter(s => normalizeStepStatus(s.status) === 'in_progress').length

    let status = 'pending'
    if (successCount >= roleOccurrence) {
      status = 'success'
    } else if (inProgressCount > 0 && successCount + 1 === roleOccurrence) {
      status = 'in_progress'
    }

    const subtaskOrder = ['prepare', 'execute', 'finalize']
    const subtaskStatus = subtaskOrder.reduce((acc, key) => {
      const ev = relatedSubEvents.filter(s => s.step_name === `${roleStepName}::${key}`)
      const latest = ev[ev.length - 1]
      acc[key] = latest ? normalizeStepStatus(latest.status) : 'pending'
      return acc
    }, {})

    // Backward-compat for existing rows without subtask events.
    if (relatedSubEvents.length === 0) {
      if (status === 'success') {
        subtaskStatus.prepare = 'success'
        subtaskStatus.execute = 'success'
        subtaskStatus.finalize = 'success'
      } else if (status === 'in_progress') {
        subtaskStatus.prepare = 'success'
        subtaskStatus.execute = 'in_progress'
      }
    }

    return {
      id: `${role}-${index}`,
      index,
      role,
      roleOccurrence,
      roleTotal,
      description: step?.description || 'Taak wordt uitgevoerd',
      status,
      subtasks: subtaskOrder.map(name => ({
        name,
        label: subtaskLabel(name),
        status: subtaskStatus[name] || 'pending'
      }))
    }
  })

  const taskDoneCount = planTasks.filter(t => t.status === 'success').length
  const generatedText = (
    ((jobData?.artifacts || [])
      .map(a => (a?.proposed_data || {}).text)
      .find(t => typeof t === 'string' && t.trim().length > 0)) ||
    jobData?.job?.context?.copy_agent?.data?.draft_text ||
    jobData?.job?.context?.copy_agent?.content ||
    ''
  ).trim()

  return (
    <PageLayout size="wide" padded>
      {/* Stepper */}
      <div className="flex items-center gap-2 mb-8">
        {stepList.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div className={"flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium " +
              (i < ci ? 'bg-green-100 text-green-700' : i === ci ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-400')}>
              {i < ci && <CheckCircle className="w-3 h-3" />}
              {labels[s]}
            </div>
            {i < stepList.length - 1 && <div className={"w-8 h-px " + (i < ci ? 'bg-green-300' : 'bg-gray-200')} />}
          </div>
        ))}
      </div>

      <div className="panel-card">

        {/* INTAKE */}
        {phase === 'intake' && (
          <div className="flex flex-col max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Nieuwe Job</h2>
            <div className="overflow-y-auto space-y-4 mb-4 min-h-64 max-h-96">
              {messages.map((msg, i) => (
                <div key={i} className={"flex gap-3 " + (msg.from === 'user' ? 'justify-end' : 'justify-start')}>
                  {msg.from === 'ceo' && (
                    <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                      <Sparkles className="w-4 h-4 text-indigo-600" />
                    </div>
                  )}
                  <div className={"max-w-sm px-4 py-3 rounded-2xl text-sm " +
                    (msg.from === 'user' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-800')}>
                    {msg.text}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center">
                    <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
            <div className="flex gap-2">
              <input value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && send()}
                placeholder="Beschrijf je job..."
                className="flex-1 px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-sm"
                disabled={loading} />
              <button onClick={send} disabled={loading || !input.trim()}
                className="px-4 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-40">
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* PLAN */}
        {phase === 'plan' && (
          <div className="max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Uitvoeringsplan</h2>
            <p className="text-gray-500 text-sm mb-6">Mr. Klein heeft het team samengesteld. Keur goed om te starten.</p>
            <div className="space-y-3 mb-6 bg-gray-50 rounded-xl p-4">
              {plan.length === 0 ? (
                <p className="text-gray-400 text-sm text-center py-2">Plan wordt geladen...</p>
              ) : (
                plan.map((step, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-white border border-gray-100">
                    <div className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-bold flex-shrink-0">{i + 1}</div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-gray-800">
                        {step.description || 'Taak'}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {(() => {
                          const role = step.agent_role || step.role || step.name || 'agent'
                          const roleOccurrence = plan.slice(0, i + 1).filter(s => (s.agent_role || s.role || s.name || 'agent') === role).length
                          const roleTotal = plan.filter(s => (s.agent_role || s.role || s.name || 'agent') === role).length
                          return `${role} (${roleOccurrence}/${roleTotal})`
                        })()}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="flex justify-end">
              <button onClick={approvePlan} disabled={loading}
                className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-40 font-medium">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                Start Workflow
              </button>
            </div>
          </div>
        )}

        {/* TRACKER */}
        {phase === 'tracker' && (
          <div className="max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Live Voortgang</h2>
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-2.5 h-2.5 rounded-full ${hb.dotClass}`} />
              <span className={`text-xs font-medium ${hb.textClass}`}>{hb.label}</span>
            </div>
            <p className="text-gray-500 text-sm mb-2">Agents werken. Updates verschijnen live.</p>
            <p className="text-gray-400 text-xs mb-6">
              {planTasks.length > 0 ? `${taskDoneCount}/${planTasks.length} taken afgerond` : `${doneCount}/${groupedSteps.length || 0} taken afgerond`}
            </p>
            <div className="space-y-3">
              {(planTasks.length > 0 ? planTasks : groupedSteps).length === 0 ? (
                <div className="text-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-400 mx-auto mb-2" />
                  <p className="text-gray-400 text-sm">Wachten op eerste stap...</p>
                </div>
              ) : (
                (planTasks.length > 0 ? planTasks : groupedSteps).map((step, i) => (
                  <div key={step.id || step.key || i} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4">
                    {step.status === 'success' ? <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                      : step.status === 'failed' ? <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                      : step.status === 'in_progress' ? <Loader2 className="w-5 h-5 animate-spin text-indigo-500 flex-shrink-0" />
                        : <Circle className="w-5 h-5 text-gray-300 flex-shrink-0" />}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-800">
                        {step.description || step.name || 'Stap ' + (i + 1)}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {step.role ? `${step.role} (${step.roleOccurrence}/${step.roleTotal}) • ` : ''}
                        Status: {step.status}
                      </div>
                      {step.subtasks && step.subtasks.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {step.subtasks.map(st => (
                            <span
                              key={st.name}
                              className={
                                "text-[11px] px-2 py-0.5 rounded-full border " +
                                (st.status === 'success'
                                  ? 'bg-green-50 border-green-200 text-green-700'
                                  : st.status === 'in_progress'
                                    ? 'bg-indigo-50 border-indigo-200 text-indigo-700'
                                    : st.status === 'failed'
                                      ? 'bg-red-50 border-red-200 text-red-700'
                                      : 'bg-gray-50 border-gray-200 text-gray-500')
                              }
                            >
                              {st.label}: {st.status}
                            </span>
                          ))}
                        </div>
                      )}
                      {step.latest?.error && <div className="text-xs text-red-500 mt-0.5">{step.latest.error}</div>}
                    </div>
                    <div className="text-xs text-gray-400 flex-shrink-0">
                      {step.latest?.tokens_used ? step.latest.tokens_used + ' tokens' : ''}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* REVIEW */}
        {phase === 'review' && (
          <div className="max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Beoordeel Resultaat</h2>
            <p className="text-gray-500 text-sm mb-6">Keur goed om te deployen, of vraag aanpassingen.</p>
            <div className="bg-indigo-50 border border-indigo-200 rounded-2xl p-5 mb-4">
              <div className="flex gap-3">
                <Sparkles className="w-5 h-5 text-indigo-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-indigo-700">
                  {job?.context?.ceo_summary || 'Job is gereed voor goedkeuring.'}
                </div>
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-2xl p-5 mb-6">
              <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">Gegenereerde tekst</div>
              {generatedText ? (
                <pre className="whitespace-pre-wrap text-sm text-gray-800 leading-6 font-sans">{generatedText}</pre>
              ) : (
                <p className="text-sm text-gray-500">Nog geen tekst gevonden in artifacts.</p>
              )}
            </div>
            {!showFeedback ? (
              <div className="flex gap-3">
                <button onClick={() => setShowFeedback(true)}
                  className="flex-1 px-6 py-3 border border-gray-200 rounded-xl text-sm font-medium hover:bg-gray-50">
                  Aanpassingen vragen
                </button>
                <button onClick={approveAndDeploy} disabled={loading}
                  className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-green-600 text-white rounded-xl hover:bg-green-700 disabled:opacity-40 text-sm font-medium">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                  Approve & Deploy
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <textarea value={feedback} onChange={e => setFeedback(e.target.value)}
                  placeholder="Wat moet er anders?"
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm outline-none resize-none" rows={3} />
                <div className="flex gap-3">
                  <button onClick={() => setShowFeedback(false)} className="px-4 py-2 text-gray-500 text-sm">Annuleer</button>
                  <button onClick={submitFeedback} disabled={loading || !feedback.trim()}
                    className="flex-1 px-6 py-3 bg-indigo-600 text-white rounded-xl text-sm font-medium disabled:opacity-40">
                    Feedback versturen
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* DONE */}
        {phase === 'done' && (
          <div className="text-center py-12">
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Job voltooid</h2>
            <p className="text-gray-500 mb-6">De job is succesvol uitgevoerd.</p>
            <button onClick={() => {
              setJobData(null); setPhase('intake'); setJobId(null)
              setMessages([{ from: 'ceo', text: 'Hallo. Beschrijf je volgende job.' }])
              if (pollRef.current) clearInterval(pollRef.current)
            }} className="px-6 py-3 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700">
              Nieuwe Job
            </button>
          </div>
        )}

      </div>
    </PageLayout>
  )
}
