import { useEffect, useMemo, useState } from 'react'
import { ChevronUp, Plus, Pencil } from 'lucide-react'
import PageLayout from './PageLayout'
import { buildAuthHeaders, getCurrentUserRole, isSuperAdmin } from './authz'

const apiBase = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')
const crewRoles = ['Developer', 'Product Owner', 'Reviewer', 'DevOps', 'AI', 'HR', 'Training', 'CIO']

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
      if (!res.ok) throw new Error(`Failed to fetch talents (${res.status})`)
      const data = await res.json()
      setTalents(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message || 'Failed to fetch talents')
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
        headers: await buildAuthHeaders(),
        body: JSON.stringify(promoteForm),
      })

      if (!res.ok) throw new Error('Promotion failed')
      setSelectedTalent(null)
      await fetchTalents()
    } catch (err) {
      setError(err.message || 'Error promoting talent')
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
        headers: await buildAuthHeaders(),
        body: JSON.stringify({ ...addForm, skills: [] }),
      })
      if (!res.ok) throw new Error(`Failed to add talent (${res.status})`)
      setShowAdd(false)
      setAddForm({ name: '', persona: '', quality: '', growth: '', avatar_url: '' })
      await fetchTalents()
    } catch (err) {
      setError(err.message || 'Failed to add talent')
    } finally {
      setAdding(false)
    }
  }

  const openAvatarModal = (talent) => {
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
        headers: await buildAuthHeaders(),
        body: JSON.stringify({ avatar_url: avatarValue }),
      })
      if (!res.ok) throw new Error(`Failed to update avatar (${res.status})`)
      setAvatarTalent(null)
      setAvatarValue('')
      await fetchTalents()
    } catch (err) {
      setError(err.message || 'Failed to update avatar')
    } finally {
      setSavingAvatar(false)
    }
  }

  return (
    <PageLayout size="wide" padded>
      <div className="flex items-center justify-between mb-6 gap-4">
        <h1 className="text-2xl font-bold">Talents</h1>
        {canEdit && (
          <button type="button" className="btn-manage gap-2" onClick={() => setShowAdd(true)}>
            <Plus className="w-4 h-4" />
            Add Talent
          </button>
        )}
      </div>

      {error && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}
      {loading && <div className="text-sm text-gray-500">Loading talents...</div>}

      {!loading && talents.length === 0 && (
        <div className="text-center text-gray-500 py-12">No talents yet.</div>
      )}

      {!loading && talents.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {talents.map((talent) => (
            <div key={talent.id} className="bg-white rounded-lg shadow p-4 flex flex-col">
              <img
                src={talent.avatar_url || `https://api.dicebear.com/7.x/personas/svg?seed=${encodeURIComponent(talent.name)}`}
                alt={talent.name}
                className="w-20 h-20 rounded-full mb-3 mx-auto object-cover border"
              />
              <div className="flex-1">
                <div className="font-semibold text-lg text-center">{talent.name}</div>
                <div className="text-gray-600 text-xs text-center mb-2">{talent.persona}</div>
                <div className="text-gray-700 text-xs mb-3">
                  <div className="font-semibold mb-1">Quality:</div>
                  <div className="line-clamp-2">{talent.quality}</div>
                </div>
              </div>

              {canEdit && (
                <>
                  <button type="button" onClick={() => openAvatarModal(talent)} className="w-full px-3 py-2 mb-2 border rounded-lg text-sm hover:bg-gray-50 flex items-center justify-center gap-2">
                    <Pencil className="w-4 h-4" />
                    Update avatar
                  </button>
                  <button type="button" onClick={() => handlePromote(talent)} className="btn-manage w-full gap-2 mt-auto">
                    <ChevronUp className="w-4 h-4" />
                    Promote to Crew
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {showAdd && (
        <div className="modal-overlay">
          <div className="modal-card space-y-3">
            <h2 className="text-xl font-bold">New Talent</h2>
            <input className="w-full px-3 py-2 border rounded-lg" placeholder="Name" value={addForm.name} onChange={(e) => setAddForm({ ...addForm, name: e.target.value })} />
            <input className="w-full px-3 py-2 border rounded-lg" placeholder="Persona" value={addForm.persona} onChange={(e) => setAddForm({ ...addForm, persona: e.target.value })} />
            <textarea className="w-full px-3 py-2 border rounded-lg" placeholder="Quality" value={addForm.quality} onChange={(e) => setAddForm({ ...addForm, quality: e.target.value })} />
            <textarea className="w-full px-3 py-2 border rounded-lg" placeholder="Growth" value={addForm.growth} onChange={(e) => setAddForm({ ...addForm, growth: e.target.value })} />
            <input className="w-full px-3 py-2 border rounded-lg" placeholder="Avatar URL" value={addForm.avatar_url} onChange={(e) => setAddForm({ ...addForm, avatar_url: e.target.value })} />
            <div className="flex gap-2">
              <button type="button" onClick={() => setShowAdd(false)} className="flex-1 px-4 py-2 border rounded-lg">Cancel</button>
              <button type="button" onClick={submitAdd} disabled={adding} className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg disabled:opacity-50">{adding ? 'Saving...' : 'Create'}</button>
            </div>
          </div>
        </div>
      )}

      {selectedTalent && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Promote {selectedTalent.name}</h2>
              <button type="button" onClick={() => setSelectedTalent(null)} className="text-gray-400 hover:text-gray-600">x</button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold mb-1">Role</label>
                <select value={promoteForm.role} onChange={(e) => setPromoteForm({ ...promoteForm, role: e.target.value })} className="w-full px-3 py-2 border rounded-lg">
                  {crewRoles.map((role) => <option key={role}>{role}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-semibold mb-1">Specialization</label>
                <input type="text" value={promoteForm.specialization} onChange={(e) => setPromoteForm({ ...promoteForm, specialization: e.target.value })} className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-1">System Instructions</label>
                <textarea value={promoteForm.system_instructions} onChange={(e) => setPromoteForm({ ...promoteForm, system_instructions: e.target.value })} className="w-full px-3 py-2 border rounded-lg h-24" />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-1">Hiring Logic</label>
                <textarea value={promoteForm.hiring_logic} onChange={(e) => setPromoteForm({ ...promoteForm, hiring_logic: e.target.value })} className="w-full px-3 py-2 border rounded-lg h-24" />
              </div>
              <div className="flex gap-3 mt-6">
                <button type="button" onClick={() => setSelectedTalent(null)} className="flex-1 px-4 py-2 border rounded-lg" disabled={promoting}>Cancel</button>
                <button type="button" onClick={submitPromotion} disabled={promoting} className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg disabled:opacity-50">{promoting ? 'Promoting...' : 'Promote Now'}</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {avatarTalent && (
        <div className="modal-overlay">
          <div className="modal-card space-y-3">
            <h2 className="text-xl font-bold">Update avatar for {avatarTalent.name}</h2>
            <input className="w-full px-3 py-2 border rounded-lg" placeholder="Avatar URL" value={avatarValue} onChange={(e) => setAvatarValue(e.target.value)} />
            <img
              src={avatarValue || `https://api.dicebear.com/7.x/personas/svg?seed=${encodeURIComponent(avatarTalent.name)}`}
              alt="Avatar preview"
              className="w-20 h-20 rounded-full border object-cover"
            />
            <div className="flex gap-2">
              <button type="button" onClick={() => setAvatarTalent(null)} className="flex-1 px-4 py-2 border rounded-lg">Cancel</button>
              <button type="button" onClick={saveAvatar} disabled={savingAvatar} className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg disabled:opacity-50">{savingAvatar ? 'Saving...' : 'Save avatar'}</button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
