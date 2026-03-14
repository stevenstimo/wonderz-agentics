import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import {
  Globe,
  MapPin,
  FileText,
  Type,
  Package,
  Plus,
  MoreVertical,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
} from 'lucide-react'
import { apiFetch } from './apiClient'

const SOURCE_TYPES = [
  { id: 'website_crawl', label: 'Website crawlen', desc: 'Zoekt alle pagina\'s op het domein', icon: Globe },
  { id: 'website_sitemap', label: 'Sitemap indienen', desc: 'Verwerkt alle URLs uit sitemap.xml', icon: MapPin },
  { id: 'file', label: 'Bestand uploaden (PDF of CSV)', icon: FileText },
  { id: 'text', label: 'Tekst invoeren', icon: Type },
  { id: 'product_feed', label: 'Product feed', desc: 'XML feed URL + splitting tag', icon: Package },
]

function SourceIcon({ type }) {
  const t = SOURCE_TYPES.find((x) => x.id === type)
  const Icon = t?.icon || FileText
  return <Icon className="w-5 h-5 text-slate-500" />
}

export default function ClientKnowledge() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [datasources, setDatasources] = useState([])
  const [knowledge, setKnowledge] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [modalStep, setModalStep] = useState(1)
  const [form, setForm] = useState({
    name: '',
    source_type: 'website_crawl',
    domain: '',
    sitemap_url: '',
    raw_text: '',
    feed_url: '',
    feed_splitting_tag: 'item',
    feed_identifier_tag: 'g:id',
  })
  const [submitting, setSubmitting] = useState(false)
  const [menuId, setMenuId] = useState(null)
  const [pollingIds, setPollingIds] = useState(new Set())
  const [processingStatus, setProcessingStatus] = useState({})

  const fetchDatasources = useCallback(async () => {
    if (!slug) return
    try {
      const res = await apiFetch(`/api/clients/${slug}/datasources`)
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) setDatasources(await res.json())
    } catch (e) {
      setError(e.message || 'Laden mislukt')
    }
  }, [slug, navigate, location])

  const fetchKnowledge = useCallback(async () => {
    if (!slug) return
    try {
      const res = await apiFetch(`/api/clients/${slug}/knowledge`)
      if (res.ok) setKnowledge(await res.json())
    } catch (_) {}
  }, [slug])

  useEffect(() => {
    if (!slug) return
    setLoading(true)
    setError('')
    Promise.all([fetchDatasources(), fetchKnowledge()]).finally(() => setLoading(false))
  }, [slug, fetchDatasources, fetchKnowledge])

  // Start polling for any datasource that is already processing (e.g. after refresh)
  useEffect(() => {
    const processing = datasources.filter((ds) => ds.status === 'processing').map((ds) => ds.id)
    if (processing.length === 0) return
    setPollingIds((prev) => {
      const next = new Set(prev)
      processing.forEach((id) => next.add(id))
      return next
    })
  }, [datasources])

  // Poll status for processing datasources
  useEffect(() => {
    if (!slug || pollingIds.size === 0) return
    const t = setInterval(async () => {
      for (const id of pollingIds) {
        try {
          const res = await apiFetch(`/api/clients/${slug}/datasources/${id}/status`)
          if (res.ok) {
            const s = await res.json()
            setProcessingStatus((prev) => ({ ...prev, [id]: s }))
            if (s.status === 'done' || s.status === 'failed') {
              setPollingIds((prev) => {
                const next = new Set(prev)
                next.delete(id)
                return next
              })
            }
          }
        } catch (_) {}
      }
      fetchDatasources()
      fetchKnowledge()
    }, 3000)
    return () => clearInterval(t)
  }, [slug, pollingIds, fetchDatasources, fetchKnowledge])

  const createDatasource = async () => {
    setSubmitting(true)
    setError('')
    try {
      const body = {
        name: form.name.trim() || form.source_type,
        source_type: form.source_type,
        domain: form.source_type === 'website_crawl' ? (form.domain || '').trim() || undefined : undefined,
        sitemap_url: form.source_type === 'website_sitemap' ? (form.sitemap_url || '').trim() || undefined : undefined,
        raw_text: form.source_type === 'text' ? (form.raw_text || '').trim() || undefined : undefined,
        feed_url: form.source_type === 'product_feed' ? (form.feed_url || '').trim() || undefined : undefined,
        feed_splitting_tag: form.source_type === 'product_feed' ? (form.feed_splitting_tag || 'item').trim() : undefined,
        feed_identifier_tag: form.source_type === 'product_feed' ? (form.feed_identifier_tag || 'g:id').trim() : undefined,
      }
      const res = await apiFetch(`/api/clients/${slug}/datasources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Aanmaken mislukt')
        return
      }
      const data = await res.json()
      const datasourceId = data.datasource_id

      if (form.source_type === 'file') {
        setMenuId(datasourceId)
      } else if (datasourceId && form.source_type !== 'text') {
        await startProcess(datasourceId)
      } else if (form.source_type === 'text' && body.raw_text) {
        await startProcess(datasourceId)
      }

      setModalOpen(false)
      setModalStep(1)
      setForm({ name: '', source_type: 'website_crawl', domain: '', sitemap_url: '', raw_text: '', feed_url: '', feed_splitting_tag: 'item', feed_identifier_tag: 'g:id' })
      await fetchDatasources()
    } catch (e) {
      setError(e?.message || 'Aanmaken mislukt')
    } finally {
      setSubmitting(false)
    }
  }

  const startProcess = async (datasourceId) => {
    const res = await apiFetch(`/api/clients/${slug}/datasources/${datasourceId}/process`, { method: 'POST' })
    if (!res.ok) {
      const j = await res.json().catch(() => ({}))
      throw new Error(j.detail || 'Verwerken starten mislukt')
    }
    setPollingIds((prev) => new Set(prev).add(datasourceId))
    await fetchDatasources()
  }

  const uploadFile = async (datasourceId, file) => {
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    try {
      const res = await apiFetch(`/api/clients/${slug}/datasources/${datasourceId}/upload`, {
        method: 'POST',
        body: fd,
      })
      if (res.ok) setPollingIds((prev) => new Set(prev).add(datasourceId))
      setMenuId(null)
      fetchDatasources()
    } catch (_) {}
  }

  const deleteDatasource = async (id) => {
    if (!confirm('Deze kennisbron en alle chunks verwijderen?')) return
    try {
      await apiFetch(`/api/clients/${slug}/datasources/${id}`, { method: 'DELETE' })
      setMenuId(null)
      fetchDatasources()
      fetchKnowledge()
    } catch (_) {}
  }

  const statusLabel = (ds) => {
    if (ds.status === 'processing') return 'Bezig...'
    if (ds.status === 'failed') return 'Mislukt'
    if (ds.status === 'done') return `${ds.chunks_created ?? 0} chunks`
    return 'In wachtrij'
  }

  if (loading) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 className="w-5 h-5 animate-spin" />
          Kennisbronnen laden...
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Kennisbronnen</h2>
        <button
          type="button"
          onClick={() => { setModalOpen(true); setModalStep(1); setError(''); }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700"
        >
          <Plus className="w-4 h-4" />
          Bron toevoegen
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100">
        {datasources.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">
            Nog geen kennisbronnen. Klik op &quot;Bron toevoegen&quot; om te starten.
          </div>
        ) : (
          datasources.map((ds) => (
            <div
              key={ds.id}
              className={`p-4 flex items-center gap-4 ${ds.error_detail?.startsWith('Sitemap index:') ? 'pl-8 border-l-4 border-indigo-200 bg-indigo-50/50' : ''}`}
            >
              <SourceIcon type={ds.source_type} />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-slate-800 truncate">{ds.name}</p>
                <p className="text-sm text-slate-500 flex items-center gap-2">
                  {ds.status === 'done' && <CheckCircle className="w-4 h-4 text-green-600" />}
                  {ds.status === 'failed' && <XCircle className="w-4 h-4 text-red-600" />}
                  {ds.status === 'processing' && <Loader2 className="w-4 h-4 text-indigo-600 animate-spin" />}
                  {statusLabel(ds)}
                  {ds.file_name && ` · ${ds.file_name}`}
                </p>
                {ds.status === 'processing' && processingStatus[ds.id] && (
                  <p className="text-xs mt-1 text-indigo-600">
                    🔄 Bezig... {processingStatus[ds.id].pages_processed ?? 0} / {processingStatus[ds.id].pages_found ?? 0} pagina&apos;s · {processingStatus[ds.id].chunks_created ?? 0} chunks aangemaakt
                  </p>
                )}
                {ds.error_detail && (
                  <p className="text-xs mt-1 text-amber-700 bg-amber-50 px-2 py-1 rounded">{ds.error_detail}</p>
                )}
              </div>
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setMenuId(menuId === ds.id ? null : ds.id)}
                  className="p-2 rounded hover:bg-slate-100 text-slate-500"
                  aria-label="Menu"
                >
                  <MoreVertical className="w-4 h-4" />
                </button>
                {menuId === ds.id && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setMenuId(null)} aria-hidden="true" />
                    <div className="absolute right-0 top-full mt-1 py-1 bg-white border border-slate-200 rounded-lg shadow-lg z-20 min-w-[160px]">
                      {ds.source_type === 'file' && (
                        <label className="block px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 cursor-pointer">
                          Bestand uploaden
                          <input
                            type="file"
                            accept=".pdf,.csv"
                            className="hidden"
                            onChange={(e) => {
                              const f = e.target.files?.[0]
                              if (f) uploadFile(ds.id, f)
                              setMenuId(null)
                            }}
                          />
                        </label>
                      )}
                      {ds.source_type !== 'file' && ds.status !== 'processing' && (
                        <button
                          type="button"
                          className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                          onClick={() => { startProcess(ds.id); setMenuId(null); }}
                        >
                          Opnieuw verwerken
                        </button>
                      )}
                      <button
                        type="button"
                        className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                        onClick={() => deleteDatasource(ds.id)}
                      >
                        Verwijderen
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {knowledge && (
        <div className="text-sm text-slate-500">
          Totaal: <strong className="text-slate-700">{knowledge.chunks_total}</strong> chunks
          {knowledge.datasources?.length > 0 && ` in ${knowledge.datasources.length} bron(nen)`}.
        </div>
      )}

      {/* Modal: add datasource */}
      {modalOpen && (
        <div className="fixed inset-0 z-30 flex items-center justify-center p-4 bg-black/50" onClick={() => !submitting && setModalOpen(false)}>
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-slate-200">
              <h3 className="text-lg font-semibold text-slate-800">Nieuwe kennisbron</h3>
            </div>
            <div className="p-6 space-y-4">
              {modalStep === 1 && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Naam</label>
                    <input
                      type="text"
                      value={form.name}
                      onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                      placeholder="bijv. Website, Algemene voorwaarden"
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <p className="block text-sm font-medium text-slate-700 mb-2">Type</p>
                    <div className="space-y-2">
                      {SOURCE_TYPES.map((t) => (
                        <label
                          key={t.id}
                          className={`flex items-start gap-3 p-3 border rounded-lg cursor-pointer ${
                            form.source_type === t.id ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 hover:bg-slate-50'
                          }`}
                        >
                          <input
                            type="radio"
                            name="source_type"
                            value={t.id}
                            checked={form.source_type === t.id}
                            onChange={() => setForm((f) => ({ ...f, source_type: t.id }))}
                            className="mt-1"
                          />
                          <div>
                            <span className="font-medium text-slate-800">{t.label}</span>
                            {t.desc && <p className="text-xs text-slate-500 mt-0.5">{t.desc}</p>}
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                </>
              )}
              {modalStep === 2 && (
                <>
                  {form.source_type === 'website_crawl' && (
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">URL / domein</label>
                      <input
                        type="text"
                        value={form.domain}
                        onChange={(e) => setForm((f) => ({ ...f, domain: e.target.value }))}
                        placeholder="https://www.asured.nl"
                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                      />
                    </div>
                  )}
                  {form.source_type === 'website_sitemap' && (
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">Sitemap URL</label>
                      <input
                        type="text"
                        value={form.sitemap_url}
                        onChange={(e) => setForm((f) => ({ ...f, sitemap_url: e.target.value }))}
                        placeholder="https://www.asured.nl/sitemap.xml"
                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                      />
                    </div>
                  )}
                  {form.source_type === 'text' && (
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">Tekst</label>
                      <textarea
                        value={form.raw_text}
                        onChange={(e) => setForm((f) => ({ ...f, raw_text: e.target.value }))}
                        rows={6}
                        placeholder="Plak hier de tekst..."
                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                      />
                    </div>
                  )}
                  {form.source_type === 'product_feed' && (
                    <>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Feed URL</label>
                        <input
                          type="text"
                          value={form.feed_url}
                          onChange={(e) => setForm((f) => ({ ...f, feed_url: e.target.value }))}
                          placeholder="https://www.asured.nl/feed.xml"
                          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Splitting tag (bijv. item)</label>
                        <input
                          type="text"
                          value={form.feed_splitting_tag}
                          onChange={(e) => setForm((f) => ({ ...f, feed_splitting_tag: e.target.value }))}
                          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Unieke identificator tag (bijv. g:id)</label>
                        <input
                          type="text"
                          value={form.feed_identifier_tag}
                          onChange={(e) => setForm((f) => ({ ...f, feed_identifier_tag: e.target.value }))}
                          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                        />
                      </div>
                    </>
                  )}
                  {form.source_type === 'file' && (
                    <p className="text-sm text-slate-600">
                      Na het aanmaken kun je via het menu bij de bron een PDF of CSV uploaden.
                    </p>
                  )}
                </>
              )}
            </div>
            <div className="p-6 border-t border-slate-200 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => modalStep === 1 ? setModalOpen(false) : setModalStep(1)}
                className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Annuleren
              </button>
              {modalStep === 1 ? (
                <button
                  type="button"
                  onClick={() => setModalStep(2)}
                  className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  Volgende
                </button>
              ) : (
                <button
                  type="button"
                  onClick={createDatasource}
                  disabled={submitting}
                  className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                >
                  {submitting ? 'Bezig...' : (form.source_type === 'file' ? 'Aanmaken' : 'Toevoegen')}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
