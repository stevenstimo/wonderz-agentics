import { useState, useCallback, useEffect } from 'react'
import { Link, useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Upload, Link2, FileText, Check, Loader2, X } from 'lucide-react'

import { apiFetch } from './apiClient'
import { useAuthReady } from './useAuthReady'

const DOC_TYPES = ['playbook', 'sop', 'framework', 'template', 'case_study', 'policy', 'research', 'client_context', 'skill_spec']
const DOMAINS = ['growth', 'gtm', 'sales', 'delivery', 'ai_systems', 'core']
const ACCESS_LEVELS = [
  { value: 'reference', label: 'Reference', desc: 'Ter inspiratie, niet als feitelijke basis' },
  { value: 'approved', label: 'Approved', desc: 'Volledig beschikbaar voor agents' },
  { value: 'restricted', label: 'Restricted', desc: 'Alleen menselijk gebruik' },
]
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB
const ACCEPTED_TYPES = '.pdf,.docx,.txt,.md,.csv,.xlsx'
const ACCEPTED_TYPES_DESC = 'PDF, DOCX, TXT, MD, CSV, XLSX'

const PROGRESS_STEPS = [
  { id: 1, label: 'Document aanmaken...' },
  { id: 2, label: 'Tekst verwerken...' },
  { id: 3, label: 'Embeddings genereren...' },
]

