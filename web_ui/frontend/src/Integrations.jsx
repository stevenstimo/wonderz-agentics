import { useState, useEffect } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Plug, Save, CheckCircle, XCircle } from 'lucide-react'

import { apiUrl, apiFetch } from './apiClient'

const PLATFORMS = [
  { id: 'klaviyo', name: 'Klaviyo', connected: false, form: true, oauth: false },
  { id: 'shopify', name: 'Shopify', connected: false, form: false, oauth: false },
  { id: 'google_ads', name: 'Google Ads', connected: false, form: false, oauth: true },
  { id: 'ga4', name: 'GA4', connected: false, form: false, oauth: true },
  { id: 'google_search_console', name: 'Google Search Console', connected: false, form: false, oauth: true },
  { id: 'meta_business', name: 'Meta Business', connected: false, form: false, oauth: false },
  { id: 'pinterest', name: 'Pinterest', connected: false, form: false, oauth: false },
]

export default function Integrations() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [integrations, setIntegrations] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [klaviyoForm, setKlaviyoForm] = useState({ api_key: '', account_id: '' })

  useEffect(() => {
    const fetchIntegrations = async () => {
      setLoading(true)
      setError('')
      try {
        const res = await apiFetch('/api/integrations', {
        })
        if (res.status === 401) {
          navigate('/login', { state: { from: location } })
          return
        }
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
        setError(err.message || 'Laden mislukt')
      } finally {
        setLoading(false)
      }
    }
    fetchIntegrations()
  }, [navigate, location])

  // Refetch when returning from OAuth callback (?connected=google)
  useEffect(() => {
    const connected = searchParams.get('connected')
    if (connected === 'google') {
      setSearchParams({}, { replace: true })
      const refetch = async () => {
        try {
          const res = await apiFetch('/api/integrations', {
          })
          if (res.ok) {
            const data = await res.json()
            setIntegrations(data)
          }
        } catch (_) {}
      }
      refetch()
    }
  }, [searchParams])

  const isConnected = (platformId) => {
    const found = integrations.find((i) => i.integration_type === platformId)
    return found && (found.api_key_masked || found.extra_config?.account_id || found.extra_config?.oauth_connected)
  }

  const handleGoogleConnect = async () => {
    setError('')
    try {
      const res = await apiFetch('/api/integrations/google/auth-url', {
        method: 'POST',
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Kon auth URL niet ophalen')
        return
      }
      const { url } = await res.json()
      if (url) {
        window.location.href = url
      }
    } catch (err) {
      console.error('Google connect failed:', err)
      setError(err.message || 'Verbinden mislukt')
    }
  }

  const handleKlaviyoSave = async () => {
    setSaving(true)
    setError('')
    try {
      const body = {}
      if (klaviyoForm.api_key) body.api_key = klaviyoForm.api_key
      if (klaviyoForm.account_id) body.extra_config = { account_id: klaviyoForm.account_id }
      const res = await apiFetch('/api/integrations/klaviyo', {
        method: 'PUT',
        body: JSON.stringify(body),
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const listRes = await apiFetch('/api/integrations', {
        })
        if (listRes.ok) {
          setIntegrations(await listRes.json())
        }
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Opslaan mislukt')
      }
    } catch (err) {
      console.error('Failed to save Klaviyo:', err)
      setError(err.message || 'Opslaan mislukt')
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
      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
          {error}
        </div>
      )}
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

              {platform.oauth && !connected && (
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={handleGoogleConnect}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition"
                  >
                    <Plug className="w-4 h-4" />
                    Verbinden
                  </button>
                </div>
              )}

              {!platform.form && !platform.oauth && (
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
