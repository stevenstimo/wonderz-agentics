import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import PageLayout from './PageLayout'
import { Search, Plus, Lock, LockKeyhole, Pencil } from 'lucide-react'

import { fetchJson } from './apiClient'
import { useAuthReady } from './useAuthReady'
import { queryKeys } from './queryKeys'

const DOMAINS = ['all', 'growth', 'gtm', 'sales', 'delivery', 'ai_systems', 'core']
const DOC_TYPES = [
  'all', 'playbook', 'sop', 'framework', 'template', 'case_study',
  'policy', 'research', 'client_context', 'skill_spec',
]
const STATUSES = ['all', 'draft', 'approved', 'stale', 'archived']

const DOC_TYPE_BADGE = {
  playbook: 'bg-indigo-100 text-indigo-700',
  sop: 'bg-blue-100 text-blue-700',
  framework: 'bg-purple-100 text-purple-700',
  template: 'bg-yellow-100 text-yellow-700',
  policy: 'bg-red-100 text-red-700',
  case_study: 'bg-green-100 text-green-700',
  research: 'bg-gray-100 text-gray-700',
  client_context: 'bg-orange-100 text-orange-700',
  skill_spec: 'bg-pink-100 text-pink-700',
}

const STATUS_BADGE = {
  draft: 'bg-gray-100 text-gray-700',
  approved: 'bg-green-100 text-green-700',
  stale: 'bg-orange-100 text-orange-700',
  archived: 'bg-red-100 text-red-700',
}

/** embedding_status from knowledge_documents (fire-and-forget lifecycle) */
const EMBEDDING_BADGE = {
  pending: { label: 'Embeddings: wachten', className: 'bg-slate-100 text-slate-600' },
  processing: { label: 'Embeddings: bezig', className: 'bg-blue-100 text-blue-800' },
  complete: { label: 'Embeddings: klaar', className: 'bg-emerald-100 text-emerald-800' },
  failed: { label: 'Embeddings: mislukt', className: 'bg-red-100 text-red-800' },
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

export default function KnowledgeLibrary() {
  const { authReady } = useAuthReady()
  const [search, setSearch] = useState('')
  const [domain, setDomain] = useState('all')
  const [docType, setDocType] = useState('all')
  const [status, setStatus] = useState('all')

  const params = new URLSearchParams()
  if (search.trim()) params.set('search', search.trim())
  if (domain !== 'all') params.set('domain', domain)
  if (docType !== 'all') params.set('doc_type', docType)
  if (status !== 'all') params.set('status', status)
  params.set('limit', '50')
  const endpoint = `/api/knowledge?${params}`

  const {
    data: documents = [],
    isLoading: loading,
    error,
    refetch,
  } = useQuery({
    queryKey: queryKeys.knowledge({ search, domain, docType, status, limit: 50 }),
    queryFn: () => fetchJson(endpoint),
    enabled: authReady,
  })

  return (
    <PageLayout size="wide" padded>
      <div className="flex gap-6">
        {/* Filters sidebar */}
        <aside className="w-56 flex-shrink-0 space-y-4">
          <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">
            Filters
          </h2>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Zoeken</label>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onBlur={() => refetch()}
                onKeyDown={(e) => e.key === 'Enter' && refetch()}
                placeholder="title, summary, keywords"
                className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Domain</label>
            <select
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              {DOMAINS.map((d) => (
                <option key={d} value={d}>{d === 'all' ? 'All' : d}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Doc type</label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              {DOC_TYPES.map((t) => (
                <option key={t} value={t}>{t === 'all' ? 'All' : t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Status</label>
            <div className="flex flex-wrap gap-1">
              {STATUSES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStatus(s)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-full transition-colors ${
                    status === s
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {s === 'all' ? 'All' : s}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* Document list */}
        <main className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-bold text-slate-900">Knowledge Library</h1>
            <Link
              to="/knowledge/upload"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Write Book
            </Link>
          </div>

          {error && (
            <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
              {error.message || 'Laden mislukt'}
            </div>
          )}

          {loading ? (
            <div className="panel-card bg-white shadow-sm border border-slate-200 p-8 rounded-xl">
              Documents laden...
            </div>
          ) : documents.length === 0 ? (
            <div className="panel-card bg-white shadow-sm border border-slate-200 p-12 rounded-xl text-center text-slate-500">
              Geen documenten gevonden. Upload een document om te beginnen.
            </div>
          ) : (
            <div className="grid gap-4">
              {documents.map((doc) => (
                <Link
                  key={doc.document_id}
                  to={`/knowledge/${doc.document_id}`}
                  className="block relative p-4 rounded-xl border border-slate-200 bg-white hover:border-indigo-300 hover:shadow-md transition-all"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <span className="absolute top-3 right-3 p-1.5 rounded-md text-slate-400 hover:text-indigo-600 hover:bg-indigo-50" aria-label="Bekijken / bewerken">
                        <Pencil className="w-4 h-4" />
                      </span>
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
                        {doc.embedding_status && EMBEDDING_BADGE[doc.embedding_status] && (
                          <span
                            className={`px-2 py-0.5 text-xs font-medium rounded ${EMBEDDING_BADGE[doc.embedding_status].className}`}
                            title="Status van chunking/embeddings op de achtergrond"
                          >
                            {EMBEDDING_BADGE[doc.embedding_status].label}
                          </span>
                        )}
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
        </main>
      </div>
    </PageLayout>
  )
}
