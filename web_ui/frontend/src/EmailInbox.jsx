import { useEffect, useState, useCallback, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import PageLayout from './PageLayout'
import { apiFetch, fetchJson } from './apiClient'
import { Inbox, Send, Loader2, ChevronDown, ChevronRight, ExternalLink, Play } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import { queryKeys } from './queryKeys'

const POLL_INTERVAL_MS = 10_000

const STATUS_BADGE = {
  new: 'bg-gray-100 text-gray-700',
  analyzing: 'bg-gray-100 text-gray-700',
  in_chat: 'bg-blue-100 text-blue-800',
  plan_ready: 'bg-green-100 text-green-800',
  converted_to_job: 'bg-purple-100 text-purple-800',
  rejected_sender: 'bg-red-100 text-red-800',
  error: 'bg-red-100 text-red-800',
}

function StatusBadge({ status }) {
  const cls = STATUS_BADGE[status] || 'bg-gray-100 text-gray-700'
  const isPlanReady = status === 'plan_ready'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {isPlanReady && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500" />
        </span>
      )}
      {status}
    </span>
  )
}

function relativeTime(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  const now = new Date()
  const s = Math.floor((now - d) / 1000)
  if (s < 60) return 'zojuist'
  if (s < 3600) return `${Math.floor(s / 60)}m`
  if (s < 86400) return `${Math.floor(s / 3600)}u`
  if (s < 604800) return `${Math.floor(s / 86400)}d`
  return d.toLocaleDateString('nl-NL')
}

