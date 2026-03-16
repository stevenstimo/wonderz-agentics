import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from './PageLayout'
import { supabase } from './supabase'
import { getCurrentUserRole } from './authz'
import { useAuthReady } from './useAuthReady'
import { useAvatarUpload } from './hooks/useAvatarUpload'
import { useToast } from './Toast'
import { ToastContainer } from './Toast'
import { Loader2 } from 'lucide-react'

function fallbackName(user) {
  return user?.user_metadata?.full_name || user?.user_metadata?.name || user?.email || 'Unknown user'
}

function getInitials(user) {
  const source =
    user?.user_metadata?.full_name ||
    user?.user_metadata?.name ||
    user?.email ||
    'U'
  return source.trim().charAt(0).toUpperCase()
}

export default function MyAccount() {
  const navigate = useNavigate()
  const { session: authSession, authReady } = useAuthReady()
  const [user, setUser] = useState(null)
  const [role, setRole] = useState('member')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [fullName, setFullName] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [displayAvatarUrl, setDisplayAvatarUrl] = useState(null)
  const fileInputRef = useRef(null)
  const toast = useToast()
  const { uploadAvatar, isUploading } = useAvatarUpload()

  useEffect(() => {
    if (!authReady) return
    let mounted = true

    const sync = async () => {
      const { data } = await supabase.auth.getSession()
      const currentUser = data?.session?.user || null
      if (!mounted) return
      setUser(currentUser)
      setFullName(fallbackName(currentUser))
      setDisplayAvatarUrl(currentUser?.user_metadata?.avatar_url ?? null)

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
      setDisplayAvatarUrl(currentUser?.user_metadata?.avatar_url ?? null)
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
  }, [authReady])

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
    navigate('/login', { replace: true })
    setBusy(false)
  }

  const handleAvatarClick = () => {
    if (isUploading) return
    fileInputRef.current?.click()
  }

  const handleAvatarFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file || !user?.id) return
    e.target.value = ''
    try {
      const publicUrl = await uploadAvatar(file, user.id)
      setDisplayAvatarUrl(publicUrl)
      toast.success('Avatar bijgewerkt.')
    } catch (err) {
      toast.error(err?.message || 'Avatar upload mislukt.')
    }
  }

  if (!authReady) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card flex items-center justify-center gap-2 py-12">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
          <span className="text-slate-600">Laden…</span>
        </div>
      </PageLayout>
    )
  }
  if (authReady && !authSession) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card">
          <h1 className="page-title">Mijn account</h1>
          <p className="page-subtitle">Je bent niet ingelogd.</p>
        </div>
      </PageLayout>
    )
  }
  if (!user) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card flex items-center justify-center gap-2 py-12">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
          <span className="text-slate-600">Laden…</span>
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

        <div className="flex items-center gap-4">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleAvatarFileChange}
          />
          <button
            type="button"
            onClick={handleAvatarClick}
            disabled={isUploading}
            className="relative w-20 h-20 rounded-full overflow-hidden flex-shrink-0 border-2 border-gray-200 hover:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-70 disabled:pointer-events-none"
            title="Avatar wijzigen"
          >
            {displayAvatarUrl ? (
              <img src={displayAvatarUrl} alt="" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full bg-gray-200 flex items-center justify-center text-2xl font-semibold text-gray-600">
                {getInitials(user)}
              </div>
            )}
            {isUploading && (
              <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-white animate-spin" />
              </div>
            )}
          </button>
          <p className="text-sm text-gray-500">Klik op de avatar om een nieuwe foto te uploaden (max. 2 MB).</p>
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
        <ToastContainer toasts={toast.toasts} onRemove={toast.removeToast} />
      </div>
    </PageLayout>
  )
}
