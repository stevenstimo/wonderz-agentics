import { useEffect, useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import PageLayout from './PageLayout'
import { getCurrentUserRole, isSuperAdmin } from './authz'

const apiBase = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')
const crewRoles = ['Developer', 'Product Owner', 'Reviewer', 'DevOps', 'AI', 'HR', 'Training', 'CIO']

function initials(name) {
  if (!name || typeof name !== 'string') return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  return (name[0] || '?').toUpperCase()
}

export default function TalentOverview() {
  const [talents, setTalents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [userRole, setUserRole] = useState('member')

  const [selectedTalent, setSelectedTalent] = useState(null)
  const [promoting, setPromoting] = useState(false)
  const [promoteForm, setPromoteForm] = useState({ role: 'Developer', system_instructions: '', hiring_logic: '', specialization: '' })

  const [showAdd, setShowAdd] = useState(false)
  const [adding, setAdding] = useState(false)
  const [addForm, setAddForm] = useState({ name: '', persona: '', quality: '', growth: '', avatar_url: '' })

  const [avatarTalent, setAvatarTalent] = useState(null)
  const [avatarValue, setAvatarValue] = useState('')
  const [savingAvatar, setSavingAvatar] = useState(false)

  const canEdit = useMemo(() => isSuperAdmin(userRole), [userRole])

  const fetchTalents = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${apiBase}/api/talents`)
      if (!res.ok) throw new Error(`Talents ophalen mislukt (${res.status})`)
      const data = await res.json()
      setTalents(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message || 'Talents ophalen mislukt')
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
      fetchTalents()
    })()
  }, [])

  const handlePromote = (talent) => {
    setSelectedTalent(talent)
    setPromoteForm({
      role: 'Developer',
      system_instructions: talent.quality || '',
      hiring_logic: talent.growth || '',
      specialization: talent.persona || '',
    })
  }

  const submitPromotion = async () => {
    if (!selectedTalent || !canEdit) return
    if (!promoteForm.system_instructions.trim() || !promoteForm.hiring_logic.trim()) return

    setPromoting(true)
    try {
      const res = await fetch(`${apiBase}/api/talents/${selectedTalent.id}/promote`, {
        method: 'POST',
        body: JSON.stringify(promoteForm),
      })

      if (!res.ok) throw new Error('Promotie mislukt')
      setSelectedTalent(null)
      await fetchTalents()
    } catch (err) {
      setError(err.message || 'Promotie mislukt')
    } finally {
      setPromoting(false)
    }
  }

  const submitAdd = async () => {
    if (!canEdit) return
    if (!addForm.name.trim() || !addForm.persona.trim() || !addForm.quality.trim() || !addForm.growth.trim()) return

    setAdding(true)
    setError('')
    try {
      const res = await fetch(`${apiBase}/api/talents`, {
        method: 'POST',
        body: JSON.stringify({ ...addForm, skills: [] }),
      })
      if (!res.ok) throw new Error(`Talent toevoegen mislukt (${res.status})`)
      setShowAdd(false)
      setAddForm({ name: '', persona: '', quality: '', growth: '', avatar_url: '' })
      await fetchTalents()
    } catch (err) {
      setError(err.message || 'Talent toevoegen mislukt')
    } finally {
      setAdding(false)
    }
  }

  const openAvatarModal = (talent, e) => {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    setAvatarTalent(talent)
    setAvatarValue(talent.avatar_url || '')
  }

  const saveAvatar = async () => {
    if (!avatarTalent || !canEdit) return
    setSavingAvatar(true)
    setError('')
    try {
      const res = await fetch(`${apiBase}/api/talents/${avatarTalent.id}`, {
        method: 'PUT',
        body: JSON.stringify({ avatar_url: avatarValue }),
      })
      if (!res.ok) throw new Error(`Avatar bijwerken mislukt (${res.status})`)
      setAvatarTalent(null)
      setAvatarValue('')
      await fetchTalents()
    } catch (err) {
      setError(err.message || 'Avatar bijwerken mislukt')
    } finally {
      setSavingAvatar(false)
    }
  }

  const avatarSrc = (talent) =>
    talent.avatar_url || `https://api.dicebear.com/7.x/personas/svg?seed=${encodeURIComponent(talent.name || talent.id)}`

  return (
    <PageLayout>
      <div className="wz-card">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="page-title mb-1">Talent Pool</h1>
            <p className="page-subtitle">Kandidaten die je kunt promoveren naar de crew.</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-icon-only" type="button" onClick={fetchTalents} aria-label="Vernieuwen">
              ↻
            </button>
            {canEdit && (
              <button type="button" className="wz-btn-primary gap-2 flex items-center" onClick={() => setShowAdd(true)}>
                <Plus className="w-4 h-4" />
                Nieuwe Talent
              </button>
            )}
          </div>
        </div>

        {error && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        {loading ? (
          <div className="text-sm text-gray-500">Laden...</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 gap-4 w-full">
            {talents.map((talent) => (
              <div
                key={talent.id}
                className="wz-card wz-card-subtle block hover:shadow-[var(--shadow-hover)] transition-[box-shadow]"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full overflow-hidden bg-indigo-100 text-indigo-700 font-semibold text-sm">
                    <img src={avatarSrc(talent)} alt="" className="w-full h-full object-cover" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-slate-800">{talent.name || '—'}</span>
                    </div>
                    <div className="text-xs text-slate-600 mt-0.5">{talent.persona || '—'}</div>
                    {talent.quality && (
                      <div className="text-xs text-slate-500 mt-1 line-clamp-2">{talent.quality}</div>
                    )}
                    <div className="mt-3 flex items-center gap-3">
                      {canEdit && (
                        <>
                          <button
                            type="button"
                            className="text-slate-600 hover:underline text-sm"
                            onClick={(e) => openAvatarModal(talent, e)}
                          >
                            Avatar aanpassen
                          </button>
                          <button
                            type="button"
                            className="text-blue-600 hover:underline text-sm font-medium"
                            onClick={() => handlePromote(talent)}
                          >
                            Promoveren naar crew
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {!talents.length && (
              <div className="col-span-full py-8 text-center text-sm text-slate-500">
                Geen talents gevonden.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modal: New Talent */}
      {showAdd && (
        <div className="modal-overlay">
          <div className="modal-card space-y-3">
            <h2 className="text-xl font-bold">Nieuwe Talent</h2>
            <input className="wz-input" placeholder="Naam" value={addForm.name} onChange={(e) => setAddForm({ ...addForm, name: e.target.value })} />
            <input className="wz-input" placeholder="Persona" value={addForm.persona} onChange={(e) => setAddForm({ ...addForm, persona: e.target.value })} />
            <textarea className="wz-input" placeholder="Quality" value={addForm.quality} onChange={(e) => setAddForm({ ...addForm, quality: e.target.value })} />
            <textarea className="wz-input" placeholder="Growth" value={addForm.growth} onChange={(e) => setAddForm({ ...addForm, growth: e.target.value })} />
            <input className="wz-input" placeholder="Avatar URL" value={addForm.avatar_url} onChange={(e) => setAddForm({ ...addForm, avatar_url: e.target.value })} />
            <div className="flex gap-2">
              <button type="button" onClick={() => setShowAdd(false)} className="flex-1 px-4 py-2 border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-bg-subtle)]">Annuleren</button>
              <button type="button" onClick={submitAdd} disabled={adding} className="wz-btn-primary flex-1 disabled:opacity-50">{adding ? 'Opslaan...' : 'Aanmaken'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Promote */}
      {selectedTalent && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Promoveren: {selectedTalent.name}</h2>
              <button type="button" onClick={() => setSelectedTalent(null)} className="text-slate-400 hover:text-slate-600">×</button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold mb-1">Rol</label>
                <select value={promoteForm.role} onChange={(e) => setPromoteForm({ ...promoteForm, role: e.target.value })} className="wz-input">
                  {crewRoles.map((role) => <option key={role}>{role}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-semibold mb-1">Specialisatie</label>
                <input type="text" value={promoteForm.specialization} onChange={(e) => setPromoteForm({ ...promoteForm, specialization: e.target.value })} className="wz-input" />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-1">System Instructions</label>
                <textarea value={promoteForm.system_instructions} onChange={(e) => setPromoteForm({ ...promoteForm, system_instructions: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg h-24" />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-1">Hiring Logic</label>
                <textarea value={promoteForm.hiring_logic} onChange={(e) => setPromoteForm({ ...promoteForm, hiring_logic: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg h-24" />
              </div>
              <div className="flex gap-3 mt-6">
                <button type="button" onClick={() => setSelectedTalent(null)} className="flex-1 px-4 py-2 border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-bg-subtle)]" disabled={promoting}>Annuleren</button>
                <button type="button" onClick={submitPromotion} disabled={promoting} className="wz-btn-primary flex-1 disabled:opacity-50">{promoting ? 'Bezig...' : 'Promoveren'}</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Avatar */}
      {avatarTalent && (
        <div className="modal-overlay">
          <div className="modal-card space-y-3">
            <h2 className="text-xl font-bold">Avatar voor {avatarTalent.name}</h2>
            <input className="wz-input" placeholder="Avatar URL" value={avatarValue} onChange={(e) => setAvatarValue(e.target.value)} />
            <div className="flex justify-center">
              <img
                src={avatarValue || `https://api.dicebear.com/7.x/personas/svg?seed=${encodeURIComponent(avatarTalent.name)}`}
                alt="Avatar preview"
                className="w-20 h-20 rounded-full border border-slate-200 object-cover"
              />
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={() => setAvatarTalent(null)} className="flex-1 px-4 py-2 border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-bg-subtle)]">Annuleren</button>
              <button type="button" onClick={saveAvatar} disabled={savingAvatar} className="wz-btn-primary flex-1 disabled:opacity-50">{savingAvatar ? 'Opslaan...' : 'Avatar opslaan'}</button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
