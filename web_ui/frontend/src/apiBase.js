/**
 * API base URL.
 * 
 * Vite proxies /api/* and /ws/* to the backend (localhost:8090).
 * So the frontend just uses relative paths — no cross-origin, no port issues.
 * VITE_API_URL env var overrides if set (for non-Vite contexts).
 */
const _env = import.meta.env.VITE_API_URL;
export const apiBase = _env ? _env.replace(/\/$/, '') : '';
export const wsBase = _env
  ? _env.replace(/^http/, 'ws').replace(/\/$/, '')
  : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
