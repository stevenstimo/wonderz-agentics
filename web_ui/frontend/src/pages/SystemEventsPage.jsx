import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageLayout from '../PageLayout'
import { apiFetch } from '../apiClient'

const SEVERITY_COLORS = {
  info: '#6B7280',
  warning: '#D97706',
  error: '#DC2626',
  critical: '#7C3AED',
}

export default function SystemEventsPage() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [showUnresolvedOnly, setShowUnresolvedOnly] = useState(false)

  const fetchEvents = async () => {
    try {
      const params = showUnresolvedOnly ? '?unresolved_only=true&limit=50' : '?limit=50'
      const res = await apiFetch(`/api/system-events${params}`)
      if (!res.ok) {
        setEvents([])
        return
      }
      const data = await res.json()
      setEvents(data.events || [])
    } catch {
      setEvents([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setLoading(true)
    fetchEvents()
  }, [showUnresolvedOnly])

  const handleResolve = async (eventId) => {
    const res = await apiFetch(`/api/system-events/${eventId}/resolve`, { method: 'PATCH' })
    if (res.ok) fetchEvents()
  }

  return (
    <PageLayout>
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-800">Platform Events</h1>
          <p className="text-slate-600 mt-1">
            Operationele fouten van de CEO/orchestrator en het platform.
          </p>
          <label className="mt-4 flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={showUnresolvedOnly}
              onChange={(e) => setShowUnresolvedOnly(e.target.checked)}
              className="rounded border-slate-300"
            />
            Alleen openstaande
          </label>
        </div>

        {loading && <p className="text-slate-500">Laden...</p>}

        {!loading && events.length === 0 && (
          <p className="text-slate-500">Geen platform-events gevonden.</p>
        )}

        <div className="space-y-4">
          {events.map((event) => (
            <div
              key={event.event_id}
              className={`rounded-xl border p-4 ${
                event.resolved
                  ? 'bg-slate-50 border-slate-200 opacity-80'
                  : 'bg-white border-slate-200 shadow-sm'
              }`}
            >
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span
                  className="text-xs font-semibold uppercase px-2 py-0.5 rounded"
                  style={{ color: SEVERITY_COLORS[event.severity] || '#6B7280' }}
                >
                  {event.severity}
                </span>
                <span className="text-sm text-slate-500">{event.event_type}</span>
                <span className="text-xs text-slate-400 ml-auto">
                  {event.created_at
                    ? new Date(event.created_at).toLocaleString('nl-NL')
                    : ''}
                </span>
              </div>

              <p className="text-slate-800 mb-2">{event.message}</p>

              {event.job_id && (
                <Link
                  to={`/jobs/${event.job_id}`}
                  className="text-sm text-indigo-600 hover:underline"
                >
                  Job bekijken
                </Link>
              )}

              {event.agent_id && (
                <p className="text-xs text-slate-500 mt-1">Agent: {event.agent_id}</p>
              )}

              {!event.resolved && (
                <button
                  type="button"
                  onClick={() => handleResolve(event.event_id)}
                  className="mt-3 px-3 py-1.5 text-sm font-medium rounded-lg bg-indigo-600 text-white hover:bg-indigo-700"
                >
                  Markeer als opgelost
                </button>
              )}

              {event.resolved && event.resolved_at && (
                <p className="mt-2 text-xs text-slate-500">
                  Opgelost op {new Date(event.resolved_at).toLocaleString('nl-NL')}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </PageLayout>
  )
}
