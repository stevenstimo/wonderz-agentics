import { useState, useEffect, useCallback, useRef } from 'react'
import { MessageCircle, Send, Loader2, Bookmark } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import { apiUrl, apiFetch } from '../apiClient'

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
  const [chatError, setChatError] = useState(null)
  const [clients, setClients] = useState([])
  const [mentionSuggestions, setMentionSuggestions] = useState([])
  const skipLoadForChatIdRef = useRef(null)
  const messagesEndRef = useRef(null)
  const scrollRef = useRef(null)

  const fetchWithAuth = useCallback((url, options = {}) => apiFetch(url, options), [])

  useEffect(() => {
    fetchWithAuth('/api/clients')
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setClients(Array.isArray(data) ? data : (data?.clients ?? data ?? [])))
      .catch(() => setClients([]))
  }, [fetchWithAuth])

  const loadChats = useCallback(async () => {
    if (!agentId) return
    setLoadingChats(true)
    setChatError(null)
    try {
      const res = await fetchWithAuth(`/api/agents/${encodeURIComponent(agentId)}/chats`)
      if (res.ok) {
        const data = await res.json()
        setChats(Array.isArray(data) ? data : [])
      } else {
        setChats([])
        if (res.status === 401) setChatError('Niet ingelogd. Log opnieuw in.')
        else if (res.status === 403) setChatError('Geen rechten om chats te zien.')
      }
    } catch {
      setChats([])
      setChatError('Kon chats niet laden.')
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
    setChatError(null)
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
      } else {
        const contentType = res.headers.get('content-type') || ''
        let detail = `Fout ${res.status}`
        if (contentType.includes('application/json')) {
          try {
            const body = await res.json()
            detail = body.detail || body.message || detail
          } catch (_) {}
        }
        if (res.status === 401) detail = 'Niet ingelogd. Log opnieuw in.'
        if (res.status === 403) detail = 'Geen rechten om een chat te starten.'
        setChatError(detail)
      }
    } catch (err) {
      console.error('Create chat failed:', err)
      setChatError(err.message || 'Kon geen chat starten. Controleer je verbinding.')
    } finally {
      setSending(false)
    }
  }, [agentId, fetchWithAuth, loadChats])

  /** Ensure we have an active chat; create one if none selected. Returns chat_id or null on error. */
  const ensureActiveChat = useCallback(async () => {
    if (selectedChat?.chat_id) return selectedChat.chat_id
    if (!agentId) return null
    setChatError(null)
    try {
      const res = await fetchWithAuth(`/api/agents/${encodeURIComponent(agentId)}/chats`, { method: 'POST' })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        if (res.status === 401) setChatError('Niet ingelogd. Log opnieuw in.')
        else if (res.status === 403) setChatError('Geen rechten om een chat te starten.')
        else setChatError(data.detail || data.message || `Fout ${res.status}`)
        return null
      }
      const chatId = data.chat_id ?? data.id
      const newChat = { chat_id: chatId, agent_id: data.agent_id || agentId, title: null, message_count: 0, token_used: 0 }
      setSelectedChat(newChat)
      setMessages([])
      setSessionTokens(0)
      setBlocked(false)
      setWarning(null)
      skipLoadForChatIdRef.current = chatId
      await loadChats()
      return chatId
    } catch (err) {
      console.error('Chat aanmaken mislukt:', err)
      setChatError(err.message || 'Kon geen chat starten.')
      return null
    }
  }, [agentId, selectedChat?.chat_id, fetchWithAuth, loadChats])

  const doSendMessage = useCallback(
    async (chatId, text) => {
      if (!chatId || !text?.trim() || !agentId || sending || blocked) return
      setSending(true)
      const userMsg = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: text.trim(),
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMsg])
      try {
        const res = await fetchWithAuth(
          `/api/agents/${encodeURIComponent(agentId)}/chats/${encodeURIComponent(chatId)}/message`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text.trim() }),
          }
        )
        const data = await res.json().catch(() => ({}))
        if (process.env.NODE_ENV === 'development') {
          console.log('API response na send:', JSON.stringify(data, null, 2))
        }
        if (res.ok && !data.error) {
          const replyText = typeof data.agent_response === 'string' ? data.agent_response : (data.agent_response ? String(data.agent_response) : '')
          const agentMsg = {
            role: 'agent',
            content: replyText,
            created_at: new Date().toISOString(),
            message_id: data.message_id,
          }
          setMessages((prev) => {
            const rest = prev.filter((m) => m.id !== userMsg.id)
            return [...rest, { ...userMsg, id: userMsg.id }, agentMsg]
          })
          setSessionTokens(data.session_tokens_used || 0)
          setWarning(data.warning || null)
          setBlocked((data.session_tokens_used || 0) >= HARD_BLOCK)
          if (data.chat_title) {
            setChats((prev) =>
              prev.map((c) => (c.chat_id === chatId ? { ...c, title: data.chat_title } : c))
            )
            setSelectedChat((prev) =>
              prev?.chat_id === chatId ? { ...prev, title: data.chat_title } : prev
            )
            setTimeout(() => loadChats(), 500)
          } else {
            await loadChats()
          }
        } else {
          setMessages((prev) => prev.filter((m) => m.id !== userMsg.id))
          if (data.error === 'session_token_limit_reached') setBlocked(true)
          const msg = typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? (data.detail[0]?.msg || JSON.stringify(data.detail)) : (data.detail && typeof data.detail === 'object' ? JSON.stringify(data.detail) : 'Bericht verzenden mislukt.')
          setChatError(msg)
        }
      } catch (err) {
        setMessages((prev) => prev.filter((m) => m.id !== userMsg.id))
        setChatError(err.message || 'Bericht verzenden mislukt.')
      } finally {
        setSending(false)
      }
    },
    [agentId, sending, blocked, fetchWithAuth, loadChats]
  )

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text) return
    const activeChatId = await ensureActiveChat()
    if (!activeChatId) return
    setInput('')
    await doSendMessage(activeChatId, text)
  }, [input, ensureActiveChat, doSendMessage])

  useEffect(() => {
    loadChats()
  }, [loadChats])

  useEffect(() => {
    if (!selectedChat) return
    if (skipLoadForChatIdRef.current === selectedChat.chat_id) {
      skipLoadForChatIdRef.current = null
      return
    }
    loadChat(selectedChat)
  }, [selectedChat?.chat_id])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInputChange = (e) => {
    const val = e.target.value
    setInput(val)
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
    setInput((prev) => prev.replace(/@([a-zA-Z0-9_-]*)$/, `@${slug} `))
    setMentionSuggestions([])
  }

  const openSaveModal = (msg) => {
    if (msg.role === 'agent') setSaveModal({ message_id: msg.message_id, content: msg.content })
  }

  const closeSaveModal = () => setSaveModal(null)

  const saveToMemory = async (label) => {
    if (!saveModal || !selectedChat || !agentId) return
    setSavingToMemory(true)
    try {
      const res = await apiFetch(`/api/agents/${encodeURIComponent(agentId)}/knowledge/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: selectedChat.chat_id, message_id: saveModal.message_id, label: label || null }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const d = body.detail
        const msg = typeof d === 'string' ? d : Array.isArray(d) ? (d[0]?.msg || 'Opslaan mislukt') : 'Opslaan mislukt'
        throw new Error(msg)
      }
      closeSaveModal()
    } catch (err) {
      setChatError(err.message || 'Opslaan mislukt')
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
    <div className="flex flex-col h-[calc(100vh-180px)] bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="flex flex-1 min-h-0">
        {/* ChatHistoryPanel */}
        <div className="w-56 border-r border-slate-200 flex flex-col bg-slate-50/50">
          <div className="p-2 border-b border-slate-200">
            {chatError && (
              <div className="mb-2 px-2 py-1.5 rounded bg-red-50 text-red-700 text-xs" role="alert">
                {chatError}
              </div>
            )}
            <button
              type="button"
              onClick={createChat}
              disabled={sending}
              className="w-full py-2 px-3 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-1.5"
            >
              {sending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Bezig…
                </>
              ) : (
                'Nieuwe chat'
              )}
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
                Typ je bericht hieronder en druk op Enter of klik Verstuur — een chat wordt automatisch aangemaakt
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
            <div ref={scrollRef} className="flex-1 overflow-y-auto min-h-0 px-6 py-4 space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.id || msg.message_id || `${msg.role}-${msg.created_at}-${msg.content?.slice(0, 20)}`}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={
                      msg.role === 'user'
                        ? 'bg-indigo-600 text-white rounded-2xl rounded-br-sm px-4 py-3 max-w-[75%]'
                        : 'bg-gray-100 text-gray-800 rounded-2xl rounded-bl-sm px-4 py-3 max-w-[75%]'
                    }
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
                    {msg.role === 'user' ? (
                      <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                    ) : (
                      <ReactMarkdown
                        remarkPlugins={[remarkBreaks]}
                        className="prose prose-sm max-w-none text-sm"
                        components={{
                          strong: ({ children }) => <em className="italic">{children}</em>,
                          em: ({ children }) => <strong className="font-semibold">{children}</strong>,
                          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                          ul: ({ children }) => <ul className="list-disc pl-4 mb-2">{children}</ul>,
                          li: ({ children }) => <li className="mb-1">{children}</li>,
                          h1: ({ children }) => <h1 className="text-lg font-bold not-italic mt-3 mb-2">{children}</h1>,
                          h2: ({ children }) => <h2 className="text-base font-bold not-italic mt-3 mb-1.5">{children}</h2>,
                          h3: ({ children }) => <h3 className="text-sm font-bold not-italic mt-2 mb-1">{children}</h3>,
                          h4: ({ children }) => <h4 className="text-sm font-bold not-italic mt-2 mb-1">{children}</h4>,
                          h5: ({ children }) => <h5 className="text-sm font-bold not-italic mt-1 mb-0.5">{children}</h5>,
                          h6: ({ children }) => <h6 className="text-sm font-bold not-italic mt-1 mb-0.5">{children}</h6>,
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    )}
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
          <div className="flex-shrink-0 border-t border-gray-100 px-4 py-3 bg-white">
            <div className={`text-xs mb-2 ${tokenIndicatorClass}`}>
              {blocked ? (
                'Sessielimiet bereikt. Start een nieuwe sessie.'
              ) : (
                <>Sessie: {sessionTokens.toLocaleString()} / {SOFT_LIMIT.toLocaleString()} tokens</>
              )}
            </div>
            <div className="flex gap-2 relative">
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
                        <span className="mention-name font-medium text-slate-800">
                          {c.client_name || c.name || c.slug}
                        </span>
                        <span className="mention-slug text-slate-500 text-xs">@{c.slug}</span>
                      </button>
                    ))}
                  </div>
                )}
                <textarea
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  placeholder="Typ je bericht... Gebruik @client voor context"
                  rows={2}
                  disabled={blocked || sending}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm resize-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-slate-100"
                />
              </div>
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim() || blocked || sending}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
                aria-label="Verstuur bericht"
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
