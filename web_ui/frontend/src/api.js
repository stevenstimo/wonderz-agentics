// Centrale API helper die de Authorization header toevoegt.
// Alle useQuery/useMutation calls gebruiken dit.

const BASE_URL = import.meta.env.VITE_API_URL || ''

export async function apiFetch(path, options = {}, session) {
  const headers = {
    'Content-Type': 'application/json',
    ...(session?.access_token
      ? { Authorization: `Bearer ${session.access_token}` }
      : {}),
    ...options.headers,
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const error = new Error(`API fout: ${response.status} ${response.statusText}`)
    error.status = response.status
    throw error
  }

  return response.json()
}
