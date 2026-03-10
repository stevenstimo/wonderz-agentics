import { useState, useEffect } from 'react'
import PageLayout from './PageLayout'
import { Plug, Save, CheckCircle, XCircle } from 'lucide-react'
import { buildAuthHeaders } from './authz'

const apiBase = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')

const PLATFORMS = [
  { id: 'klaviyo', name: 'Klaviyo', connected: false, form: true },
  { id: 'shopify', name: 'Shopify', connected: false, form: false },
  { id: 'google_ads', name: 'Google Ads', connected: false, form: false },
  { id: 'ga4', name: 'GA4', connected: false, form: false },
  { id: 'google_search_console', name: 'Google Search Console', connected: false, form: false },
  { id: 'meta_business', name: 'Meta Business', connected: false, form: false },
  { id: 'pinterest', name: 'Pinterest', connected: false, form: false },
]

export default function Integrations() {
  const [integrations, setIntegrations] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [klaviyoForm, setKlaviyoForm] = useState({ api_key: '', account_id: '' })

  useEffect(() => {
    const fetchIntegrations = async () => {
      setLoading(true)
      try {
        const res = await fetch(`${apiBase}/api/integrations`, {
          headers: await buildAuthHeaders(),
        })
        if (res.ok) {
          const data = await res.json()
          setIntegrations(data)
          const klaviyo = data.find((i) => i.integration_type === 'klaviyo')
          if (klaviyo?.extra_config?.account_id) {
            setKlaviyoForm((prev) => ({ ...prev, account_id: klaviyo.extra_config.account_id }))
          }
        }
      } catch (err) {
        console.error('Failed to load integrations:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchIntegrations()
  }, [])

  const isConnected = (platformId) => {
    const found = integrations.find((i) => i.integration_type === platformId)
    return found && (found.api_key_masked || found.extra_config?.account_id)
  }

  const handleKlaviyoSave = async () => {
    setSaving(true)
    try {
      const body = {}
      if (klaviyoForm.api_key) body.api_key = klaviyoForm.api_key
      if (klaviyoForm.account_id) body.extra_config = { account_id: klaviyoForm.account_id }
      const res = await fetch(`${apiBase}/api/integrations/klaviyo`, {
        method: 'PUT',
        headers: await buildAuthHeaders(),
        body: JSON.stringify(body),
      })
      if (res.ok) {
        const listRes = await fetch(`${apiBase}/api/integrations`, {
          headers: await buildAuthHeaders(),
        })
        if (listRes.ok) {
          setIntegrations(await listRes.json())
        }
      }
    } catch (err) {
      console.error('Failed to save Klaviyo:', err)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card">Integraties laden...</div>
      </PageLayout>
    )
  }

  return (
    <PageLayout size="narrow" padded>
      <h1 className="page-title flex items-center gap-2">
        <Plug className="w-8 h-8" />
        Integraties
      </h1>
      <p className="page-subtitle mb-8">
        Verbind je marketing- en verkoopplatforms. Per platform kun je credentials opslaan.
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        {PLATFORMS.map((platform) => {
          const connected = isConnected(platform.id)
          const klaviyoData = integrations.find((i) => i.integration_type === 'klaviyo')

          return (
            <div
              key={platform.id}
              className="panel-card flex flex-col"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-slate-800">{platform.name}</h3>
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium ${
                    connected
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {connected ? (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      Connected
                    </>
                  ) : (
                    <>
                      <XCircle className="w-4 h-4" />
                      Not connected
                    </>
                  )}
                </span>
              </div>

              {platform.id === 'klaviyo' && platform.form && (
                <div className="space-y-3 mt-2">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      API Key
                    </label>
                    <input
                      type="password"
                      value={klaviyoForm.api_key}
                      onChange={(e) =>
                        setKlaviyoForm((prev) => ({ ...prev, api_key: e.target.value }))
                      }
                      placeholder="pk_..."
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Account ID
                    </label>
                    <input
                      type="text"
                      value={klaviyoForm.account_id}
                      onChange={(e) =>
                        setKlaviyoForm((prev) => ({ ...prev, account_id: e.target.value }))
                      }
                      placeholder="Account ID"
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleKlaviyoSave}
                    disabled={saving || (!klaviyoData && !klaviyoForm.api_key && !klaviyoForm.account_id)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Save className="w-4 h-4" />
                    {saving ? 'Opslaan...' : 'Opslaan'}
                  </button>
                </div>
              )}

              {platform.id !== 'klaviyo' && (
                <p className="text-sm text-slate-500 mt-2">
                  Binnenkort beschikbaar.
                </p>
              )}
            </div>
          )
        })}
      </div>
    </PageLayout>
  )
}
