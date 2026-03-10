import { useEffect, useState } from 'react'
import { useLocation, Navigate } from 'react-router-dom'
import { supabase } from './supabase'
import PageLayout from './PageLayout'

/**
 * Wrapper that requires an authenticated session.
 * Waits for onAuthStateChange to fire (not getSession) so magic link
 * hash is processed before we decide. No session → redirect to /login.
 */
export default function RequireAuth({ children }) {
  const location = useLocation()
  const [initialized, setInitialized] = useState(false)
  const [session, setSession] = useState(null)

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        setInitialized(true)
      }
    )
    return () => subscription.unsubscribe()
  }, [])

  if (!initialized) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card flex items-center justify-center py-12">
          <span className="text-slate-500">Bezig met inloggen...</span>
        </div>
      </PageLayout>
    )
  }

  if (!session?.user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
