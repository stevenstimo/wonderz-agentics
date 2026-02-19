import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://cqasccazioqjodctawzx.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNxYXNjY2F6aW9xam9kY3Rhd3p4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA4MDU0NDEsImV4cCI6MjA4NjM4MTQ0MX0.h8wkn_Tg0pEXmQppnQcRbV7Bxw1pSP_0xPqAnVxLA38'

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  realtime: { params: { eventsPerSecond: 0 } },
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
  },
})

/**
 * Safe getSession with timeout — prevents infinite hang.
 * Returns { data: { session: null } } on timeout.
 */
export async function safeGetSession(timeoutMs = 5000) {
  try {
    return await Promise.race([
      supabase.auth.getSession(),
      new Promise(resolve =>
        setTimeout(() => resolve({ data: { session: null }, error: null }), timeoutMs)
      ),
    ])
  } catch {
    return { data: { session: null }, error: null }
  }
}
