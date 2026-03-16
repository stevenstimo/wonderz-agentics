import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Check, Shield, Trash2 } from 'lucide-react'

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

const PERM_LEVEL_BADGE = {
  read: 'bg-green-100 text-green-700',
  write: 'bg-blue-100 text-blue-700',
  admin: 'bg-purple-100 text-purple-700',
  none: 'bg-red-100 text-red-700',
}

const DOMAINS = ['growth', 'gtm', 'sales', 'delivery', 'ai_systems', 'core']

const TABS = [
  { id: 'queue', label: 'Approval Queue' },
  { id: 'stale', label: 'Stale Documents' },
  { id: 'permissions', label: 'Permissions' },
  { id: 'audit', label: 'Audit Log' },
  { id: 'lessons', label: 'Lessons' },
  { id: 'usage', label: 'Gebruik' },
  { id: 'agent-health', label: 'Agent Health' },
]

const CONFIDENCE_BADGE = (score) => {
  if (score >= 0.90) return { cls: 'bg-green-100 text-green-700', label: 'Hoog' }
  if (score >= 0.70) return { cls: 'bg-blue-100 text-blue-700', label: 'Voldoende' }
  return { cls: 'bg-gray-100 text-gray-500', label: 'Afgekeurd' }
}

const LESSON_STATUS_BADGE = {
  active: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  superseded: 'bg-gray-100 text-gray-500',
  stale: 'bg-orange-100 text-orange-700',
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

function formatDate(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleString()
}

export default function KnowledgeGovernance() {
  const { authReady } = useAuthReady()
  const navigate = useNavigate()
  const location = useLocation()
  const [tab, setTab] = useState('queue')

  const [queueData, setQueueData] = useState(null)
  const [staleDocs, setStaleDocs] = useState([])
  const [permissions, setPermissions] = useState([])
  const [auditLog, setAuditLog] = useState([])
  const [agents, setAgents] = useState([])
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [deleteModal, setDeleteModal] = useState(null)
  const [addModal, setAddModal] = useState(false)
  const [addForm, setAddForm] = useState({
    agent_id: '',
    scope: 'agency',
    domain: '',
    document_id: '',
    doc_search: '',
    permission_level: 'read',
    valid_until: '',
  })
  const [submitting, setSubmitting] = useState(false)

  const [lessons, setLessons] = useState([])
  const [lessonsStatusFilter, setLessonsStatusFilter] = useState('all')
  const [lessonsMinConf, setLessonsMinConf] = useState(0)
  const [expandedLesson, setExpandedLesson] = useState(null)
  const [usageLog, setUsageLog] = useState([])
  const [governanceMetrics, setGovernanceMetrics] = useState({ agents: [] })
  const [suspendedAgents, setSuspendedAgents] = useState([])
  const [breachHistory, setBreachHistory] = useState([])
  const [governanceCheckResult, setGovernanceCheckResult] = useState(null)
  const [releaseModal, setReleaseModal] = useState({ agentId: null, approvedBy: '' })

  const fetchQueue = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/knowledge/governance/queue')
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setQueueData(data)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [navigate, location])

  const fetchStale = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/knowledge?status=stale&limit=200')
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setStaleDocs(data)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [navigate, location])

  const fetchPermissions = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/knowledge/permissions')
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setPermissions(data)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [navigate, location])

  const fetchAudit = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/knowledge/governance/audit?limit=50')
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setAuditLog(data)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [navigate, location])

  const fetchAgents = useCallback(async () => {
    try {
      const res = await apiFetch('/api/agents')
      if (res.ok) {
        const data = await res.json()
        setAgents(data?.agents || [])
      }
    } catch {
      setAgents([])
    }
  }, [])

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await apiFetch('/api/knowledge?limit=200')
      if (res.ok) {
        const data = await res.json()
        setDocuments(data)
      }
    } catch {
      setDocuments([])
    }
  }, [])

  const fetchLessons = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (lessonsStatusFilter !== 'all') params.set('status', lessonsStatusFilter)
      if (lessonsMinConf > 0) params.set('min_confidence', String(lessonsMinConf))
      const qs = params.toString()
      const res = await apiFetch(`/api/knowledge/governance/lessons${qs ? `?${qs}` : ''}`)
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setLessons(data)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [navigate, location, lessonsStatusFilter, lessonsMinConf])

  const fetchUsage = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/knowledge/governance/usage?limit=50')
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setUsageLog(data)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [navigate, location])

  const fetchGovernanceMetrics = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/governance/metrics')
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setGovernanceMetrics(data)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [navigate, location])

  const fetchSuspendedAgents = useCallback(async () => {
    try {
      const res = await apiFetch('/api/governance/suspended')
      if (res.ok) {
        const data = await res.json()
        setSuspendedAgents(Array.isArray(data) ? data : [])
      }
    } catch {
      setSuspendedAgents([])
    }
  }, [])

  const fetchBreachHistory = useCallback(async () => {
    try {
      const res = await apiFetch('/api/governance/breaches?limit=20')
      if (res.ok) {
        const data = await res.json()
        setBreachHistory(Array.isArray(data) ? data : [])
      }
    } catch {
      setBreachHistory([])
    }
  }, [])

  const runGovernanceCheck = useCallback(async () => {
    setError('')
    setGovernanceCheckResult(null)
    try {
      const res = await apiFetch('/api/governance/run-check', { method: 'POST' })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setGovernanceCheckResult(data)
        fetchGovernanceMetrics()
        fetchSuspendedAgents()
        fetchBreachHistory()
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Run check mislukt')
      }
    } catch (err) {
      setError(err.message || 'Run check mislukt')
    }
  }, [navigate, location, fetchGovernanceMetrics, fetchSuspendedAgents, fetchBreachHistory])

  useEffect(() => {
    if (!authReady) return
    if (tab === 'queue') fetchQueue()
    else if (tab === 'stale') fetchStale()
    else if (tab === 'permissions') {
      fetchPermissions()
      fetchAgents()
      fetchDocuments()
    }
    else if (tab === 'audit') fetchAudit()
    else if (tab === 'lessons') fetchLessons()
    else if (tab === 'usage') fetchUsage()
    else if (tab === 'agent-health') {
      fetchGovernanceMetrics()
      fetchSuspendedAgents()
      fetchBreachHistory()
    }
  }, [authReady, tab, fetchQueue, fetchStale, fetchPermissions, fetchAudit, fetchAgents, fetchDocuments, fetchLessons, fetchUsage, fetchGovernanceMetrics, fetchSuspendedAgents, fetchBreachHistory])

  const handleDeletePermission = async () => {
    if (!deleteModal) return
    setSubmitting(true)
    setError('')
    try {
      const res = await apiFetch(`/api/knowledge/permissions/${deleteModal}`, { method: 'DELETE' })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        setDeleteModal(null)
        fetchPermissions()
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Verwijderen mislukt')
      }
    } catch (err) {
      setError(err.message || 'Verwijderen mislukt')
    } finally {
      setSubmitting(false)
    }
  }

  const handleReleaseSuspension = async () => {
    if (!releaseModal.agentId || !releaseModal.approvedBy.trim()) return
    setSubmitting(true)
    setError('')
    try {
      const res = await apiFetch(`/api/governance/release/${encodeURIComponent(releaseModal.agentId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved_by: releaseModal.approvedBy.trim() }),
      })
      if (res.ok) {
        setReleaseModal({ agentId: null, approvedBy: '' })
        fetchSuspendedAgents()
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Vrijgeven mislukt')
      }
    } catch (err) {
      setError(err.message || 'Vrijgeven mislukt')
    } finally {
      setSubmitting(false)
    }
  }

  const handleAddPermission = async () => {
    if (!addForm.agent_id) {
      setError('Selecteer een agent')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const body = {
        agent_id: addForm.agent_id,
        permission_level: addForm.permission_level,
        domain: addForm.scope === 'domain' ? addForm.domain || null : null,
        document_id: addForm.scope === 'document' ? addForm.document_id || null : null,
        valid_until: addForm.valid_until || null,
      }
      const res = await apiFetch('/api/knowledge/permissions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        setAddModal(false)
        setAddForm({ agent_id: '', scope: 'agency', domain: '', document_id: '', doc_search: '', permission_level: 'read', valid_until: '' })
        fetchPermissions()
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Opslaan mislukt')
      }
    } catch (err) {
      setError(err.message || 'Opslaan mislukt')
    } finally {
      setSubmitting(false)
    }
  }

  if (!authReady) return null

  const queueDocs = queueData?.documents || []
  const totalWaiting = (queueData?.draft || 0) + (queueData?.stale || 0)

  return (
    <PageLayout size="wide" padded>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Knowledge Governance</h1>

      <div className="flex gap-2 mb-6">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              tab === t.id ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
          {error}
        </div>
      )}

      {/* Tab 1: Approval Queue */}
      {tab === 'queue' && (
        <div>
          <div className="mb-4 flex items-center gap-2">
            <span className="px-3 py-1 rounded-full bg-amber-100 text-amber-800 text-sm font-medium">
              {totalWaiting} documenten wachten op goedkeuring
            </span>
          </div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : queueDocs.length === 0 ? (
            <div className="p-8 rounded-xl border border-slate-200 bg-green-50 text-center">
              <Check className="w-12 h-12 text-green-600 mx-auto mb-2" />
              <p className="text-green-800 font-medium">Geen documenten in de wachtrij</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Title</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Type</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Domain</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Access</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Wacht sinds</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {queueDocs.map((doc) => (
                    <tr key={doc.document_id} className="hover:bg-slate-50">
                      <td className="px-4 py-2">
                        <Link to={`/knowledge/${doc.document_id}`} className="font-medium text-indigo-600 hover:underline">
                          {doc.title || 'Untitled'}
                        </Link>
                        {doc.doc_type === 'policy' && (
                          <span className="ml-2 px-2 py-0.5 text-xs font-medium rounded bg-orange-100 text-orange-700">
                            4-eyes vereist
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${DOC_TYPE_BADGE[doc.doc_type] || 'bg-gray-100 text-gray-700'}`}>
                          {doc.doc_type}
                        </span>
                      </td>
                      <td className="px-4 py-2">{doc.domain}</td>
                      <td className="px-4 py-2">{doc.access_level}</td>
                      <td className="px-4 py-2 text-slate-500">{formatRelative(doc.updated_at)}</td>
                      <td className="px-4 py-2">
                        <Link
                          to={`/knowledge/${doc.document_id}`}
                          className="text-indigo-600 hover:underline font-medium"
                        >
                          Bekijk & Keur goed
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Stale Documents */}
      {tab === 'stale' && (
        <div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : staleDocs.length === 0 ? (
            <div className="p-8 rounded-xl border border-slate-200 bg-green-50 text-center">
              <Check className="w-12 h-12 text-green-600 mx-auto mb-2" />
              <p className="text-green-800 font-medium">Alle documenten zijn up-to-date</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Title</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Type</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Domain</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Version</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Last reviewed</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Reden stale</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {staleDocs.map((doc) => (
                    <tr key={doc.document_id} className="hover:bg-slate-50">
                      <td className="px-4 py-2 font-medium">{doc.title || 'Untitled'}</td>
                      <td className="px-4 py-2">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${DOC_TYPE_BADGE[doc.doc_type] || 'bg-gray-100 text-gray-700'}`}>
                          {doc.doc_type}
                        </span>
                      </td>
                      <td className="px-4 py-2">{doc.domain}</td>
                      <td className="px-4 py-2">{doc.version ?? '—'}</td>
                      <td className="px-4 py-2">{formatDate(doc.last_reviewed)}</td>
                      <td className="px-4 py-2 text-slate-600 text-xs">
                        {doc.doc_type === 'skill_spec'
                          ? 'Brondocument gewijzigd'
                          : `Review interval verstreken (elke ${doc.review_interval_days ?? 180} dagen)`}
                      </td>
                      <td className="px-4 py-2">
                        <Link to={`/knowledge/${doc.document_id}`} className="text-indigo-600 hover:underline font-medium">
                          Herzie
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Permissions */}
      {tab === 'permissions' && (
        <div>
          <div className="flex justify-end mb-4">
            <button
              type="button"
              onClick={() => { setAddModal(true); setError('') }}
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700"
            >
              Nieuwe regel toevoegen
            </button>
          </div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : (
            <>
              <div className="overflow-x-auto rounded-lg border border-slate-200 mb-8">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Agent / Role</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Scope</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Level</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Granted by</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Valid until</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {permissions.map((p) => (
                      <tr key={p.permission_id} className="hover:bg-slate-50">
                        <td className="px-4 py-2">{p.agent_id || p.role || '—'}</td>
                        <td className="px-4 py-2">
                          {p.document_id ? (p.doc_title || p.document_id) : p.domain ? `domain: ${p.domain}` : 'Agency-wide'}
                        </td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${PERM_LEVEL_BADGE[p.permission_level] || 'bg-gray-100 text-gray-700'}`}>
                            {p.permission_level}
                          </span>
                        </td>
                        <td className="px-4 py-2">{p.granted_by || '—'}</td>
                        <td className="px-4 py-2">{formatDate(p.valid_until)}</td>
                        <td className="px-4 py-2">
                          <button
                            type="button"
                            onClick={() => setDeleteModal(p.permission_id)}
                            className="text-red-600 hover:underline flex items-center gap-1"
                          >
                            <Trash2 className="w-4 h-4" /> Verwijder
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {permissions.length === 0 && (
                <p className="text-slate-500">Geen permission regels</p>
              )}
            </>
          )}
        </div>
      )}

      {/* Tab 4: Audit Log */}
      {tab === 'audit' && (
        <div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Document</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Type</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Versie</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Actie</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Door</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Goedgekeurd door</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Datum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {auditLog.map((r) => (
                    <tr key={r.version_id} className="hover:bg-slate-50">
                      <td className="px-4 py-2">
                        <Link to={`/knowledge/${r.document_id}`} className="font-medium text-indigo-600 hover:underline">
                          {r.title || 'Untitled'}
                        </Link>
                      </td>
                      <td className="px-4 py-2">{r.doc_type}</td>
                      <td className="px-4 py-2">{r.version}</td>
                      <td className="px-4 py-2">{r.change_note || '—'}</td>
                      <td className="px-4 py-2">{r.created_by || '—'}</td>
                      <td className="px-4 py-2">{r.approved_by || '—'}</td>
                      <td className="px-4 py-2">{formatDate(r.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Lessons */}
      {tab === 'lessons' && (
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <div className="flex gap-1">
              {['all', 'active', 'rejected'].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setLessonsStatusFilter(s)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    lessonsStatusFilter === s ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {s === 'all' ? 'Alle' : s}
                </button>
              ))}
            </div>
            <select
              value={lessonsMinConf}
              onChange={(e) => setLessonsMinConf(Number(e.target.value))}
              className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm"
            >
              <option value={0}>Alle confidence</option>
              <option value={0.90}>&ge; 0.90</option>
              <option value={0.70}>&ge; 0.70</option>
            </select>
          </div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : lessons.length === 0 ? (
            <div className="p-8 rounded-xl border border-slate-200 bg-slate-50 text-center">
              <p className="text-slate-600">Nog geen lessons beschikbaar.</p>
              <p className="text-slate-400 text-sm mt-1">Lessons worden aangemaakt na voltooide agent-taken.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Lesson ID</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Agent</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Domain</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Confidence</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Status</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Datum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {lessons.map((l) => {
                    const conf = CONFIDENCE_BADGE(l.confidence_score ?? 0)
                    const isExpanded = expandedLesson === l.lesson_id
                    return (
                      <tr
                        key={l.lesson_id}
                        className="hover:bg-slate-50 cursor-pointer"
                        onClick={() => setExpandedLesson(isExpanded ? null : l.lesson_id)}
                      >
                        <td className="px-4 py-2 font-mono text-xs">{l.lesson_id}</td>
                        <td className="px-4 py-2">{l.agent_id || '—'}</td>
                        <td className="px-4 py-2">{l.domain || '—'}</td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${conf.cls}`}>
                            {(l.confidence_score ?? 0).toFixed(2)} — {conf.label}
                          </span>
                        </td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${LESSON_STATUS_BADGE[l.status] || 'bg-gray-100 text-gray-500'}`}>
                            {l.status}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-slate-500">{formatDate(l.created_at)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {expandedLesson && (() => {
                const l = lessons.find((x) => x.lesson_id === expandedLesson)
                if (!l) return null
                return (
                  <div className="border-t border-slate-200 bg-slate-50 px-6 py-4 space-y-2 text-sm">
                    <p><span className="font-medium text-slate-700">Title:</span> {l.title}</p>
                    <p><span className="font-medium text-slate-700">Gevonden:</span> {l.gevonden}</p>
                    <p><span className="font-medium text-slate-700">Oorzaak:</span> {l.oorzaak}</p>
                    <p><span className="font-medium text-slate-700">Fix:</span> {l.fix}</p>
                  </div>
                )
              })()}
            </div>
          )}
        </div>
      )}

      {/* Tab 6: Gebruik (Knowledge Usage) */}
      {tab === 'usage' && (
        <div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : usageLog.length === 0 ? (
            <div className="p-8 rounded-xl border border-slate-200 bg-slate-50 text-center">
              <p className="text-slate-600">Nog geen gebruik geregistreerd.</p>
              <p className="text-slate-400 text-sm mt-1">Knowledge Centre wordt gebruikt zodra agents taken uitvoeren.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Datum</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Agent</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Job</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Chunks gebruikt</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Lessons gebruikt</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {usageLog.map((r) => (
                    <tr key={r.log_id} className="hover:bg-slate-50">
                      <td className="px-4 py-2 text-slate-500">{formatDate(r.created_at)}</td>
                      <td className="px-4 py-2">{r.agent_id || '—'}</td>
                      <td className="px-4 py-2 max-w-xs truncate" title={r.job_title || ''}>{r.job_title || '—'}</td>
                      <td className="px-4 py-2">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${r.chunks_used > 0 ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'}`}>
                          {r.chunks_used}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${r.lessons_used > 0 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                          {r.lessons_used}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 7: Agent Health */}
      {tab === 'agent-health' && (
        <div className="space-y-8">
          {/* Sectie A: Talent Agent Metrics + Run Check */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-800">Talent Agent Metrics</h2>
              <button
                type="button"
                onClick={runGovernanceCheck}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700"
              >
                Run Governance Check
              </button>
            </div>
            {governanceCheckResult && (
              <div className="mb-4 p-3 rounded-lg bg-indigo-50 text-indigo-800 text-sm">
                Check voltooid: {governanceCheckResult.breaches_found} breach(es), {governanceCheckResult.agents_suspended} gesuspendeerd
                {governanceCheckResult.tasks_blocked > 0 && `, ${governanceCheckResult.tasks_blocked} tasks geblokkeerd`}
                {governanceCheckResult.duration_ms != null && ` (${governanceCheckResult.duration_ms} ms)`}
              </div>
            )}
            {loading ? (
              <p className="text-slate-500">Laden...</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Agent</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Reviews</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Approval Rate</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Evidence Rate</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {(governanceMetrics.agents || []).map((a) => {
                      const approvalPct = a.approval_rate != null ? Math.round(a.approval_rate * 100) : null
                      const evidencePct = a.evidence_verification_rate != null ? Math.round(a.evidence_verification_rate * 100) : null
                      const statusBadge = a.monitoring_status === 'HIGH_RISK_RUBBER_STAMP'
                        ? { cls: 'bg-red-100 text-red-700', label: 'Rubber Stamp Risico' }
                        : { cls: 'bg-green-100 text-green-700', label: 'Normaal' }
                      const approvalRed = approvalPct != null && approvalPct > 85
                      const evidenceRed = evidencePct != null && evidencePct < 70
                      return (
                        <tr key={a.talent_agent_id || ''} className="hover:bg-slate-50">
                          <td className="px-4 py-2 font-medium">{a.talent_agent_id || '—'}</td>
                          <td className="px-4 py-2">{a.total_reviews ?? '—'}</td>
                          <td className={`px-4 py-2 ${approvalRed ? 'text-red-600 font-medium' : ''}`}>
                            {approvalPct != null ? `${approvalPct}%` : '—'}
                          </td>
                          <td className={`px-4 py-2 ${evidenceRed ? 'text-red-600 font-medium' : ''}`}>
                            {evidencePct != null ? `${evidencePct}%` : '—'}
                          </td>
                          <td className="px-4 py-2">
                            <span className={`px-2 py-0.5 text-xs font-medium rounded ${statusBadge.cls}`}>
                              {statusBadge.label}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                {(governanceMetrics.agents || []).length === 0 && (
                  <p className="px-4 py-4 text-slate-500">Geen metrics (min. 5 reviews per agent).</p>
                )}
              </div>
            )}
          </section>

          {/* Sectie B: Gesuspendeerde Agents */}
          <section>
            <h2 className="text-lg font-semibold text-slate-800 mb-4">Gesuspendeerde Agents</h2>
            {suspendedAgents.length === 0 ? (
              <div className="p-6 rounded-xl border border-slate-200 bg-green-50 text-center">
                <Check className="w-10 h-10 text-green-600 mx-auto mb-2" />
                <p className="text-green-800 font-medium">Geen gesuspendeerde agents</p>
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Agent</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Gesuspendeerd op</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700">Reden</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-700"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {suspendedAgents.map((s) => (
                      <tr key={s.agent_id} className="hover:bg-slate-50">
                        <td className="px-4 py-2 font-medium">{s.agent_id}</td>
                        <td className="px-4 py-2 text-slate-600">{formatDate(s.suspended_at)}</td>
                        <td className="px-4 py-2 text-slate-600 max-w-md truncate" title={s.suspension_reason}>{s.suspension_reason || '—'}</td>
                        <td className="px-4 py-2">
                          <button
                            type="button"
                            onClick={() => setReleaseModal({ agentId: s.agent_id, approvedBy: '' })}
                            className="text-indigo-600 hover:underline font-medium"
                          >
                            Vrijgeven
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Sectie C: Breach History */}
          <section>
            <h2 className="text-lg font-semibold text-slate-800 mb-4">Breach History</h2>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Datum</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Agent</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Type</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Approval Rate</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Evidence Rate</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Actie</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {breachHistory.map((b) => {
                    const typeBadge = b.breach_type === 'HIGH_RISK_RUBBER_STAMP'
                      ? { cls: 'bg-red-100 text-red-700', label: b.breach_type }
                      : { cls: 'bg-orange-100 text-orange-700', label: b.breach_type }
                    return (
                      <tr key={b.breach_id} className="hover:bg-slate-50">
                        <td className="px-4 py-2 text-slate-600">{formatDate(b.created_at)}</td>
                        <td className="px-4 py-2">{b.talent_agent_id || '—'}</td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${typeBadge.cls}`}>
                            {typeBadge.label}
                          </span>
                        </td>
                        <td className="px-4 py-2">{b.approval_rate != null ? `${Math.round(b.approval_rate * 100)}%` : '—'}</td>
                        <td className="px-4 py-2">{b.evidence_verification_rate != null ? `${Math.round(b.evidence_verification_rate * 100)}%` : '—'}</td>
                        <td className="px-4 py-2">{b.action_taken || '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {breachHistory.length === 0 && (
                <p className="px-4 py-4 text-slate-500">Geen breach history.</p>
              )}
            </div>
          </section>
        </div>
      )}

      {/* Release suspension modal */}
      {releaseModal.agentId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">Vrijgeven: {releaseModal.agentId}</h3>
            <label className="block text-sm font-medium text-slate-700 mb-2">Vrijgegeven door *</label>
            <input
              type="text"
              value={releaseModal.approvedBy}
              onChange={(e) => setReleaseModal((m) => ({ ...m, approvedBy: e.target.value }))}
              placeholder="Naam"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg mb-4"
            />
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setReleaseModal({ agentId: null, approvedBy: '' })}
                className="flex-1 px-4 py-2.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Annuleren
              </button>
              <button
                type="button"
                onClick={handleReleaseSuspension}
                disabled={submitting || !releaseModal.approvedBy.trim()}
                className="flex-1 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50"
              >
                {submitting ? 'Bezig...' : 'Vrijgeven'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation modal */}
      {deleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">Permission verwijderen</h3>
            <p className="text-slate-600 mb-6">Weet je zeker dat je deze regel wilt verwijderen?</p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setDeleteModal(null)}
                className="flex-1 px-4 py-2.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Annuleren
              </button>
              <button
                type="button"
                onClick={handleDeletePermission}
                disabled={submitting}
                className="flex-1 px-4 py-2.5 rounded-lg bg-red-600 text-white font-medium hover:bg-red-700 disabled:opacity-50"
              >
                {submitting ? 'Bezig...' : 'Verwijderen'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add permission modal */}
      {addModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">Nieuwe permission regel</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Agent *</label>
                <select
                  value={addForm.agent_id}
                  onChange={(e) => setAddForm((f) => ({ ...f, agent_id: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">— Selecteer agent —</option>
                  {agents.map((a) => (
                    <option key={a.agent_id} value={a.agent_id}>
                      {a.name || a.agent_id} ({a.role || ''})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Scope</label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="scope"
                      checked={addForm.scope === 'agency'}
                      onChange={() => setAddForm((f) => ({ ...f, scope: 'agency', domain: '', document_id: '' }))}
                    />
                    Agency-wide
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="scope"
                      checked={addForm.scope === 'domain'}
                      onChange={() => setAddForm((f) => ({ ...f, scope: 'domain', document_id: '' }))}
                    />
                    Per domein
                  </label>
                  {addForm.scope === 'domain' && (
                    <select
                      value={addForm.domain}
                      onChange={(e) => setAddForm((f) => ({ ...f, domain: e.target.value }))}
                      className="ml-6 w-full px-3 py-2 border border-slate-300 rounded-lg"
                    >
                      <option value="">— Selecteer —</option>
                      {DOMAINS.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  )}
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="scope"
                      checked={addForm.scope === 'document'}
                      onChange={() => setAddForm((f) => ({ ...f, scope: 'document', domain: '' }))}
                    />
                    Per document
                  </label>
                  {addForm.scope === 'document' && (
                    <select
                      value={addForm.document_id}
                      onChange={(e) => setAddForm((f) => ({ ...f, document_id: e.target.value }))}
                      className="ml-6 w-full px-3 py-2 border border-slate-300 rounded-lg"
                    >
                      <option value="">— Selecteer document —</option>
                      {documents.map((d) => (
                        <option key={d.document_id} value={d.document_id}>
                          {d.title || 'Untitled'} ({d.doc_type})
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Permission level</label>
                <select
                  value={addForm.permission_level}
                  onChange={(e) => setAddForm((f) => ({ ...f, permission_level: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                >
                  <option value="read">read</option>
                  <option value="write">write</option>
                  <option value="admin">admin</option>
                  <option value="none">none</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Valid until (optioneel)</label>
                <input
                  type="date"
                  value={addForm.valid_until}
                  onChange={(e) => setAddForm((f) => ({ ...f, valid_until: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                type="button"
                onClick={() => { setAddModal(false); setError('') }}
                className="flex-1 px-4 py-2.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Annuleren
              </button>
              <button
                type="button"
                onClick={handleAddPermission}
                disabled={submitting}
                className="flex-1 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50"
              >
                {submitting ? 'Bezig...' : 'Opslaan'}
              </button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
