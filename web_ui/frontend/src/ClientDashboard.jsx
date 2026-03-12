import { useParams, useLocation, Link } from 'react-router-dom'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ComposedChart,
} from 'recharts'
import PageLayout from './PageLayout'
import { BarChart3, TrendingUp, DollarSign, MousePointer, Search, Globe, Plug, RefreshCw } from 'lucide-react'

// Formatters: kosten € met 2 decimalen, percentages %, grote aantallen met duizendscheiding
const fmtNum = (v) => (v == null ? '0' : Number(v).toLocaleString('nl-NL'))
const fmtEur = (v) =>
  v == null ? '€0,00' : new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' }).format(Number(v))
const fmtPct = (v) => (v == null ? '0%' : `${Number(v).toFixed(1).replace('.', ',')}%`)

const CHANNELS = ['', 'Organic Search', 'Paid Search', 'Direct', 'Organic Social', 'Paid Social', 'Email', 'Referral']
const DEVICES = ['', 'Desktop', 'Mobile', 'Tablet']

function KpiCard({ label, value, formatter = fmtNum, icon: Icon }) {
  return (
    <div className="panel-card bg-white border border-slate-200 rounded-xl p-4">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">{label}</p>
      <div className="flex items-center gap-2">
        {Icon && <Icon className="w-5 h-5 text-indigo-500" />}
        <span className="text-xl font-semibold text-slate-800">{formatter(value)}</span>
      </div>
    </div>
  )
}

