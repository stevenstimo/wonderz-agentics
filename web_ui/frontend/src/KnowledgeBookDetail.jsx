/**
 * Book (knowledge document) detail page.
 * Route: /knowledge/:documentId — add to your router, e.g.:
 *   <Route path="/knowledge/:documentId" element={<KnowledgeBookDetail />} />
 */
import { useState, useEffect, useCallback } from 'react'
import { Link, useParams, useNavigate, useLocation } from 'react-router-dom'
import PageLayout from './PageLayout'
import { ArrowLeft, Trash2, X } from 'lucide-react'
import { apiFetch } from './apiClient'
import { useAuthReady } from './useAuthReady'

const CONFIRM_DELETE_TEXT = 'DELETE'

export default function KnowledgeBookDetail() {
  const { documentId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const authReady = useAuthReady()
  const [doc, setDoc] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deleteOverlayOpen, setDeleteOverlayOpen] = useState(false)
  const [deleteConfirmInput, setDeleteConfirmInput] = useState('')
  const [deleting, setDeleting] = useState(false)

  const fetchDoc = useCallback(async () => {
    if (!documentId) return
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch(`/api/knowledge/${documentId}`)
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Document niet gevonden')
        setDoc(null)
        return
      }
      const data = await res.json()
      setDoc(data)
    } catch (err) {
      setError(err.message || 'Laden mislukt')
      setDoc(null)
    } finally {
      setLoading(false)
    }
  }, [documentId, navigate, location])

  useEffect(() => {
    if (!authReady) return
    fetchDoc()
  }, [authReady, fetchDoc])

  const openDeleteOverlay = () => {
    setDeleteConfirmInput('')
    setDeleteOverlayOpen(true)
  }

  const closeDeleteOverlay = () => {
    setDeleteOverlayOpen(false)
    setDeleteConfirmInput('')
  }

  const handleDelete = async () => {
    if (deleteConfirmInput !== CONFIRM_DELETE_TEXT || !documentId) return
    setDeleting(true)
    try {
      const res = await apiFetch(`/api/knowledge/${documentId}`, { method: 'DELETE' })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Verwijderen mislukt')
        setDeleting(false)
        return
      }
      closeDeleteOverlay()
      const from = location.state?.from || '/knowledge'
      navigate(from, { replace: true })
    } catch (err) {
      setError(err.message || 'Verwijderen mislukt')
      setDeleting(false)
    }
  }

  if (!authReady || loading) {
    return (
      <PageLayout size="wide" padded>
        <div className="panel-card bg-white shadow-sm border border-slate-200 p-6 rounded-xl">
          Laden...
        </div>
      </PageLayout>
    )
  }

  if (error && !doc) {
    return (
      <PageLayout size="wide" padded>
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
          {error}
        </div>
        <Link to="/knowledge" className="inline-flex items-center gap-1 text-indigo-600 hover:underline">
          <ArrowLeft className="w-4 h-4" /> Terug naar Library
        </Link>
      </PageLayout>
    )
  }

  if (!doc) {
    return null
  }

  const backTo = location.state?.from || '/knowledge'

  return (
    <PageLayout size="wide" padded>
      <div className="mb-4">
        <Link
          to={backTo}
          className="inline-flex items-center gap-1 text-slate-600 hover:text-indigo-600"
        >
          <ArrowLeft className="w-4 h-4" /> Terug
        </Link>
      </div>

      <div className="panel-card bg-white shadow-sm border border-slate-200 rounded-xl overflow-hidden">
        <div className="p-6 border-b border-slate-200 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">{doc.title || 'Untitled book'}</h1>
            <p className="text-sm text-slate-500 mt-1">
              {doc.doc_type} · {doc.status} · {doc.chunk_count ?? 0} chunks
            </p>
          </div>
          <button
            type="button"
            onClick={openDeleteOverlay}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 font-medium text-sm"
          >
            <Trash2 className="w-4 h-4" /> Delete book
          </button>
        </div>

        <div className="p-6 space-y-4">
          {doc.source_url && (
            <p className="text-sm text-slate-600">
              <span className="font-medium">Source:</span>{' '}
              <a href={doc.source_url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline truncate block max-w-full">
                {doc.source_url}
              </a>
            </p>
          )}
          {doc.summary && (
            <p className="text-sm text-slate-700">{doc.summary}</p>
          )}
          <div className="text-sm text-slate-500">
            Versions: {doc.versions?.length ?? 0} · Updated: {doc.updated_at ? new Date(doc.updated_at).toLocaleString() : '-'}
          </div>
        </div>
      </div>

      {/* Delete confirmation overlay */}
      {deleteOverlayOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 border border-slate-200">
            <h2 className="text-lg font-semibold text-slate-900 mb-2">Book verwijderen</h2>
            <p className="text-slate-600 mb-4">
              Weet je zeker dat je dit book wilt deleten? Dit kan niet ongedaan worden gemaakt; er is geen backup.
            </p>
            <p className="text-sm text-slate-500 mb-2">Typ <strong>DELETE</strong> om te bevestigen:</p>
            <input
              type="text"
              value={deleteConfirmInput}
              onChange={(e) => setDeleteConfirmInput(e.target.value)}
              placeholder="DELETE"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500"
              autoFocus
            />
            <div className="flex gap-3 mt-6">
              <button
                type="button"
                onClick={closeDeleteOverlay}
                disabled={deleting}
                className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 font-medium"
              >
                <X className="w-4 h-4" /> Annuleren
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteConfirmInput !== CONFIRM_DELETE_TEXT || deleting}
                className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-red-600 text-white font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleting ? 'Bezig...' : 'Definitief verwijderen'}
              </button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
