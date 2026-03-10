import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from './supabase'
import PageLayout from './PageLayout'

/**
 * Wrapper that requires an authenticated session.
 * No session → redirect to /login.
 * Session present → render children.
 */
export default function RequireAuth({ children }) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [hasSession, setHasSession] = useState(false)

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        if (session?.user) {
          setHasSession(true)
        } else {
          navigate('/login', { replace: true })
        }
        setLoading(false)
      }
    )
    return () => subscription.unsubscribe()
  }, [navigate])

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
    return null
  }

  return children
}
