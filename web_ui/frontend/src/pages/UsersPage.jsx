import { useState, useEffect, useCallback } from 'react'
import PageLayout from '../PageLayout'
import { apiFetch } from '../apiClient'
import { useAuthReady } from '../useAuthReady'
import { getCurrentUserRole } from '../authz'
import { AlertCircle, Trash2 } from 'lucide-react'

const ROLE_LABELS = { super_admin: 'Super Admin', member: 'Medewerker' }

function formatLidSinds(createdAt) {
  if (!createdAt) return '—'
  const d = new Date(createdAt)
  return d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

function formatLaatsteLogin(lastSignInAt) {
  if (!lastSignInAt) return 'Nooit'
  const d = new Date(lastSignInAt)
  const today = new Date()
  if (d.toDateString() === today.toDateString()) return 'Vandaag'
  return d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function UsersPage() {
  const { authReady } = useAuthReady()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [currentUserId, setCurrentUserId] = useState(null)
  const [email, setEmail] = useState('')
  const [inviting, setInviting] = useState(false)
  const [inviteMessage, setInviteMessage] = useState({ type: '', text: '' })
  const [deleteConfirm, setDeleteConfirm] = useState(null)

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiFetch('/api/users/')
      if (res.status === 403 || res.status === 401) {
        setUsers([])
        return
      }
      if (res.ok) {
        const data = await res.json()
        setUsers(data.users || [])
      } else {
        setUsers([])
      }
    } catch {
      setUsers([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!authReady) return
    let mounted = true
    getCurrentUserRole().then(({ user }) => {
      if (mounted && user?.id) setCurrentUserId(user.id)
    })
    return () => { mounted = false }
  }, [authReady])

  useEffect(() => {
    if (!authReady) return
    fetchUsers()
  }, [authReady, fetchUsers])

  const handleInvite = async (e) => {
    e.preventDefault()
    const trimmed = (email || '').trim()
    if (!trimmed) {
      setInviteMessage({ type: 'error', text: 'Vul een e-mailadres in.' })
      return
    }
    setInviting(true)
    setInviteMessage({ type: '', text: '' })
    try {
      const res = await apiFetch('/api/users/invite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: trimmed, role: 'member' }),
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        setInviteMessage({ type: 'success', text: `Uitnodiging verstuurd naar ${trimmed}` })
        setEmail('')
        fetchUsers()
      } else {
        setInviteMessage({ type: 'error', text: data.detail || 'Uitnodiging mislukt.' })
      }
    } catch (err) {
      setInviteMessage({ type: 'error', text: err.message || 'Uitnodiging mislukt.' })
    } finally {
      setInviting(false)
    }
  }

  const handleDeleteClick = (user) => {
    setDeleteConfirm(user)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm) return
    const { user_id } = deleteConfirm
    try {
      const res = await apiFetch(`/api/users/${user_id}`, { method: 'DELETE' })
      if (res.ok) {
        setUsers((prev) => prev.filter((u) => u.user_id !== user_id))
        setDeleteConfirm(null)
      } else {
        const data = await res.json().catch(() => ({}))
        setInviteMessage({ type: 'error', text: data.detail || 'Verwijderen mislukt.' })
      }
    } catch (err) {
      setInviteMessage({ type: 'error', text: err.message || 'Verwijderen mislukt.' })
    } finally {
      setDeleteConfirm(null)
    }
  }

  return (
    <PageLayout size="wide" padded>
      <h1 className="text-2xl font-bold text-slate-800 mb-6">Gebruikers</h1>

      {/* Sectie 1 — Uitnodigen */}
      <section className="mb-8 p-6 bg-white rounded-xl border border-slate-200 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">Uitnodigen</h2>
        <form onSubmit={handleInvite} className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-slate-700 mb-1">E-mailadres</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="iemand@example.com"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div className="w-40">
            <label className="block text-sm font-medium text-slate-700 mb-1">Rol</label>
            <select
              className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white"
              value="member"
              readOnly
              disabled
            >
              <option value="member">Medewerker</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={inviting}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {inviting ? 'Versturen…' : 'Uitnodigingsmail versturen'}
          </button>
        </form>
        {inviteMessage.text && (
          <div
            className={`mt-4 p-4 rounded-lg flex items-start gap-3 ${
              inviteMessage.type === 'success' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
            }`}
          >
            <AlertCircle
              className={`w-5 h-5 mt-0.5 flex-shrink-0 ${
                inviteMessage.type === 'success' ? 'text-green-600' : 'text-red-600'
              }`}
            />
            <p className={inviteMessage.type === 'success' ? 'text-green-800' : 'text-red-800'}>
              {inviteMessage.text}
            </p>
          </div>
        )}
      </section>

      {/* Sectie 2 — Actieve gebruikers */}
      <section className="p-6 bg-white rounded-xl border border-slate-200 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">Actieve gebruikers</h2>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600" />
          </div>
        )}

        {!loading && users.length === 0 && (
          <p className="text-slate-500 py-6">Nog geen gebruikers geladen.</p>
        )}

        {!loading && users.length > 0 && users.every((u) => u.user_id === currentUserId) && (
          <p className="text-slate-500 py-6">Nog geen andere gebruikers uitgenodigd.</p>
        )}

        {!loading && users.length > 0 && users.some((u) => u.user_id !== currentUserId) && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="py-3 px-2 font-semibold text-slate-700">E-mail</th>
                  <th className="py-3 px-2 font-semibold text-slate-700">Rol</th>
                  <th className="py-3 px-2 font-semibold text-slate-700">Lid sinds</th>
                  <th className="py-3 px-2 font-semibold text-slate-700">Laatste login</th>
                  <th className="py-3 px-2 font-semibold text-slate-700">Actie</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.user_id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="py-3 px-2 text-slate-800">{u.email}</td>
                    <td className="py-3 px-2 text-slate-700">
                      {ROLE_LABELS[u.role] || u.role}
                    </td>
                    <td className="py-3 px-2 text-slate-600">{formatLidSinds(u.created_at)}</td>
                    <td className="py-3 px-2 text-slate-600">{formatLaatsteLogin(u.last_sign_in_at)}</td>
                    <td className="py-3 px-2">
                      {u.user_id === currentUserId ? (
                        '—'
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleDeleteClick(u)}
                          className="text-red-600 hover:text-red-800 flex items-center gap-1"
                        >
                          <Trash2 className="w-4 h-4" />
                          Verwijderen
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Bevestigingsdialog */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-slate-800 mb-2">Gebruiker verwijderen</h3>
            <p className="text-slate-600 mb-4">
              Weet je zeker dat je <strong>{deleteConfirm.email}</strong> wilt verwijderen? Deze actie kan niet ongedaan worden gemaakt.
            </p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
              >
                Annuleren
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                Verwijderen
              </button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
