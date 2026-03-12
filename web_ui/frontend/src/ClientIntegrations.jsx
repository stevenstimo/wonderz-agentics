import { useState, useEffect, useCallback } from 'react'
import { useParams, Link, useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { Save, CheckCircle, XCircle, Link2, Plug } from 'lucide-react'
import { apiFetch } from './apiClient'
import { PropertySelectorModal } from './PropertySelectorModal'
import { useAuthReady } from './useAuthReady'

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

const GOOGLE_DROPDOWN_CONFIG = {
  ga4: {
    endpoint: 'ga4-properties',
    valueKey: 'property_id',
    labelKey: 'display_name',
    configKey: 'property_id',
    description: 'Traffic data',
    optionLabel: (opt) => {
      const name = opt.display_name && opt.display_name !== opt.property_id ? opt.display_name : `Property ${opt.property_id}`
      return `${name} (${opt.property_id})`
    },
  },
  gsc: {
    endpoint: 'gsc-sites',
    valueKey: 'site_url',
    labelKey: 'site_url',
    configKey: 'site_url',
    description: 'Search performance',
  },
  google_ads: {
    endpoint: 'ads-accounts',
    valueKey: 'customer_id',
    labelKey: 'descriptive_name',
    configKey: 'customer_id',
    description: 'Campaign data',
    optionLabel: (opt) => {
      const id = opt.id ?? opt.customer_id ?? ''
      const name = (opt.descriptive_name || opt.name) && (opt.descriptive_name || opt.name) !== id ? (opt.descriptive_name || opt.name) : id
      return name ? `${name} (${id})` : String(id)
    },
  },
}

const PLATFORM_FIELDS = {
  ga4: [],
  gsc: [],
  google_ads: [],
  shopify: [{ key: 'shop_domain', label: 'Shop domain', placeholder: 'vitbliss.myshopify.com' }],
  klaviyo: [
    { key: 'account_id', label: 'Account ID', placeholder: 'AbCdEf' },
    { key: 'list_id', label: 'List ID', placeholder: 'XyZ123' },
  ],
}

const GOOGLE_PLATFORMS = ['ga4', 'gsc', 'google_ads']

// Platform (frontend) -> service_type / integration_type (backend API)
const PLATFORM_TO_SERVICE_TYPE = {
  ga4: 'ga4',
  gsc: 'google_search_console',
  google_ads: 'google_ads',
}

export default function ClientIntegrations() {
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
  const [googleOptions, setGoogleOptions] = useState({ ga4: [], google_ads: [], gsc: [] })
  const [googleLoading, setGoogleLoading] = useState({ ga4: false, google_ads: false, gsc: false })
  const [googleError, setGoogleError] = useState({ ga4: null, google_ads: null, gsc: null })
  const [connecting, setConnecting] = useState(null)
  const [selectorModal, setSelectorModal] = useState(null)
  const authReady = useAuthReady()

  const isIntegrationConnected = (integrationType) => {
    const found = integrations.find((i) => i.integration_type === integrationType)
    return found && (found.api_key_masked || found.extra_config?.account_id || found.extra_config?.oauth_connected || Object.keys(found.extra_config || {}).length > 0)
  }

  const getIntegrationType = (platform) => PLATFORM_TO_SERVICE_TYPE[platform] || platform

  const isPlatformConnected = (platform) => isIntegrationConnected(getIntegrationType(platform))

  const getIntegrationForPlatform = (platform) =>
    integrations.find((i) => i.integration_type === getIntegrationType(platform))

  const handleGoogleConnect = async (platform) => {
    const serviceType = PLATFORM_TO_SERVICE_TYPE[platform]
    if (!serviceType) return
    setConnecting(platform)
    setError('')
    try {
      const res = await apiFetch('/api/integrations/google/auth-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_slug: slug,
          return_to: `/clients/${slug}/integrations`,
          service_type: serviceType,
        }),
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
    } finally {
      setConnecting(null)
    }
  }

  const configuredPlatforms = integrations
    .filter((i) => isIntegrationConnected(i.integration_type))
    .map((i) => INTEGRATION_TO_PLATFORM[i.integration_type])
    .filter(Boolean)

  const allPlatforms = Object.keys(PLATFORM_LABELS)

  const fetchGoogleOptions = useCallback(async (platform, _retried = false) => {
    const cfg = GOOGLE_DROPDOWN_CONFIG[platform]
    if (!cfg) return Promise.resolve()
    setGoogleLoading((prev) => ({ ...prev, [platform]: true }))
    setGoogleError((prev) => ({ ...prev, [platform]: null }))
    try {
      const res = await apiFetch(`/api/clients/${slug}/google/${cfg.endpoint}`)
      if (res.status === 401) {
        const body = await res.json().catch(() => ({}))
        if (body.detail === 'token_expired' && !_retried) {
          const refreshRes = await apiFetch('/api/integrations/google/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_slug: slug, service_type: PLATFORM_TO_SERVICE_TYPE[platform] }),
          })
          const refreshData = await refreshRes.json().catch(() => ({}))
          if (refreshData.ok) {
            setGoogleLoading((prev) => ({ ...prev, [platform]: false }))
            return fetchGoogleOptions(platform, true)
          }
        }
        setGoogleError((prev) => ({ ...prev, [platform]: 'token_expired' }))
        return
      }
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        setGoogleError((prev) => ({ ...prev, [platform]: j.detail || 'Laden mislukt' }))
        return
      }
      const data = await res.json()
      const list = data?.accounts ?? (Array.isArray(data) ? data : [])
      setGoogleOptions((prev) => ({ ...prev, [platform]: list }))
    } catch (err) {
      setGoogleError((prev) => ({ ...prev, [platform]: err.message || 'Laden mislukt' }))
    } finally {
      setGoogleLoading((prev) => ({ ...prev, [platform]: false }))
    }
  }, [slug])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [clientRes, integrationsRes] = await Promise.all([
        apiFetch(`/api/clients/${slug}`),
        apiFetch(`/api/integrations?client_slug=${encodeURIComponent(slug)}`),
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
        for (const pi of integrationsData || []) {
          const platform = INTEGRATION_TO_PLATFORM[pi.integration_type]
          const cfg = GOOGLE_DROPDOWN_CONFIG[platform]
          if (platform && cfg && pi.extra_config?.[cfg.configKey] && !forms[platform]?.[cfg.configKey]) {
            forms[platform] = { ...(forms[platform] || {}), [cfg.configKey]: pi.extra_config[cfg.configKey] }
          }
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
  }, [slug, navigate, location])

  useEffect(() => {
    if (!authReady) return
    fetchData()
  }, [authReady, fetchData])

  useEffect(() => {
    const connected = searchParams.get('connected')
    const errorParam = searchParams.get('error')

    if (errorParam) {
      setSearchParams({}, { replace: true })
      const errorMessages = {
        config: 'Google OAuth niet geconfigureerd op de server.',
        token_exchange: 'Kon geen tokens ophalen van Google. Probeer opnieuw.',
        invalid_state: 'Beveiligingscheck mislukt. Probeer opnieuw.',
        missing_params: 'OAuth callback onvolledig ontvangen.',
        no_tokens: 'Geen tokens ontvangen van Google. Probeer opnieuw.',
      }
      setError(errorMessages[errorParam] || `Google verbinding mislukt (${errorParam})`)
      return
    }

    const connectedValues = ['google', 'ga4', 'google_search_console', 'google_ads']
    if (connectedValues.includes(connected)) {
      setSearchParams({}, { replace: true })
      setError('')
      const connectedService = connected
      const refetch = async () => {
        try {
          const [clientRes, integrationsRes] = await Promise.all([
            apiFetch(`/api/clients/${slug}`),
            apiFetch(`/api/integrations?client_slug=${encodeURIComponent(slug)}`),
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
            for (const pi of integrationsData || []) {
              const platform = INTEGRATION_TO_PLATFORM[pi.integration_type]
              const cfg = GOOGLE_DROPDOWN_CONFIG[platform]
              if (platform && cfg && pi.extra_config?.[cfg.configKey] && !forms[platform]?.[cfg.configKey]) {
                forms[platform] = { ...(forms[platform] || {}), [cfg.configKey]: pi.extra_config[cfg.configKey] }
              }
            }
            setPlatformForms(forms)
            await Promise.all([
              fetchGoogleOptions('ga4'),
              fetchGoogleOptions('google_ads'),
              fetchGoogleOptions('gsc'),
            ])
            if (['ga4', 'google_search_console', 'google_ads'].includes(connectedService)) {
              setSelectorModal({ serviceType: connectedService })
            }
          }
        } catch (e) {
          console.error('Refetch after OAuth failed:', e)
        }
      }
      refetch()
    }
  }, [searchParams, slug, fetchGoogleOptions])

  const getConfigForPlatform = (platform) => {
    const pc = client?.platform_configs?.find((p) => p.platform === platform)
    return pc?.config || {}
  }

  const getCurrentGoogleValue = (platform) => {
    const cfg = GOOGLE_DROPDOWN_CONFIG[platform]
    if (!cfg) return ''
    return (
      getConfigForPlatform(platform)[cfg.configKey] ||
      getIntegrationForPlatform(platform)?.extra_config?.[cfg.configKey] ||
      ''
    )
  }

  const getDisplayNameForPlatform = (platform) => {
    const cfg = GOOGLE_DROPDOWN_CONFIG[platform]
    if (!cfg) return null
    const val = getCurrentGoogleValue(platform)
    if (!val) return null
    const opts = googleOptions[platform] || []
    const found = opts.find((o) => o[cfg.valueKey] === val)
    if (found) return cfg.optionLabel ? cfg.optionLabel(found) : (found[cfg.labelKey] || val)
    return val
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
      const res = await apiFetch(`/api/clients/${slug}/platforms`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform, config }),
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const clientRes = await apiFetch(`/api/clients/${slug}`)
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

  useEffect(() => {
    if (!client || !integrations.length) return
    if (isIntegrationConnected('ga4')) fetchGoogleOptions('ga4')
    if (isIntegrationConnected('google_ads')) fetchGoogleOptions('google_ads')
    if (isIntegrationConnected('google_search_console')) fetchGoogleOptions('gsc')
  }, [client, integrations, fetchGoogleOptions])

  const handleGoogleSave = async (platform, value) => {
    const serviceType = PLATFORM_TO_SERVICE_TYPE[platform]
    const cfg = GOOGLE_DROPDOWN_CONFIG[platform]
    if (!serviceType || !cfg) return
    setSaving(platform)
    setError('')
    try {
      const res = await apiFetch(
        `/api/clients/${slug}/integrations/${serviceType}/config`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ [cfg.configKey]: value }),
        }
      )
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        await fetchData()
        fetchGoogleOptions('ga4')
        fetchGoogleOptions('google_ads')
        fetchGoogleOptions('gsc')
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Opslaan mislukt')
      }
    } catch (err) {
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
      const res = await apiFetch(`/api/clients/${slug}/platforms/${platform}`, {
        method: 'DELETE',
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const clientRes = await apiFetch(`/api/clients/${slug}`)
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
      <div className="panel-card bg-white shadow-sm border border-slate-200 p-6 rounded-xl">
        Integraties laden...
      </div>
    )
  }

  return (
    <div>
      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
          {error}
        </div>
      )}

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
                    (isGoogle ? isPlatformConnected(platform) : configured)
                      ? 'bg-emerald-100 text-emerald-800'
                      : canConfigure
                        ? 'bg-slate-100 text-slate-600'
                        : isGoogle
                          ? 'bg-slate-100 text-slate-600'
                          : 'bg-slate-200 text-slate-500'
                  }`}
                >
                  {(isGoogle ? isPlatformConnected(platform) : configured) ? (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      {isGoogle
                        ? (getDisplayNameForPlatform(platform)
                          ? `Verbonden — ${getDisplayNameForPlatform(platform)}`
                          : 'Verbonden')
                        : 'Geconfigureerd'}
                    </>
                  ) : canConfigure ? (
                    <>
                      <XCircle className="w-4 h-4" />
                      {isGoogle ? 'Niet verbonden' : 'Niet geconfigureerd'}
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

              {isGoogle && (
                <div className="mt-2">
                  {GOOGLE_DROPDOWN_CONFIG[platform]?.description && (
                    <p className="text-sm text-slate-500 mb-3">{GOOGLE_DROPDOWN_CONFIG[platform].description}</p>
                  )}
                  {isPlatformConnected(platform) ? (
                    <div className="space-y-3">
                      {(() => {
                        const cfg = GOOGLE_DROPDOWN_CONFIG[platform]
                        const opts = googleOptions[platform] || []
                        const load = googleLoading[platform]
                        const loadErr = googleError[platform]
                        const currentVal =
                          platformForms[platform]?.[cfg.configKey] ?? getCurrentGoogleValue(platform)
                        if (loadErr) {
                          if (loadErr === 'token_expired') {
                            return (
                              <div className="flex items-center gap-3 mt-2">
                                <span className="text-amber-600 text-sm">⚠️ Token verlopen</span>
                                <button
                                  type="button"
                                  onClick={() => handleGoogleConnect(platform)}
                                  className="text-sm px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-medium"
                                >
                                  Opnieuw verbinden
                                </button>
                              </div>
                            )
                          }
                          return <p className="text-sm text-amber-600">{loadErr}</p>
                        }
                        if (load) {
                          return <p className="text-sm text-slate-500">Laden...</p>
                        }
                        return (
                          <>
                            <select
                              value={currentVal}
                              onChange={(e) => updateForm(platform, cfg.configKey, e.target.value)}
                              disabled={saving === platform}
                              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                            >
                              {!currentVal && <option value="">— Selecteer —</option>}
                              {opts.map((opt) => (
                                <option key={opt[cfg.valueKey]} value={opt[cfg.valueKey]}>
                                  {cfg.optionLabel ? cfg.optionLabel(opt) : (opt[cfg.labelKey] || opt[cfg.valueKey])}
                                </option>
                              ))}
                              {currentVal && !opts.some((o) => o[cfg.valueKey] === currentVal) && (
                                <option value={currentVal}>{currentVal}</option>
                              )}
                            </select>
                            <button
                              type="button"
                              onClick={() =>
                                handleGoogleSave(
                                  platform,
                                  platformForms[platform]?.[cfg.configKey] ?? currentVal
                                )
                              }
                              disabled={!currentVal || saving === platform}
                              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              <Save className="w-4 h-4" />
                              {saving === platform ? 'Opslaan...' : 'Opslaan'}
                            </button>
                          </>
                        )
                      })()}
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleGoogleConnect(platform)}
                      disabled={connecting === platform}
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition disabled:opacity-50"
                    >
                      <Plug className="w-4 h-4" />
                      {connecting === platform ? 'Bezig...' : `Verbind ${PLATFORM_LABELS[platform]}`}
                    </button>
                  )}
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

              {canConfigure && fields.length > 0 && (
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

      {selectorModal && (
        <PropertySelectorModal
          slug={slug}
          serviceType={selectorModal.serviceType}
          onSaved={() => {
            setSelectorModal(null)
            fetchData()
            fetchGoogleOptions('ga4')
            fetchGoogleOptions('google_ads')
            fetchGoogleOptions('gsc')
          }}
          onClose={() => {
            setSelectorModal(null)
            fetchData()
          }}
        />
      )}
    </div>
  )
}
