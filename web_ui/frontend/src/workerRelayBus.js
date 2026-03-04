const STORAGE_KEY = 'wonderz_worker_relay_events_v1';
const MAX_EVENTS = 120;
const EVENT_NAME = 'wonderz-worker-relay-updated';

function nowIso() {
  return new Date().toISOString();
}

function safeReadEvents() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function safeWriteEvents(events) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(events.slice(-MAX_EVENTS)));
  } catch {
    // ignore storage failures in private mode/quota reached
  }
}

export function listRelayEvents() {
  if (typeof window === 'undefined') return [];
  return safeReadEvents();
}

export function addRelayEvent(event) {
  if (typeof window === 'undefined') return;
  const enriched = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    at: nowIso(),
    ...event,
  };
  const current = safeReadEvents();
  current.push(enriched);
  safeWriteEvents(current);
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: enriched }));
}

export function subscribeRelayEvents(callback) {
  if (typeof window === 'undefined') return () => {};
  const handler = () => callback(listRelayEvents());
  window.addEventListener(EVENT_NAME, handler);
  window.addEventListener('storage', handler);
  return () => {
    window.removeEventListener(EVENT_NAME, handler);
    window.removeEventListener('storage', handler);
  };
}

