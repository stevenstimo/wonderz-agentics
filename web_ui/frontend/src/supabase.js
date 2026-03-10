import { createClient } from '@supabase/supabase-js'

// AbortError in getSession(): komt uit _acquireLock → hk → setTimeout in @supabase/supabase-js.
// lock: false helpt niet; dit is een SDK-bug. RequireAuth vangt het op via .catch() → unauth → redirect.
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    lock: false,
    detectSessionInUrl: true,
    persistSession: true,
  },
})
