import { useState, useEffect, useCallback } from 'react'
import { Link, useParams, useNavigate, useLocation } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Plus, ArrowLeft, Lock, LockKeyhole } from 'lucide-react'

import { apiFetch } from './apiClient'
import { useAuthReady } from './useAuthReady'

const DOC_TYPE_BADGE = {
  client_context: 'bg-orange-100 text-orange-700',
}

const STATUS_BADGE = {
  draft: 'bg-gray-100 text-gray-700',
  approved: 'bg-green-100 text-green-700',
  stale: 'bg-orange-100 text-orange-700',
  archived: 'bg-red-100 text-red-700',
}

function formatRelative(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now - d
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins} min ago`
  if (diffHours < 24) return `${diffHours} hours ago`
  if (diffDays < 7) return `${diffDays} days ago`
  return d.toLocaleDateString()
}

function clientStatusIndicator(docs) {
  const hasStale = docs.some((d) => d.status === 'stale')
  const hasDraft = docs.some((d) => d.status === 'draft')
  if (hasStale) return { color: 'bg-red-500', title: 'Eén of meer stale' }
  if (hasDraft) return { color: 'bg-orange-500', title: 'Eén of meer draft' }
  return { color: 'bg-green-500', title: 'Alles approved' }
}

export default function ClientIntelligence() {
  const { client_slug } = useParams()
  const authReady = useAuthReady()
  const navigate = useNavigate()
  const location = useLocation()
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchDocuments = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      params.set('doc_type', 'client_context')
      params.set('limit', '200')
      if (client_slug) params.set('client_slug', client_slug)
      const res = await apiFetch(`/api/knowledge?${params}`)
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setDocuments(data)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      console.error('Failed to load documents:', err)
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [client_slug, navigate, location])

  useEffect(() => {
    if (!authReady) return
    fetchDocuments()
  }, [authReady, fetchDocuments])

  // Niveau 1: client overzicht — groepeer op client_slug
  const clientGroups = documents.reduce((acc, doc) => {
    const slug = doc.client_slug || '_none'
    if (!acc[slug]) acc[slug] = []
    acc[slug].push(doc)
    return acc
  }, {})

  const clients = Object.entries(clientGroups)
    .filter(([slug]) => slug !== '_none')
    .map(([slug, docs]) => ({
      client_slug: slug,
      docs,
      total: docs.length,
      approved: docs.filter((d) => d.status === 'approved').length,
      lastUpdated: docs.reduce((max, d) => {
        const t = d.updated_at ? new Date(d.updated_at).getTime() : 0
        return t > max ? t : max
      }, 0),
    }))
    .sort((a, b) => b.lastUpdated - a.lastUpdated)

  if (!authReady) return null

  // Niveau 2: client detail
  if (client_slug) {
    const uploadUrl = `/knowledge/upload?doc_type=client_context&client_slug=${encodeURIComponent(client_slug)}`
    return (
      <PageLayout size="wide" padded>
        <Link to="/knowledge/clients" className="inline-flex items-center gap-1 text-slate-600 hover:text-indigo-600 mb-6">
          <ArrowLeft className="w-4 h-4" /> Terug naar Client Intelligence
        </Link>

        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-slate-900">{client_slug}</h1>
          <Link
            to={uploadUrl}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Voeg document toe
          </Link>
        </div>

        {error && (
          <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="panel-card bg-white shadow-sm border border-slate-200 p-8 rounded-xl">
            Documenten laden...
          </div>
        ) : documents.length === 0 ? (
          <div className="panel-card bg-white shadow-sm border border-slate-200 p-12 rounded-xl text-center text-slate-500">
            Geen documenten voor deze client. Voeg een document toe om te beginnen.
          </div>
        ) : (
          <div className="grid gap-4">
            {documents.map((doc) => (
              <Link
                key={doc.document_id}
                to={`/knowledge/${doc.document_id}`}
                state={{ from: `/knowledge/clients/${encodeURIComponent(client_slug)}` }}
                className="block p-4 rounded-xl border border-slate-200 bg-white hover:border-indigo-300 hover:shadow-md transition-all"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="font-semibold text-slate-900 truncate">{doc.title || 'Untitled'}</h3>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded ${DOC_TYPE_BADGE[doc.doc_type] || 'bg-gray-100 text-gray-700'}`}>
                        {doc.doc_type}
                      </span>
                      <span className="px-2 py-0.5 text-xs font-medium rounded bg-slate-100 text-slate-600">
                        {doc.domain}
                      </span>
                      <span className={`px-2 py-0.5 text-xs font-medium rounded ${STATUS_BADGE[doc.status] || 'bg-gray-100 text-gray-700'}`}>
                        {doc.status}
                      </span>
                      {doc.access_level === 'approved' && (
                        <Lock className="w-3.5 h-3.5 inline text-green-600 ml-0.5" aria-label="approved" />
                      )}
                      {doc.access_level === 'restricted' && (
                        <LockKeyhole className="w-3.5 h-3.5 inline text-red-600 ml-0.5" aria-label="restricted" />
                      )}
                    </div>
                    {doc.summary && (
                      <p className="mt-2 text-sm text-slate-600 line-clamp-2">{doc.summary}</p>
                    )}
                    <p className="mt-2 text-xs text-slate-400">
                      {formatRelative(doc.updated_at)}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </PageLayout>
    )
  }

  // Niveau 1: client overzicht
  return (
    <PageLayout size="wide" padded>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Client Intelligence</h1>
        <Link
          to="/knowledge/upload?doc_type=client_context"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Voeg client context toe
        </Link>
      </div>

      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="panel-card bg-white shadow-sm border border-slate-200 p-8 rounded-xl">
          Clients laden...
        </div>
      ) : clients.length === 0 ? (
        <div className="panel-card bg-white shadow-sm border border-slate-200 p-12 rounded-xl text-center text-slate-500">
          Geen clients met kennisdocumenten. Upload een client_context document om te beginnen.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {clients.map((c) => {
            const status = clientStatusIndicator(c.docs)
            return (
              <Link
                key={c.client_slug}
                to={`/knowledge/clients/${encodeURIComponent(c.client_slug)}`}
                className="block p-4 rounded-xl border border-slate-200 bg-white hover:border-indigo-300 hover:shadow-md transition-all"
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`w-3 h-3 rounded-full flex-shrink-0 mt-1.5 ${status.color}`}
                    title={status.title}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <h3 className="font-semibold text-slate-900">{c.client_slug}</h3>
                    <p className="mt-1 text-sm text-slate-600">
                      {c.total} documenten · {c.approved} goedgekeurd
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                      {formatRelative(c.lastUpdated ? new Date(c.lastUpdated).toISOString() : null)}
                    </p>
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </PageLayout>
  )
}
