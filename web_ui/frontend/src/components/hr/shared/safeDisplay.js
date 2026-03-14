/**
 * Coerce any value to a React-safe display value (string or number).
 * Prevents "Objects are not valid as a React child" (minified error #31)
 * when API returns objects or double-encoded values.
 */
export function safeDisplay(value) {
  if (value == null) return '—'
  if (typeof value === 'object') return '—'
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return String(value)
}
