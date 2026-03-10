import { useEffect, useState } from 'react'
import { supabase } from './supabase'

export function useAuthReady() {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    // Check of sessie al beschikbaar is
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) setReady(true)
    })
    // Of wacht op auth state change
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (session) setReady(true)
    })
    return () => subscription.unsubscribe()
  }, [])

  return ready
}
