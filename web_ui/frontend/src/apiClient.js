import { supabase } from './supabase'

export const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')

export function apiUrl(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`
  const base = API_BASE || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}${normalized}`
}

// Centrale auth fetch — injecteert altijd automatisch de Bearer token
export async function apiFetch(path, options = {}) {
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token
  const { headers: extraHeaders, ...rest } = options
  const headers = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(extraHeaders || {}),
  }
  // #region agent log
  if (path.includes('env-vars')) {
    fetch('http://localhost:7847/ingest/23ca0604-c25a-4b22-97c6-80c0acce04c4', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '4539c6' }, body: JSON.stringify({ sessionId: '4539c6', location: 'apiClient.js:apiFetch', message: 'env-vars request', data: { path, hasToken: !!token, authHeaderSent: !!headers.Authorization, tokenLen: token ? token.length : 0 }, timestamp: Date.now(), hypothesisId: 'H1' }) }).catch(() => {});
  }
  // #endregion
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
