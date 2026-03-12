import { useState, useCallback, useEffect } from 'react'
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Link2, FileText, Loader2, X, ArrowLeft } from 'lucide-react'

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

export default function KnowledgeEdit() {
  const { id } = useParams()
  const authReady = useAuthReady()
  const navigate = useNavigate()
  const location = useLocation()

  const [doc, setDoc] = useState(null)
  const [loading, setLoading] = useState(true)
  const [title, setTitle] = useState('')
  const [docType, setDocType] = useState('')
  const [domain, setDomain] = useState('')
  const [accessLevel, setAccessLevel] = useState('reference')
  const [functionTag, setFunctionTag] = useState('')
  const [summary, setSummary] = useState('')
  const [keywords, setKeywords] = useState([])
  const [keywordInput, setKeywordInput] = useState('')
  const [clientSlug, setClientSlug] = useState('')

  const [sourceChanged, setSourceChanged] = useState(false)
  const [replaceSourceTab, setReplaceSourceTab] = useState('url')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  const [saving, setSaving] = useState(false)
  const [processingEmbeddings, setProcessingEmbeddings] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})

  const fetchDoc = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch(`/api/knowledge/${id}`)
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.status === 404) {
        setError('Document niet gevonden')
        setDoc(null)
        return
      }
      if (res.ok) {
        const data = await res.json()
        setDoc(data)
        setTitle(data.title || '')
        setDocType(data.doc_type || '')
        setDomain(data.domain || '')
        setAccessLevel(data.access_level || 'reference')
        setFunctionTag(data.function_tag || '')
        setSummary(data.summary || '')
        setKeywords(Array.isArray(data.keywords) ? data.keywords : [])
        setClientSlug(data.client_slug || '')
        if (data.source_url) setUrl(data.source_url)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [id, navigate, location])

  useEffect(() => {
    if (!authReady || !id) return
    fetchDoc()
  }, [authReady, id, fetchDoc])

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

  const validate = useCallback(() => {
    const errs = {}
    if (!title.trim()) errs.title = 'Title is verplicht'
    if (!docType) errs.docType = 'Doc type is verplicht'
    if (!domain) errs.domain = 'Domain is verplicht'
    if (sourceChanged && replaceSourceTab === 'url' && !url.trim().startsWith('http')) errs.url = 'Voer een geldige URL in'
    if (sourceChanged && replaceSourceTab === 'file' && !file) errs.file = 'Selecteer een bestand'
    if (sourceChanged && replaceSourceTab === 'file' && file && file.size > MAX_FILE_SIZE) errs.file = 'Bestand mag maximaal 10MB zijn'
    if (summary.length > 500) errs.summary = 'Max 500 tekens'
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }, [title, docType, domain, sourceChanged, replaceSourceTab, url, file, summary])

  const doSave = useCallback(async () => {
    if (!validate()) return
    setSaving(true)
    setError('')
    try {
      if (sourceChanged && replaceSourceTab === 'file' && file) {
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

        const res = await apiFetch(`/api/knowledge/${id}/replace-content`, {
          method: 'POST',
          headers: {},
          body: fd,
        })
        if (res.status === 401) {
          navigate('/login', { state: { from: location } })
          return
        }
        if (!res.ok) {
          const j = await res.json().catch(() => ({}))
          setError(j.detail || 'Opslaan mislukt')
          setSaving(false)
          return
        }
        const data = await res.json()
        setDoc(data)
        setProcessingEmbeddings(true)
      } else {
        const body = {
          title: title.trim(),
          doc_type: docType,
          domain,
          function_tag: functionTag || 'general',
          access_level: accessLevel,
          summary: summary.trim() || null,
          keywords: keywords.length ? keywords : null,
          client_slug: docType === 'client_context' ? (clientSlug.trim() || null) : null,
        }
        if (sourceChanged && replaceSourceTab === 'url' && url.trim().startsWith('http')) {
          body.source_url = url.trim()
        }
        const res = await apiFetch(`/api/knowledge/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (res.status === 401) {
          navigate('/login', { state: { from: location } })
          return
        }
        if (!res.ok) {
          const j = await res.json().catch(() => ({}))
          setError(j.detail || 'Opslaan mislukt')
          setSaving(false)
          return
        }
        const data = await res.json()
        setDoc(data)
        if (data.embedding_status === 'pending' || data.embedding_status === 'processing') {
          setProcessingEmbeddings(true)
        } else {
          navigate(`/knowledge/${id}`)
        }
      }
    } catch (err) {
      setError(err.message || 'Opslaan mislukt')
    } finally {
      setSaving(false)
    }
  }, [
    id, title, docType, domain, accessLevel, functionTag, summary, keywords, clientSlug,
    sourceChanged, replaceSourceTab, url, file, validate, navigate, location,
  ])

  // Poll embedding_status when processing
  useEffect(() => {
    if (!processingEmbeddings || !id) return
    const interval = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/knowledge/${id}`)
        if (!res.ok) return
        const data = await res.json()
        setDoc(data)
        if (data.embedding_status === 'complete') {
          setProcessingEmbeddings(false)
          navigate(`/knowledge/${id}`)
        }
        if (data.embedding_status === 'failed') {
          setProcessingEmbeddings(false)
          setError('Embeddings genereren mislukt.')
        }
      } catch (_) {}
    }, 3000)
    return () => clearInterval(interval)
  }, [processingEmbeddings, id, navigate])

  if (!authReady) return null
  if (loading) {
    return (
      <PageLayout size="medium" padded>
        <div className="flex items-center gap-2 text-slate-600">
          <Loader2 className="w-5 h-5 animate-spin" />
          Document laden...
        </div>
      </PageLayout>
    )
  }
  if (!doc) {
    return (
      <PageLayout size="medium" padded>
        {error && <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700">{error}</div>}
        <Link to="/knowledge" className="text-indigo-600 hover:underline">Terug naar bibliotheek</Link>
      </PageLayout>
    )
  }

  const currentSourceLabel = doc.source_type === 'url' && doc.source_url
    ? doc.source_url
    : 'Uploaded file'

  if (processingEmbeddings) {
    return (
      <PageLayout size="medium" padded>
        <div className="mb-6 p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 flex items-center gap-3">
          <Loader2 className="w-6 h-6 flex-shrink-0 animate-spin" />
          <div>
            <p className="font-medium">Embeddings genereren...</p>
            <p className="text-sm mt-1">Wacht tot de embeddings klaar zijn; je wordt doorgestuurd.</p>
          </div>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout size="medium" padded>
      <div className="mb-6 flex items-center gap-3">
        <Link to={`/knowledge/${id}`} className="text-slate-600 hover:text-slate-900">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-2xl font-bold text-slate-900">Document bewerken</h1>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
          {error}
        </div>
      )}

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
                    name="access_level_edit"
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

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">2. Bron</h2>
        {!sourceChanged ? (
          <div className="max-w-xl flex items-center gap-3">
            <div className="flex-1 px-3 py-2 rounded-lg bg-slate-100 text-slate-700 text-sm truncate" title={currentSourceLabel}>
              {currentSourceLabel}
            </div>
            <button
              type="button"
              onClick={() => setSourceChanged(true)}
              className="px-4 py-2 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-700 font-medium"
            >
              Vervang bron
            </button>
          </div>
        ) : (
          <>
            <div className="flex gap-2 mb-4">
              <button
                type="button"
                onClick={() => setReplaceSourceTab('url')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium ${replaceSourceTab === 'url' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
              >
                <Link2 className="w-4 h-4" />
                URL
              </button>
              <button
                type="button"
                onClick={() => setReplaceSourceTab('file')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium ${replaceSourceTab === 'file' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
              >
                <FileText className="w-4 h-4" />
                Bestand
              </button>
            </div>
            {replaceSourceTab === 'url' && (
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
            {replaceSourceTab === 'file' && (
              <div className="max-w-xl">
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault()
                    setDragOver(false)
                    const f = e.dataTransfer.files?.[0]
                    if (f && f.size <= MAX_FILE_SIZE) setFile(f)
                  }}
                  className={`border-2 border-dashed rounded-xl p-6 text-center ${dragOver ? 'border-indigo-400 bg-indigo-50' : 'border-slate-300 bg-slate-50'}`}
                >
                  <input
                    type="file"
                    accept={ACCEPTED_TYPES}
                    onChange={(e) => { const f = e.target.files?.[0]; if (f && f.size <= MAX_FILE_SIZE) setFile(f) }}
                    className="hidden"
                    id="knowledge-edit-file"
                  />
                  <label htmlFor="knowledge-edit-file" className="cursor-pointer">
                    {file ? <p className="text-slate-700 font-medium">{file.name}</p> : <p className="text-slate-600">Kies bestand ({ACCEPTED_TYPES_DESC})</p>}
                  </label>
                  {fieldErrors.file && <p className="mt-2 text-sm text-red-600">{fieldErrors.file}</p>}
                </div>
              </div>
            )}
          </>
        )}
      </section>

      <section>
        <button
          type="button"
          onClick={doSave}
          disabled={saving}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          Opslaan
        </button>
      </section>
    </PageLayout>
  )
}
