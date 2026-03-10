import { useState, useEffect, useCallback, useRef } from 'react'
import { MessageCircle, Send, Loader2, Bookmark } from 'lucide-react'
import { apiUrl } from '../apiClient'
import { buildAuthHeaders } from '../authz'

const SOFT_LIMIT = 10000
const HARD_BLOCK = 20000

function initials(name) {
  if (!name || typeof name !== 'string') return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  return (name[0] || '?').toUpperCase()
}

function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function AgentAvatar({ agent, size = 'sm' }) {
  const avatarConfig = (agent?.permissions && typeof agent.permissions === 'object' && agent.permissions?.avatar) || {}
  const avatarImageUrl = avatarConfig.imageDataUrl || avatarConfig.imageUrl || null
  const avatarInitials = avatarConfig.initials != null ? avatarConfig.initials : initials(agent?.name)
  const AVATAR_COLORS = ['bg-indigo-600', 'bg-emerald-600', 'bg-amber-500', 'bg-rose-600']
  const color = AVATAR_COLORS[Math.abs((agent?.name || '').length) % AVATAR_COLORS.length]
  const sizeClass = size === 'sm' ? 'w-8 h-8 text-sm' : 'w-10 h-10 text-base'
  return (
    <div
      className={`rounded-full flex items-center justify-center shrink-0 ${sizeClass} ${!avatarImageUrl ? `${color} text-white font-semibold` : 'bg-slate-100'}`}
    >
      {avatarImageUrl ? (
        <img src={avatarImageUrl} alt="" className="w-full h-full rounded-full object-cover" />
      ) : (
        avatarInitials
      )}
    </div>
  )
}

