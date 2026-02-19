import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import PageLayout from './PageLayout'
import { supabase } from './supabase'
import { getCurrentUserRole } from './authz'
import { User, Loader } from 'lucide-react'

function fallbackName(user) {
  return user?.user_metadata?.full_name || user?.user_metadata?.name || user?.email || 'Unknown user'
}

function withTimeout(promise, ms = 8000) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error('Verzoek duurde te lang. Probeer de pagina te herladen.')), ms))
  ])
}

export default function MyAccount() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [role, setRole] = useState('member')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [fullName, setFullName] = useState('')
  const [newPassword, setNewPassword] = useState('')

  useEffect(() => {
    let mounted = true

    const sync = async () => {
      try {
        const { data } = await withTimeout(supabase.auth.getSession(), 5000)
        const currentUser = data?.session?.user || null
        if (!mounted) return
        setUser(currentUser)
        setFullName(fallbackName(currentUser))
      } catch (e) {
        console.error('getSession failed:', e)
        if (!mounted) return
      }
      setLoading(false)

      try {
        const ctx = await getCurrentUserRole()
        if (mounted) setRole(ctx.role || 'member')
      } catch {
        if (mounted) setRole('member')
      }
    }

    sync()

    const { data: listener } = supabase.auth.onAuthStateChange(async (_event, session) => {
      const currentUser = session?.user || null
      if (!currentUser) {
        setUser(null)
        setLoading(false)
        return
      }
      setUser(currentUser)
      setFullName(fallbackName(currentUser))
      try {
        const ctx = await getCurrentUserRole()
        setRole(ctx.role || 'member')
      } catch {
        setRole('member')
      }
    })

    return () => {
      mounted = false
      listener.subscription.unsubscribe()
    }
  }, [])

  const canSaveProfile = useMemo(() => !!user && fullName.trim().length > 0, [user, fullName])
  const canChangePassword = useMemo(() => !!user && newPassword.length >= 8, [user, newPassword])

  const handleSaveProfile = async () => {
    if (!canSaveProfile) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const { error: updateError } = await withTimeout(supabase.auth.updateUser({
        data: { full_name: fullName.trim(), name: fullName.trim() },
      }))
      if (updateError) {
        setError(updateError.message)
      } else {
        setMessage('Profiel bijgewerkt.')
      }
    } catch (e) {
      setError(e.message || 'Profiel opslaan mislukt')
    } finally {
      setBusy(false)
    }
  }

  const handleChangePassword = async () => {
    if (!canChangePassword) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const { error: updateError } = await withTimeout(supabase.auth.updateUser({ password: newPassword }))
      if (updateError) {
        setError(updateError.message)
      } else {
        setMessage('Wachtwoord gewijzigd.')
        setNewPassword('')
      }
    } catch (e) {
      setError(e.message || 'Wachtwoord wijzigen mislukt')
    } finally {
      setBusy(false)
    }
  }

  const handleSignOut = async () => {
    setBusy(true)
    setError('')
    try {
      await withTimeout(supabase.auth.signOut())
    } catch (e) {
      console.error('signOut error:', e)
    } finally {
      setBusy(false)
      setUser(null)
      navigate('/login')
    }
  }

  if (loading && !user) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card flex items-center justify-center py-12">
          <Loader className="w-5 h-5 animate-spin text-indigo-600 mr-2" />
          <span className="text-sm text-gray-500">Sessie laden...</span>
        </div>
      </PageLayout>
    )
  }

  if (!user) {
    return (
      <PageLayout size="narrow" padded>
        <div className="max-w-md mx-auto">
          <div className="panel-card space-y-4 text-center">
            <div className="w-16 h-16 mx-auto bg-gray-100 rounded-full flex items-center justify-center">
              <User className="w-8 h-8 text-gray-400" />
            </div>
            <h1 className="page-title">Mijn account</h1>
            <p className="text-sm text-gray-500">Log in om je profiel te bekijken en beheren.</p>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition"
            >
              Inloggen
            </Link>
          </div>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout size="narrow" padded>
      <div className="panel-card space-y-6">
        <div>
          <h1 className="page-title">Mijn account</h1>
          <p className="page-subtitle">Bekijk en beheer je profielgegevens.</p>
        </div>

        {error && <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}
        {message && <div className="p-3 bg-emerald-50 text-emerald-700 rounded-lg text-sm">{message}</div>}

        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-700">Naam</label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg"
          />
          <button
            type="button"
            onClick={handleSaveProfile}
            disabled={busy || !canSaveProfile}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {busy ? 'Opslaan...' : 'Profiel opslaan'}
          </button>
        </div>

        <div className="space-y-2 text-sm text-gray-700">
          <div><span className="font-semibold">Email:</span> {user.email || '-'}</div>
          <div><span className="font-semibold">Rol:</span> <span className={role === 'super_admin' ? 'text-indigo-600 font-semibold' : ''}>{role}</span></div>
          <div><span className="font-semibold">User ID:</span> <code className="text-xs">{user.id}</code></div>
        </div>

        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-700">Nieuw wachtwoord</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Minimaal 8 karakters"
            className="w-full px-3 py-2 border rounded-lg"
          />
          <button
            type="button"
            onClick={handleChangePassword}
            disabled={busy || !canChangePassword}
            className="px-4 py-2 rounded-lg bg-gray-900 text-white hover:bg-black disabled:opacity-50"
          >
            {busy ? 'Bezig...' : 'Wachtwoord wijzigen'}
          </button>
        </div>

        <div className="pt-2 border-t">
          <button
            type="button"
            onClick={handleSignOut}
            disabled={busy}
            className="px-4 py-2 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            {busy ? 'Bezig...' : 'Uitloggen'}
          </button>
        </div>
      </div>
    </PageLayout>
  )
}
