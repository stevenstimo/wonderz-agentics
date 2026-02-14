import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { MessageCircle, Send, X, Bot } from 'lucide-react'

const SHERLOCK_STORAGE_KEY = 'sherlock_jr_chat_v1'
const SHERLOCK_STATS_KEY = 'sherlock_jr_stats_v1'
const SHERLOCK_ID = 'sherlock-jr'
const SHERLOCK_AVATAR =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
      <rect width="120" height="120" fill="#ded2b8"/>
      <ellipse cx="60" cy="28" rx="26" ry="8" fill="#111827"/>
      <rect x="36" y="18" width="48" height="22" rx="10" fill="#111827"/>
      <rect x="38" y="33" width="44" height="4" fill="#f5f5f4"/>
      <path d="M46 66c4-6 24-6 28 0-4 4-10 6-14 6s-10-2-14-6z" fill="#111827"/>
      <circle cx="74" cy="60" r="9" fill="none" stroke="#111827" stroke-width="2"/>
      <line x1="83" y1="68" x2="83" y2="92" stroke="#111827" stroke-width="2"/>
      <path d="M42 74c5 0 7 6 3 8-2 1-4-1-6 0-2 1-2 4 1 5" fill="none" stroke="#111827" stroke-width="2" stroke-linecap="round"/>
      <path d="M78 74c-5 0-7 6-3 8 2 1 4-1 6 0 2 1 2 4-1 5" fill="none" stroke="#111827" stroke-width="2" stroke-linecap="round"/>
      <path d="M50 92c4-7 12-7 16 0" fill="none" stroke="#6b3e1f" stroke-width="4" stroke-linecap="round"/>
      <circle cx="52" cy="56" r="4" fill="#e9b98b"/>
      <circle cx="60" cy="54" r="5" fill="#efc49c"/>
      <circle cx="67" cy="56" r="4" fill="#e9b98b"/>
    </svg>`
  )

const defaultStats = {
  level: 1,
  xp: 0,
  intelligence: 1,
  conversations: 0,
}

const starterMessage = {
  role: 'assistant',
  text: 'Hallo! Ik ben Sherlock Jr. Stel me een algemene vraag. Als het slim is om iemand anders in te schakelen, wijs ik je direct naar de juiste crew member.',
  time: new Date().toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }),
}

function nowTime() {
  return new Date().toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' })
}

function computeLevelFromXp(xp) {
  let level = 1
  let currentXp = Number(xp || 0)
  let threshold = 120
  while (currentXp >= threshold) {
    currentXp -= threshold
    level += 1
    threshold = 120 + level * 45
  }
  return { level, xpInLevel: currentXp, nextThreshold: threshold }
}

function classifyQuestion(text = '') {
  const msg = text.toLowerCase()
  const technicalKeywords = [
    'code', 'bug', 'debug', 'api', 'backend', 'frontend', 'database', 'sql', 'server', 'deploy',
    'react', 'javascript', 'python', 'ruby', 'script', 'cli', 'terminal', 'architectuur', 'tech', 'error',
  ]
  const hrKeywords = ['hr', 'team', 'conflict', 'feedback', 'training', 'hiring', 'vacature']
  const marketingKeywords = ['marketing', 'content', 'seo', 'ads', 'campaign', 'social']

  if (technicalKeywords.some((k) => msg.includes(k))) return 'technical'
  if (hrKeywords.some((k) => msg.includes(k))) return 'hr'
  if (marketingKeywords.some((k) => msg.includes(k))) return 'marketing'
  return 'general'
}

function pickCrewMember(questionType, crew) {
  if (!Array.isArray(crew) || crew.length === 0) return null
  const withoutSherlock = crew.filter((member) => !`${member?.name || ''}`.toLowerCase().includes('sherlock'))
  if (withoutSherlock.length === 0) return null

  const findByMatcher = (matcher) => withoutSherlock.find((member) => {
    const blob = `${member?.name || ''} ${member?.role || ''} ${member?.specialization || ''}`.toLowerCase()
    return matcher.some((key) => blob.includes(key))
  })

  if (questionType === 'technical') {
    return findByMatcher(['dave', 'developer', 'engineer', 'devops', 'architect', 'backend', 'frontend']) || withoutSherlock[0]
  }
  if (questionType === 'hr') {
    return findByMatcher(['hr', 'training', 'reviewer', 'people', 'talent']) || withoutSherlock[0]
  }
  if (questionType === 'marketing') {
    return findByMatcher(['marketing', 'content', 'growth', 'brand', 'creative']) || withoutSherlock[0]
  }

  return findByMatcher(['product owner', 'manager', 'operations', 'support']) || withoutSherlock[0]
}

function buildSherlockReply(userText, route) {
  const lower = userText.toLowerCase()
  const greeting = ['hallo', 'hey', 'hi', 'goedemorgen', 'goedenavond'].some((word) => lower.includes(word))

  let text = greeting
    ? 'Hi! Sherlock Jr. hier. Ik help je meteen op weg.'
    : 'Top, ik denk met je mee.'

  if (route) {
    text += ` Voor uitvoering kun je het beste bij ${route.name} (${route.role}) zijn.`
  } else {
    text += ' Ik kan nu geen duidelijke specialist kiezen, dus begin bij de algemene crew intake.'
  }
  return text
}

function toCrewPayload(member, nextDevelopmentNotes) {
  return {
    name: member?.name || 'Sherlock Jr.',
    role: member?.role || 'AI',
    specialization: member?.specialization || 'General assistant and crew routing',
    system_instructions: member?.system_instructions || 'Handle general questions and route work to the right crew member.',
    knowledge_base_sources: Array.isArray(member?.knowledge_base_sources) ? member.knowledge_base_sources : [],
    tool_access_whitelist: Array.isArray(member?.tool_access_whitelist) ? member.tool_access_whitelist : [],
    hiring_logic: member?.hiring_logic || 'Route requests and reduce triage delay.',
    persona: member?.persona || 'Friendly and direct assistant.',
    quality_notes: member?.quality_notes || 'Strong at intake and routing.',
    development_notes: nextDevelopmentNotes,
  }
}

export default function SherlockWidget() {
  const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
  const messagesEndRef = useRef(null)
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [crew, setCrew] = useState([])
  const [sherlockCrewMember, setSherlockCrewMember] = useState(null)
  const [messages, setMessages] = useState(() => {
    try {
      const raw = localStorage.getItem(SHERLOCK_STORAGE_KEY)
      const parsed = raw ? JSON.parse(raw) : null
      return Array.isArray(parsed) && parsed.length > 0 ? parsed : [starterMessage]
    } catch {
      return [starterMessage]
    }
  })
  const [stats, setStats] = useState(() => {
    try {
      const raw = localStorage.getItem(SHERLOCK_STATS_KEY)
      const parsed = raw ? JSON.parse(raw) : null
      return parsed && typeof parsed === 'object' ? { ...defaultStats, ...parsed } : defaultStats
    } catch {
      return defaultStats
    }
  })

  const statsLabel = useMemo(() => {
    const levelStats = computeLevelFromXp(stats.xp)
    return `Lv ${levelStats.level} • IQ ${stats.intelligence}`
  }, [stats])

  const fabStyle = {
    position: 'fixed',
    right: '16px',
    bottom: '16px',
    width: 64,
    height: 64,
    borderRadius: '999px',
    background: '#2563eb',
    color: '#fff',
    zIndex: 2147483647,
    boxShadow: '0 18px 40px rgba(37,99,235,0.35)',
    border: '2px solid rgba(255,255,255,0.95)',
  }

  const panelStyle = {
    position: 'fixed',
    right: '16px',
    bottom: '92px',
    zIndex: 2147483646,
  }

  useEffect(() => {
    localStorage.setItem(SHERLOCK_STORAGE_KEY, JSON.stringify(messages.slice(-60)))
  }, [messages])

  useEffect(() => {
    localStorage.setItem(SHERLOCK_STATS_KEY, JSON.stringify(stats))
  }, [stats])

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    const forceOpen = () => setOpen(true)
    window.addEventListener('open-sherlock-jr', forceOpen)
    return () => window.removeEventListener('open-sherlock-jr', forceOpen)
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing, open])

  useEffect(() => {
    const loadCrew = async () => {
      try {
        const res = await fetch(`${apiBase}/api/crew`)
        if (!res.ok) return
        const data = await res.json()
        const list = Array.isArray(data) ? data : []
        setCrew(list)
        const foundSherlock = list.find((member) => `${member?.name || ''}`.toLowerCase().includes('sherlock'))
        setSherlockCrewMember(foundSherlock || null)

        if (!foundSherlock) {
          const createPayload = {
            name: 'Sherlock Jr.',
            role: 'AI',
            specialization: 'General assistant and crew routing',
            system_instructions: 'Answer general questions and route users to the best crew member.',
            knowledge_base_sources: [],
            tool_access_whitelist: [],
            hiring_logic: 'First-line assistant that triages requests and points to the right specialist.',
            persona: 'Friendly, practical and clear.',
            quality_notes: 'Strong at quick intake and helping users choose the right specialist.',
            development_notes: 'Learning from every conversation and routing feedback.',
          }
          const createRes = await fetch(`${apiBase}/api/crew`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(createPayload),
          })
          if (createRes.ok) {
            const listRes = await fetch(`${apiBase}/api/crew`)
            if (listRes.ok) {
              const nextList = await listRes.json()
              if (Array.isArray(nextList)) {
                setCrew(nextList)
                const nextSherlock = nextList.find((member) => `${member?.name || ''}`.toLowerCase().includes('sherlock'))
                setSherlockCrewMember(nextSherlock || null)
              }
            }
          }
        }
      } catch {
        // Keep widget functional without backend.
      }
    }
    loadCrew()
  }, [apiBase])

  const persistSherlockGrowth = async (userText, nextStats) => {
    if (!sherlockCrewMember?.id) return
    const appendedLine = `- ${new Date().toISOString()}: Learned from "${userText.slice(0, 120)}" | level ${nextStats.level}, iq ${nextStats.intelligence}`
    const currentNotes = sherlockCrewMember?.development_notes || 'Learning log:'
    const nextNotes = `${currentNotes}\n${appendedLine}`.slice(-2000)
    const payload = toCrewPayload(sherlockCrewMember, nextNotes)

    try {
      const res = await fetch(`${apiBase}/api/crew/${sherlockCrewMember.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (res.ok) {
        setSherlockCrewMember((prev) => prev ? { ...prev, development_notes: nextNotes } : prev)
      }
    } catch {
      // Non-blocking sync.
    }
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || typing) return

    const userMessage = { role: 'user', text, time: nowTime() }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setTyping(true)

    const questionType = classifyQuestion(text)
    const routedMember = pickCrewMember(questionType, crew)
    const routeHint = routedMember
      ? `Beste match: ${routedMember.name} (${routedMember.role})`
      : 'Beste match: algemene intake crew'

    const botMessage = {
      role: 'assistant',
      text: `${buildSherlockReply(text, routedMember)}\n\n${routeHint}`,
      time: nowTime(),
    }

    const xpGain = questionType === 'technical' ? 26 : 18
    const nextXp = stats.xp + xpGain
    const levelCalc = computeLevelFromXp(nextXp)
    const nextStats = {
      ...stats,
      xp: nextXp,
      level: levelCalc.level,
      intelligence: 1 + Math.floor(nextXp / 90),
      conversations: (stats.conversations || 0) + 1,
    }

    window.setTimeout(async () => {
      setMessages((prev) => [...prev, botMessage])
      setStats(nextStats)
      setTyping(false)
      await persistSherlockGrowth(text, nextStats)
    }, 450)
  }

  if (!mounted) return null

  return createPortal((
    <>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="transition hover:scale-105"
        style={fabStyle}
        aria-label="Open Sherlock Jr."
      >
        <MessageCircle className="mx-auto h-7 w-7" />
      </button>

      {open && (
        <div style={panelStyle} className="flex h-[78vh] w-[min(410px,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_24px_70px_rgba(15,23,42,0.24)]">
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="relative flex h-11 w-11 items-center justify-center rounded-full border-2 border-blue-600 bg-blue-100 text-blue-700">
                  <img src={SHERLOCK_AVATAR} alt="Sherlock Jr. avatar" className="h-11 w-11 rounded-full object-cover" />
                  <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-white bg-emerald-500" />
                </div>
                <div>
                  <div className="text-2xl font-bold leading-none text-slate-900">Sherlock Jr.</div>
                  <div className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-blue-600">Assistant Bot</div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-xl border border-slate-200 bg-white p-2 text-slate-500 hover:text-slate-800"
                aria-label="Close Sherlock Jr."
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-2 text-xs text-slate-500">
              General assistant + crew router. {statsLabel}
            </div>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto bg-white px-4 py-4">
            <div className="flex justify-center">
              <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-medium text-slate-500">TODAY</span>
            </div>

            {messages.map((msg, idx) => (
              <div key={`${msg.time}-${idx}`} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[86%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'rounded-br-md bg-blue-600 text-white'
                    : 'rounded-bl-md bg-slate-100 text-slate-800'
                }`}>
                  {msg.text}
                  <div className={`mt-1 text-[10px] ${msg.role === 'user' ? 'text-blue-100' : 'text-slate-400'}`}>
                    {msg.time}
                  </div>
                </div>
              </div>
            ))}

            {typing && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-md bg-slate-100 px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-blue-300" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-blue-300 [animation-delay:-0.15s]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-blue-300 [animation-delay:-0.3s]" />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-slate-200 bg-white px-3 py-3">
            <div className="flex items-center gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSend() }}
                placeholder="Type je vraag..."
                className="h-12 flex-1 rounded-full border border-slate-200 bg-slate-100 px-4 text-sm text-slate-800 outline-none focus:border-blue-300"
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={typing || !input.trim()}
                className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-white shadow disabled:opacity-50"
                aria-label="Send message"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  ), document.body)
}
