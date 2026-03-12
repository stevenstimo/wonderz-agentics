import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import PageLayout from './PageLayout'
import { ArrowLeft, Check, Archive, AlertTriangle, Lock, Trash2, X } from 'lucide-react'

import { apiFetch } from './apiClient'
import { useAuthReady } from './useAuthReady'

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

function formatDate(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleString()
}

export default function KnowledgeDetail() {
  const { id } = useParams()
  const authReady = useAuthReady()
  const navigate = useNavigate()
  const location = useLocation()
  const [doc, setDoc] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [approveModal, setApproveModal] = useState(false)
  const [archiveModal, setArchiveModal] = useState(false)
  const [changeNote, setChangeNote] = useState('')
  const [secondApprover, setSecondApprover] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [relatedDocs, setRelatedDocs] = useState([])
  const [deleteOverlayOpen, setDeleteOverlayOpen] = useState(false)
  const [deleteConfirmInput, setDeleteConfirmInput] = useState('')
  const [deleting, setDeleting] = useState(false)

  const CONFIRM_DELETE_TEXT = 'DELETE'

  const fetchDocument = async () => {
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
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      console.error('Failed to load document:', err)
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!authReady || !id) return
    fetchDocument()
  }, [authReady, id, navigate, location])

  const fetchRelatedDocs = useCallback(async (docIds) => {
    if (!docIds || docIds.length === 0) return []
    const results = await Promise.allSettled(
      docIds.map((docId) => apiFetch(`/api/knowledge/${docId}`).then((r) => (r.ok ? r.json() : null)))
    )
    return results.map((r) => (r.status === 'fulfilled' && r.value ? r.value : null)).filter(Boolean)
  }, [])

  useEffect(() => {
    if (doc?.doc_type === 'skill_spec' && doc?.related_docs?.length > 0) {
      fetchRelatedDocs(doc.related_docs).then(setRelatedDocs)
    } else {
      setRelatedDocs([])
    }
  }, [doc?.doc_type, doc?.related_docs, fetchRelatedDocs])

  const handleApprove = async () => {
    if (doc?.doc_type === 'policy' && !secondApprover.trim()) {
      setActionError('Policy documents require second_approver')
      return
    }
    setSubmitting(true)
    setActionError('')
    try {
      const body = { change_note: changeNote || 'approved' }
      if (doc?.doc_type === 'policy') body.second_approver = secondApprover
      const res = await apiFetch(`/api/knowledge/${id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        setApproveModal(false)
        setChangeNote('')
        setSecondApprover('')
        fetchDocument()
      } else {
        const j = await res.json().catch(() => ({}))
        setActionError(j.detail || 'Approve mislukt')
      }
    } catch (err) {
      setActionError(err.message || 'Approve mislukt')
    } finally {
      setSubmitting(false)
    }
  }

  const handleArchive = async () => {
    setSubmitting(true)
    setActionError('')
    try {
      const res = await apiFetch(`/api/knowledge/${id}/archive`, { method: 'POST' })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        setArchiveModal(false)
        fetchDocument()
      } else {
        const j = await res.json().catch(() => ({}))
        setActionError(j.detail || 'Archive mislukt')
      }
    } catch (err) {
      setActionError(err.message || 'Archive mislukt')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (deleteConfirmInput !== CONFIRM_DELETE_TEXT || !id) return
    setDeleting(true)
    setActionError('')
    try {
      const res = await apiFetch(`/api/knowledge/${id}`, { method: 'DELETE' })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        setActionError(j.detail || 'Verwijderen mislukt')
        setDeleting(false)
        return
      }
      setDeleteOverlayOpen(false)
      setDeleteConfirmInput('')
      const from = location.state?.from || (doc?.doc_type === 'skill_spec' ? '/knowledge/skills' : doc?.doc_type === 'client_context' ? '/knowledge/clients' : '/knowledge')
      navigate(from, { replace: true })
    } catch (err) {
      setActionError(err.message || 'Verwijderen mislukt')
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <PageLayout size="medium" padded>
        <div className="panel-card bg-white shadow-sm border border-slate-200 p-8 rounded-xl">
          Document laden...
        </div>
      </PageLayout>
    )
  }

  if (error || !doc) {
    return (
      <PageLayout size="medium" padded>
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200">
          {error || 'Document niet gevonden'}
        </div>
        <Link to="/knowledge" className="text-indigo-600 hover:underline flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" /> Terug naar Library
        </Link>
      </PageLayout>
    )
  }

  const isPolicy = doc.doc_type === 'policy'
  const showApprove = doc.status === 'draft' || doc.status === 'stale'
  const showArchive = doc.status === 'approved'
  const showReapprove = doc.status === 'stale'

  return (
    <PageLayout size="medium" padded>
      <Link
        to={location.state?.from || (doc.doc_type === 'skill_spec' ? '/knowledge/skills' : doc.doc_type === 'client_context' ? '/knowledge/clients' : '/knowledge')}
        className="inline-flex items-center gap-1 text-slate-600 hover:text-indigo-600 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        {location.state?.from
          ? 'Terug'
          : doc.doc_type === 'skill_spec'
            ? 'Terug naar Skill Factory'
            : doc.doc_type === 'client_context'
              ? 'Terug naar Client Intelligence'
              : 'Terug naar Library'}
      </Link>

      {/* Stale banner */}
      {doc.status === 'stale' && (
        <div className="mb-6 p-4 rounded-lg bg-orange-50 border border-orange-200 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-orange-600 flex-shrink-0" />
          <span className="text-orange-800">Dit document vereist een herziening</span>
        </div>
      )}

      {/* Archived banner */}
      {doc.status === 'archived' && (
        <div className="mb-6 p-4 rounded-lg bg-red-50 border border-red-200 flex items-center gap-2">
          <Lock className="w-5 h-5 text-red-600 flex-shrink-0" />
          <span className="text-red-800">Gearchiveerd — niet beschikbaar voor agents</span>
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Sectie A — Document info */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap gap-2 mb-4">
            <span className={`px-2.5 py-1 text-sm font-medium rounded ${DOC_TYPE_BADGE[doc.doc_type] || 'bg-gray-100 text-gray-700'}`}>
              {doc.doc_type}
            </span>
            <span className="px-2.5 py-1 text-sm font-medium rounded bg-slate-100 text-slate-600">
              {doc.domain}
            </span>
            <span className={`px-2.5 py-1 text-sm font-medium rounded ${STATUS_BADGE[doc.status] || 'bg-gray-100 text-gray-700'}`}>
              {doc.status}
            </span>
          </div>

          <h1 className="text-2xl font-bold text-slate-900 mb-6">{doc.title || 'Untitled'}</h1>

          <div className="overflow-x-auto mb-6">
            <table className="min-w-full text-sm">
              <tbody className="divide-y divide-slate-200">
                <tr><td className="py-2 font-medium text-slate-500 w-40">Owner</td><td>{doc.owner || '—'}</td></tr>
                <tr><td className="py-2 font-medium text-slate-500">Version</td><td>{doc.version ?? '—'}</td></tr>
                <tr><td className="py-2 font-medium text-slate-500">Access level</td><td>{doc.access_level || '—'}</td></tr>
                <tr><td className="py-2 font-medium text-slate-500">Created</td><td>{formatDate(doc.created_at)}</td></tr>
                <tr><td className="py-2 font-medium text-slate-500">Last reviewed</td><td>{formatDate(doc.last_reviewed)}</td></tr>
                <tr><td className="py-2 font-medium text-slate-500">Review interval</td><td>{doc.review_interval_days ?? '—'} days</td></tr>
              </tbody>
            </table>
          </div>

          {doc.summary && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-slate-700 mb-2">Summary</h3>
              <p className="text-slate-600">{doc.summary}</p>
            </div>
          )}

          {doc.keywords && doc.keywords.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-slate-700 mb-2">Keywords</h3>
              <div className="flex flex-wrap gap-1.5">
                {doc.keywords.map((k) => (
                  <span key={k} className="px-2 py-0.5 text-xs rounded-full bg-slate-100 text-slate-700">
                    {k}
                  </span>
                ))}
              </div>
            </div>
          )}

          <p className="text-sm text-slate-500">
            {doc.chunk_count ?? 0} chunks geïndexeerd
          </p>
        </div>

        {/* Sectie B — Acties */}
        <div className="w-full lg:w-64 flex-shrink-0 space-y-3">
          {showApprove && (
            <button
              type="button"
              onClick={() => setApproveModal(true)}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-green-600 text-white font-medium hover:bg-green-700 disabled:opacity-50"
            >
              <Check className="w-4 h-4" />
              {showReapprove ? 'Re-approve' : 'Approve'}
            </button>
          )}
          {showArchive && (
            <button
              type="button"
              onClick={() => setArchiveModal(true)}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-slate-600 text-white font-medium hover:bg-slate-700"
            >
              <Archive className="w-4 h-4" />
              Archive
            </button>
          )}
          <button
            type="button"
            onClick={() => { setDeleteOverlayOpen(true); setDeleteConfirmInput(''); setActionError('') }}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-red-200 bg-red-50 text-red-700 font-medium hover:bg-red-100"
          >
            <Trash2 className="w-4 h-4" />
            Delete book
          </button>
        </div>
      </div>

      {/* Sectie D — Bronbestanden (alleen voor skill_spec) */}
      {doc.doc_type === 'skill_spec' && (
        <div className="mt-12">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Bronbestanden</h2>
          {relatedDocs.length === 0 && (!doc.related_docs || doc.related_docs.length === 0) ? (
            <p className="text-slate-500">Geen bronbestanden</p>
          ) : relatedDocs.length === 0 && doc.related_docs?.length > 0 ? (
            <p className="text-slate-500">Bronbestanden laden...</p>
          ) : (
            <ul className="space-y-2">
              {relatedDocs.map((rd) => (
                <li key={rd.document_id} className="flex items-center gap-3 p-3 rounded-lg border border-slate-200 bg-slate-50/50">
                  <Link to={`/knowledge/${rd.document_id}`} className="font-medium text-indigo-600 hover:underline flex-1 min-w-0 truncate">
                    {rd.title || 'Untitled'}
                  </Link>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded flex-shrink-0 ${STATUS_BADGE[rd.status] || 'bg-gray-100 text-gray-700'}`}>
                    {rd.status}
                  </span>
                  <span className="text-xs text-slate-500 flex-shrink-0">v{rd.version ?? '—'}</span>
                  {(rd.status === 'stale' || rd.status === 'archived') && (
                    <span className={`px-2 py-0.5 text-xs font-medium rounded flex-shrink-0 ${rd.status === 'archived' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'}`}>
                      ⚠ Dit bronbestand is gewijzigd
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Sectie C — Versiehistorie */}
      <div className="mt-12">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Versiehistorie</h2>
        {doc.versions && doc.versions.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-slate-700">Version</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-700">Change note</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-700">Approved by</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-700">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {doc.versions.map((v) => (
                  <tr key={v.version_id}>
                    <td className="px-4 py-2">{v.version}</td>
                    <td className="px-4 py-2">{v.change_note || '—'}</td>
                    <td className="px-4 py-2">{v.approved_by || '—'}</td>
                    <td className="px-4 py-2">{formatDate(v.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-slate-500">Geen versiehistorie</p>
        )}
      </div>

      {/* Approve modal */}
      {approveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">{showReapprove ? 'Re-approve' : 'Approve'} document</h3>
            {actionError && (
              <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm">{actionError}</div>
            )}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Change note</label>
                <input
                  type="text"
                  value={changeNote}
                  onChange={(e) => setChangeNote(e.target.value)}
                  placeholder="eerste goedkeuring"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              {isPolicy && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Second approver (required for policy)</label>
                  <input
                    type="text"
                    value={secondApprover}
                    onChange={(e) => setSecondApprover(e.target.value)}
                    placeholder="user_id or email"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              )}
            </div>
            <div className="flex gap-3 mt-6">
              <button
                type="button"
                onClick={() => { setApproveModal(false); setActionError(''); setChangeNote(''); setSecondApprover('') }}
                className="flex-1 px-4 py-2.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApprove}
                disabled={submitting || (isPolicy && !secondApprover.trim())}
                className="flex-1 px-4 py-2.5 rounded-lg bg-green-600 text-white font-medium hover:bg-green-700 disabled:opacity-50"
              >
                {submitting ? 'Bezig...' : 'Approve'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Archive modal */}
      {archiveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">Archive document</h3>
            {actionError && (
              <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm">{actionError}</div>
            )}
            <p className="text-slate-600 mb-6">
              Dit document wordt gearchiveerd en is niet meer beschikbaar voor agents.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => { setArchiveModal(false); setActionError('') }}
                className="flex-1 px-4 py-2.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleArchive}
                disabled={submitting}
                className="flex-1 px-4 py-2.5 rounded-lg bg-red-600 text-white font-medium hover:bg-red-700 disabled:opacity-50"
              >
                {submitting ? 'Bezig...' : 'Archive'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete book overlay */}
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
            {actionError && (
              <div className="mt-3 p-3 rounded-lg bg-red-50 text-red-700 text-sm">{actionError}</div>
            )}
            <div className="flex gap-3 mt-6">
              <button
                type="button"
                onClick={() => { setDeleteOverlayOpen(false); setDeleteConfirmInput(''); setActionError('') }}
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
