import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Upload, X, Paperclip, FileSpreadsheet, FileText, Image as ImageIcon, MessageCircle, Play, CheckCircle, XCircle, BookOpen, BookMarked, BookX, Layers } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import PageLayout from './PageLayout'
import DocumentViewer from './components/DocumentViewer'
import { apiUrl, apiFetch, fetchJson } from './apiClient'
import { useJobWebSocket } from './hooks/useJobWebSocket'

/** Parses job context (object or JSON string). Never throws; returns {} on invalid input. */
function parseContext(ctx) {
  if (ctx == null) return {}
  if (typeof ctx === 'object' && !Array.isArray(ctx)) return ctx
  try {
    const parsed = JSON.parse(ctx)
    if (typeof parsed === 'string') return JSON.parse(parsed)
    return typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed) ? parsed : {}
  } catch {
    return {}
  }
}

/** Parses jobs.payload (JSONB / object / string). */
function parsePayload(raw) {
  if (raw == null) return {}
  if (typeof raw === 'object' && !Array.isArray(raw)) return raw
  try {
    const parsed = JSON.parse(String(raw))
    return typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed) ? parsed : {}
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
  BLOCKED: 'bg-amber-200 text-amber-950',
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

const EVENT_ICONS = {
  TaskCreated: Play,
  TaskEvidenceCollected: FileText,
  TaskFixProposed: FileText,
  TaskValidated: CheckCircle,
  TaskRejected: XCircle,
  LessonProposed: BookOpen,
  LessonApproved: BookMarked,
  LessonRejected: BookX,
  PatternRegistered: Layers
}

function EventTimeline({ events }) {
  if (!events?.length) return null
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
      <h3 className="text-sm font-medium text-slate-700 mb-3">Events</h3>
      <ul className="space-y-2">
        {events.map((ev) => {
          const Icon = EVENT_ICONS[ev.event_type] || FileText
          const isGreen = ev.event_type === 'TaskValidated' || ev.event_type === 'LessonApproved'
          const isRed = ev.event_type === 'TaskRejected' || ev.event_type === 'LessonRejected'
          const time = ev.created_at ? new Date(ev.created_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''
          return (
            <li key={ev.event_id} className="flex items-center gap-3 text-sm">
              <span className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${isGreen ? 'bg-green-100 text-green-700' : isRed ? 'bg-red-100 text-red-700' : 'bg-slate-200 text-slate-600'}`}>
                <Icon className="w-4 h-4" />
              </span>
              <span className="flex-1 min-w-0 font-medium text-slate-800">{ev.event_type}</span>
              {ev.confidence_score != null && (
                <span className="flex-shrink-0 text-xs px-2 py-0.5 rounded bg-indigo-100 text-indigo-800 font-medium">
                  {(ev.confidence_score * 100).toFixed(0)}%
                </span>
              )}
              <span className="flex-shrink-0 text-xs text-slate-500">{time}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function getAttachmentIcon(filename) {
  const ext = (filename || '').toLowerCase().split('.').pop()
  if (['xlsx', 'xls', 'csv'].includes(ext)) return FileSpreadsheet
  if (['pdf', 'docx', 'txt', 'md'].includes(ext)) return FileText
  if (['png', 'jpg', 'jpeg'].includes(ext)) return ImageIcon
  return Paperclip
}

function AttachmentPill({ attachment, isUserBubble }) {
  const filename = attachment?.filename || 'bestand'
  const url = attachment?.url
  const summary = attachment?.summary
  const Icon = getAttachmentIcon(filename)
  const pillClass = isUserBubble
    ? 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/20 text-white/95 text-xs font-medium mb-1.5 w-fit hover:bg-white/30 cursor-pointer transition'
    : 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-200/80 text-slate-700 text-xs font-medium mb-1.5 w-fit hover:bg-slate-300/80 cursor-pointer transition'

  const handleClick = () => {
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
  }

  // Tooltip: summary als beschikbaar, anders edge case (leeg) of default
  let tooltip = url ? 'Open bestand in nieuw tabblad' : 'Bestand verwerkt door agent'
  if (typeof summary === 'string' && summary.length > 0) {
    tooltip = summary
  } else if (attachment) {
    tooltip = 'Bestand ontvangen — inhoud kon niet worden gelezen'
  }

  return (
    <span
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(e) => e.key === 'Enter' && handleClick()}
      title={tooltip}
      className={pillClass}
    >
      <Icon className="w-3.5 h-3.5 shrink-0" />
      <span className="truncate max-w-[180px]">{filename}</span>
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
  const [attachedFile, setAttachedFile] = useState(null)
  const [extractedText, setExtractedText] = useState('')
  const [uploadingFile, setUploadingFile] = useState(false)
  const fileInputRef = useRef(null)
  const [chatAttachedFile, setChatAttachedFile] = useState(null)
  const chatFileInputRef = useRef(null)
  const chatSectionRef = useRef(null)
  const [events, setEvents] = useState([])
  const [jobSystemEvents, setJobSystemEvents] = useState([])
  const [serverKeys, setServerKeys] = useState(null)
  const [clients, setClients] = useState([])
  const [mentionSuggestions, setMentionSuggestions] = useState([])
  const [detectedClient, setDetectedClient] = useState(null)
  const [authError, setAuthError] = useState(false)
  const [ceoName, setCeoName] = useState(null)

  // CEO agent name for UI labels (fallback: "your AI agent")
  useEffect(() => {
    fetchJson('/api/agents/ceo')
      .then((d) => setCeoName(d?.name && typeof d.name === 'string' ? d.name : 'your AI agent'))
      .catch(() => setCeoName('your AI agent'))
  }, [])

  const ceoDisplayName = ceoName !== null ? ceoName : 'your AI agent'
  const ceoInitials = ceoDisplayName.split(/\s+/).filter(Boolean).map((w) => w[0]).join('').toUpperCase().slice(0, 2) || 'AI'
  const { jobData: wsJob } = useJobWebSocket(jobId)

  const fetchJob = useCallback(async () => {
    if (!jobId) return null
    setLoading(true)
    setError(null)
    setAuthError(false)
    let rethrowServerError = false
    try {
      const res = await apiFetch(`/api/jobs/${jobId}`)
      if (!res.ok) {
        if (res.status === 404) throw new Error('Job not found')
        if (res.status === 401) {
          setError('Session expired or unauthorized. Please log in again.')
          setAuthError(true)
          return null
        }
        if (res.status >= 500) {
          rethrowServerError = true
          throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to load job')
        }
        throw new Error('Failed to load job')
      }
      let json
      try {
        json = await res.json()
      } catch (_) {
        setError('Invalid response from server.')
        return null
      }
      setData(json)
      return json
    } catch (err) {
      // ASSUMPTION: 5xx and network errors go to ErrorBoundary
      if (rethrowServerError || (err.name === 'TypeError' && err.message?.includes('fetch'))) throw err
      setError(err.message || 'Failed to load job')
      return null
    } finally {
      setLoading(false)
    }
  }, [jobId])

  // Initial load remains HTTP-based; live updates come from WebSocket.
  useEffect(() => {
    if (!jobId) return
    fetchJob()
  }, [jobId, fetchJob])

  // Merge partial/full websocket job updates into local state.
  useEffect(() => {
    if (!wsJob) return
    setData((prev) => {
      if (!prev) return { job: wsJob }
      return {
        ...prev,
        job: {
          ...(prev.job || {}),
          ...wsJob,
        },
      }
    })
  }, [wsJob])

  // When background tasks don't run (e.g. exe.xyz): trigger intake synchronously when user opens job in INTAKE_CLARIFICATION with no plan yet
  useEffect(() => {
    if (!jobId || !data?.job) return
    if (data.job.status !== 'INTAKE_CLARIFICATION') return
    const ctx = parseContext(data.job.context)
    if (ctx.plan && (ctx.plan.steps?.length ?? 0) > 0) return
    if (runIntakeTriggeredRef.current === jobId) return
    runIntakeTriggeredRef.current = jobId
    setRunningIntake(true)
    apiFetch(`/api/jobs/${jobId}/run-intake`, { method: 'POST' })
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

  // V4: Event timeline — fetch events when job detail is open
  useEffect(() => {
    if (!jobId) return
    apiFetch(`/api/events?job_id=${encodeURIComponent(jobId)}&limit=50`)
      .then((res) => (res.ok ? res.json() : { events: [] }))
      .then((d) => setEvents(d.events || []))
      .catch(() => setEvents([]))
  }, [jobId])

  // Platform system events for this job (Optie C: job-detail view)
  useEffect(() => {
    if (!jobId) return
    apiFetch(`/api/jobs/${jobId}/system-events`)
      .then((res) => (res.ok ? res.json() : { events: [] }))
      .then((d) => setJobSystemEvents(d.events || []))
      .catch(() => setJobSystemEvents([]))
  }, [jobId])

  // Derived values before any useEffect that uses them (avoids TDZ: job was used in deps before declaration)
  const job = data?.job
  const steps = data?.steps ?? []
  const artifacts = data?.artifacts ?? []
  const context = job ? parseContext(job.context) : {}
  const jobPayload = job ? parsePayload(job.payload) : {}
  const imageUrl = context.image_url
  const plan = context.plan || {}
  const planSteps = Array.isArray(plan.steps) ? plan.steps : []
  const chatHistory = Array.isArray(context.chat_history) ? context.chat_history : []
  const clarifications = data?.clarifications ?? []
  const statusStr = job?.status != null ? String(job.status) : ''
  const statusUpper = statusStr.toUpperCase()
  const isIntake = statusUpper === 'INTAKE_CLARIFICATION'

  // Volledige conversatie: initiële job_post + chat_history + clarification-antwoorden (backend zet die niet in chat_history)
  const fullChatHistory = (() => {
    const list = []
    const jobPost = (job?.job_post || context.job_post || context.brief?.job_post || '').trim()
    if (jobPost) list.push({ role: 'user', content: jobPost })
    list.push(...chatHistory)
    const answered = clarifications.filter((c) => c.user_answer)
    if (answered.length) {
      const text = answered
        .map((c) => (c.question ? `• ${c.question}\n  ${c.user_answer}` : c.user_answer))
        .join('\n\n')
      list.push({ role: 'user', content: `Mijn antwoorden op de vragen:\n\n${text}` })
    }
    return list
  })()
  const displayChatHistory = [...fullChatHistory, ...optimisticMessages]
  const inputDisabled = sendingChat || statusUpper === 'BLOCKED'

  // When showing API key error, fetch current server fingerprint so user can compare
  useEffect(() => {
    if (job?.status !== 'INTAKE_CLARIFICATION') return
    const ctx = job?.context ? parseContext(job.context) : {}
    const briefCtx = ctx.brief?.context
    const errFp = briefCtx && typeof briefCtx === 'object' && briefCtx.key_fingerprint
    if (!errFp) return
    fetch(apiUrl('/api/status/keys'))
      .then((r) => (r.ok ? r.json() : null))
      .then((k) => (k ? setServerKeys(k) : setServerKeys({})))
      .catch(() => setServerKeys({}))
  }, [job?.status, job?.context])

  useEffect(() => {
    apiFetch('/api/clients')
      .then((r) => (r.ok ? r.json() : Promise.resolve([])))
      .then((data) => setClients(Array.isArray(data) ? data : (data?.clients ?? data ?? [])))
      .catch(() => setClients([]))
  }, [])

  useEffect(() => {
    if (!sendingChat && ceoTyping) {
      const t = setTimeout(() => setCeoTyping(false), 8000)
      return () => clearTimeout(t)
    }
  }, [sendingChat, ceoTyping])

  // Auto-scroll chat to bottom on each new message (or when typing indicator appears)
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [displayChatHistory.length, ceoTyping])

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
      const res = await apiFetch(`/api/jobs/${jobId}/approve-plan`, { method: 'POST', signal: controller.signal })
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
      const res = await apiFetch(`/api/jobs/${jobId}/approve`, { method: 'POST' })
      if (!res.ok) throw new Error('Failed to approve and deploy')
      await fetchJob()
    } catch (err) {
      setError(err.message)
    } finally {
      setApprovingDeploy(false)
    }
  }

  const [downloadingArtifact, setDownloadingArtifact] = useState(false)
  const handleDownloadArtifact = useCallback(async () => {
    if (!jobId) return
    setDownloadingArtifact(true)
    setError(null)
    setAuthError(false)
    try {
      const res = await apiFetch(`/api/jobs/${jobId}/download`, { method: 'GET' })
      if (!res.ok) {
        if (res.status === 401) {
          setAuthError(true)
          setError('Session expired or unauthorized. Please log in again.')
        } else if (res.status === 404) {
          setError('Geen bestand beschikbaar voor deze job.')
        } else {
          setError('Download mislukt.')
        }
        return
      }
      const blob = await res.blob()
      const name = job?.file_artifact_name || `job_${jobId}.docx`
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = name
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message || 'Download mislukt.')
    } finally {
      setDownloadingArtifact(false)
    }
  }, [jobId, job?.file_artifact_name])

  const handleFileSelect = async (files) => {
    const f = files?.[0]
    if (!f) return
    const ext = (f.name || '').toLowerCase().split('.').pop()
    const allowed = ['pdf', 'csv', 'md', 'docx', 'xlsx', 'xls', 'txt']
    if (!allowed.includes(ext)) {
      setError(`Bestandstype .${ext} niet ondersteund. Gebruik: ${allowed.join(', ')}`)
      return
    }
    setUploadingFile(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', f)
      const res = await apiFetch('/api/jobs/upload', { method: 'POST', body: form })
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        throw new Error(j.detail || 'Upload mislukt')
      }
      const data = await res.json()
      setAttachedFile(f)
      setExtractedText(data.extracted_text || '')
    } catch (err) {
      setError(err.message || 'Bestand uploaden mislukt')
    } finally {
      setUploadingFile(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const clearAttachment = () => {
    setAttachedFile(null)
    setExtractedText('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleChatFileSelect = (files) => {
    const f = files?.[0]
    if (!f) return
    const ext = (f.name || '').toLowerCase().split('.').pop()
    const allowed = ['pdf', 'csv', 'txt', 'docx', 'png', 'jpg', 'jpeg', 'md', 'xlsx', 'xls']
    if (!allowed.includes(ext)) {
      setError(`Bestandstype .${ext} niet toegestaan. Gebruik: ${allowed.join(', ')}`)
      return
    }
    setChatAttachedFile(f)
    setError(null)
  }

  const clearChatAttachment = () => {
    setChatAttachedFile(null)
    if (chatFileInputRef.current) chatFileInputRef.current.value = ''
  }

  const handleJobInputChange = (e) => {
    const val = e.target.value
    setChatInput(val)
    const match = val.match(/@([a-zA-Z0-9_-]*)$/)
    if (match) {
      const query = (match[1] || '').toLowerCase()
      const filtered = clients.filter(
        (c) =>
          (c.slug || '').toLowerCase().includes(query) ||
          (c.client_name || c.name || '').toLowerCase().includes(query)
      )
      setMentionSuggestions(filtered.slice(0, 5))
    } else {
      setMentionSuggestions([])
    }
  }

  const handleMentionSelect = (client) => {
    const slug = client.slug || client.client_name || ''
    setChatInput((prev) => prev.replace(/@([a-zA-Z0-9_-]*)$/, `@${slug} `))
    setMentionSuggestions([])
  }


  const handleSendMessage = async (e) => {
    e?.preventDefault()
    const msg = chatInput.trim()
    const hasChatAttachment = !!chatAttachedFile
    if ((!msg && !extractedText && !hasChatAttachment) || sendingChat) return

    if (!jobId) {
      const jobPost = extractedText
        ? (msg ? `${msg}\n\n--- Bijlage: ${attachedFile?.name || 'document'} ---\n${extractedText}` : `Document bijgevoegd:\n\n${extractedText}`)
        : msg
      if (jobPost.length < 10) {
        setError('Beschrijf je opdracht (min. 10 tekens) of voeg een bestand toe.')
        return
      }
      setSendingChat(true)
      setChatInput('')
      clearAttachment()
      try {
        const res = await apiFetch('/api/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: '00000000-0000-0000-0000-000000000001',
            job_post: jobPost,
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

    const fileToSend = chatAttachedFile
    setOptimisticMessages((prev) => [...prev, { role: 'user', content: msg, attachment: fileToSend ? { filename: fileToSend.name } : undefined }])
    setChatInput('')
    clearChatAttachment()
    setSendingChat(true)
    const sendingTimeout = setTimeout(() => setSendingChat(false), 15000)
    if (statusUpper === 'INTAKE_CLARIFICATION' || statusUpper === 'RUNNING') {
      setCeoTyping(true)
    }
    try {
      let res
      if (statusUpper === 'INTAKE_CLARIFICATION' || statusUpper === 'RUNNING') {
        const hasFile = !!fileToSend
        if (hasFile) {
          const form = new FormData()
          form.append('message', msg || '(bijlage)')
          form.append('file', fileToSend)
          res = await apiFetch(`/api/jobs/${jobId}/chat`, {
            method: 'POST',
            body: form
          })
        } else {
          res = await apiFetch(`/api/jobs/${jobId}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg })
          })
        }
      } else if (statusUpper === 'PLAN_PROPOSED') {
        res = await apiFetch(`/api/jobs/${jobId}/request-changes`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ feedback: msg })
        })
      } else if (statusUpper === 'JOB_READY' || statusUpper === 'AWAITING_APPROVAL' || statusUpper === 'COMPLETED') {
        res = await apiFetch(`/api/jobs/${jobId}/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ feedback: msg })
        })
      } else {
        setError('Chat not available for this status. Refresh the page.')
        setOptimisticMessages((prev) => prev.filter((m) => m.content !== msg))
        clearTimeout(sendingTimeout)
        setSendingChat(false)
        return
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to send message')
      }
      setOptimisticMessages([])
      // Refetch job so UI shows latest status (e.g. PLAN_PROPOSED after intake). Background task may take a few seconds.
      await fetchJob()
      if (statusUpper === 'INTAKE_CLARIFICATION' || statusUpper === 'RUNNING') {
        const pollDelays = [1000, 2000, 3500, 5500, 8000, 12000, 18000, 25000]
        pollDelays.forEach((ms) => setTimeout(() => fetchJob(), ms))
      }
    } catch (err) {
      setError(err.message)
      setOptimisticMessages((prev) => prev.filter((m) => m.content !== msg))
      setCeoTyping(false)
    } finally {
      clearTimeout(sendingTimeout)
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
          {authError ? (
            <button type="button" onClick={() => navigate('/login', { state: { from: `/jobs/${jobId}` } })} className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700">Log in again</button>
          ) : (
            <button type="button" onClick={() => { setError(null); setAuthError(false); fetchJob(); }} className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700">Retry</button>
          )}
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

  const jobPostText = job
    ? (typeof job.job_post === 'string' && job.job_post.trim()
        ? job.job_post
        : job.payload?.brief?.job_post || 'Job')
    : 'New Job'
  const title = jobPostText.slice(0, 60).trim() + (jobPostText.length > 60 ? '…' : '')

  return (
    <PageLayout size="wide" padded className="!max-w-none">
      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800 flex items-center justify-between gap-2 flex-wrap">
          <span className="text-sm">{error}</span>
          <button type="button" onClick={() => { setError(null); fetchJob(); }} className="text-sm font-medium text-red-600 hover:text-red-800 underline">Dismiss & refresh</button>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 min-h-[calc(100vh-8rem)]">
        {/* Left: Chat — on mobile order-2 (below viewer) */}
        <div ref={chatSectionRef} className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden min-h-0 order-2 md:order-1 overflow-y-auto">
          <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200 flex items-center justify-between gap-2">
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-slate-900 truncate">{title}</h2>
              {!job && <p className="text-xs text-slate-500 mt-0.5">Chat with {ceoDisplayName} — describe your project</p>}
            </div>
            {job && <StatusBadge status={job.status} />}
            {job?.intake_source === 'email' && (
              <span style={{
                background: '#EBF5FB', color: '#1A5276',
                borderRadius: '4px', padding: '2px 8px',
                fontSize: '11px', marginLeft: '6px'
              }}>✉ Via Email</span>
            )}
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto space-y-4 p-4">
            {statusUpper === 'BLOCKED' && (
              <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950">
                <h3 className="text-base font-semibold text-amber-950 mb-2">Job geblokkeerd</h3>
                <p className="text-sm text-amber-900 whitespace-pre-wrap mb-3">
                  {jobPayload.block_reason || 'Deze job kan niet worden uitgevoerd.'}
                </p>
                {Array.isArray(jobPayload.missing_roles) && jobPayload.missing_roles.length > 0 && (
                  <div className="text-sm">
                    <p className="font-medium text-amber-950 mb-1">Ontbrekende rollen</p>
                    <ul className="list-disc pl-5 space-y-0.5 text-amber-900 mb-3">
                      {jobPayload.missing_roles.map((role, i) => (
                        <li key={i}>{typeof role === 'string' ? role : JSON.stringify(role)}</li>
                      ))}
                    </ul>
                    <Link
                      to={`/hr/blocked-jobs?job_id=${encodeURIComponent(jobId || '')}`}
                      className="inline-flex text-sm font-medium text-indigo-700 hover:text-indigo-900 underline"
                    >
                      Bekijk bij HR →
                    </Link>
                  </div>
                )}
              </div>
            )}
            {displayChatHistory.length === 0 && !ceoTyping && !jobId && (
              <p className="text-slate-500 text-sm">Describe your task below. {ceoDisplayName} will create a plan for you.</p>
            )}
            {displayChatHistory.length === 0 && !ceoTyping && jobId && isIntake && (
              <div className="thinking-indicator flex items-center gap-1.5 text-slate-500 text-sm">
                <span>{ceoDisplayName} is thinking</span>
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
            {displayChatHistory.map((msg, i) => {
              const prevMsg = displayChatHistory[i - 1]
              const isCeoRespondingToAttachment = msg.role === 'ceo' && prevMsg?.role === 'user' && prevMsg?.attachment
              const attachmentFilename = prevMsg?.attachment?.filename
              return (
              <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'ceo' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 text-xs font-semibold">{ceoInitials}</div>
                )}
                <div className="flex flex-col gap-0.5 max-w-[80%]">
                  {msg.role === 'ceo' && <span className="text-xs text-slate-500">{ceoDisplayName}</span>}
                  <div
                    className={`px-4 py-2.5 rounded-xl ${
                      msg.role === 'ceo' ? 'bg-slate-100 text-slate-800 rounded-tl-none' : 'bg-indigo-600 text-white rounded-tr-none'
                    }`}
                  >
                    {msg.role === 'user' && msg.attachment && (
                      <AttachmentPill attachment={msg.attachment} isUserBubble />
                    )}
                    {isCeoRespondingToAttachment && attachmentFilename && (
                      <p className="text-xs text-slate-500 mb-1">📎 Gebaseerd op: {attachmentFilename}</p>
                    )}
                    {msg.role === 'user' ? (
                      <p className="text-sm whitespace-pre-wrap">{msg.content || ''}</p>
                    ) : (
                      <div className="text-sm [&_p]:mb-1 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4">
                        <ReactMarkdown remarkPlugins={[remarkBreaks]}>{msg.content || ''}</ReactMarkdown>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )})}
            {ceoTyping && (
              <div className="flex gap-2 justify-start items-center text-slate-500 text-sm">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 text-xs font-semibold">{ceoInitials}</div>
                <div className="px-4 py-2.5 rounded-xl rounded-tl-none bg-slate-100 text-slate-600 flex items-center gap-1">
                  <span>{ceoDisplayName} is thinking</span>
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
          {!jobId && (
            <div className="flex-shrink-0 px-3 pb-2">
              <div
                onClick={() => !uploadingFile && fileInputRef.current?.click()}
                onDrop={(e) => { e.preventDefault(); handleFileSelect(e.dataTransfer?.files) }}
                onDragOver={(e) => e.preventDefault()}
                className={`border-2 border-dashed rounded-lg p-3 flex items-center justify-center gap-2 cursor-pointer transition text-sm ${
                  uploadingFile ? 'border-slate-200 bg-slate-50 opacity-60' : 'border-slate-200 hover:border-indigo-300 bg-slate-50/50'
                }`}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={(e) => handleFileSelect(e.target?.files)}
                  accept=".pdf,.csv,.md,.docx,.xlsx,.xls,.txt"
                  className="hidden"
                />
                {attachedFile ? (
                  <span className="flex items-center gap-2 text-slate-700">
                    <span className="font-medium truncate max-w-[180px]">{attachedFile.name}</span>
                    <span className="text-slate-500">({extractedText.length.toLocaleString()} tekens)</span>
                    <button type="button" onClick={(e) => { e.stopPropagation(); clearAttachment() }} className="p-0.5 rounded hover:bg-slate-200" aria-label="Verwijderen">
                      <X className="w-4 h-4" />
                    </button>
                  </span>
                ) : (
                  <>
                    <Upload className="w-4 h-4 text-slate-500" />
                    <span className="text-slate-600">
                      {uploadingFile ? 'Bestand verwerken…' : 'Sleep PDF, CSV of .md hier of klik om te uploaden'}
                    </span>
                  </>
                )}
              </div>
            </div>
          )}
          <form onSubmit={handleSendMessage} className="flex-shrink-0 flex flex-col gap-2 p-3 border-t border-slate-200 bg-white">
            {jobId && chatAttachedFile && (
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <span className="font-medium truncate max-w-[200px]">{chatAttachedFile.name}</span>
                <button type="button" onClick={clearChatAttachment} className="p-0.5 rounded hover:bg-slate-200" aria-label="Verwijderen">
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
            <div className="flex gap-2">
            {jobId && (
              <>
                <input
                  type="file"
                  ref={chatFileInputRef}
                  onChange={(e) => handleChatFileSelect(e.target?.files)}
                  accept=".pdf,.csv,.txt,.docx,.png,.jpg,.jpeg,.md,.xlsx,.xls"
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => chatFileInputRef.current?.click()}
                  className="flex-shrink-0 p-2.5 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-50 hover:border-slate-400 transition self-end"
                  title="Bestand bijvoegen"
                  aria-label="Bestand bijvoegen"
                >
                  <Paperclip className="w-5 h-5" />
                </button>
              </>
            )}
            <div className="flex-1 relative">
              {mentionSuggestions.length > 0 && (
                <div
                  className="absolute bottom-full left-0 right-0 mb-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-[200px] overflow-y-auto z-50"
                  role="listbox"
                  aria-label="Client vermelden"
                >
                  {mentionSuggestions.map((c) => (
                    <button
                      key={c.slug || c.client_id}
                      type="button"
                      onClick={() => handleMentionSelect(c)}
                      className="mention-option w-full flex justify-between px-3 py-2 text-left text-sm border-none bg-transparent cursor-pointer hover:bg-slate-100"
                      role="option"
                    >
                      <span className="font-medium text-slate-800">{c.client_name || c.name || c.slug}</span>
                      <span className="text-slate-500 text-xs">@{c.slug}</span>
                    </button>
                  ))}
                </div>
              )}
              <textarea
                value={chatInput}
                onChange={handleJobInputChange}
                onKeyDown={handleKeyDown}
                placeholder={jobId ? 'Type your message... Gebruik @client voor context.' : 'Beschrijf je opdracht... Gebruik @client (bijv. @asured) voor context.'}
                className="w-full px-4 py-2.5 border border-slate-300 rounded-xl text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none min-h-[44px] max-h-32"
                disabled={inputDisabled || uploadingFile}
                rows={1}
              />
            </div>
            <button
              type="submit"
              disabled={inputDisabled || uploadingFile || (!chatInput.trim() && !extractedText && !chatAttachedFile)}
              className="px-5 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition self-end"
            >
              {sendingChat ? 'Sending…' : 'Send'}
            </button>
            </div>
            {detectedClient && (
              <div className="flex items-center gap-1.5 mt-1.5 text-sm text-emerald-600">
                <CheckCircle className="w-4 h-4 flex-shrink-0" />
                <span>Client context geladen: <strong>{detectedClient.client_name || detectedClient.name || detectedClient.slug}</strong> — GA4, Ads en GSC data beschikbaar</span>
              </div>
            )}
          </form>
        </div>

        {/* Right: Document viewer — on mobile order-1 (above chat) */}
        {/* pipeline_type and proposed_data from same parsed context (not raw job.context) */}
        <div className="flex flex-col min-h-0 order-1 md:order-2 overflow-y-auto border-l border-slate-200 rounded-r-xl md:rounded-l-none">
          <DocumentViewer
            documentPreview={data?.document_preview ?? null}
            jobId={jobId}
            jobStatus={job?.status}
            jobTitle={job?.job_post || title}
            pipelineType={context.pipeline_type}
            proposedData={context.proposed_data}
            onApprove={handleApproveDeploy}
            onApprovePlan={handleApprovePlan}
            onRequestChanges={() => chatSectionRef.current?.scrollIntoView({ behavior: 'smooth' })}
            approvingDeploy={approvingDeploy}
            approvingPlan={approvingPlan}
          />
        </div>
      </div>
    </PageLayout>
  )
}
