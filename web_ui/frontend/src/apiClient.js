import { supabase } from './supabase'

export const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export function apiUrl(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`
  const base = API_BASE || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}${normalized}`
}

// Centrale auth fetch — injecteert automatisch de Bearer token
export async function apiFetch(path, options = {}) {
  let session = null
  try {
    const result = await supabase.auth.getSession()
    session = result?.data?.session
  } catch (_) {
    // auth unavailable — proceed without token
  }
  const token = session?.access_token
  const { headers: extraHeaders, ...rest } = options
  const headers = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(extraHeaders || {}),
  }
  return fetch(apiUrl(path), { ...rest, headers })
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
