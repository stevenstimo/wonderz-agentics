import React, { useEffect, useState } from 'react'
import { supabase } from './supabase'
import { Link, useNavigate } from 'react-router-dom'

function getInitials(user) {
  const source =
    user?.user_metadata?.full_name ||
    user?.user_metadata?.name ||
    user?.email ||
    'U'
  return source.trim().charAt(0).toUpperCase()
}

function getAvatarUrl(user) {
  return (
    user?.user_metadata?.avatar_url ||
    user?.user_metadata?.picture ||
    ''
  )
}

export default function TopHeader() {
  const [user, setUser] = useState(null)
  const [backendOk, setBackendOk] = useState(null)
  const navigate = useNavigate()

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || ''
  const healthUrl = `${apiBaseUrl.replace(/\/$/, '')}/api/health`
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

  useEffect(() => {
    let active = true
    const checkHealth = async () => {
      try {
        const res = await fetch(apiBaseUrl ? healthUrl : '/api/health')
        if (!active) return
        setBackendOk(res.ok)
      } catch (_err) {
        if (!active) return
        setBackendOk(false)
      }
    }
    checkHealth()
    const timer = setInterval(checkHealth, 30000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  const avatarUrl = getAvatarUrl(user)

  return (
    <header className="top-header">
      <div className="top-header-inner">
        <div className="top-header-brand">Wonderz</div>
        <div className="top-header-account">
          <Link to="/status" title="Open status dashboard">
            <span
              className={`inline-block w-2.5 h-2.5 rounded-full mr-3 ${backendOk === null ? 'bg-gray-400' : backendOk ? 'bg-emerald-500' : 'bg-amber-500'}`}
              title={backendOk === null ? 'Backend status onbekend' : backendOk ? 'Backend online' : 'Backend check required'}
            />
          </Link>
          <button
            type="button"
            className="top-header-account-link"
            title={user ? 'Mijn account' : 'Inloggen'}
            onClick={() => navigate(user ? '/my-account' : '/login')}
          >
            {!user ? (
              <span className="top-header-signin">Sign in</span>
            ) : avatarUrl ? (
              <img className="top-header-avatar" src={avatarUrl} alt="Account avatar" />
            ) : (
              <div className="top-header-avatar top-header-avatar-fallback">
                {getInitials(user)}
              </div>
            )}
          </button>
        </div>
      </div>
    </header>
  )
}
