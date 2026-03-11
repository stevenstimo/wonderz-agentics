import { supabase } from './supabase'

export const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')

// #region agent log
console.log('[DBG-4f273a] API_BASE =', API_BASE, '| VITE_API_URL =', import.meta.env.VITE_API_URL)
// #endregion

export function apiUrl(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`
  const base = API_BASE || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}${normalized}`
}

export async function apiFetch(path, options = {}) {
  const url = apiUrl(path)
  // #region agent log
  console.log('[DBG-4f273a] apiFetch', path, '→', url)
  // #endregion
  let token = null
  try {
    const { data: { session } } = await supabase.auth.getSession()
    token = session?.access_token
    // #region agent log
    console.log('[DBG-4f273a] session ok, hasToken:', !!token)
    // #endregion
  } catch (e) {
    // #region agent log
    console.error('[DBG-4f273a] getSession FAILED:', e?.message)
    // #endregion
  }
  const { headers: extraHeaders, ...rest } = options
  const headers = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(extraHeaders || {}),
  }
  try {
    const res = await fetch(url, { ...rest, headers })
    // #region agent log
    console.log('[DBG-4f273a] fetch done', path, 'status:', res.status, 'ok:', res.ok)
    // #endregion
    return res
  } catch (fetchErr) {
    // #region agent log
    console.error('[DBG-4f273a] fetch NETWORK ERROR', path, fetchErr?.message)
    // #endregion
    throw fetchErr
  }
}

// JSON helper met auth
export async function fetchJson(path, options = {}) {
  const res = await apiFetch(path, options)
  const contentType = (res.headers.get('content-type') || '').toLowerCase()
  const raw = await res.text()
  let parsed = null
  if (raw.length > 0 && contentType.includes('application/json')) {
    try { parsed = JSON.parse(raw) } catch (_) {
      throw new Error(`Invalid JSON from ${path}`)
    }
  }
  if (!res.ok) {
    const detail = parsed?.detail || parsed?.error || parsed?.message
    throw new Error(detail || `Request failed (${res.status}) for ${path}`)
  }
  return parsed
}

// Backward compat alias
export const fetchJsonStrict = fetchJson
