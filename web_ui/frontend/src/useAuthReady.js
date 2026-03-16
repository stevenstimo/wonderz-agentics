import { useEffect, useState } from 'react'
import { supabase } from './supabase'

/** Returns { session, authReady }. Use authReady before fetching; use session for redirect when !session. */
export function useAuthReady() {
  const [state, setState] = useState({ ready: false, session: null })

  useEffect(() => {
    supabase.auth.getSession()
      .then(({ data: { session } }) => { setState({ ready: true, session: session ?? null }) })
      .catch(() => { setState((s) => ({ ...s, ready: true })) })
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setState({ ready: true, session: session ?? null })
    })
    return () => subscription.unsubscribe()
  }, [])

  return { session: state.session, authReady: state.ready }
}
