import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Building, ArrowLeft, Save, CheckCircle, XCircle, Link2, Plug } from 'lucide-react'
import { buildAuthHeaders } from './authz'
import { apiUrl } from './apiClient'

// integration_type (from client_integrations) -> platform (for client_platform_configs)
const INTEGRATION_TO_PLATFORM = {
  ga4: 'ga4',
  google_search_console: 'gsc',
  google_ads: 'google_ads',
  shopify: 'shopify',
  klaviyo: 'klaviyo',
}

const PLATFORM_LABELS = {
  ga4: 'GA4',
  gsc: 'Google Search Console',
  google_ads: 'Google Ads',
  shopify: 'Shopify',
  klaviyo: 'Klaviyo',
}

const PLATFORM_FIELDS = {
  ga4: [{ key: 'property_id', label: 'Property ID', placeholder: 'properties/123456789' }],
  gsc: [{ key: 'site_url', label: 'Site URL', placeholder: 'https://vitbliss.nl/' }],
  google_ads: [{ key: 'customer_id', label: 'Customer ID', placeholder: '123-456-7890' }],
  shopify: [{ key: 'shop_domain', label: 'Shop domain', placeholder: 'vitbliss.myshopify.com' }],
  klaviyo: [
    { key: 'account_id', label: 'Account ID', placeholder: 'AbCdEf' },
    { key: 'list_id', label: 'List ID', placeholder: 'XyZ123' },
  ],
}

const GOOGLE_PLATFORMS = ['ga4', 'gsc', 'google_ads']

