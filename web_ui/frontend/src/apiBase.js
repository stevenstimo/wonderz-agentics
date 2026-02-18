/**
 * Dynamically resolve the backend API base URL.
 * - If accessed via wonderz-agentic.exe.xyz → use https://wonderz-agentic.exe.xyz:8090
 * - If accessed via localhost → use http://localhost:8090
 * - VITE_API_URL env var always wins if set.
 */
const _env = import.meta.env.VITE_API_URL;
let _base;
if (_env) {
  _base = _env.replace(/\/$/, '');
} else if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') {
  _base = `${window.location.protocol}//${window.location.hostname}:8090`;
} else {
  _base = 'http://localhost:8090';
}

export const apiBase = _base;

// WebSocket base (same host, ws(s) protocol)
export const wsBase = _base.replace(/^http/, 'ws');
