import { supabase, safeGetSession } from './supabase'

export const DEFAULT_ROLE = 'member'
export const SUPER_ADMIN_EMAIL = 'stevenstimo@gmail.com'

export function extractRole(user) {
  const metadataRole =
    user?.app_metadata?.role ||
    user?.user_metadata?.role ||
    user?.user_metadata?.app_role ||
    DEFAULT_ROLE

  const email = String(user?.email || '').toLowerCase()
  if (email === SUPER_ADMIN_EMAIL) {
    return 'super_admin'
  }

  return String(metadataRole).toLowerCase()
}

export async function getCurrentSessionUser() {
  const { data } = await safeGetSession()
  return data?.session?.user || null
}

export async function getAccessToken() {
  // Try with longer timeout for token retrieval
  const { data } = await safeGetSession(8000)
  if (data?.session?.access_token) return data.session.access_token
  // Retry once with direct call (no timeout wrapper)
  try {
    const { data: d2 } = await supabase.auth.getSession()
    return d2?.session?.access_token || null
  } catch {
    return null
  }
}

export async function buildAuthHeaders(extraHeaders = {}) {
  const token = await getAccessToken()
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extraHeaders,
  }
}

export async function getCurrentUserRole() {
  const user = await getCurrentSessionUser()
  if (!user?.id) {
    return { user: null, role: DEFAULT_ROLE }
  }

  const email = String(user.email || '').toLowerCase()
  if (email === SUPER_ADMIN_EMAIL) {
    return { user, role: 'super_admin' }
  }

  const { data, error } = await supabase
    .from('user_roles')
    .select('role')
    .eq('user_id', user.id)
    .maybeSingle()

  if (error) {
    return { user, role: extractRole(user) || DEFAULT_ROLE }
  }

  return { user, role: data?.role || extractRole(user) || DEFAULT_ROLE }
}

export function isAdmin(role) {
  return role === 'admin' || role === 'super_admin'
}

export function isSuperAdmin(role) {
  return role === 'super_admin'
}
