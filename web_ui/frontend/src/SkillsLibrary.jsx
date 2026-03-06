import { useState, useEffect, useRef } from 'react'
import { BookOpen, Paperclip, Send, Loader2 } from 'lucide-react'
import { apiUrl } from './apiClient'
import PageLayout from './PageLayout'

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
  const [handledState, setHandledState] = useState({}) // index -> 'approved' | 'skipped'
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

  async function handleFileSelect(e) {
    const file = e.target?.files?.[0]
    if (!file) return
    e.target.value = ''
    setUploading(true)
    setChatMessages((prev) => [...prev, { role: 'assistant', content: 'Uploading…' }])
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(apiUrl('/api/skills/judson/upload'), {
        method: 'POST',
        body: form,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Upload failed')
      setLastUploadId(data.upload_id)
      setChatMessages((prev) => prev.slice(0, -1).concat([{ role: 'assistant', content: `"${data.filename}" received. Analyzing…` }]))
      setUploading(false)
      setAnalyzing(true)
      const analyzeRes = await fetch(apiUrl('/api/skills/judson/analyze'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upload_id: data.upload_id }),
      })
      const analyzeData = await analyzeRes.json()
      setAnalyzing(false)
      if (!analyzeRes.ok) throw new Error(analyzeData.detail || 'Analysis failed')
      setProposedSkills(analyzeData.proposed_skills || [])
      setHandledState({})
      setChatMessages((prev) => prev.slice(0, -1).concat([
        { role: 'assistant', content: (analyzeData.message || '') + (analyzeData.proposed_skills?.length ? `\n\nFound ${analyzeData.proposed_skills.length} proposed skill(s) below. Approve or skip each.` : '') },
      ]))
    } catch (err) {
      setUploading(false)
      setAnalyzing(false)
      setChatMessages((prev) => prev.slice(0, -1).concat([{ role: 'assistant', content: `Error: ${err.message}` }]))
    }
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
          setHandledState({})
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
        setHandledState({})
        loadSkills()
      }
      return next
    })
  }

  const domains = [...new Set(skills.map((s) => s.domain).filter(Boolean))].sort()

  return (
    <PageLayout size="wide" padded className="space-y-4 !max-w-none">
      <div className="grid grid-cols-1 md:grid-cols-[55%_45%] gap-4 min-h-[calc(100vh-8rem)]">
        {/* Left: Judson Chat */}
        <div className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden min-h-0">
          <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-slate-600" />
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Judson</h2>
              <p className="text-xs text-slate-500">Library Owner</p>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto space-y-4 p-4 min-h-[10rem]">
            {chatMessages.length === 0 && !sendingChat && !uploading && !analyzing && (
              <p className="text-slate-500 text-sm">Ask Judson about skills, upload a document to extract skills, or check gaps.</p>
            )}
            {chatMessages.map((msg, i) => (
              <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'assistant' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-slate-100 text-xs font-semibold">J</div>
                )}
                <div className={`flex flex-col gap-0.5 max-w-[80%] ${msg.role === 'user' ? 'items-end' : ''}`}>
                  {msg.role === 'assistant' && <span className="text-xs text-slate-500">Judson</span>}
                  <div
                    className={`px-4 py-2.5 rounded-xl whitespace-pre-wrap ${
                      msg.role === 'user' ? 'bg-indigo-600 text-white rounded-tr-none' : 'bg-slate-700 text-slate-100 rounded-tl-none'
                    }`}
                  >
                    <p className="text-sm">{msg.content || ''}</p>
                  </div>
                </div>
              </div>
            ))}
            {(uploading || analyzing || sendingChat) && (
              <div className="flex gap-2 justify-start items-center text-slate-500 text-sm">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-slate-100 text-xs font-semibold">J</div>
                <div className="px-4 py-2.5 rounded-xl rounded-tl-none bg-slate-100 text-slate-600 flex items-center gap-1">
                  {uploading ? 'Uploading…' : analyzing ? 'Analyzing…' : 'Judson is thinking…'}
                  <Loader2 className="w-4 h-4 animate-spin" />
                </div>
              </div>
            )}
            {proposedSkills.length > 0 && (
              <div className="space-y-2 mt-4">
                <p className="text-xs font-medium text-slate-600">Proposed skills — approve or skip (cards stay until all are handled)</p>
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
          <form onSubmit={handleSendChat} className="flex-shrink-0 flex gap-2 p-3 border-t border-slate-200 bg-white">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept=".pdf,.txt,.md,.doc"
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading || analyzing}
              className="p-2.5 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              aria-label="Upload file"
            >
              <Paperclip className="w-5 h-5" />
            </button>
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask Judson or describe a skill..."
              className="flex-1 px-4 py-2.5 border border-slate-300 rounded-xl text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              disabled={sendingChat || uploading || analyzing}
            />
            <button
              type="submit"
              disabled={sendingChat || !chatInput.trim() || uploading || analyzing}
              className="px-5 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>

        {/* Right: Skills Library */}
        <div className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden min-h-0">
          <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200 flex items-center justify-between gap-2 flex-wrap">
            <h3 className="text-lg font-semibold text-slate-900">Skills Library</h3>
            <span className="text-sm text-slate-500">{skills.length} skills</span>
          </div>
          <div className="flex-shrink-0 px-4 py-2 border-b border-slate-100 flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => setDomainFilter('')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${!domainFilter ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
            >
              All
            </button>
            {domains.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDomainFilter(d)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium ${domainFilter === d ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
              >
                {d}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {loading && <p className="text-slate-500 text-sm">Loading…</p>}
            {!loading && skills.length === 0 && <p className="text-slate-500 text-sm">No skills yet. Upload a document or ask Judson.</p>}
            {!loading && skills.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {skills.map((skill) => (
                  <div
                    key={skill.skill_id}
                    onClick={() => setSelectedSkill(selectedSkill?.skill_id === skill.skill_id ? null : skill)}
                    className="rounded-lg border border-slate-200 p-4 hover:border-indigo-300 hover:bg-slate-50/50 transition cursor-pointer"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-medium text-slate-900 truncate">{skill.name}</h4>
                      <span className={`flex-shrink-0 text-xs px-2 py-0.5 rounded ${(skill.status || 'active') === 'active' ? 'bg-green-100 text-green-800' : (skill.status || '') === 'draft' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600'}`}>
                        {skill.status || 'active'}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-2">
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-700">{skill.domain}</span>
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600">{skill.skill_type}</span>
                    </div>
                    <div className="mt-2 text-xs text-slate-500">
                      {skill.success_rate != null ? `${(skill.success_rate * 100).toFixed(0)}% success` : ''}
                      {(skill.success_rate != null && (skill.usage_count || 0) > 0) ? ' · ' : ''}
                      {skill.usage_count || 0} uses
                    </div>
                    {selectedSkill?.skill_id === skill.skill_id && (
                      <div className="mt-3 pt-3 border-t border-slate-200 text-sm text-slate-700 whitespace-pre-wrap">
                        {(skill.content || '').slice(0, 500)}{(skill.content || '').length > 500 ? '…' : ''}
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
