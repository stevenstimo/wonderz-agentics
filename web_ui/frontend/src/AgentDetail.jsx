import { useEffect, useState, useCallback, useRef } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Briefcase, Target, BookOpen, Activity, ImagePlus, Trash2, MessageCircle, GraduationCap } from 'lucide-react'
import PageLayout from './PageLayout'
import { apiUrl, apiFetch, fetchJson } from './apiClient'
import { VALID_TOOLS, VALID_CATEGORIES } from './agentConstants'
import AgentDirectChat from './components/AgentDirectChat'
import AgentKnowledgeTab from './components/AgentKnowledgeTab'
import HireCelebration from './components/HireCelebration'
import { queryKeys } from './queryKeys'

const AVATAR_COLORS = [
  { name: 'indigo', bg: 'bg-indigo-600' },
  { name: 'emerald', bg: 'bg-emerald-600' },
  { name: 'amber', bg: 'bg-amber-500' },
  { name: 'rose', bg: 'bg-rose-600' },
  { name: 'cyan', bg: 'bg-cyan-600' },
  { name: 'slate', bg: 'bg-slate-600' },
]

function initials(name) {
  if (!name || typeof name !== 'string') return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  return (name[0] || '?').toUpperCase()
}

function relativeTime(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  const now = new Date()
  const s = Math.floor((now - d) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  if (s < 604800) return `${Math.floor(s / 86400)}d ago`
  return d.toLocaleDateString()
}

function truncate(str, len = 40) {
  if (!str) return '—'
  return str.length <= len ? str : str.slice(0, len) + '…'
}

const AVATAR_SIZE = 200
function resizeImageToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      URL.revokeObjectURL(url)
      const canvas = document.createElement('canvas')
      let { width, height } = img
      if (width > AVATAR_SIZE || height > AVATAR_SIZE) {
        if (width > height) {
          height = Math.round((height * AVATAR_SIZE) / width)
          width = AVATAR_SIZE
        } else {
          width = Math.round((width * AVATAR_SIZE) / height)
          height = AVATAR_SIZE
        }
      }
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0, width, height)
      resolve(canvas.toDataURL('image/jpeg', 0.85))
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Image load failed'))
    }
    img.src = url
  })
}

const TAB_PROFIEL = 'profiel'
const TAB_TRAINING = 'training'
const TAB_KENNIS = 'kennis'
const TAB_KNOWLEDGEBANK = 'kennisbank'
const TAB_PRESTATIES = 'prestaties'
const TAB_CHAT = 'chat'

