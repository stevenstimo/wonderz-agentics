import { useEffect, useState } from 'react'
import { Plus, GraduationCap, UserPlus } from 'lucide-react'
import PageLayout from './PageLayout'
import { apiUrl } from './apiClient'
import { getCurrentUserRole, isSuperAdmin } from './authz'

const CATEGORIES = [
  { key: 'score_management', label: 'Management' },
  { key: 'score_creative', label: 'Creative' },
  { key: 'score_development', label: 'Development' },
  { key: 'score_operations', label: 'Operations' },
]

function truncate(str, max = 120) {
  if (!str || typeof str !== 'string') return '—'
  return str.length <= max ? str : str.slice(0, max).trim() + '…'
}

function StatusBadge({ status }) {
  const styles = {
    in_training: 'bg-slate-200 text-slate-700',
    ready: 'bg-green-100 text-green-800',
    hired: 'bg-blue-100 text-blue-800',
    inactive: 'bg-slate-100 text-slate-600',
  }
  const labels = {
    in_training: 'In Training',
    ready: 'Ready ✓',
    hired: 'Hired',
    inactive: 'Inactive',
  }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status] || styles.in_training}`}>
      {labels[status] || status}
    </span>
  )
}

export default function Newbies() {
  const [newbies, setNewbies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [userRole, setUserRole] = useState('member')
  const [showAdd, setShowAdd] = useState(false)
  const [adding, setAdding] = useState(false)
  const [addForm, setAddForm] = useState({
    newbie_name: '',
    persona: '',
    qualities: '',
    development: '',
    suggested_role: '',
  })

  const canEdit = isSuperAdmin(userRole)

  const fetchNewbies = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(apiUrl('/api/newbies'))
      if (!res.ok) throw new Error(`Newbies ophalen mislukt (${res.status})`)
      const data = await res.json()
      setNewbies(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message || 'Newbies ophalen mislukt')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    ;(async () => {
      try {
        const ctx = await getCurrentUserRole()
        setUserRole(ctx.role || 'member')
      } catch {
        setUserRole('member')
      }
      fetchNewbies()
    })()
  }, [])

  const submitAdd = async () => {
    if (!canEdit) return
    if (!addForm.newbie_name?.trim() || !addForm.persona?.trim() || !addForm.qualities?.trim() || !addForm.development?.trim()) {
      setError('Naam, persona, kwaliteiten en ontwikkelpunten zijn verplicht.')
      return
    }
    setAdding(true)
    setError('')
    try {
      const res = await fetch(apiUrl('/api/newbies'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          newbie_name: addForm.newbie_name.trim(),
          persona: addForm.persona.trim(),
          qualities: addForm.qualities.trim(),
          development: addForm.development.trim(),
          suggested_role: addForm.suggested_role?.trim() || null,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Toevoegen mislukt (${res.status})`)
      }
      setShowAdd(false)
      setAddForm({ newbie_name: '', persona: '', qualities: '', development: '', suggested_role: '' })
      await fetchNewbies()
    } catch (err) {
      setError(err.message || 'Newbie toevoegen mislukt')
    } finally {
      setAdding(false)
    }
  }

  const handleHireNow = (newbie) => {
    window.location.href = `/hiring?promote=${encodeURIComponent(newbie.newbie_id)}`
  }

  return (
    <PageLayout>
      <div className="panel-card">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="page-title mb-1">Newbies</h1>
            <p className="page-subtitle">Persona&apos;s in ontwikkeling. Train ze tot readiness ≥ 70, dan verschijnen ze in de Hiring Hall.</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-icon-only" type="button" onClick={fetchNewbies} aria-label="Vernieuwen">
              ↻
            </button>
            {canEdit && (
              <button type="button" className="btn-manage gap-2" onClick={() => setShowAdd(true)}>
                <Plus className="w-4 h-4" />
                Add Newbie
              </button>
            )}
          </div>
        </div>

        {error && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        {loading ? (
          <div className="text-sm text-slate-500">Laden...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
            {newbies.map((n) => (
              <div
                key={n.newbie_id}
                className="block rounded-lg border border-slate-200 p-4 hover:border-indigo-300 hover:bg-slate-50/50 transition"
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div>
                    <h3 className="font-semibold text-slate-800">{n.newbie_name || '—'}</h3>
                    <span className="text-sm text-slate-600">score: {n.readiness_score ?? 0}/100</span>
                  </div>
                  <StatusBadge status={n.status || 'in_training'} />
                </div>
                <p className="text-xs text-slate-600 mt-1 line-clamp-2">{truncate(n.persona, 100)}</p>

                {/* Progress bar */}
                <div className="mt-3">
                  <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 rounded-full transition-all"
                      style={{ width: `${Math.min(100, n.readiness_score ?? 0)}%` }}
                    />
                  </div>
                </div>

                {/* Score breakdown */}
                <div className="mt-3 space-y-1.5">
                  {CATEGORIES.map(({ key, label }) => (
                    <div key={key} className="flex items-center gap-2">
                      <span className="text-[10px] font-medium text-slate-500 w-20 shrink-0">{label}</span>
                      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-slate-400 rounded-full"
                          style={{ width: `${Math.min(100, n[key] ?? 0)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-slate-500 w-6 text-right">{n[key] ?? 0}</span>
                    </div>
                  ))}
                </div>

                <div className="mt-4 flex items-center gap-2">
                  <button
                    type="button"
                    className="text-sm text-indigo-600 hover:underline font-medium flex items-center gap-1"
                    onClick={() => {}}
                    title="Training (komt in Fase 4)"
                  >
                    <GraduationCap className="w-4 h-4" />
                    Train
                  </button>
                  {(n.readiness_score ?? 0) >= 70 && n.status === 'ready' && (
                    <button
                      type="button"
                      className="text-sm text-green-600 hover:underline font-medium flex items-center gap-1"
                      onClick={() => handleHireNow(n)}
                    >
                      <UserPlus className="w-4 h-4" />
                      Hire Now
                    </button>
                  )}
                </div>
              </div>
            ))}
            {!newbies.length && (
              <div className="col-span-full py-8 text-center text-sm text-slate-500">
                Geen newbies gevonden. Klik op &quot;Add Newbie&quot; om te starten.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modal: Add Newbie */}
      {showAdd && (
        <div className="modal-overlay" onClick={() => !adding && setShowAdd(false)}>
          <div className="modal-card space-y-3" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold">Add Newbie</h2>
            <input
              className="w-full px-3 py-2 border border-slate-300 rounded-lg"
              placeholder="Naam"
              value={addForm.newbie_name}
              onChange={(e) => setAddForm({ ...addForm, newbie_name: e.target.value })}
            />
            <textarea
              className="w-full px-3 py-2 border border-slate-300 rounded-lg"
              placeholder="Persona (wie is hij/zij?)"
              rows={3}
              value={addForm.persona}
              onChange={(e) => setAddForm({ ...addForm, persona: e.target.value })}
            />
            <textarea
              className="w-full px-3 py-2 border border-slate-300 rounded-lg"
              placeholder="Kwaliteiten (waar is hij/zij goed in?)"
              rows={2}
              value={addForm.qualities}
              onChange={(e) => setAddForm({ ...addForm, qualities: e.target.value })}
            />
            <textarea
              className="w-full px-3 py-2 border border-slate-300 rounded-lg"
              placeholder="Ontwikkelpunten (wat moet nog groeien?)"
              rows={2}
              value={addForm.development}
              onChange={(e) => setAddForm({ ...addForm, development: e.target.value })}
            />
            <input
              className="w-full px-3 py-2 border border-slate-300 rounded-lg"
              placeholder="Suggested role (optioneel, bijv. support)"
              value={addForm.suggested_role}
              onChange={(e) => setAddForm({ ...addForm, suggested_role: e.target.value })}
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => !adding && setShowAdd(false)}
                className="flex-1 px-4 py-2 border border-slate-300 rounded-lg hover:bg-slate-50"
                disabled={adding}
              >
                Annuleren
              </button>
              <button
                type="button"
                onClick={submitAdd}
                disabled={adding}
                className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg disabled:opacity-50"
              >
                {adding ? 'Bezig...' : 'Aanmaken'}
              </button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
