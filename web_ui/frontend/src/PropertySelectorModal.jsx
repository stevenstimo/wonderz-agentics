import { useState, useEffect } from 'react'
import { apiFetch } from './apiClient'

const SERVICE_CONFIG = {
  ga4: {
    label: 'GA4 Property',
    endpoint: (slug) => `/api/clients/${slug}/google/ga4-properties`,
    optionLabel: (opt) => {
      const name = opt.display_name && opt.display_name !== opt.property_id ? opt.display_name : `Property ${opt.property_id}`;
      return `${name} (${opt.property_id})`;
    },
    optionValue: (opt) => opt.property_id,
    configKey: 'property_id',
  },
  google_search_console: {
    label: 'Search Console Site',
    endpoint: (slug) => `/api/clients/${slug}/google/gsc-sites`,
    optionLabel: (opt) => opt.site_url,
    optionValue: (opt) => opt.site_url,
    configKey: 'site_url',
  },
  google_ads: {
    label: 'Google Ads Account',
    endpoint: (slug) => `/api/clients/${slug}/google/ads-accounts`,
    optionLabel: (opt) => {
      const id = opt.id ?? opt.customer_id ?? '';
      const name = (opt.descriptive_name || opt.name) && (opt.descriptive_name || opt.name) !== id ? (opt.descriptive_name || opt.name) : id;
      return name ? `${name} (${id})` : String(id);
    },
    optionValue: (opt) => opt.customer_id,
    configKey: 'customer_id',
  },
}

export function PropertySelectorModal({ slug, serviceType, onSaved, onClose }) {
  const [options, setOptions] = useState([])
  const [selected, setSelected] = useState('')
  const [loginCustomerId, setLoginCustomerId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const config = SERVICE_CONFIG[serviceType]

  useEffect(() => {
    const cfg = SERVICE_CONFIG[serviceType]
    if (!cfg || !slug) return
    setLoading(true)
    setError(null)
    apiFetch(cfg.endpoint(slug))
      .then((res) => res.json())
      .then((data) => {
        const list = data?.accounts ?? (Array.isArray(data) ? data : [])
        setOptions(list)
        if (serviceType === 'google_ads') setLoginCustomerId(data?.login_customer_id ?? null)
        else setLoginCustomerId(null)
        if (list.length === 1) setSelected(cfg.optionValue(list[0]))
      })
      .catch(() => setError('Kon opties niet laden.'))
      .finally(() => setLoading(false))
  }, [slug, serviceType])

  const handleSave = async () => {
    if (!selected || !config) return
    setSaving(true)
    setError(null)
    const body = { [config.configKey]: selected }
    if (serviceType === 'google_ads') {
      const chosen = options.find((o) => (config.optionValue(o) || '').toString() === (selected || '').toString())
      body.login_customer_id = chosen?.login_customer_id ?? loginCustomerId ?? undefined
      if (body.login_customer_id === undefined) delete body.login_customer_id
    }
    try {
      const res = await apiFetch(
        `/api/clients/${slug}/integrations/${serviceType}/config`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      )
      if (!res.ok) throw new Error('Opslaan mislukt')
      onSaved(selected)
    } catch {
      setError('Opslaan mislukt.')
    } finally {
      setSaving(false)
    }
  }

  if (!config) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold mb-1">Selecteer {config.label}</h2>
        <p className="text-sm text-gray-500 mb-4">
          Kies welke {config.label.toLowerCase()} je wilt koppelen aan deze client.
        </p>

        {loading && <p className="text-sm text-gray-400">Laden...</p>}
        {error && <p className="text-sm text-red-500 mb-4">{error}</p>}

        {!loading && !error && (
          <select
            className="w-full border rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            <option value="">— Selecteer een optie —</option>
            {options.map((opt) => (
              <option key={config.optionValue(opt)} value={config.optionValue(opt)}>
                {config.optionLabel(opt)}
              </option>
            ))}
          </select>
        )}

        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border hover:bg-gray-50"
          >
            Annuleren
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={!selected || saving}
            className="px-4 py-2 text-sm rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? 'Opslaan...' : 'Opslaan'}
          </button>
        </div>
      </div>
    </div>
  )
}
