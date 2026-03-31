import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, Upload, Loader2, Download, CheckCircle } from 'lucide-react'
import PageLayout from './PageLayout'
import { apiUrl, apiFetch, fetchJson, getAccessToken } from './apiClient'
import { supabase } from './supabase'
import { useAuthReady } from './useAuthReady'
import { queryKeys } from './queryKeys'

const MANUAL_ENTRY_VALUE = '__manual__'

function domainFromSiteUrl(siteUrl) {
  if (!siteUrl) return ''

  // GSC domain property formaat: sc-domain:example.com
  if (siteUrl.startsWith('sc-domain:')) {
    return siteUrl.replace('sc-domain:', '')
  }

  // Bestaande logica blijft ongewijzigd
  try {
    const u = new URL(siteUrl.startsWith('http') ? siteUrl : `https://${siteUrl}`)
    return u.hostname || ''
  } catch {
    return ''
  }
}

export default function SEOTool() {
  const [clients, setClients] = useState([])
  const [selectedClientSlug, setSelectedClientSlug] = useState('')
  const [brandName, setBrandName] = useState('')
  const [domain, setDomain] = useState('')
  const [audience, setAudience] = useState('')
  const [language, setLanguage] = useState('nl')
  const [file, setFile] = useState(null)
  const [fileUk, setFileUk] = useState(null)
  const [fileDe, setFileDe] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState(null)
  const [progress, setProgress] = useState(0)
  const [keywordsProcessed, setKeywordsProcessed] = useState(0)
  const [keywordsTotal, setKeywordsTotal] = useState(0)
  const [currentSilo, setCurrentSilo] = useState('')
  const [downloadUrl, setDownloadUrl] = useState(null)
  const [sheetsUrl, setSheetsUrl] = useState(null)
  const [talentScore, setTalentScore] = useState(null)
  const [talentStatus, setTalentStatus] = useState(null)
  const [talentComments, setTalentComments] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const fileInputRef = useRef(null)
  const { authReady } = useAuthReady()
  const manualEntry = selectedClientSlug === MANUAL_ENTRY_VALUE
  const clientSelected = selectedClientSlug && selectedClientSlug !== MANUAL_ENTRY_VALUE

  async function fetchJobHistory() {
    try {
      const res = await apiFetch('/api/seo/jobs')
      const data = await res.json()
      if (res.ok && data.jobs) setHistory(data.jobs)
    } catch (_) {}
  }

  useEffect(() => {
    if (!authReady) return
    const savedJobId = localStorage.getItem('seo_active_job_id')
    if (savedJobId) {
      setJobId(savedJobId)
      setStatus('processing')
    }
    fetchJobHistory()
    const loadClients = async () => {
      try {
        const res = await apiFetch('/api/clients')
        const data = await res.json()
        setClients(Array.isArray(data) ? data : (data?.clients ?? []))
      } catch (_) {}
    }
    loadClients()
  }, [authReady])

  useEffect(() => {
    if (!selectedClientSlug || selectedClientSlug === MANUAL_ENTRY_VALUE) return
    const c = clients.find((x) => x.slug === selectedClientSlug)
    if (c) {
      setBrandName(c.client_name ?? '')
      setDomain('')
      const fetchDomain = async () => {
        try {
          let siteUrl = null
          const res = await apiFetch(`/api/clients/${encodeURIComponent(c.slug)}`)
          if (res.ok) {
            const detail = await res.json()
            if (detail?.default_audience) setAudience((prev) => prev || detail.default_audience)
            const configs = detail?.platform_configs ?? []
            const gsc = configs.find((p) => p.platform === 'gsc')
            let config = gsc?.config
            if (typeof config === 'string') {
              try {
                config = JSON.parse(config)
              } catch {
                config = null
              }
            }
            siteUrl = config?.site_url ?? config?.siteUrl ?? null
          }
          if (!siteUrl) {
            const intRes = await apiFetch(`/api/integrations?client_slug=${encodeURIComponent(c.slug)}`)
            if (intRes.ok) {
              const data = await intRes.json()
              const gscIntegration = Array.isArray(data)
                ? data.find((i) => i.integration_type === 'google_search_console')
                : null
              siteUrl = gscIntegration?.extra_config?.site_url ?? null
            }
          }
          if (siteUrl) setDomain(domainFromSiteUrl(siteUrl))
        } catch (_) {}
      }
      fetchDomain()
    }
  }, [selectedClientSlug, clients])

  const { data: seoStatusData } = useQuery({
    queryKey: queryKeys.seoJob(jobId || 'none'),
    queryFn: () => fetchJson(`/api/seo/status/${jobId}`),
    enabled: !!jobId && status !== 'ready' && status !== 'failed',
    refetchInterval: (query) => {
      if (query.state.status === 'error') return false
      const s = query.state.data?.status
      if (s === 'ready' || s === 'failed') return false
      return 3000
    },
  })

  useEffect(() => {
    if (!seoStatusData) return
    setStatus(seoStatusData.status)
    setProgress(seoStatusData.progress ?? 0)
    setKeywordsProcessed(seoStatusData.keywords_processed ?? 0)
    setKeywordsTotal(seoStatusData.keywords_total ?? seoStatusData.keyword_count ?? seoStatusData.total ?? 0)
    if (seoStatusData.status === 'ready' && seoStatusData.download_url) {
      setDownloadUrl(apiUrl(seoStatusData.download_url))
      setSheetsUrl(seoStatusData.sheets_url ?? null)
      setTalentScore(
        seoStatusData.talent_score !== undefined && seoStatusData.talent_score !== null
          ? seoStatusData.talent_score
          : null
      )
      setTalentStatus(seoStatusData.talent_status ?? null)
      setTalentComments(seoStatusData.talent_comments ?? null)
      localStorage.removeItem('seo_active_job_id')
      fetchJobHistory()
    }
    if (seoStatusData.status === 'failed') {
      setError('Verwerking mislukt')
      localStorage.removeItem('seo_active_job_id')
      fetchJobHistory()
    }
  }, [seoStatusData])

  function handleFileSelect(files) {
    const f = files?.[0]
    if (!f) return
    const ext = (f.name || '').toLowerCase().split('.').pop()
    if (ext !== 'csv' && ext !== 'xlsx' && ext !== 'xls' && ext !== 'numbers') {
      setError('Alleen CSV, XLSX of Numbers bestanden worden ondersteund')
      return
    }
    setError(null)
    setFile(f)
  }

  async function handleSubmit(e) {
    e?.preventDefault()
    if (!file || !brandName.trim() || !domain.trim()) {
      setError('Vul brand naam, domein in en kies een bestand')
      return
    }
    setError(null)
    setUploading(true)
    try {
      let token = await getAccessToken()
      if (!token) {
        const { data } = await supabase.auth.getSession()
        token = data?.session?.access_token ?? null
      }
      if (!token) {
        setError('Log in om een SEO plan te maken.')
        setUploading(false)
        return
      }
      const form = new FormData()
      form.append('file', file)
      form.append('brand_name', brandName.trim())
      form.append('domain', domain.trim())
      form.append('audience', audience.trim())
      form.append('language', language.trim() || 'nl')
      if (clientSelected && selectedClientSlug) {
        form.append('client_slug', selectedClientSlug)
      }
      if (fileUk) form.append('file_uk', fileUk)
      if (fileDe) form.append('file_de', fileDe)

      const res = await apiFetch('/api/seo/upload', {
        method: 'POST',
        body: form,
        headers: { Authorization: `Bearer ${token}` },
      })

      if (res.status === 413) {
        throw new Error('Upload geblokkeerd door server (413). Probeer een kleiner bestand of neem contact op met de beheerder.')
      }
      if (!res.ok) {
        const ct = res.headers.get('content-type') || ''
        const msg = ct.includes('application/json')
          ? (await res.json()).detail || 'Onbekende fout'
          : `Serverfout (${res.status})`
        throw new Error(msg)
      }

      const data = await res.json()
      setJobId(data.job_id)
      localStorage.setItem('seo_active_job_id', data.job_id)
      setKeywordsTotal(data.keyword_count ?? 0)
      setKeywordsProcessed(0)
      setProgress(0)
      setStatus('processing')
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  function handleDownload() {
    if (downloadUrl) {
      window.open(downloadUrl, '_blank')
    }
  }

  function reset() {
    setJobId(null)
    setStatus(null)
    setProgress(0)
    setKeywordsProcessed(0)
    setKeywordsTotal(0)
    setDownloadUrl(null)
    setSheetsUrl(null)
    setTalentScore(null)
    setTalentStatus(null)
    setTalentComments(null)
    setFile(null)
    setFileUk(null)
    setFileDe(null)
    setError(null)
    setCurrentSilo('')
    localStorage.removeItem('seo_active_job_id')
  }

  const showUpload = !jobId || status === 'failed'
  const showProgress = jobId && (status === 'processing' || status === 'pending')
  const showDownload = jobId && status === 'ready'

  return (
    <PageLayout size="wide" padded>
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold text-slate-800 mb-2 flex items-center gap-2">
          <BarChart3 className="w-7 h-7 text-indigo-600" />
          SEO Keyword Plan Generator
        </h1>
        <p className="text-slate-600 mb-6">
          Upload een keyword CSV (Semrush, Ahrefs) — optioneel aparte UK- en DE-exports in dezelfde run. Je ontvangt
          een Excel met o.a. Keyword Plan (Markt, SERP Features, GSC), Silo-overzicht, Quick Wins, Strategie,
          Content Gaps, GSC Performance en Markt Expansie.
        </p>

        {error && (
          <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200">
            {error}
          </div>
        )}

        {/* Step 1: Upload */}
        {showUpload && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Client selecteren</label>
              <select
                value={selectedClientSlug}
                onChange={(e) => setSelectedClientSlug(e.target.value)}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="">— Kies een client —</option>
                {clients.filter((c) => c.is_active !== false).map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.client_name ?? c.slug}
                  </option>
                ))}
                <option value={MANUAL_ENTRY_VALUE}>— Handmatig invoeren —</option>
              </select>
            </div>

            {manualEntry && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Brand naam</label>
                  <input
                    type="text"
                    value={brandName}
                    onChange={(e) => setBrandName(e.target.value)}
                    placeholder="bijv. IKARIA Clinics"
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Domein</label>
                  <input
                    type="text"
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    placeholder="bijv. ikaria.nl"
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
              </div>
            )}

            {clientSelected && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Brand naam</label>
                  <input
                    type="text"
                    readOnly
                    value={brandName}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg bg-slate-50 text-slate-700"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Domein</label>
                  {domain ? (
                    <input
                      type="text"
                      readOnly
                      value={domain}
                      className="w-full px-4 py-2 border border-slate-200 rounded-lg bg-slate-50 text-slate-700"
                    />
                  ) : (
                    <input
                      type="text"
                      value={domain}
                      onChange={(e) => setDomain(e.target.value)}
                      placeholder="Vul domein in (geen GSC gekoppeld)"
                      className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    />
                  )}
                </div>
              </div>
            )}

            {!selectedClientSlug && (
              <p className="text-sm text-slate-500">Kies een client of kies Handmatig invoeren om brand en domein zelf in te vullen.</p>
            )}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Doelgroep</label>
              <input
                type="text"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="bijv. Mannen 35-60, gezondheid en hormonen"
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Taal</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="nl">NL</option>
                <option value="en">EN</option>
                <option value="de">DE</option>
              </select>
            </div>

            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                dragOver ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 cursor-pointer hover:border-slate-400'
              }`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFileSelect(e.dataTransfer?.files) }}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx,.xls,.numbers"
                className="hidden"
                onChange={(e) => handleFileSelect(e.target?.files)}
              />
              <Upload className="w-12 h-12 mx-auto text-slate-400 mb-2" />
              <p className="text-slate-600">
                {file ? file.name : 'Sleep CSV, XLSX of Numbers hier of klik om te uploaden'}
              </p>
              <p className="text-sm text-slate-500 mt-1">Max 2000 keywords totaal, 5MB per bestand</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Optioneel: Semrush UK (database United Kingdom)
                </label>
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.numbers"
                  className="w-full text-sm text-slate-600"
                  onChange={(e) => setFileUk(e.target?.files?.[0] ?? null)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Optioneel: Semrush DE (database Germany)
                </label>
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.numbers"
                  className="w-full text-sm text-slate-600"
                  onChange={(e) => setFileDe(e.target?.files?.[0] ?? null)}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={uploading || !file || !brandName.trim() || !domain.trim()}
              className="w-full py-3 px-6 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {uploading ? 'Uploaden…' : 'Analyseer Keywords'}
              {uploading && <Loader2 className="w-5 h-5 animate-spin" />}
            </button>
          </form>
        )}

        {/* Step 2: Progress */}
        {showProgress && (
          <div className="bg-white rounded-xl shadow border border-slate-200 p-8">
            <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
              SEO Agent analyseert keywords
            </h2>
            <div className="space-y-4">
              <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-600 transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-slate-600">
                {status === 'pending' && progress === 0
                  ? 'Starten…'
                  : `${keywordsProcessed} van ${keywordsTotal} keywords verwerkt`}
              </p>
              {currentSilo && (
                <p className="text-sm text-slate-500">Huidige silo: {currentSilo}</p>
              )}
            </div>
          </div>
        )}

        {/* Step 3: Download */}
        {showDownload && (
          <div className="bg-white rounded-xl shadow border border-slate-200 p-8">
            <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              SEO Plan klaar!
            </h2>
            <div className="space-y-2 text-slate-600 mb-6">
              <p>{keywordsTotal} keywords verwerkt</p>
              <p>
                Download het Excel-bestand met Keyword Plan, Silo-overzicht, Quick Wins, Strategie, Content Gaps,
                GSC Performance en Markt Expansie (UK/DE).
              </p>
              {talentScore !== null && (
                <p>Kwaliteitsscore: <span className="font-semibold">{talentScore}/100</span>{talentStatus ? ` (${talentStatus})` : ''}</p>
              )}
            </div>
            {Array.isArray(talentComments?.top_3_acties) && talentComments.top_3_acties.length > 0 && (
              <div className="mb-6 rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="font-medium text-slate-700 mb-2">Top 3 acties (Talent review)</p>
                <ul className="list-disc pl-5 text-sm text-slate-600 space-y-1">
                  {talentComments.top_3_acties.map((actie, i) => (
                    <li key={i}>{actie}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="flex gap-4">
              <button
                onClick={handleDownload}
                className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700"
              >
                <Download className="w-5 h-5" />
                Download Excel
              </button>
              {sheetsUrl && (
                <a
                  href={sheetsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 border border-slate-300 font-medium rounded-lg hover:bg-slate-50"
                >
                  📊 Open in Google Sheets
                </a>
              )}
              <button
                onClick={reset}
                className="px-6 py-3 border border-slate-300 font-medium rounded-lg hover:bg-slate-50"
              >
                Nieuw plan
              </button>
            </div>
          </div>
        )}

        {/* Job history */}
        {history.length > 0 && (
          <div className="mt-10 bg-white rounded-xl shadow border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-800 mb-4">Eerdere SEO jobs</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-600">
                    <th className="py-2 pr-4">Brand</th>
                    {history.some((j) => j.client_slug) && <th className="py-2 pr-4">Client</th>}
                    <th className="py-2 pr-4">Keywords</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Datum</th>
                    <th className="py-2">Actie</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((job) => {
                    const date = job.created_at
                      ? new Date(job.created_at).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
                      : '—'
                    const statusLabel = job.status === 'ready' ? '✅ Klaar' : job.status === 'failed' ? '❌ Mislukt' : job.status === 'processing' || job.status === 'pending' ? '⏳ Bezig' : job.status || '—'
                    return (
                      <tr key={job.job_id} className="border-b border-slate-100">
                        <td className="py-2 pr-4 font-medium text-slate-800">{job.brand_name || '—'}</td>
                        {history.some((j) => j.client_slug) && (
                          <td className="py-2 pr-4 text-slate-600">{job.client_slug || '—'}</td>
                        )}
                        <td className="py-2 pr-4 text-slate-600">{job.keyword_count ?? '—'}</td>
                        <td className="py-2 pr-4 text-slate-600">{statusLabel}</td>
                        <td className="py-2 pr-4 text-slate-600">{date}</td>
                        <td className="py-2">
                          {job.status === 'ready' && (
                            <button
                              type="button"
                              onClick={() => window.open(apiUrl(`/api/seo/download/${job.job_id}`), '_blank')}
                              className="text-indigo-600 hover:text-indigo-800 font-medium"
                            >
                              Download
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  )
}
