import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { supabase } from './supabase'
import PageLayout from './PageLayout'
import { Mail, Lock, Eye, EyeOff, Loader } from 'lucide-react'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname ?? location.state?.from ?? '/'
  const fromLabel = from === '/job-center' ? 'Job Center' : from === '/clients' ? 'Clients' : from.startsWith('/clients/') ? 'Clients' : null
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [mode, setMode] = useState('login') // 'login' | 'register' | 'magic'
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  // If already logged in, redirect to returnTo or account
  useEffect(() => {
    supabase.auth.getSession()
      .then(({ data }) => {
        if (data?.session?.user) navigate(from, { replace: true })
      })
      .catch(() => {})
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) navigate(from, { replace: true })
    })
    return () => listener.subscription.unsubscribe()
  }, [navigate, from])

  const handleLogin = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')

    const { error: authError } = await supabase.auth.signInWithPassword({ email, password })
    if (authError) {
      setError(authError.message)
      setBusy(false)
    } else {
      // SPA-navigatie (geen reload): sessie staat al in Supabase-client, RequireAuth vindt die via getSession/onAuthStateChange
      navigate(from || '/', { replace: true })
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')

    const { error: authError } = await supabase.auth.signUp({ email, password })
    if (authError) {
      setError(authError.message)
    } else {
      setMessage('Check je e-mail voor een bevestigingslink.')
    }
    setBusy(false)
  }

  // Magic link: not yet supported — /auth/callback route missing
  const handleMagicLink = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')

    const { error: authError } = await supabase.auth.signInWithOtp({ email })
    if (authError) {
      setError(authError.message)
    } else {
      setMessage('Magic link verstuurd! Check je e-mail.')
    }
    setBusy(false)
  }

  const onSubmit = mode === 'login' ? handleLogin : mode === 'register' ? handleRegister : handleMagicLink

  return (
    <PageLayout size="narrow" padded>
      <div className="max-w-md mx-auto">
        <div className="panel-card space-y-6">
          <div>
            <h1 className="page-title">Inloggen</h1>
            <p className="page-subtitle">
              {fromLabel && mode === 'login' && `Log in om ${fromLabel} te bekijken.`}
              {(!fromLabel || mode !== 'login') && mode === 'login' && 'Log in met je e-mail en wachtwoord.'}
              {mode === 'register' && 'Maak een nieuw account aan.'}
              {mode === 'magic' && 'Ontvang een inloglink via e-mail.'}
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">E-mail</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="naam@voorbeeld.nl"
                  required
                  className="w-full pl-10 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
            </div>

            {mode !== 'magic' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Wachtwoord</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={mode === 'register' ? 'Minimaal 6 karakters' : 'Je wachtwoord'}
                    required
                    minLength={mode === 'register' ? 6 : undefined}
                    className="w-full pl-10 pr-10 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition disabled:opacity-50"
            >
              {busy && <Loader className="w-4 h-4 animate-spin" />}
              {mode === 'login' && 'Inloggen'}
              {mode === 'register' && 'Account aanmaken'}
              {mode === 'magic' && 'Magic link versturen'}
            </button>
          </form>

          {error && <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}
          {message && <div className="p-3 bg-emerald-50 text-emerald-700 rounded-lg text-sm">{message}</div>}

          <div className="border-t pt-4 space-y-2 text-sm text-center">
            {mode === 'login' && (
              <>
                <button type="button" onClick={() => { setMode('register'); setError(''); setMessage('') }} className="text-indigo-600 hover:underline">
                  Nog geen account? Registreer
                </button>
                <span className="block text-gray-400">of</span>
                <button type="button" onClick={() => { setMode('magic'); setError(''); setMessage('') }} className="text-indigo-600 hover:underline">
                  Login via magic link
                </button>
              </>
            )}
            {mode === 'register' && (
              <button type="button" onClick={() => { setMode('login'); setError(''); setMessage('') }} className="text-indigo-600 hover:underline">
                Al een account? Log in
              </button>
            )}
            {mode === 'magic' && (
              <button type="button" onClick={() => { setMode('login'); setError(''); setMessage('') }} className="text-indigo-600 hover:underline">
                Terug naar inloggen met wachtwoord
              </button>
            )}
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
