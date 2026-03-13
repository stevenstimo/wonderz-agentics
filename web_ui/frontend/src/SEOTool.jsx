import { useState, useRef, useEffect } from 'react'
import { BarChart3, Upload, Loader2, Download, CheckCircle } from 'lucide-react'
import PageLayout from './PageLayout'
import { apiUrl, apiFetch } from './apiClient'

export default function SEOTool() {
  const [brandName, setBrandName] = useState('')
  const [domain, setDomain] = useState('')
  const [audience, setAudience] = useState('')
  const [language, setLanguage] = useState('nl')
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState(null)
  const [progress, setProgress] = useState(0)
  const [keywordsProcessed, setKeywordsProcessed] = useState(0)
  const [keywordsTotal, setKeywordsTotal] = useState(0)
  const [currentSilo, setCurrentSilo] = useState('')
  const [downloadUrl, setDownloadUrl] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const fileInputRef = useRef(null)
  const pollIntervalRef = useRef(null)

  async function fetchJobHistory() {
    try {
      const res = await apiFetch('/api/seo/jobs')
      const data = await res.json()
      if (res.ok && data.jobs) setHistory(data.jobs)
    } catch (_) {}
  }

  useEffect(() => {
    const savedJobId = localStorage.getItem('seo_active_job_id')
    if (savedJobId) {
      setJobId(savedJobId)
      setStatus('processing')
    }
    fetchJobHistory()
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    }
  }, [])

  async function pollStatus(id) {
    try {
      const res = await apiFetch(`/api/seo/status/${id}`)
      const data = await res.json()
      console.log('[SEO POLL]', data)
      if (!res.ok) throw new Error(data.detail || 'Status check failed')
      setStatus(data.status)
      setProgress(data.progress ?? 0)
      setKeywordsProcessed(data.keywords_processed ?? 0)
      setKeywordsTotal(data.keywords_total ?? data.keyword_count ?? data.total ?? 0)
      if (data.status === 'ready' && data.download_url) {
        setDownloadUrl(apiUrl(data.download_url))
        localStorage.removeItem('seo_active_job_id')
        fetchJobHistory()
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
          pollIntervalRef.current = null
        }
      }
      if (data.status === 'failed') {
        setError('Verwerking mislukt')
        localStorage.removeItem('seo_active_job_id')
        fetchJobHistory()
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
          pollIntervalRef.current = null
        }
      }
    } catch (err) {
      setError(err.message)
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
    }
  }

  useEffect(() => {
    if (!jobId || status === 'ready' || status === 'failed') return
    pollStatus(jobId)
    pollIntervalRef.current = setInterval(() => pollStatus(jobId), 3000)
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    }
  }, [jobId, status])

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
      const form = new FormData()
      form.append('file', file)
      form.append('brand_name', brandName.trim())
      form.append('domain', domain.trim())
      form.append('audience', audience.trim())
      form.append('language', language.trim() || 'nl')

      const res = await apiFetch('/api/seo/upload', {
        method: 'POST',
        body: form,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Upload mislukt')
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
    setFile(null)
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
          Upload een keyword CSV (Semrush, Ahrefs) en ontvang een volledig SEO plan als Excel.
        </p>

        {error && (
          <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200">
            {error}
          </div>
        )}

        {/* Step 1: Upload */}
        {showUpload && (
          <form onSubmit={handleSubmit} className="space-y-4">
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
              <p className="text-sm text-slate-500 mt-1">Max 2000 keywords, 5MB</p>
            </div>

            <button
              type="submit"
              disabled={uploading || !file}
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
              <p>Download het Excel bestand met Keyword Plan, Silo Overzicht, Quick Wins en Strategie Notes.</p>
            </div>
            <div className="flex gap-4">
              <button
                onClick={handleDownload}
                className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700"
              >
                <Download className="w-5 h-5" />
                Download Excel
              </button>
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
