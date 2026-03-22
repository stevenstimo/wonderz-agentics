import { useState, useEffect } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Plug, Save, CheckCircle, XCircle } from 'lucide-react'

import { apiUrl, apiFetch } from './apiClient'

const PLATFORMS = [
  { id: 'klaviyo', name: 'Klaviyo', connected: false, form: true, oauth: false },
  { id: 'shopify', name: 'Shopify', connected: false, form: false, oauth: false },
  { id: 'google_ads', name: 'Google Ads', connected: false, form: false, oauth: true, googleService: 'google_ads' },
  { id: 'ga4', name: 'GA4', connected: false, form: false, oauth: true, googleService: 'ga4' },
  {
    id: 'google_search_console',
    name: 'Google Search Console',
    connected: false,
    form: false,
    oauth: true,
    googleService: 'google_search_console',
  },
  {
    id: 'business_profile',
    name: 'Google Business Profile',
    description: 'Locaties, reviews en berichten (Google Maps / Business Profile API).',
    connected: false,
    form: false,
    oauth: true,
    googleService: 'business_profile',
  },
  {
    id: 'youtube',
    name: 'YouTube',
    description: 'Kanaal, video’s en YouTube Analytics (read-only).',
    connected: false,
    form: false,
    oauth: true,
    googleService: 'youtube',
  },
  {
    id: 'merchant_center',
    name: 'Google Merchant Center',
    description: 'Productfeed en accountstatus (Content API).',
    connected: false,
    form: false,
    oauth: true,
    googleService: 'merchant_center',
  },
  {
    id: 'sheets',
    name: 'Google Sheets',
    description: 'Spreadsheets lezen voor rapportages (read-only).',
    connected: false,
    form: false,
    oauth: true,
    googleService: 'sheets',
  },
  { id: 'meta_business', name: 'Meta Business', connected: false, form: false, oauth: true },
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
  const [metaClientModalOpen, setMetaClientModalOpen] = useState(false)
  const [metaConnecting, setMetaConnecting] = useState(false)
  const [clients, setClients] = useState([])
  const [metaConnectedCount, setMetaConnectedCount] = useState(0)
  const [metaConnectedClients, setMetaConnectedClients] = useState([])
  const [metaDisconnectModalOpen, setMetaDisconnectModalOpen] = useState(false)
  const [metaDisconnecting, setMetaDisconnecting] = useState(false)

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

  // Refetch when returning from OAuth callback (?connected=...)
  useEffect(() => {
    const connected = searchParams.get('connected')
    if (!connected) return
    setSearchParams({}, { replace: true })
    const refetch = async () => {
      try {
        const res = await apiFetch('/api/integrations', {})
        if (res.ok) {
          const data = await res.json()
          setIntegrations(data)
        }
      } catch (_) {}
    }
    refetch()
  }, [searchParams])

  // meta_error from URL (e.g. redirect from failed Meta callback)
  useEffect(() => {
    const metaError = searchParams.get('meta_error')
    if (!metaError) return
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('meta_error')
      return next
    }, { replace: true })
    const messages = {
      auth_failed: 'Meta OAuth mislukt of geannuleerd.',
      invalid_state: 'Beveiligingscheck mislukt. Probeer opnieuw.',
      token_exchange: 'Kon geen tokens ophalen van Meta. Probeer opnieuw.',
      client_not_found: 'Client niet gevonden.',
      config: 'Meta app niet geconfigureerd op de server.',
    }
    setError(messages[metaError] || `Meta verbinding mislukt (${metaError})`)
  }, [searchParams])

  // Meta connected count when page is ready (clients + per-client integrations with meta_ads)
  useEffect(() => {
    if (loading) return
    const run = async () => {
      try {
        const res = await apiFetch('/api/clients')
        if (!res.ok) return
        const clientList = await res.json()
        if (!clientList?.length) {
          setMetaConnectedCount(0)
          setMetaConnectedClients([])
          return
        }
        const withMeta = []
        for (const c of clientList) {
          const ir = await apiFetch(`/api/integrations?client_slug=${encodeURIComponent(c.slug)}`)
          if (!ir.ok) continue
          const list = await ir.json()
          const meta = list.find((i) => i.integration_type === 'meta_ads' && i.extra_config?.oauth_connected)
          if (meta) withMeta.push({ slug: c.slug, client_name: c.client_name || c.slug })
        }
        setMetaConnectedCount(withMeta.length)
        setMetaConnectedClients(withMeta)
      } catch (_) {}
    }
    run()
  }, [loading])

  const isConnected = (platformId) => {
    const found = integrations.find((i) => i.integration_type === platformId)
    return found && (found.api_key_masked || found.extra_config?.account_id || found.extra_config?.oauth_connected)
  }

  const handleMetaConnect = async (selectedSlug) => {
    if (!selectedSlug) return
    setError('')
    setMetaConnecting(true)
    try {
      const res = await apiFetch(`/api/clients/${selectedSlug}/meta/auth-url`)
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Kon auth URL niet ophalen')
        return
      }
      const data = await res.json()
      if (data.auth_url) {
        window.location.href = data.auth_url
      } else {
        console.error('Geen auth_url ontvangen:', data)
        setError('Geen auth URL ontvangen')
      }
    } catch (err) {
      console.error('Meta connect fout:', err)
      setError(err?.message || 'Verbinden mislukt')
    } finally {
      setMetaConnecting(false)
    }
  }

  const openMetaConnectFlow = async () => {
    setError('')
    setMetaConnecting(true)
    try {
      const res = await apiFetch('/api/clients')
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (!res.ok) {
        setError('Kon clients niet laden')
        return
      }
      const list = await res.json()
      if (!list?.length) {
        setError('Maak eerst een client aan.')
        return
      }
      if (list.length === 1) {
        await handleMetaConnect(list[0].slug)
        return
      }
      setClients(list)
      setMetaClientModalOpen(true)
    } catch (err) {
      setError(err?.message || 'Laden mislukt')
    } finally {
      setMetaConnecting(false)
    }
  }

  const handleGoogleConnect = async (serviceType) => {
    if (!serviceType) return
    setError('')
    try {
      const res = await apiFetch('/api/integrations/google/auth-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service_type: serviceType }),
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

  const handleGoogleDisconnect = async (serviceType) => {
    if (!serviceType) return
    if (!confirm('Google-verbinding voor dit platform verbreken?')) return
    setError('')
    try {
      const res = await apiFetch(`/api/integrations/${encodeURIComponent(serviceType)}`, {
        method: 'DELETE',
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Ontkoppelen mislukt')
        return
      }
      const listRes = await apiFetch('/api/integrations', {})
      if (listRes.ok) setIntegrations(await listRes.json())
    } catch (err) {
      setError(err.message || 'Ontkoppelen mislukt')
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
          const isMeta = platform.id === 'meta_business'
          const connected = isMeta ? metaConnectedCount > 0 : isConnected(platform.id)
          const klaviyoData = integrations.find((i) => i.integration_type === 'klaviyo')

          return (
            <div
              key={platform.id}
              className="panel-card flex flex-col"
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-slate-800">{platform.name}</h3>
                  {platform.description && (
                    <p className="text-sm text-slate-500 mt-1">{platform.description}</p>
                  )}
                </div>
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
                      {isMeta ? `Connected (${metaConnectedCount} ${metaConnectedCount === 1 ? 'client' : 'clients'})` : 'Connected'}
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

              {platform.oauth && platform.googleService && !connected && (
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={() => handleGoogleConnect(platform.googleService)}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition"
                  >
                    <Plug className="w-4 h-4" />
                    Verbinden
                  </button>
                </div>
              )}

              {platform.oauth && platform.googleService && connected && (
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={() => handleGoogleDisconnect(platform.googleService)}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-red-200 text-red-700 bg-white hover:bg-red-50 transition"
                  >
                    Verbreek verbinding
                  </button>
                </div>
              )}

              {platform.id === 'meta_business' && !metaConnectedCount && (
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={openMetaConnectFlow}
                    disabled={metaConnecting}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition disabled:opacity-50"
                  >
                    <Plug className="w-4 h-4" />
                    {metaConnecting ? 'Bezig...' : 'Verbinden'}
                  </button>
                </div>
              )}

              {platform.id === 'meta_business' && metaConnectedCount > 0 && (
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={() => setMetaDisconnectModalOpen(true)}
                    disabled={metaDisconnecting}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-red-200 text-red-700 bg-white hover:bg-red-50 transition disabled:opacity-50"
                  >
                    {metaDisconnecting ? 'Bezig...' : 'Verbreek verbinding'}
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

      {metaClientModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-slate-800 mb-2">Kies een client voor Meta</h3>
            <p className="text-sm text-slate-500 mb-4">Meta wordt per client gekoppeld. Selecteer de client waarvoor je wilt verbinden.</p>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {clients.map((c) => (
                <button
                  key={c.slug}
                  type="button"
                  onClick={() => {
                    setMetaClientModalOpen(false)
                    handleMetaConnect(c.slug)
                  }}
                  className="w-full text-left px-4 py-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 font-medium text-slate-800"
                >
                  {c.client_name || c.slug}
                </button>
              ))}
            </div>
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() => setMetaClientModalOpen(false)}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Annuleren
              </button>
            </div>
          </div>
        </div>
      )}

      {metaDisconnectModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-slate-800 mb-2">Verbreek Meta-verbinding</h3>
            <p className="text-sm text-slate-500 mb-4">Kies de client waarvoor je de Meta-koppeling wilt verbreken.</p>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {metaConnectedClients.map((c) => (
                <button
                  key={c.slug}
                  type="button"
                  onClick={async () => {
                    setMetaDisconnecting(true)
                    setError('')
                    try {
                      const res = await apiFetch(
                        `/api/integrations/meta_ads?client_slug=${encodeURIComponent(c.slug)}`,
                        { method: 'DELETE' }
                      )
                      if (res.ok) {
                        setMetaDisconnectModalOpen(false)
                        const withMeta = metaConnectedClients.filter((x) => x.slug !== c.slug)
                        setMetaConnectedCount(withMeta.length)
                        setMetaConnectedClients(withMeta)
                      } else {
                        const j = await res.json().catch(() => ({}))
                        setError(j.detail || 'Ontkoppelen mislukt')
                      }
                    } catch (err) {
                      setError(err?.message || 'Ontkoppelen mislukt')
                    } finally {
                      setMetaDisconnecting(false)
                    }
                  }}
                  disabled={metaDisconnecting}
                  className="w-full text-left px-4 py-2.5 rounded-lg border border-red-200 text-red-700 hover:bg-red-50 font-medium disabled:opacity-50"
                >
                  {c.client_name || c.slug}
                </button>
              ))}
            </div>
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() => setMetaDisconnectModalOpen(false)}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Sluiten
              </button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
