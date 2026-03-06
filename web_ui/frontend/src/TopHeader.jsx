import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { supabase } from './supabase'

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
      <div className="w-full h-full flex items-center justify-end pr-4 lg:pr-6 gap-3">
      <Link to="/status" title="Open status dashboard" className="flex items-center gap-2 text-slate-500 hover:text-slate-700">
        <span
          className={`inline-block w-2.5 h-2.5 rounded-full flex-shrink-0 ${
            backendOk === null ? 'bg-slate-400' : backendOk ? 'bg-emerald-500' : 'bg-amber-500'
          }`}
          title={backendOk === null ? 'Backend status unknown' : backendOk ? 'Backend online' : 'Backend check required'}
        />
      </Link>
      <button
        type="button"
        className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition"
        aria-label="Notifications"
      >
        <Bell className="w-5 h-5" />
      </button>
      <button
        type="button"
        className="flex items-center gap-2 rounded-lg hover:opacity-90 transition"
        title={user ? 'Open account' : 'Sign in'}
        onClick={() => navigate(user ? '/my-account' : '/login')}
      >
        {!user ? (
          <span className="text-sm font-medium text-slate-600">Sign in</span>
        ) : avatarUrl ? (
          <img className="w-8 h-8 rounded-full object-cover border border-slate-200" src={avatarUrl} alt="Account avatar" />
        ) : (
          <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-sm font-semibold border border-slate-200">
            {getInitials(user)}
          </div>
        )}
      </button>
      </div>
    </header>
  )
}
