import React, { useEffect, useState } from 'react'
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

  const avatarUrl = getAvatarUrl(user)

  return (
    <header className="top-header">
      <div className="top-header-inner">
        <div className="top-header-brand">Wonderz</div>
        <div className="top-header-account">
          {!user ? (
            <span className="top-header-signin">Sign in</span>
          ) : avatarUrl ? (
            <img className="top-header-avatar" src={avatarUrl} alt="Account avatar" />
          ) : (
            <div className="top-header-avatar top-header-avatar-fallback">
              {getInitials(user)}
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
