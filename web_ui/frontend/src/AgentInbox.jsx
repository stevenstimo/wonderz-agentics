import { useEffect, useState, useCallback } from 'react'
import PageLayout from './PageLayout'
import { apiUrl } from './apiClient'
import { Inbox, Check, X, Trash2 } from 'lucide-react'

const URGENCY_COLORS = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  high: 'bg-amber-100 text-amber-800 border-amber-200',
  normal: 'bg-blue-100 text-blue-800 border-blue-200',
  low: 'bg-slate-100 text-slate-600 border-slate-200',
}

const MESSAGE_TYPE_LABELS = {
  info: 'Info',
  gap_report: 'Gap Report',
  instruction: 'Instruction',
  alert: 'Alert',
}

function relativeTime(dateStr) {
  const d = new Date(dateStr)
  const now = new Date()
  const s = Math.floor((now - d) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  const days = Math.floor(s / 86400)
  if (days === 1) return 'yesterday'
  if (s < 604800) return `${days}d ago`
  return d.toLocaleDateString()
}

export default function AgentInbox() {
  const [messages, setMessages] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [updating, setUpdating] = useState(false)

  const fetchMessages = useCallback(async () => {
    try {
      const res = await fetch(apiUrl('/api/inbox'))
      if (!res.ok) throw new Error('Failed to load inbox')
      const data = await res.json()
      setMessages(Array.isArray(data) ? data : [])
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to load inbox')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMessages()
  }, [fetchMessages])

  const markAsRead = async (msg) => {
    if (msg.status === 'unread') {
      setUpdating(true)
      try {
        const res = await fetch(apiUrl(`/api/inbox/${msg.id}`), {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'read' }),
        })
        if (res.ok) {
          setMessages((prev) =>
            prev.map((m) => (m.id === msg.id ? { ...m, status: 'read' } : m))
          )
          setSelected((s) => (s?.id === msg.id ? { ...s, status: 'read' } : s))
        }
      } finally {
        setUpdating(false)
      }
    }
  }

  const markActioned = async (msg) => {
    setUpdating(true)
    try {
      const res = await fetch(apiUrl(`/api/inbox/${msg.id}`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'actioned' }),
      })
      if (res.ok) {
        setMessages((prev) =>
          prev.map((m) => (m.id === msg.id ? { ...m, status: 'actioned' } : m))
        )
        setSelected((s) => (s?.id === msg.id ? { ...s, status: 'actioned' } : s))
      }
    } finally {
      setUpdating(false)
    }
  }

  const markDismissed = async (msg) => {
    setUpdating(true)
    try {
      const res = await fetch(apiUrl(`/api/inbox/${msg.id}`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'dismissed' }),
      })
      if (res.ok) {
        setMessages((prev) =>
          prev.map((m) => (m.id === msg.id ? { ...m, status: 'dismissed' } : m))
        )
        setSelected((s) => (s?.id === msg.id ? { ...s, status: 'dismissed' } : s))
      }
    } finally {
      setUpdating(false)
    }
  }

  const deleteMessage = async (msg) => {
    setUpdating(true)
    try {
      const res = await fetch(apiUrl(`/api/inbox/${msg.id}`), { method: 'DELETE' })
      if (res.ok) {
        setMessages((prev) => prev.filter((m) => m.id !== msg.id))
        if (selected?.id === msg.id) setSelected(null)
      }
    } finally {
      setUpdating(false)
    }
  }

  const handleSelect = (msg) => {
    setSelected(msg)
    markAsRead(msg)
  }

  return (
    <PageLayout size="wide" padded>
      <div className="flex flex-col h-[calc(100vh-8rem)] min-h-[32rem]">
        <div className="flex items-center gap-2 mb-4">
          <Inbox className="w-6 h-6 text-indigo-600" />
          <h1 className="text-2xl font-bold text-slate-900">Agent Inbox</h1>
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 text-red-800 px-4 py-3 mb-4">
            {error}
          </div>
        )}

        <div className="flex flex-1 min-h-0 rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          {/* Left: message list */}
          <div className="w-80 flex-shrink-0 border-r border-slate-200 flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
              <h2 className="text-sm font-semibold text-slate-700">Messages</h2>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="p-4 text-slate-500 text-sm">Loading…</div>
              ) : messages.length === 0 ? (
                <div className="p-4 text-slate-500 text-sm">No messages yet.</div>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {messages.map((msg) => (
                    <li key={msg.id}>
                      <button
                        type="button"
                        onClick={() => handleSelect(msg)}
                        className={`w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors ${
                          selected?.id === msg.id ? 'bg-indigo-50 border-l-2 border-indigo-500' : ''
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span
                            className={`text-xs font-medium px-2 py-0.5 rounded ${
                              URGENCY_COLORS[msg.urgency] || URGENCY_COLORS.normal
                            }`}
                          >
                            {msg.urgency}
                          </span>
                          {msg.status === 'unread' && (
                            <span className="w-2 h-2 rounded-full bg-indigo-500 flex-shrink-0 mt-1.5" />
                          )}
                        </div>
                        <div className="mt-1 font-medium text-slate-900 truncate">
                          {msg.subject}
                        </div>
                        <div className="mt-0.5 text-xs text-slate-500">
                          {msg.from_agent_id} → {msg.to_agent_id}
                        </div>
                        <div className="mt-1 text-xs text-slate-400">
                          {relativeTime(msg.created_at)}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Right: detail */}
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            {selected ? (
              <>
                <div className="flex-shrink-0 px-6 py-4 border-b border-slate-200 bg-slate-50">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-lg font-semibold text-slate-900">
                        {selected.subject}
                      </h2>
                      <div className="mt-1 flex flex-wrap gap-2">
                        <span
                          className={`text-xs font-medium px-2 py-0.5 rounded ${
                            URGENCY_COLORS[selected.urgency] || URGENCY_COLORS.normal
                          }`}
                        >
                          {selected.urgency}
                        </span>
                        <span className="text-xs text-slate-500">
                          {MESSAGE_TYPE_LABELS[selected.message_type] || selected.message_type}
                        </span>
                        <span className="text-xs text-slate-500">
                          {selected.from_agent_id} → {selected.to_agent_id}
                        </span>
                        <span className="text-xs text-slate-400">
                          {relativeTime(selected.created_at)}
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {selected.status === 'read' && (
                        <>
                          <button
                            type="button"
                            onClick={() => markActioned(selected)}
                            disabled={updating}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-green-700 bg-green-100 rounded-lg hover:bg-green-200 disabled:opacity-50"
                          >
                            <Check className="w-4 h-4" />
                            Actioned
                          </button>
                          <button
                            type="button"
                            onClick={() => markDismissed(selected)}
                            disabled={updating}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 disabled:opacity-50"
                          >
                            <X className="w-4 h-4" />
                            Dismiss
                          </button>
                        </>
                      )}
                      <button
                        type="button"
                        onClick={() => deleteMessage(selected)}
                        disabled={updating}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-700 bg-red-100 rounded-lg hover:bg-red-200 disabled:opacity-50"
                      >
                        <Trash2 className="w-4 h-4" />
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
                <div className="flex-1 overflow-y-auto p-6">
                  <div className="prose prose-slate max-w-none">
                    <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans bg-transparent p-0">
                      {selected.body}
                    </pre>
                  </div>
                  {selected.job_id && (
                    <div className="mt-4 pt-4 border-t border-slate-200">
                      <span className="text-xs text-slate-500">Job ID:</span>{' '}
                      <code className="text-sm text-slate-700">{selected.job_id}</code>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-500">
                Select a message to view details
              </div>
            )}
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
