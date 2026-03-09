export const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')

export function apiUrl(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`
  const base = API_BASE || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}${normalized}`
}

export async function fetchJsonStrict(path, options = {}) {
  const res = await fetch(apiUrl(path), options)
  const contentType = (res.headers.get('content-type') || '').toLowerCase()
  const raw = await res.text()

  let parsed = null
  if (raw.length > 0 && contentType.includes('application/json')) {
    try {
      parsed = JSON.parse(raw)
    } catch (_err) {
      throw new Error(`Invalid JSON response from ${apiUrl(path)}`)
    }
  }

  if (!res.ok) {
    const detail = parsed?.detail || parsed?.error || parsed?.message
    throw new Error(detail || `Request failed (${res.status}) for ${apiUrl(path)}`)
  }

  if (raw.length > 0 && !contentType.includes('application/json')) {
    throw new Error(`Expected JSON but got ${contentType || 'unknown'} from ${apiUrl(path)}`)
  }

  return parsed
}
