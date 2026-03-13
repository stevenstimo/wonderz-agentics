import { supabase } from './supabase'

export const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export function apiUrl(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`
  const base = API_BASE || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}${normalized}`
}

// Korte cache voor access token om lock-contention met Supabase Gotrue te verminderen
const SESSION_CACHE_MS = 20_000
let cachedToken = null
let cachedAt = 0

/** Get current Supabase access token (cached). Used by apiFetch and by callers that need to send auth with FormData etc. */
export async function getAccessToken() {
  if (cachedToken && Date.now() - cachedAt < SESSION_CACHE_MS) return cachedToken
  try {
    const result = await supabase.auth.getSession()
    const token = result?.data?.session?.access_token ?? null
    cachedToken = token
    cachedAt = Date.now()
    return token
  } catch (_) {
    return cachedToken
  }
}

// Centrale auth fetch — injecteert automatisch de Bearer token
export async function apiFetch(path, options = {}) {
  const token = await getAccessToken()
  const { headers: extraHeaders, body, ...rest } = options
  const headers = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(extraHeaders || {}),
  }
  // Ensure JSON body is sent with correct Content-Type so backend parses it
  if (body !== undefined && typeof body === 'string' && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  return fetch(apiUrl(path), { ...rest, body, headers })
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