export default function ClientDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [client, setClient] = useState(null)
  const [integrations, setIntegrations] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(null)
  const [error, setError] = useState('')
  const [platformForms, setPlatformForms] = useState({})

  const isIntegrationConnected = (integrationType) => {
    const found = integrations.find((i) => i.integration_type === integrationType)
    return found && (found.api_key_masked || found.extra_config?.account_id || found.extra_config?.oauth_connected || Object.keys(found.extra_config || {}).length > 0)
  }

  const handleGoogleConnect = async () => {
    setError('')
    try {
      const res = await fetch(apiUrl('/api/integrations/google/auth-url'), {
        method: 'POST',
        headers: { ...(await buildAuthHeaders()), 'Content-Type': 'application/json' },
        body: JSON.stringify({ return_to: `/clients/${slug}` }),
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

  const configuredPlatforms = integrations
    .filter((i) => isIntegrationConnected(i.integration_type))
    .map((i) => INTEGRATION_TO_PLATFORM[i.integration_type])
    .filter(Boolean)

  const allPlatforms = Object.keys(PLATFORM_LABELS)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError('')
      try {
        const headers = await buildAuthHeaders()
        const [clientRes, integrationsRes] = await Promise.all([
          fetch(apiUrl(`/api/clients/${slug}`), { headers }),
          fetch(apiUrl('/api/integrations'), { headers }),
        ])
        if (clientRes.status === 401 || integrationsRes.status === 401) {
          navigate('/login', { state: { from: location } })
          return
        }
        if (clientRes.ok && integrationsRes.ok) {
          const clientData = await clientRes.json()
          const integrationsData = await integrationsRes.json()
          setClient(clientData)
          setIntegrations(integrationsData)
          const forms = {}
          for (const pc of clientData.platform_configs || []) {
            forms[pc.platform] = { ...pc.config }
          }
          setPlatformForms(forms)
        } else if (!clientRes.ok) {
          const j = await clientRes.json().catch(() => ({}))
          setError(j.detail || 'Client niet gevonden')
        }
      } catch (err) {
        console.error('Failed to load:', err)
        setError(err.message || 'Laden mislukt')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [slug, navigate, location])

  // Refetch when returning from OAuth callback (?connected=google)
  useEffect(() => {
    const connected = searchParams.get('connected')
    if (connected === 'google') {
      setSearchParams({}, { replace: true })
      const refetch = async () => {
        try {
          const headers = await buildAuthHeaders()
          const [clientRes, integrationsRes] = await Promise.all([
            fetch(apiUrl(`/api/clients/${slug}`), { headers }),
            fetch(apiUrl('/api/integrations'), { headers }),
          ])
          if (clientRes.ok && integrationsRes.ok) {
            const [clientData, integrationsData] = await Promise.all([
              clientRes.json(),
              integrationsRes.json(),
            ])
            setClient(clientData)
            setIntegrations(integrationsData)
            const forms = {}
            for (const pc of clientData.platform_configs || []) {
              forms[pc.platform] = { ...pc.config }
            }
            setPlatformForms(forms)
          }
        } catch (_) {}
      }
      refetch()
    }
  }, [searchParams, slug])

  const getConfigForPlatform = (platform) => {
    const pc = client?.platform_configs?.find((p) => p.platform === platform)
    return pc?.config || {}
  }

  const isConfigured = (platform) => {
    const config = getConfigForPlatform(platform)
    const fields = PLATFORM_FIELDS[platform] || []
    return fields.some((f) => config[f.key])
  }

  const updateForm = (platform, key, value) => {
    setPlatformForms((prev) => ({
      ...prev,
      [platform]: { ...(prev[platform] || {}), [key]: value },
    }))
  }

  const handleSavePlatform = async (platform) => {
    setSaving(platform)
    setError('')
    try {
      const config = platformForms[platform] || {}
      const res = await fetch(apiUrl(`/api/clients/${slug}/platforms`), {
        method: 'POST',
        headers: await buildAuthHeaders(),
        body: JSON.stringify({ platform, config }),
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const clientRes = await fetch(apiUrl(`/api/clients/${slug}`), {
          headers: await buildAuthHeaders(),
        })
        if (clientRes.ok) {
          const clientData = await clientRes.json()
          setClient(clientData)
          setPlatformForms((prev) => {
            const next = { ...prev }
            next[platform] = config
            return next
          })
        }
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Opslaan mislukt')
      }
    } catch (err) {
      console.error('Failed to save:', err)
      setError(err.message || 'Opslaan mislukt')
    } finally {
      setSaving(null)
    }
  }

  const handleDeletePlatform = async (platform) => {
    if (!confirm(`Platform ${PLATFORM_LABELS[platform]} ontkoppelen?`)) return
    setSaving(platform)
    setError('')
    try {
      const res = await fetch(apiUrl(`/api/clients/${slug}/platforms/${platform}`), {
        method: 'DELETE',
        headers: await buildAuthHeaders(),
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const clientRes = await fetch(apiUrl(`/api/clients/${slug}`), {
          headers: await buildAuthHeaders(),
        })
        if (clientRes.ok) {
          setClient(await clientRes.json())
          setPlatformForms((prev) => {
            const next = { ...prev }
            delete next[platform]
            return next
          })
        }
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Verwijderen mislukt')
      }
    } catch (err) {
      console.error('Failed to delete:', err)
      setError(err.message || 'Verwijderen mislukt')
    } finally {
      setSaving(null)
    }
  }

  if (loading) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card bg-white shadow-sm border border-slate-200 p-6 rounded-xl">
          Client laden...
        </div>
      </PageLayout>
    )
  }

  if (!client) {
    return (
      <PageLayout size="narrow" padded>
        {error && (
          <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
            {error}
          </div>
        )}
        <Link to="/clients" className="text-indigo-600 hover:underline">
          Terug naar clients
        </Link>
      </PageLayout>
    )
  }

  return (
    <PageLayout size="narrow" padded>
      <Link
        to="/clients"
        className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Terug naar clients
      </Link>
      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
          {error}
        </div>
      )}

      <div className="mb-8">
        <h1 className="page-title flex items-center gap-2">
          <Building className="w-8 h-8" />
          {client.client_name}
        </h1>
        <div className="mt-3 p-4 rounded-xl bg-indigo-50 border border-indigo-100">
          <p className="text-sm text-indigo-800 font-medium mb-1">@mention voor jobs</p>
          <code className="text-lg font-mono text-indigo-900 bg-white px-2 py-1 rounded border border-indigo-200">
            @{client.slug}
          </code>
          <p className="text-xs text-indigo-600 mt-2">
            Gebruik dit in job posts om de client te adresseren
          </p>
        </div>
      </div>

      <h2 className="text-base font-semibold text-slate-800 mb-4 flex items-center gap-2">
        <Link2 className="w-5 h-5" />
        Platform koppelingen
      </h2>

      <div className="space-y-4">
        {allPlatforms.map((platform) => {
          const isGoogle = GOOGLE_PLATFORMS.includes(platform)
          const canConfigure = configuredPlatforms.includes(platform)
          const configured = isConfigured(platform)
          const form = platformForms[platform] || {}
          const fields = PLATFORM_FIELDS[platform] || []

          return (
            <div
              key={platform}
              className={`panel-card rounded-xl border p-5 ${
                canConfigure
                  ? 'bg-white border-slate-200'
                  : 'bg-slate-50 border-slate-200 opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-slate-800">{PLATFORM_LABELS[platform]}</h3>
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium ${
                    configured
                      ? 'bg-emerald-100 text-emerald-800'
                      : canConfigure
                        ? 'bg-slate-100 text-slate-600'
                        : isGoogle
                          ? 'bg-slate-100 text-slate-600'
                          : 'bg-slate-200 text-slate-500'
                  }`}
                >
                  {configured ? (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      Geconfigureerd
                    </>
                  ) : canConfigure ? (
                    <>
                      <XCircle className="w-4 h-4" />
                      Niet geconfigureerd
                    </>
                  ) : isGoogle ? (
                    <>
                      <XCircle className="w-4 h-4" />
                      Niet verbonden
                    </>
                  ) : (
                    <>Koppel eerst in Integrations</>
                  )}
                </span>
              </div>

              {isGoogle && !canConfigure && (
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={handleGoogleConnect}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition"
                  >
                    <Plug className="w-4 h-4" />
                    Verbind Google
                  </button>
                </div>
              )}

              {!isGoogle && !canConfigure && (
                <p className="text-sm text-slate-500">
                  <Link
                    to="/integrations"
                    className="text-indigo-600 hover:underline hover:text-indigo-800"
                  >
                    Configureer eerst {PLATFORM_LABELS[platform]} in Integrations
                  </Link>
                </p>
              )}

              {canConfigure && (
                <div className="space-y-3 mt-2">
                  {fields.map(({ key, label, placeholder }) => (
                    <div key={key}>
                      <label className="block text-sm font-medium text-slate-700 mb-1">
                        {label}
                      </label>
                      <input
                        type="text"
                        value={form[key] || ''}
                        onChange={(e) => updateForm(platform, key, e.target.value)}
                        placeholder={placeholder}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      />
                    </div>
                  ))}
                  <div className="flex gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => handleSavePlatform(platform)}
                      disabled={saving === platform}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Save className="w-4 h-4" />
                      {saving === platform ? 'Opslaan...' : 'Opslaan'}
                    </button>
                    {configured && (
                      <button
                        type="button"
                        onClick={() => handleDeletePlatform(platform)}
                        disabled={saving === platform}
                        className="px-4 py-2 rounded-lg border border-red-300 text-red-700 hover:bg-red-50 disabled:opacity-50"
                      >
                        Ontkoppelen
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </PageLayout>
  )
}