function extractPlanFromContent(content) {
  if (!content || typeof content !== 'string') return null
  const start = content.indexOf('%%PLAN%%')
  const end = content.indexOf('%%/PLAN%%', start)
  if (start === -1 || end === -1) return null
  try {
    const raw = content.slice(start + 8, end).trim()
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function PlanCard({ plan, showStartButton, onStartJob, converting }) {
  if (!plan || !plan.steps?.length) return null
  const steps = Array.isArray(plan.steps) ? plan.steps : []
  const score = plan.completeness_score
  const assumptions = plan.assumptions || []
  return (
    <div className="rounded-xl border border-green-200 bg-green-50/80 p-4 mt-3">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-green-900">Plan</h4>
        {typeof score === 'number' && (
          <span className="text-xs font-medium text-green-700">Score: {(score * 100).toFixed(0)}%</span>
        )}
      </div>
      <ul className="space-y-2 mb-3">
        {steps.map((s, i) => (
          <li key={i} className="flex items-center gap-2 text-sm">
            <span className="px-2 py-0.5 rounded bg-slate-200 text-slate-800 text-xs font-medium">
              {s.agent_role || 'step'}
            </span>
            <span className="text-slate-700">{s.description || '—'}</span>
          </li>
        ))}
      </ul>
      {assumptions.length > 0 && (
        <div className="text-xs text-amber-800 bg-amber-100/80 rounded p-2 mb-3">
          <span className="font-medium">Aannames:</span>{' '}
          {assumptions.map((a) => (typeof a === 'string' ? a : JSON.stringify(a))).join('; ')}
        </div>
      )}
      {showStartButton && (
        <button
          type="button"
          onClick={onStartJob}
          disabled={converting}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-green-600 text-white font-medium hover:bg-green-700 disabled:opacity-50"
        >
          {converting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Start Job →
        </button>
      )}
    </div>
  )
}

export default function EmailInbox() {
  const [emails, setEmails] = useState([])
  const [selectedEmailId, setSelectedEmailId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [sending, setSending] = useState(false)
  const [convertLoading, setConvertLoading] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [showBody, setShowBody] = useState(true)
  const messagesEndRef = useRef(null)
  const fetchWithAuth = useCallback((url, opts = {}) => apiFetch(url, opts), [])

  const {
    data: listData = [],
    isLoading: loading,
    refetch: refetchList,
  } = useQuery({
    queryKey: ['inbox-list', ...queryKeys.inboxSummary()],
    queryFn: () => fetchJson('/api/inbox'),
    refetchInterval: POLL_INTERVAL_MS,
  })
  const { data: detailData, refetch: refetchDetail } = useQuery({
    queryKey: ['inbox-detail', selectedEmailId],
    queryFn: () => fetchJson(`/api/inbox/${encodeURIComponent(selectedEmailId)}`),
    enabled: !!selectedEmailId,
  })

  useEffect(() => {
    setEmails(Array.isArray(listData) ? listData : [])
  }, [listData])

  useEffect(() => {
    if (!selectedEmailId) {
      setDetail(null)
      return
    }
    setDetail(detailData || null)
  }, [selectedEmailId, detailData])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [detail?.messages?.length])

  const handleSendMessage = async () => {
    const text = chatInput.trim()
    if (!text || !detail?.email?.chat_id || !detail?.email?.agent_id || sending) return
    setSending(true)
    setChatInput('')
    const optimisticMsg = { role: 'user', content: text, created_at: new Date().toISOString() }
    setDetail((prev) => ({
      ...prev,
      messages: [...(prev?.messages || []), optimisticMsg],
    }))
    try {
      const res = await fetchWithAuth(
        `/api/agents/${encodeURIComponent(detail.email.agent_id)}/chats/${encodeURIComponent(detail.email.chat_id)}/message`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text }),
        }
      )
      const data = await res.json().catch(() => ({}))
      if (res.ok && !data.error && data.agent_response) {
        const agentMsg = {
          role: 'agent',
          content: data.agent_response,
          created_at: new Date().toISOString(),
        }
        setDetail((prev) => ({
          ...prev,
          messages: [...(prev?.messages || []).filter((m) => m.content !== text), optimisticMsg, agentMsg],
        }))
        refetchDetail()
      } else {
        setDetail((prev) => ({
          ...prev,
          messages: (prev?.messages || []).filter((m) => m.content !== text),
        }))
      }
    } catch {
      setDetail((prev) => ({
        ...prev,
        messages: (prev?.messages || []).filter((m) => m.content !== text),
      }))
    } finally {
      setSending(false)
    }
  }

  const handleConvertToJob = async () => {
    if (!selectedEmailId || convertLoading || detail?.email?.status !== 'plan_ready') return
    setConvertLoading(true)
    try {
      const res = await fetchWithAuth(`/api/inbox/${encodeURIComponent(selectedEmailId)}/convert`, {
        method: 'POST',
      })
      if (res.ok) {
        const data = await res.json()
        refetchDetail()
        refetchList()
        if (data.job_id) {
          setDetail((prev) => ({ ...prev, email: { ...prev?.email, status: 'converted_to_job', job_id: data.job_id } }))
        }
      }
    } finally {
      setConvertLoading(false)
    }
  }

  const email = detail?.email
  const messages = detail?.messages || []
  const lastPlanIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'agent' && extractPlanFromContent(messages[i].content)) return i
    }
    return -1
  })()
  const isConverted = email?.status === 'converted_to_job'

  return (
    <PageLayout padded={false} className="h-[calc(100vh-4rem)]">
      <div className="flex h-full border border-slate-200 rounded-xl bg-white overflow-hidden">
        {/* Left: email list */}
        <div className="w-96 border-r border-slate-200 flex flex-col bg-slate-50/50">
          <div className="p-3 border-b border-slate-200 flex items-center gap-2">
            <Inbox className="w-5 h-5 text-slate-600" />
            <h1 className="font-semibold text-slate-800">Inbox</h1>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading && emails.length === 0 ? (
              <div className="p-4 flex justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
              </div>
            ) : emails.length === 0 ? (
              <p className="p-4 text-sm text-slate-500">Geen e-mails</p>
            ) : (
              emails.map((em) => (
                <button
                  key={em.email_id}
                  type="button"
                  onClick={() => setSelectedEmailId(em.email_id)}
                  className={`w-full text-left p-3 border-b border-slate-100 hover:bg-slate-100/80 transition ${
                    selectedEmailId === em.email_id ? 'bg-white border-l-2 border-l-indigo-500' : ''
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-slate-800 truncate flex-1">
                      {em.from_name || em.from_address || '—'}
                    </span>
                    <StatusBadge status={em.status} />
                  </div>
                  <div className="text-sm text-slate-600 truncate">{em.subject || '—'}</div>
                  <div className="text-xs text-slate-400 mt-1">{relativeTime(em.received_at)}</div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Right: chat + action */}
        <div className="flex-1 flex flex-col min-w-0">
          {!email ? (
            <div className="flex-1 flex items-center justify-center text-slate-500">
              Selecteer een e-mail
            </div>
          ) : (
            <>
              <div className="p-4 border-b border-slate-200 bg-white">
                <h2 className="font-semibold text-slate-900 truncate">{email.subject || '—'}</h2>
                <p className="text-sm text-slate-600 mt-0.5">
                  {email.from_name || email.from_address} · {relativeTime(email.received_at)}
                </p>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Collapsible original email */}
                <div className="rounded-lg border border-slate-200 bg-slate-50/80 overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setShowBody((b) => !b)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100/80"
                  >
                    {showBody ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    Originele e-mail
                  </button>
                  {showBody && (
                    <div className="px-3 pb-3 pt-0 text-sm text-slate-700 whitespace-pre-wrap border-t border-slate-100">
                      {email.body_clean || '—'}
                    </div>
                  )}
                </div>

                {/* Chat thread */}
                <div className="space-y-3">
                  {messages.map((m, idx) => {
                    const isUser = m.role === 'user'
                    const plan = m.role === 'agent' ? extractPlanFromContent(m.content) : null
                    const isLastPlan = plan && lastPlanIndex === idx
                    const textWithoutPlan =
                      m.role === 'agent' && m.content
                        ? m.content
                            .replace(/\s*%%PLAN%%.*?%%\/PLAN%%\s*/s, '')
                            .trim()
                        : m.content
                    return (
                      <div
                        key={m.message_id || idx}
                        className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[85%] rounded-lg px-3 py-2 ${
                            isUser
                              ? 'bg-indigo-600 text-white rounded-tr-none'
                              : 'bg-slate-100 text-slate-800 rounded-tl-none'
                          }`}
                        >
                          {!isUser && <span className="text-xs text-slate-500 block mb-1">CEO</span>}
                          {textWithoutPlan && (
                            <div className="text-sm prose prose-sm max-w-none">
                              <ReactMarkdown remarkPlugins={[remarkBreaks]}>{textWithoutPlan}</ReactMarkdown>
                            </div>
                          )}
                          {plan && (
                            <PlanCard
                              plan={plan}
                              showStartButton={isLastPlan && email?.status === 'plan_ready'}
                              onStartJob={handleConvertToJob}
                              converting={convertLoading}
                            />
                          )}
                        </div>
                      </div>
                    )
                  })}
                  <div ref={messagesEndRef} />
                </div>
              </div>

              {isConverted ? (
                <div className="p-4 border-t border-slate-200 bg-slate-50/50">
                  {email.job_id ? (
                    <Link
                      to={`/jobs/${email.job_id}`}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700"
                    >
                      <ExternalLink className="w-4 h-4" />
                      Bekijk Job →
                    </Link>
                  ) : (
                    <span className="text-sm text-slate-500">Job aangemaakt</span>
                  )}
                </div>
              ) : (
                email.chat_id &&
                email.agent_id && (
                  <div className="p-4 border-t border-slate-200 flex gap-2">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
                      placeholder="Bericht..."
                      className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      disabled={sending}
                    />
                    <button
                      type="button"
                      onClick={handleSendMessage}
                      disabled={sending || !chatInput.trim()}
                      className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2"
                    >
                      {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                      Verstuur
                    </button>
                  </div>
                )
              )}
            </>
          )}
        </div>
      </div>
    </PageLayout>
  )
}
