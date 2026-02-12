import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://cqasccazioqjodctawzx.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNxYXNjY2F6aW9xam9kY3Rhd3p4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA4MDU0NDEsImV4cCI6MjA4NjM4MTQ0MX0.h8wkn_Tg0pEXmQppnQcRbV7Bxw1pSP_0xPqAnVxLA38'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

