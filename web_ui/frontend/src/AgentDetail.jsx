import { useEffect, useState, useCallback, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ChevronDown, ChevronRight, Briefcase, Target, BookOpen, Activity, ImagePlus, Trash2 } from 'lucide-react'
import PageLayout from './PageLayout'
import { apiUrl } from './apiClient'

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

export default function AgentDetail() {
  const { agentId } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [nameEdit, setNameEdit] = useState('')
  const [editingName, setEditingName] = useState(false)
  const [systemInstructionsEdit, setSystemInstructionsEdit] = useState('')
  const [systemInstructionsDirty, setSystemInstructionsDirty] = useState(false)
  const [savingInstructions, setSavingInstructions] = useState(false)
  const [savingName, setSavingName] = useState(false)
  const [savingStatus, setSavingStatus] = useState(false)
  const [savingAvatar, setSavingAvatar] = useState(false)
  const [showAvatarColors, setShowAvatarColors] = useState(false)
  const [systemInstructionsOpen, setSystemInstructionsOpen] = useState(true)
  const [toolsOpen, setToolsOpen] = useState(true)
  const [knowledgeOpen, setKnowledgeOpen] = useState(true)

  const loadDetail = useCallback(async () => {
    if (!agentId) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(apiUrl(`/api/agents/${encodeURIComponent(agentId)}/detail`))
      if (!res.ok) {
        if (res.status === 404) throw new Error('Agent not found')
        throw new Error((await res.json()).detail || 'Failed to load')
      }
      const json = await res.json()
      setData(json)
      setSystemInstructionsEdit(json.agent?.system_instructions ?? json.agent?.system_prompt ?? '')
      setSystemInstructionsDirty(false)
    } catch (err) {
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
  const recentWork = data?.recent_work || []
  const developmentPoints = data?.development_points || []
  const skills = data?.skills || []
  const avatarConfig = (agent.permissions && typeof agent.permissions === 'object' && agent.permissions.avatar) || {}
  const avatarColor = avatarConfig.color || 'indigo'
  const avatarInitials = avatarConfig.initials != null ? avatarConfig.initials : initials(agent.name)
  const avatarImageUrl = avatarConfig.imageDataUrl || avatarConfig.imageUrl || null
  const avatarBg = AVATAR_COLORS.find((c) => c.name === avatarColor)?.bg || 'bg-indigo-600'
  const fileInputRef = useRef(null)
  const toolsList = Array.isArray(agent.tool_access_whitelist) ? agent.tool_access_whitelist : []
  const knowledgeSources = Array.isArray(agent.knowledge_base_sources) ? agent.knowledge_base_sources : []

  const totalTokens = recentWork.reduce((acc, s) => acc + (Number(s.tokens_used) || 0), 0)
  const completedSteps = recentWork.filter((s) => (s.status || '').toUpperCase() === 'COMPLETED').length
  const successRate = recentWork.length ? Math.round((completedSteps / recentWork.length) * 100) : 0
  const avgTiming = recentWork.length
    ? Math.round(recentWork.reduce((acc, s) => acc + (Number(s.timing_ms) || 0), 0) / recentWork.length)
    : 0
  const performanceScore = Math.min(100, Math.max(0, Number(agent.performance_score) * 100 || 0))
  const circumference = 2 * Math.PI * 36
  const strokeDash = (performanceScore / 100) * circumference

  const startEditName = () => {
    setNameEdit(agent.name || '')
    setEditingName(true)
  }
  const cancelEditName = () => {
    setEditingName(false)
    setNameEdit('')
  }
  const saveName = async () => {
    const trimmed = (nameEdit || '').trim()
    if (trimmed === (agent.name || '').trim()) {
      setEditingName(false)
      return
    }
    setSavingName(true)
    try {
      const res = await fetch(apiUrl(`/api/agents/${encodeURIComponent(agentId)}`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Update failed')
      await loadDetail()
      setEditingName(false)
    } catch (err) {
      alert(err.message)
    } finally {
      setSavingName(false)
    }
  }

  const saveSystemInstructions = async () => {
    setSavingInstructions(true)
    try {
      const res = await fetch(apiUrl(`/api/agents/${encodeURIComponent(agentId)}`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_instructions: systemInstructionsEdit }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Update failed')
      await loadDetail()
      setSystemInstructionsDirty(false)
    } catch (err) {
      alert(err.message)
    } finally {
      setSavingInstructions(false)
    }
  }

  const toggleStatus = async () => {
    const next = (agent.status === 'active' || !agent.is_suspended) ? 'suspended' : 'active'
    if (!window.confirm(`Set status to ${next}?`)) return
    setSavingStatus(true)
    try {
      const res = await fetch(apiUrl(`/api/agents/${encodeURIComponent(agentId)}`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: next }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Update failed')
      await loadDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setSavingStatus(false)
    }
  }

  const setAvatarColor = async (color, initialsVal) => {
    setSavingAvatar(true)
    setShowAvatarColors(false)
    try {
      const body = { color, initials: initialsVal || avatarInitials }
      if (avatarImageUrl) body.imageDataUrl = avatarImageUrl
      const res = await fetch(apiUrl(`/api/agents/${encodeURIComponent(agentId)}/avatar`), {
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
      const res = await fetch(apiUrl(`/api/agents/${encodeURIComponent(agentId)}/avatar`), {
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
      const res = await fetch(apiUrl(`/api/agents/${encodeURIComponent(agentId)}/avatar`), {
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

  const isActive = agent.status === 'active' && !agent.is_suspended

  return (
    <PageLayout size="wide" padded className="!max-w-none">
      <div className="mb-4 flex items-center gap-2">
        <Link
          to="/agents"
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Agents
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[40%_60%] gap-6">
        {/* LEFT: Profile & Settings */}
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
                {editingName ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="text"
                      value={nameEdit}
                      onChange={(e) => setNameEdit(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveName()
                        if (e.key === 'Escape') cancelEditName()
                      }}
                      className="flex-1 min-w-[120px] px-2 py-1 border border-slate-300 rounded text-lg font-semibold text-slate-900"
                      autoFocus
                    />
                    <button type="button" onClick={saveName} disabled={savingName} className="btn-manage text-sm">
                      Save
                    </button>
                    <button type="button" onClick={cancelEditName} className="px-2 py-1 text-slate-600 text-sm">
                      Cancel
                    </button>
                  </div>
                ) : (
                  <h1
                    className="text-xl font-bold text-slate-900 cursor-pointer hover:bg-slate-50 rounded px-1 -mx-1"
                    onClick={startEditName}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && startEditName()}
                  >
                    {agent.name || '—'}
                  </h1>
                )}
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
                    onClick={toggleStatus}
                    disabled={savingStatus}
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none ${isActive ? 'bg-green-500' : 'bg-slate-300'}`}
                    role="switch"
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition translate-x-0.5 ${isActive ? 'translate-x-5' : 'translate-x-0.5'}`}
                    />
                  </button>
                  <span className={`text-xs font-medium ${isActive ? 'text-green-700' : 'text-red-700'}`}>
                    {isActive ? 'Active' : 'Suspended'}
                  </span>
                </div>
                <p className="text-xs text-slate-500 font-mono mt-1">{agent.agent_id}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Hired: {relativeTime(agent.hired_at)} · Updated: {relativeTime(agent.updated_at)}
                </p>
              </div>
            </div>
          </div>

          {/* System Instructions */}
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <button
              type="button"
              onClick={() => setSystemInstructionsOpen(!systemInstructionsOpen)}
              className="w-full flex items-center justify-between px-4 py-3 text-left font-semibold text-slate-900 bg-slate-50/50"
            >
              System Instructions
              {systemInstructionsOpen ? (
                <ChevronDown className="w-4 h-4 text-slate-500" />
              ) : (
                <ChevronRight className="w-4 h-4 text-slate-500" />
              )}
            </button>
            {systemInstructionsOpen && (
              <div className="p-4 border-t border-slate-200">
                <textarea
                  value={systemInstructionsEdit}
                  onChange={(e) => {
                    setSystemInstructionsEdit(e.target.value)
                    setSystemInstructionsDirty(true)
                  }}
                  rows={6}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-800 font-mono"
                  placeholder="System instructions or prompt..."
                />
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-slate-500">{systemInstructionsEdit.length} characters</span>
                  <button
                    type="button"
                    onClick={saveSystemInstructions}
                    disabled={!systemInstructionsDirty || savingInstructions}
                    className="btn-manage text-sm"
                  >
                    {savingInstructions ? 'Saving…' : 'Save'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Tools Access */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-2">Tools Access</h3>
            <div className="flex flex-wrap gap-1.5">
              {toolsList.map((t, i) => (
                <span
                  key={i}
                  className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700"
                >
                  {typeof t === 'string' ? t : t.name || JSON.stringify(t)}
                </span>
              ))}
              <span className="text-xs text-slate-400">(add/remove via API)</span>
            </div>
          </div>

          {/* Knowledge Sources */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-2">Knowledge Sources</h3>
            {knowledgeSources.length === 0 ? (
              <p className="text-xs text-slate-500">No sources</p>
            ) : (
              <ul className="space-y-2">
                {knowledgeSources.map((src, i) => (
                  <li key={i} className="flex items-start justify-between gap-2 text-xs">
                    <span className="min-w-0 truncate text-slate-700">
                      {typeof src === 'string' ? src : (src?.url || src?.source || JSON.stringify(src))}
                    </span>
                    {typeof src === 'object' && (src.chunks != null || src.added_at) && (
                      <span className="text-slate-400 shrink-0">
                        {src.chunks != null ? `${src.chunks} chunks` : ''}
                        {src.added_at ? ` · ${relativeTime(src.added_at)}` : ''}
                      </span>
                    )}
                    <button type="button" className="text-red-600 hover:underline shrink-0" title="Remove (API)">
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* RIGHT: Performance & Activity */}
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
    </PageLayout>
  )
}
