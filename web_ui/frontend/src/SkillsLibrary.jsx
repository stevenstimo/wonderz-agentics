import { useState, useEffect, useRef } from 'react'
import { Send, Loader2, Upload } from 'lucide-react'
import { apiUrl } from './apiClient'
import PageLayout from './PageLayout'

const DOMAIN_BADGE = {
  seo: 'bg-blue-100 text-blue-800',
  copywriting: 'bg-purple-100 text-purple-800',
  quality: 'bg-red-100 text-red-800',
  management: 'bg-indigo-100 text-indigo-800',
  structure: 'bg-amber-100 text-amber-800',
  voice: 'bg-emerald-100 text-emerald-800',
}

function domainBadgeClass(domain) {
  if (!domain) return 'bg-slate-100 text-slate-600'
  const key = String(domain).toLowerCase().replace(/\s+/g, '_')
  return DOMAIN_BADGE[key] || 'bg-slate-100 text-slate-600'
}

const WELCOME_MESSAGE = 'Ask me about skills, upload a document, or check for gaps in the library.'

export default function SkillsLibrary() {
  const [skills, setSkills] = useState([])
  const [selectedSkill, setSelectedSkill] = useState(null)
  const [domainFilter, setDomainFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [sendingChat, setSendingChat] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [lastUploadId, setLastUploadId] = useState(null)
  const [proposedSkills, setProposedSkills] = useState([])
  const [handledState, setHandledState] = useState({})
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)
  const chatEndRef = useRef(null)

  useEffect(() => {
    loadSkills()
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, proposedSkills])

  async function loadSkills() {
    setLoading(true)
    try {
      const url = domainFilter
        ? apiUrl(`/api/skills?domain=${encodeURIComponent(domainFilter)}`)
        : apiUrl('/api/skills')
      const res = await fetch(url)
      const data = await res.json()
      setSkills(data.skills || [])
    } catch (err) {
      console.error('Failed to load skills:', err)
      setSkills([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSkills()
  }, [domainFilter])

  async function handleSendChat(e) {
    e?.preventDefault()
    const msg = (chatInput || '').trim()
    if (!msg || sendingChat) return
    setChatInput('')
    const userMsg = { role: 'user', content: msg }
    setChatMessages((prev) => [...prev, userMsg])
    setSendingChat(true)
    try {
      const res = await fetch(apiUrl('/api/skills/judson/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: msg,
          conversation_history: [...chatMessages, userMsg].map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Chat failed')
      setChatMessages((prev) => [...prev, { role: 'assistant', content: data.response || '' }])
    } catch (err) {
      setChatMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${err.message}` }])
    } finally {
      setSendingChat(false)
    }
  }

  function handleFile(files) {
    const file = files?.[0]
    if (!file) return
    if (fileInputRef.current) fileInputRef.current.value = ''
    setUploading(true)
    setChatMessages((prev) => [...prev, { role: 'assistant', content: 'Uploading…' }])
    const form = new FormData()
    form.append('file', file)
    fetch(apiUrl('/api/skills/judson/upload'), { method: 'POST', body: form })
      .then(async (res) => {
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Upload failed')
        return data
      })
      .then((data) => {
        setLastUploadId(data.upload_id)
        setChatMessages((prev) => prev.slice(0, -1).concat([{ role: 'assistant', content: `"${data.filename}" received. Analyzing…` }]))
        setUploading(false)
        setAnalyzing(true)
        return fetch(apiUrl('/api/skills/judson/analyze'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ upload_id: data.upload_id }),
        })
      })
      .then(async (res) => {
        const analyzeData = await res.json()
        if (!res.ok) throw new Error(analyzeData.detail || 'Analysis failed')
        return analyzeData
      })
      .then((analyzeData) => {
        setAnalyzing(false)
        setProposedSkills(analyzeData.proposed_skills || [])
        setHandledState({})
        setChatMessages((prev) =>
          prev.slice(0, -1).concat([
            {
              role: 'assistant',
              content:
                (analyzeData.message || '') +
                (analyzeData.proposed_skills?.length ? `\n\nFound ${analyzeData.proposed_skills.length} proposed skill(s) below. Approve or skip each.` : ''),
            },
          ])
        )
      })
      .catch((err) => {
        setUploading(false)
        setAnalyzing(false)
        setChatMessages((prev) => prev.slice(0, -1).concat([{ role: 'assistant', content: `Error: ${err.message}` }]))
      })
  }

  async function handleFileSelect(e) {
    handleFile(e.target?.files)
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    handleFile(e.dataTransfer?.files)
  }

  function handleDragOver(e) {
    e.preventDefault()
    setDragOver(true)
  }

  function handleDragLeave() {
    setDragOver(false)
  }

  async function handleApproveSkills(approvedIndices) {
    if (!lastUploadId || approvedIndices.length === 0) return
    try {
      const res = await fetch(apiUrl('/api/skills/judson/approve'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upload_id: lastUploadId, approved_skill_indices: approvedIndices }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Approve failed')
      setChatMessages((prev) => [...prev, { role: 'assistant', content: data.message || 'Approved.' }])
      setHandledState((prev) => {
        const next = { ...prev }
        approvedIndices.forEach((i) => { next[i] = 'approved' })
        const allHandled = proposedSkills.length > 0 && proposedSkills.every((_, i) => next[i] != null)
        if (allHandled) {
          setProposedSkills([])
          setLastUploadId(null)
          loadSkills()
        }
        return next
      })
      loadSkills()
    } catch (err) {
      setChatMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${err.message}` }])
    }
  }

  function handleSkipSkill(idx) {
    setHandledState((prev) => {
      const next = { ...prev, [idx]: 'skipped' }
      const allHandled = proposedSkills.length > 0 && proposedSkills.every((_, i) => next[i] != null)
      if (allHandled) {
        setProposedSkills([])
        setLastUploadId(null)
        loadSkills()
      }
      return next
    })
  }

  const domains = [...new Set(skills.map((s) => s.domain).filter(Boolean))].sort()
  const showWelcome = chatMessages.length === 0 && !sendingChat && !uploading && !analyzing

  return (
    <PageLayout size="wide" padded className="!max-w-none !p-0">
      <div className="flex h-[calc(100vh-var(--top-header-height,56px))] overflow-hidden">
        {/* Left: Judson Chat — messages scroll, input sticky */}
        <div className="w-full lg:w-96 flex-shrink-0 flex flex-col border-r border-slate-200 bg-white overflow-hidden">
          <div className="flex-shrink-0 p-6 border-b border-slate-200 bg-slate-50/50">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center text-white font-semibold flex-shrink-0">
                J
              </div>
              <div>
                <p className="font-semibold text-slate-900">Judson</p>
                <p className="text-sm text-slate-500">Library Owner</p>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-4 min-h-0">
            {showWelcome && (
              <div className="flex gap-2 justify-start">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-white text-xs font-semibold">
                  J
                </div>
                <div className="flex flex-col gap-0.5 max-w-[85%]">
                  <span className="text-xs text-slate-500">Judson</span>
                  <div className="px-4 py-2.5 rounded-xl rounded-tl-none bg-slate-700 text-white">
                    <p className="text-sm">{WELCOME_MESSAGE}</p>
                  </div>
                </div>
              </div>
            )}
            {chatMessages.map((msg, i) => (
              <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'assistant' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-white text-xs font-semibold">
                    J
                  </div>
                )}
                <div className={`flex flex-col gap-0.5 max-w-[85%] ${msg.role === 'user' ? 'items-end' : ''}`}>
                  {msg.role === 'assistant' && <span className="text-xs text-slate-500">Judson</span>}
                  <div
                    className={`px-4 py-2.5 rounded-xl whitespace-pre-wrap ${
                      msg.role === 'user' ? 'bg-indigo-600 text-white rounded-tr-none' : 'bg-slate-700 text-white rounded-tl-none'
                    }`}
                  >
                    <p className="text-sm">{msg.content || ''}</p>
                  </div>
                </div>
              </div>
            ))}
            {(uploading || analyzing || sendingChat) && (
              <div className="flex gap-2 justify-start items-center text-slate-500 text-sm">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-white text-xs font-semibold">
                  J
                </div>
                <div className="px-4 py-2.5 rounded-xl rounded-tl-none bg-slate-100 text-slate-600 flex items-center gap-1">
                  {uploading ? 'Uploading…' : analyzing ? 'Analyzing…' : 'Judson is thinking…'}
                  <Loader2 className="w-4 h-4 animate-spin" />
                </div>
              </div>
            )}
            {proposedSkills.length > 0 && (
              <div className="space-y-2 mt-4">
                <p className="text-xs font-medium text-slate-600">Proposed skills — approve or skip</p>
                {proposedSkills.map((skill, idx) => {
                  const status = handledState[idx]
                  return (
                    <div key={idx} className="rounded-lg border border-slate-200 p-3 bg-slate-50">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className="font-medium text-slate-800">{skill.name}</span>
                        <div className="flex gap-1 items-center">
                          {status === 'approved' && (
                            <span className="px-2 py-1 text-xs font-medium rounded bg-green-100 text-green-800">Approved</span>
                          )}
                          {status === 'skipped' && (
                            <span className="px-2 py-1 text-xs font-medium rounded bg-slate-200 text-slate-600">Skipped</span>
                          )}
                          {!status && (
                            <>
                              <button
                                type="button"
                                onClick={() => handleApproveSkills([idx])}
                                className="px-2 py-1 text-xs font-medium rounded bg-green-600 text-white hover:bg-green-700"
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                onClick={() => handleSkipSkill(idx)}
                                className="px-2 py-1 text-xs font-medium rounded bg-slate-200 text-slate-700 hover:bg-slate-300"
                              >
                                Skip
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">{skill.domain} · {skill.skill_type}</p>
                    </div>
                  )
                })}
                {!proposedSkills.every((_, i) => handledState[i] != null) && (
                  <button
                    type="button"
                    onClick={() => handleApproveSkills(proposedSkills.map((_, i) => i).filter((i) => !handledState[i]))}
                    className="text-sm font-medium text-indigo-600 hover:text-indigo-800"
                  >
                    Approve all remaining
                  </button>
                )}
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Upload + Input — sticky onderaan */}
          <div className="flex-shrink-0 p-4 border-t border-slate-100 space-y-3 bg-white">
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-4 flex items-center justify-center gap-2 cursor-pointer transition ${
                dragOver ? 'border-indigo-400 bg-indigo-50/50' : 'border-slate-200 hover:border-slate-300 bg-slate-50/50'
              } ${uploading || analyzing ? 'pointer-events-none opacity-60' : ''}`}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept=".pdf,.xlsx,.xls,.csv,.docx,.txt,.md,.skill"
                className="hidden"
              />
              <Upload className="w-5 h-5 text-slate-500" />
              <span className="text-sm text-slate-600">Drop a document or click to upload</span>
            </div>
            <p className="text-xs text-slate-400 text-center">
              PDF, Excel (.xlsx, .xls), CSV, Word (.docx), Markdown (.md), Skill files (.skill)
            </p>
            <form onSubmit={handleSendChat} className="flex gap-2">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask Judson or describe a skill..."
                className="flex-1 px-4 py-3 border border-slate-200 rounded-xl text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none min-h-[44px] max-h-32"
                disabled={sendingChat || uploading || analyzing}
                rows={1}
              />
              <button
                type="submit"
                disabled={sendingChat || !chatInput.trim() || uploading || analyzing}
                className="w-10 h-10 bg-indigo-600 text-white rounded-xl flex items-center justify-center hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex-shrink-0"
              >
                <Send className="w-5 h-5" />
              </button>
            </form>
          </div>
        </div>

        {/* Right: Skills grid — filter tabs sticky, grid scrollbaar */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <div className="flex-shrink-0 p-6 border-b border-slate-100 bg-white">
            <h2 className="text-xl font-semibold text-slate-900 mb-4">Skills Library ({skills.length})</h2>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setDomainFilter('')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                  !domainFilter ? 'bg-indigo-600 text-white' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                All
              </button>
              {domains.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDomainFilter(d)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                    domainFilter === d ? 'bg-indigo-600 text-white' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-6 min-h-0 min-w-0">
            {loading && <p className="text-slate-500 text-sm">Loading…</p>}
            {!loading && skills.length === 0 && (
              <p className="text-slate-500 text-sm">No skills yet. Upload a document or ask Judson.</p>
            )}
            {!loading && skills.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 overflow-hidden min-w-0">
                {skills.map((skill) => (
                  <div
                    key={skill.skill_id}
                    onClick={() => setSelectedSkill(selectedSkill?.skill_id === skill.skill_id ? null : skill)}
                    className="flex flex-col justify-between h-full bg-white border border-slate-200 rounded-xl p-4 hover:shadow-md hover:border-slate-300 transition cursor-pointer text-left min-w-0 break-words"
                  >
                    <div className="flex-1 min-h-0">
                      <div className="flex items-start justify-between gap-2 min-w-0">
                        <h4 className="font-medium text-slate-900 line-clamp-2 flex-1 min-w-0 break-words">{skill.name}</h4>
                        <span
                          className={`flex-shrink-0 text-xs px-2 py-0.5 rounded ${
                            (skill.status || 'active') === 'active'
                              ? 'bg-green-100 text-green-800'
                              : (skill.status || '') === 'draft'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {skill.status || 'active'}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        <span className={`text-xs px-2 py-0.5 rounded font-medium ${domainBadgeClass(skill.domain)}`}>
                          {skill.domain || '—'}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                          {skill.skill_type || '—'}
                        </span>
                      </div>
                      <div className="mt-2 text-[11px] text-slate-400">
                        {skill.success_rate != null ? `${(skill.success_rate * 100).toFixed(0)}% success` : ''}
                        {skill.success_rate != null && (skill.usage_count || 0) > 0 ? ' · ' : ''}
                        {skill.usage_count || 0} uses
                      </div>
                    </div>
                    {selectedSkill?.skill_id === skill.skill_id && (
                      <div className="mt-3 pt-3 border-t border-slate-200 text-sm text-slate-700 whitespace-pre-wrap break-words">
                        {(skill.content || '').slice(0, 500)}
                        {(skill.content || '').length > 500 ? '…' : ''}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
