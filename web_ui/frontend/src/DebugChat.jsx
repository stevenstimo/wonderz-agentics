import { useState, useRef, useEffect } from 'react'
import { apiUrl, apiFetch } from './apiClient'

function renderMarkdown(text) {
  if (!text) return ''
  return text
    .split('\n\n')
    .map((block) => {
      if (block.startsWith('## ')) return `<h2 class="text-lg font-bold mt-3 mb-1 text-slate-100">${block.slice(3)}</h2>`
      if (block.startsWith('# ')) return `<h1 class="text-xl font-bold mt-3 mb-2 text-slate-100">${block.slice(2)}</h1>`
      return `<p class="mb-2 leading-relaxed text-slate-200">${block}</p>`
    })
    .join('')
}

export default function DebugChat() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, loading])

  const handleSend = async () => {
    const msg = input.trim()
    if (!msg || loading) return

    const userMsg = { role: 'user', content: msg }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    const conversation_history = [...messages, userMsg]

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 90000) // 90s timeout

    // #region agent log
    console.log('[DBG-c78650] handleSend start', { msgLen: msg.length, apiBase: import.meta.env.VITE_API_URL });
    // #endregion

    try {
      // #region agent log
      console.log('[DBG-c78650] calling apiFetch...');
      // #endregion
      const res = await apiFetch('/api/debug/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, conversation_history }),
        signal: controller.signal,
      })
      clearTimeout(timeoutId)
      // #region agent log
      console.log('[DBG-c78650] fetch completed', { status: res.status, ok: res.ok });
      // #endregion
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const detail = data.detail
        const errMsg = typeof detail === 'string'
          ? detail
          : Array.isArray(detail) && detail[0]?.msg
            ? detail.map((d) => d.msg).join('; ')
            : data.message || `Request failed (${res.status})`
        throw new Error(errMsg)
      }
      const responseText = data.response ?? ''
      const content = responseText.trim()
        ? responseText
        : 'Geen antwoord ontvangen van de AI. Controleer of ANTHROPIC_API_KEY correct is geconfigureerd op de backend.'
      // #region agent log
      console.log('[DBG-c78650] success', { responseLen: responseText.length, contentLen: content.length });
      // #endregion
      setMessages((prev) => [...prev, { role: 'assistant', content }])
    } catch (err) {
      clearTimeout(timeoutId)
      // #region agent log
      console.log('[DBG-c78650] catch block', { errName: err.name, errMsg: err.message });
      // #endregion
      let msg = err.message || 'Onbekende fout'
      if (err.name === 'AbortError') {
        msg = 'Timeout: de AI reageerde niet binnen 90 seconden. Probeer opnieuw.'
      } else if (msg === 'Failed to fetch' || msg.includes('NetworkError')) {
        msg = 'Geen verbinding met de backend. Controleer of de backend draait (lokaal: localhost:8090).'
      }
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${msg}` },
      ])
      console.error('[DebugChat]', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* Toggle button: fixed bottom-right */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-4 right-4 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 text-slate-200 shadow-lg border border-slate-600 hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        title="Debug Chat"
        aria-label="Toggle debug chat"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </button>

      {/* Chat panel */}
      {open && (
        <div
          className="fixed bottom-20 right-4 z-50 flex w-[400px] flex-col rounded-xl border border-slate-700 bg-slate-900 shadow-xl"
          style={{ height: '500px' }}
        >
          <div className="flex-shrink-0 border-b border-slate-700 px-4 py-2">
            <h3 className="text-sm font-semibold text-slate-100">Debug Chat</h3>
          </div>
          <div className="flex-1 overflow-y-auto space-y-3 p-3 min-h-0">
            {messages.length === 0 && !loading && (
              <p className="text-slate-400 text-sm">Ask about a job (paste UUID or #0001), agents, failed/running jobs, or system status.</p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                    m.role === 'user'
                      ? 'bg-indigo-600 text-white rounded-br-none'
                      : 'bg-slate-700 text-slate-100 rounded-bl-none'
                  }`}
                >
                  {m.role === 'assistant' ? (
                    <div
                      className="prose prose-invert prose-sm max-w-none"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }}
                    />
                  ) : (
                    <p className="whitespace-pre-wrap">{m.content}</p>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="rounded-lg rounded-bl-none bg-slate-700 px-3 py-2 text-sm text-slate-400">
                  Thinking...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
          <form
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
            className="flex-shrink-0 flex gap-2 border-t border-slate-700 p-3 bg-slate-900"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Message..."
              className="flex-1 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </form>
        </div>
      )}
    </>
  )
}
