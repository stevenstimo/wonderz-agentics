import { useEffect, useState } from 'react'
import { useLocation, Navigate } from 'react-router-dom'
import { supabase } from './supabase'
import PageLayout from './PageLayout'

/**
 * Wrapper that requires an authenticated session.
 * No session → redirect to /login with returnTo.
 * Session present → render children.
 */
export default function RequireAuth({ children }) {
  const location = useLocation()
  const [loading, setLoading] = useState(true)
  const [hasSession, setHasSession] = useState(false)

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setHasSession(!!session?.user)
        setLoading(false)
      }
    )
    return () => subscription.unsubscribe()
  }, [])

  if (loading) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card flex items-center justify-center py-12">
          <span className="text-slate-500">Bezig met inloggen...</span>
        </div>
      </PageLayout>
    )
  }

  if (!hasSession) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
