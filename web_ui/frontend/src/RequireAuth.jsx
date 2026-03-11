import { useEffect, useState, useRef } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { supabase } from './supabase'

export default function RequireAuth({ children }) {
  const [status, setStatus] = useState('loading') // 'loading' | 'auth' | 'unauth'
  const location = useLocation()
  const resolved = useRef(false)

  useEffect(() => {
    let mounted = true
    const timeout = setTimeout(() => {
      if (mounted && !resolved.current) {
        setStatus('unauth')
      }
    }, 8000)

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!mounted) return
      resolved.current = true
      setStatus(session?.user ? 'auth' : 'unauth')
    }).catch(() => {
      if (!mounted) return
      resolved.current = true
      setStatus('unauth')
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!mounted) return
      resolved.current = true
      setStatus(session?.user ? 'auth' : 'unauth')
    })

    return () => {
      mounted = false
      clearTimeout(timeout)
      subscription.unsubscribe()
    }
  }, [])

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
          <p className="text-slate-600 text-sm">Loading...</p>
        </div>
      </div>
    )
  }
  if (status === 'unauth') return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return children
}