export default function AgentDirectChat({ agentId, agent }) {
  const [chats, setChats] = useState([])
  const [selectedChat, setSelectedChat] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sessionTokens, setSessionTokens] = useState(0)
  const [warning, setWarning] = useState(null)
  const [blocked, setBlocked] = useState(false)
  const [loadingChats, setLoadingChats] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [saveModal, setSaveModal] = useState(null)
  const [savingToMemory, setSavingToMemory] = useState(false)
  const messagesEndRef = useRef(null)
  const scrollRef = useRef(null)

  const fetchWithAuth = useCallback(async (url, options = {}) => {
    const headers = await buildAuthHeaders(options.headers || {})
    return fetch(apiUrl(url), { ...options, headers: { ...headers, ...options.headers } })
  }, [])

  const loadChats = useCallback(async () => {
    if (!agentId) return
    setLoadingChats(true)
    try {
      const res = await fetchWithAuth(`/api/agents/${encodeURIComponent(agentId)}/chats`)
      if (res.ok) {
        const data = await res.json()
        setChats(Array.isArray(data) ? data : [])
      } else {
        setChats([])
      }
    } catch {
      setChats([])
    } finally {
      setLoadingChats(false)
    }
  }, [agentId, fetchWithAuth])

  const loadChat = useCallback(
    async (chat) => {
      if (!chat || !agentId) return
      setSelectedChat(chat)
      setLoadingMessages(true)
      try {
        const res = await fetchWithAuth(
          `/api/agents/${encodeURIComponent(agentId)}/chats/${encodeURIComponent(chat.chat_id)}`
        )
        if (res.ok) {
          const data = await res.json()
          setMessages(data.messages || [])
          setSessionTokens(data.chat?.token_used || 0)
          setBlocked((data.chat?.token_used || 0) >= HARD_BLOCK)
        } else {
          setMessages([])
        }
      } catch {
        setMessages([])
      } finally {
        setLoadingMessages(false)
      }
    },
    [agentId, fetchWithAuth]
  )

  const createChat = useCallback(async () => {
    if (!agentId) return
    setSending(true)
    try {
      const res = await fetchWithAuth(`/api/agents/${encodeURIComponent(agentId)}/chats`, {
        method: 'POST',
      })
      if (res.ok) {
        const data = await res.json()
        await loadChats()
        setSelectedChat({ chat_id: data.chat_id, agent_id: data.agent_id, title: null, message_count: 0, token_used: 0 })
        setMessages([])
        setSessionTokens(0)
        setBlocked(false)
        setWarning(null)
      }
    } catch (err) {
      console.error('Create chat failed:', err)
    } finally {
      setSending(false)
    }
  }, [agentId, fetchWithAuth, loadChats])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || !selectedChat || !agentId || sending || blocked) return

    setSending(true)
    setInput('')
    const userMsg = { role: 'user', content: text, created_at: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])

    try {
      const res = await fetchWithAuth(
        `/api/agents/${encodeURIComponent(agentId)}/chats/${encodeURIComponent(selectedChat.chat_id)}/message`,
        {
          method: 'POST',
          body: JSON.stringify({ message: text }),
        }
      )
      const data = await res.json().catch(() => ({}))
      if (res.ok && !data.error) {
        setMessages((prev) => [
          ...prev,
          { role: 'agent', content: data.agent_response || '', created_at: new Date().toISOString(), message_id: data.message_id },
        ])
        setSessionTokens(data.session_tokens_used || 0)
        setWarning(data.warning || null)
        setBlocked((data.session_tokens_used || 0) >= HARD_BLOCK)
        await loadChats()
      } else {
        setMessages((prev) => prev.filter((m) => m !== userMsg))
        if (data.error === 'session_token_limit_reached') {
          setBlocked(true)
        }
        alert(data.detail || 'Failed to send message')
      }
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m !== userMsg))
      alert(err.message || 'Failed to send message')
    } finally {
      setSending(false)
    }
  }, [input, selectedChat, agentId, sending, blocked, fetchWithAuth, loadChats])

  useEffect(() => {
    loadChats()
  }, [loadChats])

  useEffect(() => {
    if (selectedChat) loadChat(selectedChat)
  }, [selectedChat?.chat_id])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const openSaveModal = (msg) => {
    if (msg.role === 'agent') setSaveModal({ message_id: msg.message_id, content: msg.content })
  }

  const closeSaveModal = () => setSaveModal(null)

  const saveToMemory = async (label) => {
    if (!saveModal || !selectedChat || !agentId) return
    setSavingToMemory(true)
    try {
      const headers = await buildAuthHeaders()
      const res = await fetch(apiUrl(`/api/agents/${encodeURIComponent(agentId)}/knowledge/save`), {
        method: 'POST',
        headers,
        body: JSON.stringify({ chat_id: selectedChat.chat_id, message_id: saveModal.message_id, label: label || null }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Save failed')
      closeSaveModal()
    } catch (err) {
      alert(err.message || 'Opslaan mislukt')
    } finally {
      setSavingToMemory(false)
    }
  }

  const tokenPct = SOFT_LIMIT > 0 ? (sessionTokens / SOFT_LIMIT) * 100 : 0
  const tokenIndicatorClass =
    tokenPct >= 200 ? 'text-red-600 font-semibold' : tokenPct >= 80 ? 'text-amber-600' : 'text-slate-500'

  const emptyState = !selectedChat || (messages.length === 0 && !sending)
  const agentName = agent?.name || agent?.agent_name || 'Agent'
  const agentGoal = agent?.goal || ''

  return (
    <div className="flex flex-col h-[600px] bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="flex flex-1 min-h-0">
        {/* ChatHistoryPanel */}
        <div className="w-56 border-r border-slate-200 flex flex-col bg-slate-50/50">
          <div className="p-2 border-b border-slate-200">
            <button
              type="button"
              onClick={createChat}
              disabled={sending}
              className="w-full py-2 px-3 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
            >
              Nieuwe chat
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {loadingChats ? (
              <div className="text-xs text-slate-500 py-4">Laden...</div>
            ) : chats.length === 0 ? (
              <div className="text-xs text-slate-500 py-4">Geen chats</div>
            ) : (
              chats.map((c) => (
                <button
                  key={c.chat_id}
                  type="button"
                  onClick={() => loadChat(c)}
                  className={`w-full text-left py-2 px-3 rounded-lg mb-1 text-sm ${
                    selectedChat?.chat_id === c.chat_id
                      ? 'bg-indigo-100 text-indigo-800'
                      : 'hover:bg-slate-100 text-slate-700'
                  }`}
                >
                  <div className="truncate font-medium">{c.title || 'Direct Chat'}</div>
                  <div className="text-xs text-slate-500 truncate">{c.last_message_at ? new Date(c.last_message_at).toLocaleDateString() : ''}</div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {emptyState && !selectedChat ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
              <MessageCircle className="w-16 h-16 text-slate-300 mb-4" />
              <p className="text-lg font-semibold text-slate-800">
                Stel {agentName} een vraag over {agentGoal || 'hun expertise'}
              </p>
              <p className="text-sm text-slate-500 mt-2">
                Klik op &quot;Nieuwe chat&quot; om te beginnen
              </p>
            </div>
          ) : emptyState && selectedChat ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
              <MessageCircle className="w-16 h-16 text-slate-300 mb-4" />
              <p className="text-lg font-semibold text-slate-800">
                Stel {agentName} een vraag over {agentGoal || 'hun expertise'}
              </p>
              <p className="text-sm text-slate-500 mt-2">
                Typ je bericht hieronder en druk op Enter
              </p>
            </div>
          ) : (
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.message_id || `${msg.role}-${msg.created_at}-${msg.content?.slice(0, 20)}`}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-xl px-4 py-2.5 ${
                      msg.role === 'user'
                        ? 'bg-[var(--color-direct-chat-user)] text-white'
                        : 'bg-slate-100 text-slate-800'
                    }`}
                  >
                    {msg.role === 'agent' && (
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <div className="flex items-center gap-2">
                          <AgentAvatar agent={agent} size="sm" />
                          <span className="text-xs font-medium text-slate-600">
                            {agentName} — {agent?.role || ''}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => openSaveModal(msg)}
                          className="p-1 rounded text-slate-400 hover:text-indigo-600 hover:bg-indigo-50"
                          title="Opslaan als kennisbron"
                        >
                          <Bookmark className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    <span className={`text-xs block mt-1 ${msg.role === 'user' ? 'text-slate-300' : 'text-slate-500'}`}>
                      {formatTime(msg.created_at)}
                    </span>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}

          {/* TokenIndicator + ChatInput */}
          <div className="border-t border-slate-200 p-3 bg-white">
            <div className={`text-xs mb-2 ${tokenIndicatorClass}`}>
              {blocked ? (
                'Sessielimiet bereikt. Start een nieuwe sessie.'
              ) : (
                <>Sessie: {sessionTokens.toLocaleString()} / {SOFT_LIMIT.toLocaleString()} tokens</>
              )}
            </div>
            <div className="flex gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Typ je bericht..."
                rows={2}
                disabled={blocked || sending}
                className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm resize-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-slate-100"
              />
              <button
                type="button"
                onClick={sendMessage}
                disabled={!input.trim() || blocked || sending}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {sending ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {saveModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={closeSaveModal}>
          <div
            className="bg-white rounded-xl p-6 shadow-xl max-w-md w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-slate-900 mb-2">
              Opslaan als kennisbron voor {agentName}?
            </h3>
            <p className="text-sm text-slate-600 mb-4">Dit bericht wordt toegevoegd aan de kennisbank van de agent.</p>
            <input
              type="text"
              placeholder="Optioneel label (bijv. B2C toon advies)"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm mb-4"
              id="save-memory-label"
            />
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={closeSaveModal}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Annuleren
              </button>
              <button
                type="button"
                onClick={() => saveToMemory(document.getElementById('save-memory-label')?.value?.trim() || null)}
                disabled={savingToMemory}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {savingToMemory ? 'Opslaan…' : 'Opslaan'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
