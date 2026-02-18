import { useEffect, useMemo, useState } from 'react'
import PageLayout from './PageLayout'
import { supabase } from './supabase'
import { getCurrentUserRole } from './authz'

function fallbackName(user) {
  return user?.user_metadata?.full_name || user?.user_metadata?.name || user?.email || 'Unknown user'
}

export default function MyAccount() {
  const [user, setUser] = useState(null)
  const [role, setRole] = useState('member')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [fullName, setFullName] = useState('')
  const [newPassword, setNewPassword] = useState('')

  useEffect(() => {
    let mounted = true

    const sync = async () => {
      const { data } = await supabase.auth.getSession()
      const currentUser = data?.session?.user || null
      if (!mounted) return
      setUser(currentUser)
      setFullName(fallbackName(currentUser))

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

    const { error: updateError } = await supabase.auth.updateUser({
      data: {
        full_name: fullName.trim(),
        name: fullName.trim(),
      },
    })

    if (updateError) {
      setError(updateError.message)
    } else {
      setMessage('Profiel bijgewerkt.')
    }
    setBusy(false)
  }

  const handleChangePassword = async () => {
    if (!canChangePassword) return
    setBusy(true)
    setError('')
    setMessage('')

    const { error: updateError } = await supabase.auth.updateUser({
      password: newPassword,
    })

    if (updateError) {
      setError(updateError.message)
    } else {
      setMessage('Wachtwoord gewijzigd.')
      setNewPassword('')
    }
    setBusy(false)
  }

  const handleSignOut = async () => {
    setBusy(true)
    setError('')
    await supabase.auth.signOut()
    setBusy(false)
  }

  if (!user) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card">
          <h1 className="page-title">Mijn account</h1>
          <p className="page-subtitle">Je bent niet ingelogd.</p>
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

        <div className="space-y-3 text-sm text-gray-700">
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
          <div><span className="font-semibold">Rol:</span> {role}</div>
          <div><span className="font-semibold">User ID:</span> <code>{user.id}</code></div>
          <p className="text-xs text-gray-500">E-mail aanpassen is momenteel niet beschikbaar.</p>
        </div>

        <div className="space-y-3 text-sm text-gray-700">
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

        <button
          type="button"
          onClick={handleSignOut}
          disabled={busy}
          className="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
        >
          Uitloggen
        </button>

        {error && <div className="text-sm text-red-600">{error}</div>}
        {message && <div className="text-sm text-emerald-700">{message}</div>}
      </div>
    </PageLayout>
  )
}