function EmptyState({ title, description, buttonText, href, onRetry, retrying, needsReconnect }) {
  return (
    <div className="panel-card bg-slate-50 border border-slate-200 rounded-xl p-8 text-center">
      <Plug className="w-12 h-12 text-slate-400 mx-auto mb-3" />
      <h3 className="font-semibold text-slate-700 mb-1">{title}</h3>
      <p className="text-sm text-slate-500 mb-4">{description}</p>
      {needsReconnect && onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${retrying ? 'animate-spin' : ''}`} />
          {retrying ? 'Bezig...' : 'Herverbind Google'}
        </button>
      ) : (
        <Link
          to={href}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition"
        >
          <Plug className="w-4 h-4" />
          {buttonText}
        </Link>
      )}
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-20 bg-slate-200 rounded-xl" />
        ))}
      </div>
      <div className="h-64 bg-slate-200 rounded-xl" />
      <div className="h-48 bg-slate-200 rounded-xl" />
    </div>
  )
}

export default function ClientDashboard({
  data: liveData,
  loading,
  error,
  blockErrors = {},
  retryingBlock,
  filters,
  onFilterChange,
  onRetry,
  onBlockRetry,
}) {
  const { slug } = useParams()
  const location = useLocation()
  const integrationsUrl = `/clients/${slug}/integrations`

  const overview = liveData?.overview || {}
  const ga4 = liveData?.ga4
  const googleAds = liveData?.google_ads
  const gsc = liveData?.gsc

  const ga4Connected = ga4 && !ga4.not_connected
  const adsConnected = googleAds && !googleAds.not_connected
  const gscConnected = gsc && !gsc.not_connected

  const ga4BlockError = blockErrors.ga4
  const adsBlockError = blockErrors.google_ads
  const gscBlockError = blockErrors.gsc

  const ga4TokenError = ga4?.not_connected && (ga4?.error?.toLowerCase?.().includes('token') || ga4?.error?.toLowerCase?.().includes('refresh'))
  const adsTokenError = googleAds?.not_connected && (googleAds?.error?.toLowerCase?.().includes('token') || googleAds?.error?.toLowerCase?.().includes('refresh'))
  const gscTokenError = gsc?.not_connected && (gsc?.error?.toLowerCase?.().includes('token') || gsc?.error?.toLowerCase?.().includes('refresh'))

  const timeseries = (() => {
    const byDate = {}
    ;(ga4?.timeseries || []).forEach((r) => {
      const d = r.date?.slice(5) || r.date || ''
      byDate[d] = {
        date: d,
        sessions: r.sessions || 0,
        cost: 0,
        conversions: r.conversions || 0,
      }
    })
    ;(googleAds?.timeseries || []).forEach((r) => {
      const d = r.date?.slice(5) || r.date || ''
      if (!byDate[d]) byDate[d] = { date: d, sessions: 0, cost: 0, conversions: 0 }
      byDate[d].cost = r.cost || 0
    })
    return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))
  })()

  const campaigns = googleAds?.campaigns || []
  const adsTimeseries = (googleAds?.timeseries || []).map((r) => ({
    date: r.date?.slice(5) || r.date,
    cost: r.cost || 0,
  }))

  const topQueries = gsc?.top_queries || []
  const topPages = gsc?.top_pages || []
  const gscTimeseries = (gsc?.timeseries || []).map((r) => ({
    date: r.date?.slice(5) || r.date,
    clicks: r.clicks || 0,
  }))

  const traffic = ga4?.traffic_by_channel || []
  const engagementRate = ga4?.kpis?.engagement_rate || 0
  const conversionRate = ga4?.kpis?.conversion_rate || overview?.conversion_rate || 0

  if (error?.type === 'auth') {
    return (
      <PageLayout size="wide" padded>
        <div className="mb-6 p-4 rounded-lg bg-amber-50 text-amber-800 border border-amber-200">
          <p className="font-medium">{error.message}</p>
          <Link to="/login" state={{ from: location }} className="mt-2 inline-block text-amber-700 underline hover:no-underline">
            Naar inloggen
          </Link>
        </div>
      </PageLayout>
    )
  }

  if (loading && !liveData) {
    return (
      <PageLayout size="wide" padded>
        <div className="mb-6">
          <div className="h-8 w-48 bg-slate-200 rounded animate-pulse" />
          <div className="h-4 w-64 bg-slate-200 rounded animate-pulse mt-2" />
        </div>
        <LoadingSkeleton />
      </PageLayout>
    )
  }

  if (error && !liveData) {
    return (
      <PageLayout size="wide" padded>
        <div className="mb-6 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200">
          <p className="font-medium">{error.message}</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 text-white font-medium hover:bg-red-700"
          >
            <RefreshCw className="w-4 h-4" />
            Opnieuw proberen
          </button>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout size="wide" padded>
      {error && liveData && (
        <div className="mb-4 p-4 rounded-lg bg-amber-50 text-amber-800 border border-amber-200 flex items-center justify-between">
          <span>{error.message}</span>
          <button
            type="button"
            onClick={onRetry}
            className="px-3 py-1.5 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-700"
          >
            Opnieuw
          </button>
        </div>
      )}

      {/* Block 1 — Overzicht */}
      <div className="mb-8">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Marketing overzicht
          </h2>
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="date"
              value={filters?.start || ''}
              onChange={(e) => onFilterChange?.({ start: e.target.value })}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
            <input
              type="date"
              value={filters?.end || ''}
              onChange={(e) => onFilterChange?.({ end: e.target.value })}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
            <select
              value={filters?.channel || ''}
              onChange={(e) => onFilterChange?.({ channel: e.target.value })}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
            >
              {CHANNELS.map((c) => (
                <option key={c || 'all'} value={c}>{c || 'Alle kanalen'}</option>
              ))}
            </select>
            <select
              value={filters?.device || ''}
              onChange={(e) => onFilterChange?.({ device: e.target.value })}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
            >
              {DEVICES.map((d) => (
                <option key={d || 'all'} value={d}>{d || 'Alle devices'}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
          <KpiCard label="Users" value={overview.users} icon={TrendingUp} />
          <KpiCard label="Sessions" value={overview.sessions} icon={BarChart3} />
          <KpiCard label="Conversions" value={overview.conversions} icon={MousePointer} />
          <KpiCard label="Conversion Value" value={overview.conversion_value} formatter={fmtEur} icon={DollarSign} />
          <KpiCard label="Total Cost" value={overview.total_cost} formatter={fmtEur} icon={DollarSign} />
          <KpiCard label="CPA" value={overview.cpa} formatter={fmtEur} icon={DollarSign} />
        </div>

        <div className="panel-card bg-white border border-slate-200 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Verkeer, kosten & conversies</h3>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={timeseries}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 12 }} tickFormatter={fmtNum} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} tickFormatter={(v) => `€${v}`} />
              <Tooltip formatter={(v, name) => [name === 'cost' ? fmtEur(v) : fmtNum(v), name]} />
              <Legend />
              <Line yAxisId="left" type="monotone" dataKey="sessions" stroke="#3b82f6" strokeWidth={2} name="Sessions" dot={false} />
              <Line yAxisId="left" type="monotone" dataKey="conversions" stroke="#10b981" strokeWidth={2} name="Conversions" dot={false} />
              <Line yAxisId="right" type="monotone" dataKey="cost" stroke="#f59e0b" strokeWidth={2} name="Kosten" dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Block 2 — Google Ads */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <DollarSign className="w-5 h-5" />
          Google Ads
        </h2>
        {(adsBlockError?.needsReconnect || adsTokenError) ? (
          <EmptyState
            title="Google Ads token verlopen"
            description={adsBlockError?.message || googleAds?.error || 'Token verlopen. Herverbind Google.'}
            buttonText="Herverbind Google"
            onRetry={() => onBlockRetry?.('google_ads')}
            retrying={retryingBlock === 'google_ads'}
            needsReconnect
          />
        ) : !adsConnected ? (
          <EmptyState
            title="Google Ads niet verbonden"
            description={googleAds?.error || 'Koppel Google Ads om campagne- en kosten data te zien.'}
            buttonText="Verbind Google Ads"
            href={integrationsUrl}
          />
        ) : googleAds?.error ? (
          <div className="panel-card bg-amber-50 border border-amber-200 rounded-xl p-6">
            <p className="font-medium text-amber-800">Google Ads-fout</p>
            <p className="text-sm text-amber-700 mt-1">{googleAds.error}</p>
            <Link to={integrationsUrl} className="inline-block mt-3 text-sm font-medium text-indigo-600 hover:underline">Controleer integratie →</Link>
          </div>
        ) : (!campaigns || campaigns.length === 0) ? (
          <div className="text-center py-12 text-gray-400">
            <p>Geen Google Ads account geselecteerd.</p>
            <p className="text-sm mt-1">Ga naar Integraties om een account te koppelen.</p>
            <Link to={integrationsUrl} className="inline-block mt-4 text-sm text-indigo-600 hover:underline">
              Naar Integraties
            </Link>
          </div>
        ) : (
          <>
            {googleAds?._used_first_account && (
              <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
                We tonen het eerste beschikbare Google Ads-account. Wil je het account van deze klant?{' '}
                <Link to={integrationsUrl} className="font-medium text-indigo-600 hover:underline">Kies onder Integraties</Link>.
              </div>
            )}
            <div className="overflow-x-auto mb-6">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="text-left py-3 px-2 font-semibold text-slate-700">Campagne</th>
                    <th className="text-right py-3 px-2 font-semibold text-slate-700">Klikken</th>
                    <th className="text-right py-3 px-2 font-semibold text-slate-700">Vertoningen</th>
                    <th className="text-right py-3 px-2 font-semibold text-slate-700">Conversies</th>
                    <th className="text-right py-3 px-2 font-semibold text-slate-700">Conv. waarde</th>
                    <th className="text-right py-3 px-2 font-semibold text-slate-700">Kosten</th>
                    <th className="text-right py-3 px-2 font-semibold text-slate-700">CPA</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((c, i) => (
                    <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="py-2 px-2">{c.campaign_name}</td>
                      <td className="text-right py-2 px-2">{fmtNum(c.clicks)}</td>
                      <td className="text-right py-2 px-2">{fmtNum(c.impressions)}</td>
                      <td className="text-right py-2 px-2">{fmtNum(c.conversions)}</td>
                      <td className="text-right py-2 px-2">{fmtEur(c.conversion_value)}</td>
                      <td className="text-right py-2 px-2">{fmtEur(c.cost)}</td>
                      <td className="text-right py-2 px-2">{fmtEur(c.cpa)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="panel-card bg-white border border-slate-200 rounded-xl p-6">
              <h3 className="text-sm font-semibold text-slate-700 mb-4">Kosten per dag</h3>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={adsTimeseries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `€${v}`} />
                  <Tooltip formatter={(v) => [fmtEur(v), 'Kosten']} />
                  <Bar dataKey="cost" fill="#3b82f6" name="Kosten" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>

      {/* Block 3 — SEO */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <Search className="w-5 h-5" />
          SEO (Search Console)
        </h2>
        {(gscBlockError?.needsReconnect || gscTokenError) ? (
          <EmptyState
            title="Search Console token verlopen"
            description={gscBlockError?.message || gsc?.error || 'Token verlopen. Herverbind Google.'}
            buttonText="Herverbind Google"
            onRetry={() => onBlockRetry?.('gsc')}
            retrying={retryingBlock === 'gsc'}
            needsReconnect
          />
        ) : !gscConnected ? (
          <EmptyState
            title="Search Console niet verbonden"
            description="Koppel Google Search Console om zoekwoorden en pagina's te analyseren."
            buttonText="Verbind Search Console"
            href={integrationsUrl}
          />
        ) : (
          <>
            <div className="grid md:grid-cols-2 gap-6 mb-6">
              <div className="panel-card bg-white border border-slate-200 rounded-xl overflow-hidden">
                <h3 className="text-sm font-semibold text-slate-700 p-4 border-b border-slate-100">Top zoekwoorden</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100">
                        <th className="text-left py-2 px-3 font-medium text-slate-600">Zoekwoord</th>
                        <th className="text-right py-2 px-3 font-medium text-slate-600">Clicks</th>
                        <th className="text-right py-2 px-3 font-medium text-slate-600">Impressions</th>
                        <th className="text-right py-2 px-3 font-medium text-slate-600">CTR</th>
                        <th className="text-right py-2 px-3 font-medium text-slate-600">Position</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topQueries.slice(0, 10).map((q, i) => (
                        <tr key={i} className="border-b border-slate-50">
                          <td className="py-2 px-3 truncate max-w-[180px]" title={q.query}>{q.query}</td>
                          <td className="text-right py-2 px-3">{fmtNum(q.clicks)}</td>
                          <td className="text-right py-2 px-3">{fmtNum(q.impressions)}</td>
                          <td className="text-right py-2 px-3">{fmtPct((q.ctr ?? 0) * 100)}</td>
                          <td className="text-right py-2 px-3">{Number(q.position || 0).toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="panel-card bg-white border border-slate-200 rounded-xl overflow-hidden">
                <h3 className="text-sm font-semibold text-slate-700 p-4 border-b border-slate-100">Top pagina's</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100">
                        <th className="text-left py-2 px-3 font-medium text-slate-600">Pagina</th>
                        <th className="text-right py-2 px-3 font-medium text-slate-600">Clicks</th>
                        <th className="text-right py-2 px-3 font-medium text-slate-600">Impressions</th>
                        <th className="text-right py-2 px-3 font-medium text-slate-600">CTR</th>
                        <th className="text-right py-2 px-3 font-medium text-slate-600">Position</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topPages.slice(0, 10).map((p, i) => (
                        <tr key={i} className="border-b border-slate-50">
                          <td className="py-2 px-3 truncate max-w-[180px]" title={p.page}>{p.page}</td>
                          <td className="text-right py-2 px-3">{fmtNum(p.clicks)}</td>
                          <td className="text-right py-2 px-3">{fmtNum(p.impressions)}</td>
                          <td className="text-right py-2 px-3">{fmtPct((p.ctr ?? 0) * 100)}</td>
                          <td className="text-right py-2 px-3">{Number(p.position || 0).toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            <div className="panel-card bg-white border border-slate-200 rounded-xl p-6">
              <h3 className="text-sm font-semibold text-slate-700 mb-4">SEO klikken per dag</h3>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={gscTimeseries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="clicks" stroke="#10b981" strokeWidth={2} name="Clicks" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>

      {/* Block 4 — Website gedrag (GA4) */}
      <div>
        <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <Globe className="w-5 h-5" />
          Website gedrag (GA4)
        </h2>
        {(ga4BlockError?.needsReconnect || ga4TokenError) ? (
          <EmptyState
            title="GA4 token verlopen"
            description={ga4BlockError?.message || ga4?.error || 'Token verlopen. Herverbind Google.'}
            buttonText="Herverbind Google"
            onRetry={() => onBlockRetry?.('ga4')}
            retrying={retryingBlock === 'ga4'}
            needsReconnect
          />
        ) : !ga4Connected ? (
          <EmptyState
            title="GA4 niet verbonden"
            description={ga4?.error || 'Koppel Google Analytics 4 om verkeer en gedrag te analyseren.'}
            buttonText="Verbind GA4"
            href={integrationsUrl}
          />
        ) : ga4?.error ? (
          <div className="panel-card bg-amber-50 border border-amber-200 rounded-xl p-6">
            <p className="font-medium text-amber-800">GA4-fout</p>
            <p className="text-sm text-amber-700 mt-1">{ga4.error}</p>
            <Link to={integrationsUrl} className="inline-block mt-3 text-sm font-medium text-indigo-600 hover:underline">Controleer integratie →</Link>
          </div>
        ) : (
          <>
            {ga4?._used_first_property && (
              <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
                We tonen het eerste beschikbare GA4-property. Wil je het property van deze klant?{' '}
                <Link to={integrationsUrl} className="font-medium text-indigo-600 hover:underline">Kies onder Integraties</Link>.
              </div>
            )}
            <div className="grid sm:grid-cols-2 gap-4 mb-6">
              <KpiCard label="Engagement rate" value={engagementRate} formatter={(v) => fmtPct(v)} icon={TrendingUp} />
              <KpiCard label="Conversion rate" value={conversionRate} formatter={(v) => fmtPct(v)} icon={MousePointer} />
            </div>
            <div className="panel-card bg-white border border-slate-200 rounded-xl overflow-hidden">
              <h3 className="text-sm font-semibold text-slate-700 p-4 border-b border-slate-100">Traffic bronnen</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100">
                      <th className="text-left py-2 px-3 font-medium text-slate-600">Kanaal</th>
                      <th className="text-right py-2 px-3 font-medium text-slate-600">Users</th>
                      <th className="text-right py-2 px-3 font-medium text-slate-600">Sessions</th>
                      <th className="text-right py-2 px-3 font-medium text-slate-600">Conversions</th>
                      <th className="text-right py-2 px-3 font-medium text-slate-600">Conv. Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {traffic.map((t, i) => (
                      <tr key={i} className="border-b border-slate-50">
                        <td className="py-2 px-3">{t.channel}</td>
                        <td className="text-right py-2 px-3">{fmtNum(t.users)}</td>
                        <td className="text-right py-2 px-3">{fmtNum(t.sessions)}</td>
                        <td className="text-right py-2 px-3">{fmtNum(t.conversions)}</td>
                        <td className="text-right py-2 px-3">{fmtPct(t.conversion_rate)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </PageLayout>
  )
}
