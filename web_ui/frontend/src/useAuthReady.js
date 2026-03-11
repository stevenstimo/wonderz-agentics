import { useEffect, useState } from 'react'
import { supabase } from './supabase'

export function useAuthReady() {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    // Zodra we weten of er een sessie is, kunnen we fetchen (401 wordt afgehandeld)
    supabase.auth.getSession()
      .then(({ data: { session } }) => { setReady(true) })
      .catch(() => { setReady(true) })
    const { data: { subscription } } = supabase.auth.onAuthStateChange(() => {
      setReady(true)
    })
    return () => subscription.unsubscribe()
  }, [])

  return ready
}
