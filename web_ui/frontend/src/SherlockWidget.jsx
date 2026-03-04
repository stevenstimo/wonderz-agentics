import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { MessageCircle, Send, X } from 'lucide-react'

const CHAT_KEY = 'sherlock_jr_chat_v1'

function now() {
  return new Date().toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' })
}

export default function SherlockWidget() {
  const [mounted, setMounted] = useState(false)
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState(() => {
    try {
      const raw = localStorage.getItem(CHAT_KEY)
      if (raw) return JSON.parse(raw)
    } catch {
      // ignore
    }
    return [{ role: 'assistant', text: 'Hallo! Ik ben Sherlock Jr. Hoe kan ik je helpen?', time: now() }]
  })
  const endRef = useRef(null)

  useEffect(() => setMounted(true), [])

  useEffect(() => {
    localStorage.setItem(CHAT_KEY, JSON.stringify(messages.slice(-60)))
  }, [messages])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  const send = () => {
    const text = input.trim()
    if (!text) return
    setMessages((prev) => [...prev, { role: 'user', text, time: now() }])
    setInput('')
    setTimeout(() => {
      setMessages((prev) => [...prev, { role: 'assistant', text: 'Ik heb je vraag ontvangen. Ik kan je ook doorverwijzen naar de juiste crew member.', time: now() }])
    }, 250)
  }

  if (!mounted) return null

  return createPortal(
    <>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Open Sherlock Jr"
        style={{
          position: 'fixed',
          right: 16,
          bottom: 16,
          width: 64,
          height: 64,
          borderRadius: 999,
          border: '2px solid rgba(255,255,255,0.95)',
          background: '#2563eb',
          color: '#fff',
          zIndex: 2147483647,
          boxShadow: '0 18px 40px rgba(37,99,235,0.35)',
        }}
      >
        <MessageCircle className="mx-auto h-7 w-7" />
      </button>

      {open && (
        <div
          style={{
            position: 'fixed',
            right: 16,
            bottom: 92,
            zIndex: 2147483646,
          }}
          className="flex h-[72vh] w-[min(400px,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_24px_70px_rgba(15,23,42,0.24)]"
        >
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3 flex items-center justify-between">
            <div>
              <div className="text-xl font-bold text-slate-900">Sherlock Jr.</div>
              <div className="text-[10px] uppercase tracking-[0.16em] text-blue-600 font-semibold">Assistant Bot</div>
            </div>
            <button type="button" onClick={() => setOpen(false)} className="rounded-xl border border-slate-200 bg-white p-2 text-slate-500">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto bg-white px-4 py-4">
            {messages.map((msg, i) => (
              <div key={`${msg.time}-${i}`} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[86%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${msg.role === 'user' ? 'rounded-br-md bg-blue-600 text-white' : 'rounded-bl-md bg-slate-100 text-slate-800'}`}>
                  {msg.text}
                  <div className={`mt-1 text-[10px] ${msg.role === 'user' ? 'text-blue-100' : 'text-slate-400'}`}>{msg.time}</div>
                </div>
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <div className="border-t border-slate-200 bg-white px-3 py-3">
            <div className="flex items-center gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') send() }}
                placeholder="Type je vraag..."
                className="h-12 flex-1 rounded-full border border-slate-200 bg-slate-100 px-4 text-sm text-slate-800 outline-none"
              />
              <button type="button" onClick={send} disabled={!input.trim()} className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-white disabled:opacity-50">
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>,
    document.body,
  )
}