function KennisTab({ agentId, knowledgeSources, relativeTime }) {
  const { data: manualChunks = [], isLoading: loading } = useQuery({
    queryKey: queryKeys.agentKnowledgeManual(agentId),
    queryFn: async () => {
      const r = await apiFetch(`/api/training/${encodeURIComponent(agentId)}/knowledge-base`)
      if (!r.ok) return []
      const data = await r.json()
      const list = Array.isArray(data) ? data : []
      return list.filter((c) => (c.source_url || '').startsWith('direct_chat:'))
    },
    enabled: Boolean(agentId),
  })
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900 mb-4">Kennisbronnen</h3>
      <Link
        to="/training"
        className="inline-flex items-center gap-2 text-sm font-medium text-indigo-600 hover:text-indigo-800 mb-4"
      >
        + URL toevoegen (Training Hub)
      </Link>
      {knowledgeSources.length === 0 ? (
        <p className="text-sm text-slate-500">Geen kennisbronnen. Voeg URLs toe via de Training Hub.</p>
      ) : (
        <ul className="space-y-2">
          {knowledgeSources.map((src, i) => (
            <li key={i} className="flex items-start justify-between gap-2 text-sm">
              <span className="min-w-0 truncate text-slate-700">
                {typeof src === 'string' ? src : (src?.url || src?.source || JSON.stringify(src))}
              </span>
              {typeof src === 'object' && (src.chunks != null || src.added_at) && (
                <span className="text-slate-400 shrink-0">
                  {src.chunks != null ? `${src.chunks} chunks` : ''}
                  {src.added_at ? ` · ${relativeTime(src.added_at)}` : ''}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      <h4 className="text-sm font-semibold text-slate-800 mt-6 mb-2">Handmatig opgeslagen</h4>
      {loading ? (
        <p className="text-xs text-slate-500">Laden...</p>
      ) : manualChunks.length === 0 ? (
        <p className="text-xs text-slate-500">Geen items. Sla berichten op vanuit Direct Chat met het bookmark-icoon.</p>
      ) : (
        <ul className="space-y-2">
          {manualChunks.map((c) => (
            <li key={c.id} className="text-sm text-slate-700 border-l-2 border-indigo-200 pl-3 py-1">
              {c.text}
              <span className="text-xs text-slate-500 block mt-0.5">{c.source_url} · {relativeTime(c.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function AgentDetail() {
  const { agentId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || TAB_PROFIEL
  const setTab = (t) => setSearchParams(t === TAB_PROFIEL ? {} : { tab: t })

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [profileForm, setProfileForm] = useState({ name: '', goal: '', system_prompt: '', category: 'Custom', tool_access_whitelist: [] })
  const [profileDirty, setProfileDirty] = useState(false)
  const [savingProfile, setSavingProfile] = useState(false)
  const [savingStatus, setSavingStatus] = useState(false)
  const [savingAvatar, setSavingAvatar] = useState(false)
  const [showAvatarColors, setShowAvatarColors] = useState(false)
  const [showDeactivateModal, setShowDeactivateModal] = useState(false)
  const [trainUrl, setTrainUrl] = useState('')
  const [trainMessage, setTrainMessage] = useState('')
  const [isTraining, setIsTraining] = useState(false)
  const [trainingPollUrl, setTrainingPollUrl] = useState(null)
  const [trainingPollAttempts, setTrainingPollAttempts] = useState(0)
  const [celebration, setCelebration] = useState(null)
  const closeCelebration = useCallback(() => setCelebration(null), [])

  const loadDetail = useCallback(async () => {
    if (!agentId) return
    setLoading(true)
    setError(null)
    let rethrowServerError = false
    try {
      const res = await apiFetch(`/api/agents/${encodeURIComponent(agentId)}/detail`)
      if (!res.ok) {
        if (res.status === 404) throw new Error('Agent not found')
        const detail = (await res.json().catch(() => ({}))).detail || 'Failed to load'
        if (res.status >= 500) {
          rethrowServerError = true
          throw new Error(detail)
        }
        throw new Error(detail)
      }
      const json = await res.json()
      setData(json)
      const a = json.agent || {}
      const tools = Array.isArray(a.tool_access_whitelist) ? a.tool_access_whitelist : []
      setProfileForm({
        name: a.name || '',
        goal: a.goal || '',
        system_prompt: a.system_prompt || a.system_instructions || '',
        category: a.category || 'Custom',
        tool_access_whitelist: tools.map((t) => (typeof t === 'string' ? t : t.name || t)),
      })
      setProfileDirty(false)
    } catch (err) {
      // ASSUMPTION: 5xx and network errors go to ErrorBoundary
      if (rethrowServerError || (err.name === 'TypeError' && err.message?.includes('fetch'))) throw err
      setError(err.message || 'Failed to load agent')
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [agentId])

  useEffect(() => {
    loadDetail()
  }, [loadDetail])

  const agent = data?.agent || {}
  const personaText = typeof agent.persona === 'string' ? agent.persona.trim() : ''
  const qualitiesText = typeof agent.qualities === 'string' ? agent.qualities.trim() : ''
  const developmentText = typeof agent.development === 'string' ? agent.development.trim() : ''
  const recentWork = data?.recent_work || []
  const developmentPoints = data?.development_points || []
  const skills = data?.skills || []
  const avatarConfig = (agent.permissions && typeof agent.permissions === 'object' && agent.permissions.avatar) || {}
  const avatarColor = avatarConfig.color || 'indigo'
  const avatarInitials = avatarConfig.initials != null ? avatarConfig.initials : initials(agent.name)
  const avatarImageUrl = avatarConfig.imageDataUrl || avatarConfig.imageUrl || null
  const avatarBg = AVATAR_COLORS.find((c) => c.name === avatarColor)?.bg || 'bg-indigo-600'
  const fileInputRef = useRef(null)
  const knowledgeSources = Array.isArray(agent.knowledge_base_sources) ? agent.knowledge_base_sources : []
  const { data: trainingAgentData } = useQuery({
    queryKey: [...queryKeys.agent(agentId || 'none'), 'training-status', trainingPollUrl || 'none'],
    queryFn: () => fetchJson(`/api/agents/${encodeURIComponent(agentId)}`),
    enabled: !!agentId && isTraining && !!trainingPollUrl,
    refetchInterval: trainingPollAttempts >= 20 ? false : 10_000,
  })

  useEffect(() => {
    if (!isTraining || !trainingPollUrl || !trainingAgentData) return
    setTrainingPollAttempts((prev) => prev + 1)
    const sources = Array.isArray(trainingAgentData?.knowledge_base_sources) ? trainingAgentData.knowledge_base_sources : []
    const source = sources.find((s) => s && s.url === trainingPollUrl)
    if (source && source.status !== 'processing') {
      setIsTraining(false)
      setTrainingPollUrl(null)
      setTrainMessage(source.status === 'active' ? 'Training voltooid ✓' : `Training mislukt${source.error ? `: ${source.error}` : ''}`)
      setData((prev) => (prev ? { ...prev, agent: { ...prev.agent, ...trainingAgentData } } : prev))
      return
    }
    if (trainingPollAttempts >= 20) {
      setIsTraining(false)
      setTrainingPollUrl(null)
      setTrainMessage('Training duurt langer dan verwacht. Ververs de pagina later.')
    }
  }, [isTraining, trainingPollUrl, trainingAgentData, trainingPollAttempts])

  const totalTokens = recentWork.reduce((acc, s) => acc + (Number(s.tokens_used) || 0), 0)
  const completedSteps = recentWork.filter((s) => (s.status || '').toUpperCase() === 'COMPLETED').length
  const successRate = recentWork.length ? Math.round((completedSteps / recentWork.length) * 100) : 0
  const avgTiming = recentWork.length
    ? Math.round(recentWork.reduce((acc, s) => acc + (Number(s.timing_ms) || 0), 0) / recentWork.length)
    : 0
  const performanceScore = Math.min(100, Math.max(0, Number(agent.performance_score) * 100 || 0))
  const circumference = 2 * Math.PI * 36
  const strokeDash = (performanceScore / 100) * circumference

  const syncProfileFormFromAgent = useCallback(() => {
    const tools = Array.isArray(agent.tool_access_whitelist) ? agent.tool_access_whitelist : []
    setProfileForm({
      name: agent.name || '',
      goal: agent.goal || '',
      system_prompt: agent.system_prompt || agent.system_instructions || '',
      category: agent.category || 'Custom',
      tool_access_whitelist: tools.map((t) => (typeof t === 'string' ? t : t.name || t)),
    })
    setProfileDirty(false)
  }, [agent.name, agent.goal, agent.system_prompt, agent.system_instructions, agent.category, agent.tool_access_whitelist])

  const saveProfile = async () => {
    const payload = {
      name: profileForm.name.trim(),
      goal: profileForm.goal.trim() || undefined,
      system_prompt: profileForm.system_prompt.trim(),
      category: profileForm.category || undefined,
      tool_access_whitelist: profileForm.tool_access_whitelist,
    }
    setSavingProfile(true)
    try {
      const res = await apiFetch(`/api/agents/${encodeURIComponent(agentId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Update failed')
      await loadDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setSavingProfile(false)
    }
  }

  const cancelProfile = () => {
    syncProfileFormFromAgent()
  }

  const toggleTool = (tool) => {
    setProfileForm((prev) => {
      const exists = prev.tool_access_whitelist.includes(tool)
      return {
        ...prev,
        tool_access_whitelist: exists
          ? prev.tool_access_whitelist.filter((t) => t !== tool)
          : [...prev.tool_access_whitelist, tool],
      }
    })
    setProfileDirty(true)
  }

  const setProfileIsActive = async (value) => {
    const wasInactive = agent.is_active === false
    setSavingStatus(true)
    try {
      const res = await apiFetch(`/api/agents/${encodeURIComponent(agentId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: value }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Update failed')
      await loadDetail()
      if (value === true && wasInactive) {
        const displayName = agent.name || agent.agent_name || '—'
        const roleLabel = agent.role || agent.specialization || 'Agent'
        const cat = agent.category || ''
        setCelebration({
          agentName: displayName,
          roleName: roleLabel,
          badge:
            cat && roleLabel
              ? `${cat} · ${roleLabel}`
              : cat || null,
        })
      }
    } catch (err) {
      alert(err.message)
    } finally {
      setSavingStatus(false)
      setShowDeactivateModal(false)
    }
  }

  const handleTrain = async () => {
    const urlToTrain = trainUrl.trim()
    if (!urlToTrain.startsWith('http://') && !urlToTrain.startsWith('https://')) {
      setTrainMessage('URL moet beginnen met http:// of https://')
      return
    }
    setIsTraining(true)
    setTrainMessage('Training gestart. Dit kan ~30 seconden duren.')
    try {
      const res = await apiFetch(`/api/agents/${encodeURIComponent(agentId)}/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: urlToTrain, approved_by: 'user' }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        setTrainMessage(err?.detail || 'Training start mislukt')
        setIsTraining(false)
        return
      }
      setTrainUrl('')
      setTrainingPollAttempts(0)
      setTrainingPollUrl(urlToTrain)
    } catch (err) {
      setTrainMessage(err?.message || 'Fout')
      setIsTraining(false)
      setTrainingPollUrl(null)
    }
  }

  const handleIsActiveToggle = () => {
    const currentlyActive = agent.is_active !== false
    if (currentlyActive) {
      setShowDeactivateModal(true)
    } else {
      setProfileIsActive(true)
    }
  }

  const setAvatarColor = async (color, initialsVal) => {
    setSavingAvatar(true)
    setShowAvatarColors(false)
    try {
      const body = { color, initials: initialsVal || avatarInitials }
      if (avatarImageUrl) body.imageDataUrl = avatarImageUrl
      const res = await apiFetch(`/api/agents/${encodeURIComponent(agentId)}/avatar`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Update failed')
      await loadDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setSavingAvatar(false)
    }
  }

  const setAvatarImage = async (dataUrl) => {
    setSavingAvatar(true)
    setShowAvatarColors(false)
    try {
      const res = await apiFetch(`/api/agents/${encodeURIComponent(agentId)}/avatar`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          color: avatarColor,
          initials: avatarInitials,
          imageDataUrl: dataUrl,
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Update failed')
      await loadDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setSavingAvatar(false)
    }
  }

  const removeAvatarImage = async () => {
    setSavingAvatar(true)
    setShowAvatarColors(false)
    try {
      const res = await apiFetch(`/api/agents/${encodeURIComponent(agentId)}/avatar`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          color: avatarColor,
          initials: avatarInitials,
          imageDataUrl: null,
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Update failed')
      await loadDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setSavingAvatar(false)
    }
  }

  const onAvatarFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file || !file.type.startsWith('image/')) return
    e.target.value = ''
    setSavingAvatar(true)
    try {
      const dataUrl = await resizeImageToDataUrl(file)
      await setAvatarImage(dataUrl)
    } catch (err) {
      alert(err.message || 'Upload failed')
    } finally {
      setSavingAvatar(false)
    }
  }

  const activityEvents = [
    ...recentWork.slice(0, 10).map((s) => ({
      type: 'step',
      date: s.created_at || s.completed_at,
      label: s.step_name || 'Step',
      jobId: s.job_id,
    })),
    ...developmentPoints.slice(0, 10).map((d) => ({
      type: 'dev',
      date: d.created_at,
      label: d.description || d.category || 'Development point',
    })),
  ]
    .filter((e) => e.date)
    .sort((a, b) => new Date(b.date) - new Date(a.date))
    .slice(0, 10)

  if (loading && !data) {
    return (
      <PageLayout size="wide" padded>
        <div className="flex items-center justify-center py-16 text-slate-500 text-sm">Loading agent…</div>
      </PageLayout>
    )
  }

  if (error || !data) {
    return (
      <PageLayout size="wide" padded>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm text-center">
          <p className="text-red-600 mb-4">{error || 'Agent not found'}</p>
          <Link to="/agents" className="inline-flex items-center gap-2 text-sm font-medium text-indigo-600 hover:text-indigo-800">
            <ArrowLeft className="w-4 h-4" /> Back to Agents
          </Link>
        </div>
      </PageLayout>
    )
  }

  const isActive = agent.is_active !== false

  const tabClass = (t) =>
    tab === t
      ? 'bg-white border border-slate-200 border-b-0 text-indigo-600'
      : 'text-slate-500 hover:text-slate-900'

  return (
    <PageLayout size="wide" padded className="!max-w-none">
      {celebration && (
        <HireCelebration
          visible
          agentName={celebration.agentName}
          roleName={celebration.roleName}
          badge={celebration.badge}
          onClose={closeCelebration}
        />
      )}
      {showDeactivateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true" aria-labelledby="deactivate-modal-title">
          <div className="rounded-xl bg-white p-6 shadow-xl max-w-md mx-4">
            <h2 id="deactivate-modal-title" className="text-lg font-semibold text-slate-900 mb-2">Agent deactiveren</h2>
            <p className="text-slate-600 text-sm mb-4">
              Weet je zeker dat je <strong>{agent.agent_name || agent.name || 'deze agent'}</strong> wilt deactiveren?
            </p>
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={() => setShowDeactivateModal(false)}
                className="rounded-lg px-4 py-2 border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50"
              >
                Annuleren
              </button>
              <button
                type="button"
                onClick={() => setProfileIsActive(false)}
                disabled={savingStatus}
                className="rounded-lg px-4 py-2 bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              >
                {savingStatus ? 'Bezig…' : 'Deactiveren'}
              </button>
            </div>
          </div>
        </div>
      )}
      <div className="mb-4 flex items-center gap-2">
        <Link
          to="/agents"
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Agents
        </Link>
      </div>

      {/* Sticky agent header — altijd zichtbaar boven de tabs */}
      <div className="sticky top-0 z-10 bg-white border-b border-slate-200 shadow-sm mb-4">
        <div className="px-6 py-3 flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-semibold text-sm flex-shrink-0">
            {initials(agent?.name || agent?.agent_name)}
          </div>
          <div>
            <div className="font-semibold text-slate-900 leading-tight">
              {agent?.name || agent?.agent_name || '—'}
            </div>
            <div className="text-xs text-slate-500 leading-tight">
              {agent?.role ?? agent?.specialization ?? 'Agent'}
            </div>
          </div>
        </div>
        <div className="flex gap-2 border-t border-slate-100 px-6">
          <button
            type="button"
            onClick={() => setTab(TAB_PROFIEL)}
            className={`px-6 py-3 font-semibold rounded-t-xl transition-colors ${tabClass(TAB_PROFIEL)}`}
          >
            Profiel
          </button>
          <button
            type="button"
            onClick={() => setTab(TAB_TRAINING)}
            className={`px-6 py-3 font-semibold rounded-t-xl transition-colors flex items-center gap-2 ${tabClass(TAB_TRAINING)}`}
          >
            <GraduationCap className="w-4 h-4" /> Training
          </button>
          <button
            type="button"
            onClick={() => setTab(TAB_KENNIS)}
            className={`px-6 py-3 font-semibold rounded-t-xl transition-colors ${tabClass(TAB_KENNIS)}`}
          >
            Kennis
          </button>
          <button
            type="button"
            onClick={() => setTab(TAB_KNOWLEDGEBANK)}
            className={`px-6 py-3 font-semibold rounded-t-xl transition-colors ${tabClass(TAB_KNOWLEDGEBANK)}`}
          >
            Kennisbank
          </button>
          <button
            type="button"
            onClick={() => setTab(TAB_PRESTATIES)}
            className={`px-6 py-3 font-semibold rounded-t-xl transition-colors ${tabClass(TAB_PRESTATIES)}`}
          >
            Prestaties
          </button>
          <button
            type="button"
            onClick={() => setTab(TAB_CHAT)}
            className={`px-6 py-3 font-semibold rounded-t-xl transition-colors flex items-center gap-2 ${tabClass(TAB_CHAT)}`}
          >
            <MessageCircle className="w-4 h-4" /> Chat
          </button>
        </div>
      </div>

      {tab === TAB_CHAT && (
        <AgentDirectChat agentId={agentId} agent={agent} />
      )}

      {tab === TAB_PROFIEL && (
      <div className="grid grid-cols-1 lg:grid-cols-[40%_60%] gap-6">
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-start gap-4">
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowAvatarColors(!showAvatarColors)}
                  className={`w-20 h-20 rounded-full flex items-center justify-center shrink-0 ring-2 ring-white shadow overflow-hidden ${!avatarImageUrl ? `${avatarBg} text-white text-2xl font-semibold` : 'bg-slate-100'}`}
                  disabled={savingAvatar}
                  title="Avatar aanpassen"
                >
                  {avatarImageUrl ? (
                    <img src={avatarImageUrl} alt="" className="w-full h-full object-cover" />
                  ) : (
                    avatarInitials
                  )}
                </button>
                {showAvatarColors && (
                  <div className="absolute left-0 top-full mt-2 flex flex-col gap-2 p-2 rounded-lg bg-white border border-slate-200 shadow-lg z-10 min-w-[140px]">
                    <div className="flex flex-wrap gap-1">
                      {AVATAR_COLORS.map((c) => (
                        <button
                          key={c.name}
                          type="button"
                          onClick={() => setAvatarColor(c.name)}
                          className={`w-8 h-8 rounded-full ${c.bg} ring-2 ring-offset-1 ${avatarColor === c.name ? 'ring-slate-800' : 'ring-transparent'}`}
                          title={c.name}
                        />
                      ))}
                    </div>
                    <label className="flex items-center gap-2 px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-100 rounded cursor-pointer">
                      <ImagePlus className="w-4 h-4" />
                      Foto uploaden
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={onAvatarFileChange}
                      />
                    </label>
                    {avatarImageUrl && (
                      <button
                        type="button"
                        onClick={removeAvatarImage}
                        disabled={savingAvatar}
                        className="flex items-center gap-2 px-2 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded"
                      >
                        <Trash2 className="w-4 h-4" />
                        Foto verwijderen
                      </button>
                    )}
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <h1 className="text-xl font-bold text-slate-900">{agent.name || '—'}</h1>
                <div className="flex flex-wrap items-center gap-2 mt-1">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-800">
                    {agent.role || '—'}
                  </span>
                  {agent.specialization && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800">
                      {agent.specialization}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 mt-2">
                  <button
                    type="button"
                    onClick={handleIsActiveToggle}
                    disabled={savingStatus}
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none ${isActive ? 'bg-green-500' : 'bg-slate-300'}`}
                    role="switch"
                    aria-checked={isActive}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition translate-x-0.5 ${isActive ? 'translate-x-5' : 'translate-x-0.5'}`}
                    />
                  </button>
                  <span className={`text-xs font-medium ${isActive ? 'text-green-700' : 'text-slate-600'}`}>
                    {isActive ? 'Actief' : 'Inactief'}
                  </span>
                </div>
                <p className="text-xs text-slate-500 font-mono mt-1">{agent.agent_id}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Hired: {relativeTime(agent.hired_at)} · Updated: {relativeTime(agent.updated_at)}
                </p>
              </div>
            </div>
          </div>

          {/* Bewerkbare velden */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-slate-900">Profiel bewerken</h3>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Naam</label>
              <input
                type="text"
                value={profileForm.name}
                onChange={(e) => { setProfileForm((p) => ({ ...p, name: e.target.value })); setProfileDirty(true) }}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Doel binnen crew</label>
              <input
                type="text"
                value={profileForm.goal}
                onChange={(e) => { setProfileForm((p) => ({ ...p, goal: e.target.value })); setProfileDirty(true) }}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                placeholder="Doel van de agent"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Categorie</label>
              <select
                value={profileForm.category}
                onChange={(e) => { setProfileForm((p) => ({ ...p, category: e.target.value })); setProfileDirty(true) }}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {VALID_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">System Instructions</label>
              <textarea
                value={profileForm.system_prompt}
                onChange={(e) => { setProfileForm((p) => ({ ...p, system_prompt: e.target.value })); setProfileDirty(true) }}
                rows={6}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono"
                placeholder="System instructions..."
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-2">Tool Access</label>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {VALID_TOOLS.map((tool) => (
                  <label key={tool} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50">
                    <input
                      type="checkbox"
                      checked={profileForm.tool_access_whitelist.includes(tool)}
                      onChange={() => toggleTool(tool)}
                    />
                    <span className="text-sm text-slate-700">{tool}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={saveProfile}
                disabled={!profileDirty || savingProfile}
                className="rounded-lg px-4 py-2 bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {savingProfile ? 'Opslaan…' : 'Opslaan'}
              </button>
              <button
                type="button"
                onClick={cancelProfile}
                disabled={!profileDirty}
                className="rounded-lg px-4 py-2 border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Annuleren
              </button>
            </div>
          </div>

          {(personaText || qualitiesText || developmentText) && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-4">
              {personaText && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 mb-1">Persona</h3>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{personaText}</p>
                </div>
              )}
              {qualitiesText && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 mb-1">Kwaliteiten</h3>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{qualitiesText}</p>
                </div>
              )}
              {developmentText && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 mb-1">Ontwikkelpunten</h3>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{developmentText}</p>
                </div>
              )}
            </div>
          )}

        </div>
        <div className="hidden lg:block" />
      </div>
      )}

      {tab === TAB_TRAINING && (
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm max-w-2xl">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Kennisbronnen trainen</h2>
        <div className="flex gap-2 flex-wrap items-center mb-4">
          <input
            type="url"
            placeholder="https://..."
            value={trainUrl}
            onChange={(e) => setTrainUrl(e.target.value)}
            className="flex-1 min-w-[200px] rounded-lg border border-slate-300 px-3 py-2 text-sm"
            aria-label="URL om te trainen"
          />
          <button
            type="button"
            onClick={handleTrain}
            disabled={isTraining}
            className="rounded-lg px-4 py-2 bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isTraining ? 'Bezig...' : 'Train'}
          </button>
        </div>
        {trainMessage && <p className="mb-4 text-sm text-slate-600">{trainMessage}</p>}
        <p className="text-sm text-slate-500 mb-4">
          Status: {knowledgeSources.some((s) => s?.status === 'processing') ? '● Bezig' : '● Actief'}{' '}
          ({knowledgeSources.filter((s) => s?.status === 'active').length} bronnen)
        </p>
        <h3 className="text-sm font-semibold text-slate-800 mb-2">Bronnen</h3>
        {knowledgeSources.length === 0 ? (
          <p className="text-sm text-slate-500">Geen bronnen. Voeg een URL toe en klik op Train.</p>
        ) : (
          <ul className="space-y-3">
            {knowledgeSources.map((src, i) => (
              <li key={i} className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-slate-100 p-3 text-sm">
                <span className="min-w-0 truncate text-slate-700 font-medium">
                  {typeof src === 'string' ? src : (src?.url || src?.source || JSON.stringify(src))}
                </span>
                <span className={`shrink-0 px-2 py-0.5 rounded text-xs font-medium ${
                  (src?.status === 'active') ? 'bg-green-100 text-green-800' :
                  (src?.status === 'processing') ? 'bg-amber-100 text-amber-800' :
                  (src?.status === 'failed') ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-600'
                }`}>
                  {src?.status === 'active' ? '✓' : ''}{src?.status || 'pending'}
                </span>
                {typeof src === 'object' && (src.chunks != null || src.added_at) && (
                  <span className="text-slate-400 shrink-0 w-full text-xs mt-0.5">
                    {src.chunks != null ? `${src.chunks} chunks` : ''}
                    {src.added_at ? ` · ${relativeTime(src.added_at)}` : ''}
                  </span>
                )}
                {typeof src === 'object' && src?.status === 'failed' && src?.error && (
                  <span className="text-red-600 text-xs w-full mt-1">{src.error}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      )}

      {tab === TAB_KENNIS && (
      <KennisTab agentId={agentId} knowledgeSources={knowledgeSources} relativeTime={relativeTime} />
      )}

      {tab === TAB_KNOWLEDGEBANK && (
      <AgentKnowledgeTab agentId={agentId} />
      )}

      {tab === TAB_PRESTATIES && (
      <div className="grid grid-cols-1 lg:grid-cols-[40%_60%] gap-6">
        <div className="space-y-4" />
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">Performance</h3>
            <div className="flex flex-wrap items-center gap-6">
              <div className="relative w-24 h-24">
                <svg className="w-24 h-24 -rotate-90" viewBox="0 0 80 80">
                  <circle cx="40" cy="40" r="36" fill="none" stroke="#e2e8f0" strokeWidth="8" />
                  <circle
                    cx="40"
                    cy="40"
                    r="36"
                    fill="none"
                    stroke="#6366f1"
                    strokeWidth="8"
                    strokeDasharray={`${strokeDash} ${circumference}`}
                    strokeLinecap="round"
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-slate-900">
                  {Math.round(performanceScore)}%
                </span>
              </div>
              <div>
                <p className="text-3xl font-bold text-slate-900">{agent.completed_tasks ?? 0}</p>
                <p className="text-xs text-slate-500">Completed tasks</p>
              </div>
              <div className="grid grid-cols-1 gap-1 text-sm">
                <p className="text-slate-600">Tokens used: <span className="font-medium text-slate-900">{totalTokens.toLocaleString()}</span></p>
                <p className="text-slate-600">Avg timing: <span className="font-medium text-slate-900">{avgTiming} ms</span></p>
                <p className="text-slate-600">Success rate: <span className="font-medium text-slate-900">{successRate}%</span></p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <BookOpen className="w-4 h-4" /> Skills ({skills.length})
            </h3>
            <p className="text-xs text-slate-500 mb-2">Managed by Judson</p>
            {skills.length === 0 ? (
              <p className="text-xs text-slate-500">No applicable skills</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {skills.map((s) => (
                  <Link
                    key={s.skill_id || s.name}
                    to="/skills-library"
                    className="rounded-lg border border-slate-200 p-2 hover:bg-slate-50 flex items-center justify-between gap-2"
                  >
                    <span className="text-sm font-medium text-slate-800 truncate">{s.name || s.skill_id}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 shrink-0">{s.domain || '—'}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <Briefcase className="w-4 h-4" /> Recent Work
            </h3>
            {recentWork.length === 0 ? (
              <p className="text-xs text-slate-500">No tasks completed yet</p>
            ) : (
              <ul className="space-y-2">
                {recentWork.slice(0, 10).map((s) => (
                  <li key={s.id || `${s.job_id}-${s.step_index}`}>
                    <Link
                      to={s.job_id ? `/jobs/${s.job_id}` : '#'}
                      className="flex flex-wrap items-center gap-2 py-1.5 px-2 rounded hover:bg-slate-50 text-sm"
                    >
                      <span className="font-medium text-slate-800 truncate">{s.step_name || 'Step'}</span>
                      <span className="text-slate-500 truncate max-w-[120px]">{truncate(s.job_post, 30)}</span>
                      <span
                        className={`inline-flex px-1.5 py-0.5 rounded text-xs ${
                          (s.status || '').toUpperCase() === 'COMPLETED' ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {s.status || '—'}
                      </span>
                      <span className="text-xs text-slate-400">{s.tokens_used ?? 0} tok</span>
                      <span className="text-xs text-slate-400">{s.timing_ms ?? 0} ms</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <Target className="w-4 h-4" /> Development Points
            </h3>
            {developmentPoints.length === 0 ? (
              <p className="text-xs text-slate-500">No development points — great performance!</p>
            ) : (
              <ul className="space-y-2">
                {developmentPoints.map((d) => (
                  <li key={d.id} className="flex flex-wrap items-start gap-2 text-sm">
                    <span className="px-1.5 py-0.5 rounded text-xs bg-slate-100 text-slate-700">{d.category || '—'}</span>
                    <span className="text-slate-700">{truncate(d.description, 80)}</span>
                    <span
                      className={`shrink-0 px-1.5 py-0.5 rounded text-xs font-medium ${
                        (d.impact || '').toLowerCase() === 'high'
                          ? 'bg-red-100 text-red-800'
                          : (d.impact || '').toLowerCase() === 'medium'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-green-100 text-green-800'
                      }`}
                    >
                      {d.impact || 'low'}
                    </span>
                    <span className="text-xs text-slate-500">{d.status || ''}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <Activity className="w-4 h-4" /> Activity
            </h3>
            {activityEvents.length === 0 ? (
              <p className="text-xs text-slate-500">No recent activity</p>
            ) : (
              <ul className="space-y-2">
                {activityEvents.map((e, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm">
                    <span className="text-slate-400">
                      {e.type === 'step' ? <Briefcase className="w-4 h-4" /> : <Target className="w-4 h-4" />}
                    </span>
                    {e.type === 'step' && e.jobId ? (
                      <Link to={`/jobs/${e.jobId}`} className="text-indigo-600 hover:underline truncate">
                        {truncate(e.label, 50)}
                      </Link>
                    ) : (
                      <span className="text-slate-700 truncate">{truncate(e.label, 50)}</span>
                    )}
                    <span className="text-xs text-slate-400 shrink-0">{relativeTime(e.date)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
      )}
    </PageLayout>
  )
}
