import { useEffect, useMemo, useState } from 'react'
import PageLayout from './PageLayout'
import { supabase } from './supabase'
import { extractRole } from './authz'

function fallbackName(user) {
  return (
    user?.user_metadata?.full_name ||
    user?.user_metadata?.name ||
    user?.email ||
    'Unknown user'
  )
}

export default function MyAccount() {
  const [user, setUser] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let mounted = true

    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return
      setUser(data?.session?.user || null)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user || null)
    })

    return () => {
      mounted = false
      listener.subscription.unsubscribe()
    }
  }, [])

  const role = useMemo(() => extractRole(user), [user])

  const handleSignIn = async () => {
    setBusy(true)
    setError('')
    setMessage('')
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    })
    if (signInError) setError(signInError.message)
    setBusy(false)
  }

  const handleSignUp = async () => {
    setBusy(true)
    setError('')
    setMessage('')
    const { error: signUpError } = await supabase.auth.signUp({
      email: email.trim(),
      password,
    })
    if (signUpError) {
      setError(signUpError.message)
    } else {
      setMessage('Account aangemaakt. Check je email voor verificatie indien nodig.')
    }
    setBusy(false)
  }

  const handleSignOut = async () => {
    setBusy(true)
    setError('')
    const { error: signOutError } = await supabase.auth.signOut()
    if (signOutError) setError(signOutError.message)
    setBusy(false)
  }

  return (
    <PageLayout size="narrow" padded>
      <div className="bg-white rounded-xl shadow-lg p-8 space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">My Account</h1>

        {!user ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">You are not signed in.</p>
            <div className="space-y-2">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                className="w-full px-3 py-2 border rounded-lg"
              />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Wachtwoord"
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleSignIn}
                disabled={busy || !email.trim() || !password}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                {busy ? 'Signing in...' : 'Sign in'}
              </button>
              <button
                onClick={handleSignUp}
                disabled={busy || !email.trim() || !password}
                className="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-60"
              >
                {busy ? 'Creating...' : 'Sign up'}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3 text-sm text-gray-700">
            <div><span className="font-semibold">Name:</span> {fallbackName(user)}</div>
            <div><span className="font-semibold">Email:</span> {user.email || '-'}</div>
            <div><span className="font-semibold">Role:</span> {role}</div>
            <div><span className="font-semibold">User ID:</span> <code>{user.id}</code></div>

            <button
              onClick={handleSignOut}
              disabled={busy}
              className="mt-3 px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-60"
            >
              {busy ? 'Signing out...' : 'Sign out'}
            </button>
          </div>
        )}

        {error && <div className="text-sm text-red-600">{error}</div>}
        {message && <div className="text-sm text-emerald-700">{message}</div>}
      </div>
    </PageLayout>
  )
}
