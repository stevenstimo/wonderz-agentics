/**
 * GoogleIntegrationsStatus.jsx
 * Toont de status van alle Google-integraties.
 * Groen = actief (env var gezet), Grijs = niet gekoppeld, Geel = per klant (OAuth).
 */
import { useState, useEffect } from 'react'
import { useAuthReady } from '../../useAuthReady'
import { apiFetch } from '../../apiClient'

const INTEGRATION_LABELS = {
  pagespeed: 'PageSpeed Insights',
  crux: 'Chrome UX Report',
  natural_language: 'Natural Language',
  indexing: 'Indexing API',
  knowledge_graph: 'Knowledge Graph',
  translate: 'Translate',
  business_profile: 'Business Profile (per klant)',
  youtube: 'YouTube',
  merchant_center: 'Merchant Center',
  sheets: 'Google Sheets',
}

export default function GoogleIntegrationsStatus() {
  const { authReady, session } = useAuthReady()
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!authReady) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await apiFetch('/api/integrations/google/status')
        const data = await res.json()
        if (!cancelled) setStatus(data.status)
      } catch (_) {
        if (!cancelled) setStatus(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [authReady, session])

  if (loading) return <p className="text-sm text-gray-400">Laden...</p>
  if (!status) return null

  return (
    <div className="grid grid-cols-2 gap-2">
      {Object.entries(status).map(([key, enabled]) => (
        <div key={key} className="flex items-center gap-2 p-2 rounded bg-gray-800">
          <span
            className={`w-2 h-2 rounded-full flex-shrink-0 ${
              enabled === true
                ? 'bg-green-400'
                : enabled === false
                  ? 'bg-gray-500'
                  : 'bg-yellow-400'
            }`}
          />
          <span className="text-xs text-gray-300">{INTEGRATION_LABELS[key] || key}</span>
          <span className="ml-auto text-xs text-gray-500">
            {enabled === true ? 'Actief' : enabled === false ? 'Inactief' : 'Per klant'}
          </span>
        </div>
      ))}
    </div>
  )
}
