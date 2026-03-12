import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import ClientDashboard from './ClientDashboard'
import { apiFetch } from './apiClient'

const toDate = (d) => {
  if (!d) return ''
  const x = new Date(d)
  return x.toISOString().slice(0, 10)
}

export default function ClientDashboardPage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const location = useLocation()

  const today = toDate(new Date())
  const monthAgo = toDate(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000))

  const [filters, setFilters] = useState({
    start: monthAgo,
    end: today,
    channel: '',
    device: '',
  })
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [blockErrors, setBlockErrors] = useState({ ga4: null, google_ads: null, gsc: null })
  const [retryingBlock, setRetryingBlock] = useState(null)

  // Eén dashboard-call met start/end; backend gebruikt deze periode voor alle 4 blokken (Marketing overzicht, Google Ads, SEO, Website gedrag).
  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    setBlockErrors({ ga4: null, google_ads: null, gsc: null })
    try {
      const params = new URLSearchParams()
      if (filters.start) params.set('start', filters.start)
      if (filters.end) params.set('end', filters.end)
      if (filters.channel) params.set('channel', filters.channel)
      if (filters.device) params.set('device', filters.device)
      const qs = params.toString()
      const path = `/api/clients/${encodeURIComponent(slug)}/dashboard${qs ? `?${qs}` : ''}`
      const res = await apiFetch(path)
      const raw = await res.text()
      let parsed = null
      if (raw.length > 0) {
        try {
          parsed = JSON.parse(raw)
        } catch (_) {
          throw new Error('Ongeldige response')
        }
      }

      if (res.status === 401) {
        setError({ type: 'auth', message: 'Sessie verlopen, log opnieuw in' })
        setData(null)
        return
      }
      if (res.status === 404) {
        navigate('/clients')
        return
      }
      if (!res.ok) {
        const detail = parsed?.detail || parsed?.error || parsed?.message || `Request mislukt (${res.status})`
        setError({ type: 'server', message: detail })
        setData(null)
        return
      }

      setData(parsed)
      setError(null)
    } catch (err) {
      if (err.name === 'TypeError' && err.message?.includes('fetch')) {
        setError({ type: 'network', message: 'Netwerkfout. Controleer je verbinding.' })
      } else {
        setError({ type: 'server', message: err.message || 'Dashboard laden mislukt' })
      }
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [slug, filters.start, filters.end, filters.channel, filters.device, navigate])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleFilterChange = (updates) => {
    setFilters((prev) => ({ ...prev, ...updates }))
  }

  const handleRetry = useCallback(() => {
    setError(null)
    loadData()
  }, [loadData])

  const handleRefreshAndRetry = useCallback(async (block) => {
    setRetryingBlock(block)
    try {
      const res = await apiFetch('/api/integrations/google/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_slug: slug }),
      })
      if (res.status === 401) {
        setError({ type: 'auth', message: 'Sessie verlopen, log opnieuw in' })
        return
      }
      const parsed = await res.json().catch(() => ({}))
      if (res.ok && parsed.ok) {
        await loadData()
        setBlockErrors((prev) => ({ ...prev, [block]: null }))
      } else {
        setBlockErrors((prev) => ({
          ...prev,
          [block]: { needsReconnect: true, message: 'Token verlopen. Herverbind Google.' },
        }))
      }
    } catch (_) {
      setBlockErrors((prev) => ({
        ...prev,
        [block]: { needsReconnect: true, message: 'Token verlopen. Herverbind Google.' },
      }))
    } finally {
      setRetryingBlock(null)
    }
  }, [slug, loadData])

  const handleBlockRetry = useCallback(
    async (block) => {
      const blockData = data?.[block]
      const tokenError =
        blockData?.not_connected &&
        (blockData?.error?.toLowerCase?.().includes('token') ||
          blockData?.error?.toLowerCase?.().includes('refresh'))
      if (tokenError) {
        await handleRefreshAndRetry(block)
      } else {
        handleRetry()
      }
    },
    [data, handleRefreshAndRetry, handleRetry]
  )

  return (
    <ClientDashboard
      data={data}
      loading={loading}
      error={error}
      blockErrors={blockErrors}
      retryingBlock={retryingBlock}
      filters={filters}
      onFilterChange={handleFilterChange}
      onRetry={handleRetry}
      onBlockRetry={handleBlockRetry}
    />
  )
}
