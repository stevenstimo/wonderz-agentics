import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from './supabase'
import PageLayout from './PageLayout'

/**
 * Auth callback route: landing page for magic link / OAuth redirects.
 * Supabase processes the URL hash (detectSessionInUrl). We wait for
 * onAuthStateChange to fire with the session, then redirect to /.
 */
export default function AuthCallback() {
  const navigate = useNavigate()
  const [done, setDone] = useState(false)

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setDone(true)
        navigate('/', { replace: true })
      }
    )
    return () => subscription.unsubscribe()
  }, [navigate])

  if (!done) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card flex items-center justify-center py-12">
          <span className="text-slate-500">Bezig met inloggen...</span>
        </div>
      </PageLayout>
    )
  }

  return null
}