export default function KnowledgeUpload() {
  const authReady = useAuthReady()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()

  const [title, setTitle] = useState('')
  const [docType, setDocType] = useState('')
  const [domain, setDomain] = useState('')
  const [accessLevel, setAccessLevel] = useState('reference')
  const [functionTag, setFunctionTag] = useState('')
  const [summary, setSummary] = useState('')
  const [keywords, setKeywords] = useState([])
  const [keywordInput, setKeywordInput] = useState('')
  const [clientSlug, setClientSlug] = useState('')

  const [sourceTab, setSourceTab] = useState('url')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  const [uploading, setUploading] = useState(false)
  const [progressStep, setProgressStep] = useState(0)
  const [result, setResult] = useState(null)
  const [embeddingStatus, setEmbeddingStatus] = useState(null) // 'processing' | 'complete' | 'failed'
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})

  useEffect(() => {
    const dt = searchParams.get('doc_type')
    const cs = searchParams.get('client_slug')
    if (cs) {
      setClientSlug(cs)
      if (!dt || !DOC_TYPES.includes(dt)) setDocType('client_context')
    }
    if (dt && DOC_TYPES.includes(dt)) {
      setDocType(dt)
      if (dt === 'skill_spec') setDomain('ai_systems')
    }
  }, [searchParams])

  // Poll embedding_status when document is created with status processing (202)
  useEffect(() => {
    if (!result?.document_id || result.status !== 'processing') return
    const id = result.document_id
    const interval = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/knowledge/${id}`)
        if (!res.ok) return
        const doc = await res.json()
        const status = doc.embedding_status
        setEmbeddingStatus(status)
        if (status === 'complete') {
          setResult((r) => (r ? { ...r, status: 'complete' } : r))
          navigate(`/knowledge/${id}`)
        }
        if (status === 'failed') {
          setError('Embeddings genereren mislukt. Bekijk het document voor details.')
        }
      } catch (_) {}
    }, 3000)
    return () => clearInterval(interval)
  }, [result?.document_id, result?.status, navigate])

  const addKeyword = useCallback(() => {
    const v = keywordInput.trim()
    if (v && !keywords.includes(v)) {
      setKeywords((k) => [...k, v])
      setKeywordInput('')
    }
  }, [keywordInput, keywords])

  const removeKeyword = useCallback((idx) => {
    setKeywords((k) => k.filter((_, i) => i !== idx))
  }, [])

  const metadataComplete = Boolean(title.trim() && docType && domain)
  const sourceReady = sourceTab === 'url' ? url.trim().startsWith('http') : file

  const validate = useCallback(() => {
    const errs = {}
    if (!title.trim()) errs.title = 'Title is verplicht'
    if (!docType) errs.docType = 'Doc type is verplicht'
    if (!domain) errs.domain = 'Domain is verplicht'
    if (sourceTab === 'url' && !url.trim().startsWith('http')) errs.url = 'Voer een geldige URL in'
    if (sourceTab === 'file' && !file) errs.file = 'Selecteer een bestand'
    if (sourceTab === 'file' && file && file.size > MAX_FILE_SIZE) errs.file = 'Bestand mag maximaal 10MB zijn'
    if (summary.length > 500) errs.summary = 'Max 500 tekens'
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }, [title, docType, domain, sourceTab, url, file, summary])

  const resetForm = useCallback(() => {
    setTitle('')
    setDocType('')
    setDomain('')
    setAccessLevel('reference')
    setFunctionTag('')
    setSummary('')
    setKeywords([])
    setKeywordInput('')
    setClientSlug('')
    setUrl('')
    setFile(null)
    setResult(null)
    setEmbeddingStatus(null)
    setError('')
    setFieldErrors({})
    setUploading(false)
    setProgressStep(0)
  }, [])

  const doUpload = useCallback(async () => {
    if (!validate()) return
    setUploading(true)
    setError('')
    setProgressStep(1)

    const stepInterval = setInterval(() => {
      setProgressStep((s) => Math.min(s + 1, 3))
    }, 800)

    try {
      let res
      if (sourceTab === 'url') {
        res = await apiFetch('/api/knowledge/upload/url', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url: url.trim(),
            title: title.trim() || undefined,
            doc_type: docType,
            domain,
            function_tag: functionTag || 'general',
            client_slug: docType === 'client_context' ? (clientSlug.trim() || null) : null,
            access_level: accessLevel,
            summary: summary.trim() || null,
            keywords: keywords.length ? keywords : null,
          }),
        })
      } else {
        const fd = new FormData()
        fd.append('file', file)
        fd.append('title', title.trim())
        fd.append('doc_type', docType)
        fd.append('domain', domain)
        fd.append('function_tag', functionTag || 'general')
        if (docType === 'client_context' && clientSlug.trim()) fd.append('client_slug', clientSlug.trim())
        fd.append('access_level', accessLevel)
        if (summary.trim()) fd.append('summary', summary.trim())
        if (keywords.length) fd.append('keywords', JSON.stringify(keywords))

        res = await apiFetch('/api/knowledge/upload', {
          method: 'POST',
          headers: {},
          body: fd,
        })
      }

      clearInterval(stepInterval)
      setProgressStep(3)

      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }

      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        const msg = j.detail || (Array.isArray(j.detail) ? j.detail.map((d) => d.msg || d).join(', ') : '') || 'Upload mislukt'
        setError(msg)
        setUploading(false)
        return
      }

      const data = await res.json()
      setResult(data)
      setUploading(false)
      if (res.status === 202) {
        setEmbeddingStatus('processing')
      }
    } catch (err) {
      clearInterval(stepInterval)
      setError(err.message || 'Upload mislukt')
      setUploading(false)
    }
  }, [
    sourceTab, url, file, title, docType, domain, accessLevel, functionTag, summary, keywords, clientSlug,
    validate, navigate, location,
  ])

  if (!authReady) return null

  if (result) {
    if (result.status === 'processing') {
      return (
        <PageLayout size="medium" padded>
          <div className="mb-6 p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 flex items-center gap-3">
            <Loader2 className="w-6 h-6 flex-shrink-0 animate-spin" />
            <div>
              <p className="font-medium">Embeddings genereren...</p>
              <p className="text-sm mt-1">
                Document opgeslagen ({result.chunks_stored ?? 0} chunks). Wacht tot de embeddings klaar zijn; je wordt doorgestuurd.
              </p>
            </div>
          </div>
        </PageLayout>
      )
    }
    return (
      <PageLayout size="medium" padded>
        <div className="mb-6 p-4 rounded-lg bg-green-50 border border-green-200 text-green-800">
          Document aangemaakt als draft. {result.chunks_stored != null && `✓ ${result.chunks_stored} chunks geïndexeerd. `}
          Goedkeuring vereist voor gebruik door agents.
        </div>
        <div className="flex gap-3">
          <Link
            to={`/knowledge/${result.document_id}`}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700"
          >
            Bekijk document
          </Link>
          <button
            type="button"
            onClick={resetForm}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
          >
            Nog een uploaden
          </button>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout size="medium" padded>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Document uploaden</h1>

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
          {error}
        </div>
      )}

      {/* STAP 1 — Metadata */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">1. Metadata</h2>
        <div className="space-y-4 max-w-xl">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Title *</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 ${fieldErrors.title ? 'border-red-500' : 'border-slate-300'}`}
              placeholder="Documenttitel"
            />
            {fieldErrors.title && <p className="mt-1 text-sm text-red-600">{fieldErrors.title}</p>}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Doc type *</label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 ${fieldErrors.docType ? 'border-red-500' : 'border-slate-300'}`}
              >
                <option value="">— Selecteer —</option>
                {DOC_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              {fieldErrors.docType && <p className="mt-1 text-sm text-red-600">{fieldErrors.docType}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Domain *</label>
              <select
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 ${fieldErrors.domain ? 'border-red-500' : 'border-slate-300'}`}
              >
                <option value="">— Selecteer —</option>
                {DOMAINS.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              {fieldErrors.domain && <p className="mt-1 text-sm text-red-600">{fieldErrors.domain}</p>}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Access level</label>
            <div className="space-y-2">
              {ACCESS_LEVELS.map((a) => (
                <label key={a.value} className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="access_level"
                    value={a.value}
                    checked={accessLevel === a.value}
                    onChange={() => setAccessLevel(a.value)}
                    className="mt-1"
                  />
                  <div>
                    <span className="font-medium text-slate-800">{a.label}</span>
                    <span className="text-slate-600"> — {a.desc}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Function tag</label>
            <input
              type="text"
              value={functionTag}
              onChange={(e) => setFunctionTag(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              placeholder="bijv. seo-strategist"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Summary</label>
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              maxLength={500}
              rows={3}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 ${fieldErrors.summary ? 'border-red-500' : 'border-slate-300'}`}
              placeholder="Korte samenvatting"
            />
            <p className="mt-1 text-xs text-slate-500">{summary.length}/500</p>
            {fieldErrors.summary && <p className="mt-1 text-sm text-red-600">{fieldErrors.summary}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Keywords</label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
                className="flex-1 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="Typ + Enter om toe te voegen"
              />
              <button type="button" onClick={addKeyword} className="px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700">
                Toevoegen
              </button>
            </div>
            {keywords.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {keywords.map((k, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-sm"
                  >
                    {k}
                    <button type="button" onClick={() => removeKeyword(i)} className="hover:text-red-600" aria-label="Verwijder">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
          {docType === 'client_context' && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Client slug</label>
              <input
                type="text"
                value={clientSlug}
                onChange={(e) => setClientSlug(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="leeg = agency-wide"
              />
            </div>
          )}
        </div>
      </section>

      {/* STAP 2 — Bronkeuze */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">2. Bron</h2>
        <div className="flex gap-2 mb-4">
          <button
            type="button"
            onClick={() => setSourceTab('url')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium ${sourceTab === 'url' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
          >
            <Link2 className="w-4 h-4" />
            URL
          </button>
          <button
            type="button"
            onClick={() => setSourceTab('file')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium ${sourceTab === 'file' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
          >
            <FileText className="w-4 h-4" />
            Bestand
          </button>
        </div>

        {sourceTab === 'url' && (
          <div className="max-w-xl">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 ${fieldErrors.url ? 'border-red-500' : 'border-slate-300'}`}
              placeholder="https://..."
            />
            {fieldErrors.url && <p className="mt-1 text-sm text-red-600">{fieldErrors.url}</p>}
          </div>
        )}

        {sourceTab === 'file' && (
          <div className="max-w-xl">
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragOver(false)
                const f = e.dataTransfer.files?.[0]
                if (f) {
                  if (f.size <= MAX_FILE_SIZE) {
                    setFile(f)
                    setFieldErrors((err) => ({ ...err, file: undefined }))
                  } else {
                    setFile(null)
                    setFieldErrors((err) => ({ ...err, file: 'Bestand mag maximaal 10MB zijn' }))
                  }
                }
              }}
              className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
                dragOver ? 'border-indigo-400 bg-indigo-50' : 'border-slate-300 bg-slate-50'
              }`}
            >
              <input
                type="file"
                accept={ACCEPTED_TYPES}
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) {
                    if (f.size > MAX_FILE_SIZE) {
                      setFile(null)
                      setFieldErrors((err) => ({ ...err, file: 'Bestand mag maximaal 10MB zijn' }))
                    } else {
                      setFile(f)
                      setFieldErrors((err) => ({ ...err, file: undefined }))
                    }
                  }
                }}
                className="hidden"
                id="knowledge-file-input"
              />
              <label htmlFor="knowledge-file-input" className="cursor-pointer">
                {file ? (
                  <p className="text-slate-700 font-medium">{file.name}</p>
                ) : (
                  <>
                    <Upload className="w-10 h-10 mx-auto text-slate-400 mb-2" />
                    <p className="text-slate-600">Sleep een bestand hierheen of klik om te kiezen</p>
                  </>
                )}
              </label>
              <p className="mt-2 text-sm text-slate-500">{ACCEPTED_TYPES_DESC}</p>
              {fieldErrors.file && <p className="mt-2 text-sm text-red-600">{fieldErrors.file}</p>}
            </div>
          </div>
        )}
      </section>

      {/* STAP 3 — Voortgang of Upload knop */}
      <section>
        {uploading ? (
          <div className="space-y-3 max-w-xl">
            {PROGRESS_STEPS.map((s) => (
              <div key={s.id} className="flex items-center gap-3">
                {progressStep > s.id ? (
                  <Check className="w-5 h-5 text-green-600 flex-shrink-0" />
                ) : progressStep === s.id ? (
                  <Loader2 className="w-5 h-5 text-indigo-600 animate-spin flex-shrink-0" />
                ) : (
                  <div className="w-5 h-5 rounded-full border-2 border-slate-300 flex-shrink-0" />
                )}
                <span className={progressStep >= s.id ? 'text-slate-800' : 'text-slate-400'}>
                  {s.label}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <button
            type="button"
            onClick={doUpload}
            disabled={!metadataComplete || !sourceReady}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Upload className="w-4 h-4" />
            Upload
          </button>
        )}
      </section>
    </PageLayout>
  )
}
