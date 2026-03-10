import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { supabase } from './supabase'

export default function RequireAuth({ children }) {
  const [status, setStatus] = useState('loading') // 'loading' | 'auth' | 'unauth'
  const location = useLocation()

  useEffect(() => {
    let mounted = true
    console.log('[RequireAuth] mount, location:', location.pathname)

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!mounted) return
      console.log('[RequireAuth] getSession result:', session?.user?.email ?? 'no session')
      setStatus(session?.user ? 'auth' : 'unauth')
    }).catch((err) => {
      if (!mounted) return
      console.log('[RequireAuth] getSession error:', err)
      setStatus('unauth')
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!mounted) return
      console.log('[RequireAuth] onAuthStateChange:', _event, session?.user?.email ?? 'no session')
      setStatus(session?.user ? 'auth' : 'unauth')
    })

    return () => {
      console.log('[RequireAuth] unmount')
      mounted = false
      subscription.unsubscribe()
    }
  }, [])

  if (status === 'loading') return null
  if (status === 'unauth') return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return children
}
