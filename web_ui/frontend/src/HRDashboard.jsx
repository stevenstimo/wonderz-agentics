import React, { useEffect, useState, useCallback, useRef } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './apiClient'
import PageLayout from './PageLayout'
import { RefreshCw, Loader2 } from 'lucide-react'
import { useAuthReady } from './useAuthReady'
import { queryKeys } from './queryKeys'

const TABS = [
  { id: 'points', label: 'Development Points' },
  { id: 'training', label: 'Trainingsverzoeken' },
  { id: 'suggestions', label: 'Trainingssuggesties' },
  { id: 'improvements', label: 'Improvements' },
  { id: 'blocked-jobs', label: 'Blocked Jobs' },
  { id: 'cross', label: 'Cross-Training' },
]

const IMPACT_COLOR = { high: '#E74C3C', medium: '#E67E22', low: '#95A5A6' }
const IMPACT_BADGE = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-orange-100 text-orange-700',
  low: 'bg-gray-100 text-gray-500',
}

const STATUS_BADGE = {
  OPEN: 'bg-blue-100 text-blue-700',
  IN_TRAINING: 'bg-purple-100 text-purple-700',
  RESOLVED: 'bg-green-100 text-green-700',
  DISMISSED: 'bg-gray-100 text-gray-500',
  AWAITING_APPROVAL: 'bg-orange-100 text-orange-700',
}

/** Child route content for /hr/training-requests — rendered via <Outlet />. */
export function TrainingRequestsTabContent() {
  const { authReady } = useAuthReady()
  const [error, setError] = useState('')
  const [approveModalRequest, setApproveModalRequest] = useState(null)
  const [approveSourceUrl, setApproveSourceUrl] = useState('')
  const [rejectConfirmRequestId, setRejectConfirmRequestId] = useState(null)
  const [trainingActionLoading, setTrainingActionLoading] = useState(null)
  const [modalLoading, setModalLoading] = useState(false)
  const [trainingSuccessMessage, setTrainingSuccessMessage] = useState(null)
  const queryClient = useQueryClient()
  const {
    data: trainingRequests = [],
    isLoading: loading,
    error: queryError,
  } = useQuery({
    queryKey: queryKeys.trainingRequests({ status: 'PENDING' }),
    queryFn: async () => {
      const res = await apiFetch('/api/hr/training-requests?status=PENDING')
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Laden mislukt')
      const data = await res.json().catch(() => null)
      const list = Array.isArray(data) ? data : (data?.training_requests != null ? data.training_requests : [])
      return Array.isArray(list) ? list : []
    },
    enabled: authReady,
  })
  const approveMutation = useMutation({
    mutationFn: async ({ requestId, sourceUrl, approved }) => {
      const res = await apiFetch('/api/hr/approve-training', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request_id: requestId,
          approved,
          source_url: sourceUrl || undefined,
          approved_by: 'hr-dashboard',
        }),
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Request failed')
      return true
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.trainingRequests({ status: 'PENDING' }) })
    },
  })

  function openApproveModal(r) {
    if (!r || typeof r !== 'object') return
    setApproveModalRequest(r)
    setApproveSourceUrl(r.suggested_url ?? '')
    setError('')
  }

  async function confirmApproveTraining() {
    if (!approveModalRequest) return
    const id = approveModalRequest.request_id
    setTrainingActionLoading(id)
    setModalLoading(true)
    setError('')
    try {
      await approveMutation.mutateAsync({
        requestId: id,
        approved: true,
        sourceUrl: (approveSourceUrl ?? approveModalRequest?.suggested_url) || '',
      })
      const agentName = approveModalRequest?.agent_name ?? approveModalRequest?.agent_id ?? 'agent'
      setTrainingSuccessMessage(`Training gestart voor ${agentName}.`)
      setTimeout(() => setTrainingSuccessMessage(null), 5000)
      setApproveModalRequest(null)
      setApproveSourceUrl('')
    } catch (err) {
      setError(err?.message || 'Goedkeuren mislukt')
    } finally {
      setTrainingActionLoading(null)
      setModalLoading(false)
    }
  }

  function dismissTrainingRequest(requestId) {
    setRejectConfirmRequestId(requestId)
  }

  async function confirmRejectTraining() {
    const requestId = rejectConfirmRequestId
    if (!requestId) return
    setTrainingActionLoading(requestId)
    setModalLoading(true)
    setError('')
    try {
      await approveMutation.mutateAsync({
        requestId,
        approved: false,
        sourceUrl: '',
      })
      setRejectConfirmRequestId(null)
    } catch (err) {
      setError(err?.message || 'Afwijzen mislukt')
    } finally {
      setTrainingActionLoading(null)
      setModalLoading(false)
    }
  }

  if (!authReady) return null

  return (
    <div>
      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">{error}</div>
      )}
      {queryError && !error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">{queryError.message || 'Laden mislukt'}</div>
      )}
      {trainingSuccessMessage && (
        <div className="mb-4 p-4 rounded-lg bg-green-50 text-green-700 border border-green-200 text-sm">
          {trainingSuccessMessage}
        </div>
      )}
      {loading ? (
        <div className="flex items-center gap-2 text-slate-500 py-8">
          <Loader2 className="w-5 h-5 animate-spin shrink-0" />
          <span>Laden...</span>
        </div>
      ) : trainingRequests.length === 0 ? (
        <div className="p-8 rounded-xl border border-slate-200 bg-slate-50 text-center">
          <p className="text-slate-600">Geen openstaande trainingsverzoeken.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-slate-700">Agent</th>
                <th className="px-4 py-2 text-left font-medium text-slate-700">Rol</th>
                <th className="px-4 py-2 text-left font-medium text-slate-700">Reden</th>
                <th className="px-4 py-2 text-left font-medium text-slate-700">Confidence</th>
                <th className="px-4 py-2 text-left font-medium text-slate-700">Voorgestelde URL</th>
                <th className="px-4 py-2 text-left font-medium text-slate-700">Datum</th>
                <th className="px-4 py-2 text-left font-medium text-slate-700">Actie</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {(Array.isArray(trainingRequests) ? trainingRequests : [])
                .filter((r) => r != null && typeof r === 'object')
                .map((r, idx) => {
                  const id = r.request_id ?? r.point_id ?? r.id ?? `row-${idx}`
                  const isBusy = trainingActionLoading === id
                  const rawCreated = r.created_at
                  const created = rawCreated != null
                    ? (typeof rawCreated === 'string' ? new Date(rawCreated) : rawCreated)
                    : null
                  const isValidDate = created instanceof Date && !Number.isNaN(created.getTime())
                  const dateStr = isValidDate ? created.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'
                  return (
                  <tr key={id} className="hover:bg-slate-50">
                    <td className="px-4 py-2">{r.agent_name ?? r.agent_id ?? '—'}</td>
                    <td className="px-4 py-2">{r.role ?? '—'}</td>
                    <td className="px-4 py-2 max-w-xs">{r.reason ?? '—'}</td>
                    <td className="px-4 py-2">
                      {r.confidence_score != null ? (
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                          Number(r.confidence_score) >= 0.80 ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'
                        }`}>
                          {Math.round(Number(r.confidence_score) * 100)}%
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-500 max-w-xs truncate" title={r.suggested_url ?? ''}>{r.suggested_url ?? '—'}</td>
                    <td className="px-4 py-2 text-slate-600">{dateStr}</td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          disabled={isBusy}
                          onClick={() => openApproveModal(r != null ? r : undefined)}
                          className="text-xs font-medium text-green-600 hover:underline disabled:opacity-50 disabled:pointer-events-none"
                        >
                          Goedkeuren
                        </button>
                        <button
                          type="button"
                          disabled={isBusy}
                          onClick={() => dismissTrainingRequest(id)}
                          className="text-xs font-medium text-red-600 hover:underline disabled:opacity-50 disabled:pointer-events-none"
                        >
                          Afwijzen
                        </button>
                        {isBusy && <Loader2 className="w-4 h-4 animate-spin text-slate-400 shrink-0" />}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {approveModalRequest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" role="dialog" aria-modal="true" aria-labelledby="approve-modal-title">
          <div className="bg-white rounded-xl shadow-lg max-w-md w-full p-6 border border-slate-200">
            <h2 id="approve-modal-title" className="text-lg font-semibold text-slate-900 mb-3">Trainingsverzoek goedkeuren</h2>
            {error && (
              <div className="mb-3 p-3 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
                {error}
              </div>
            )}
            <div className="text-sm text-slate-600 space-y-2 mb-4">
              <p><strong>Agent:</strong> {approveModalRequest?.agent_name ?? approveModalRequest?.agent_id ?? '—'}</p>
              <p><strong>Reden:</strong> {approveModalRequest?.reason ?? '—'}</p>
              <p><strong>Confidence:</strong> {approveModalRequest?.confidence_score != null ? `${Math.round(Number(approveModalRequest.confidence_score) * 100)}%` : '—'}</p>
            </div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Source URL (trainingsbron)</label>
            <input
              type="url"
              value={approveSourceUrl ?? ''}
              onChange={(e) => setApproveSourceUrl(e.target.value)}
              placeholder="https://..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm mb-4"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                disabled={modalLoading}
                onClick={() => { setApproveModalRequest(null); setApproveSourceUrl(''); setError('') }}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 disabled:opacity-50 disabled:pointer-events-none"
              >
                Annuleren
              </button>
              <button
                type="button"
                disabled={modalLoading}
                onClick={confirmApproveTraining}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:pointer-events-none inline-flex items-center gap-2"
              >
                {modalLoading ? <Loader2 className="w-4 h-4 animate-spin shrink-0" aria-hidden /> : null}
                {modalLoading ? 'Bezig...' : 'Goedkeuren'}
              </button>
            </div>
          </div>
        </div>
      )}

      {rejectConfirmRequestId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" role="dialog" aria-modal="true" aria-labelledby="reject-dialog-title">
          <div className="bg-white rounded-xl shadow-lg max-w-sm w-full p-6 border border-slate-200">
            <h2 id="reject-dialog-title" className="text-lg font-semibold text-slate-900 mb-2">Verzoek afwijzen?</h2>
            <p className="text-sm text-slate-600 mb-4">Dit kan niet ongedaan worden gemaakt.</p>
            {error && (
              <div className="mb-3 p-3 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
                {error}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                disabled={modalLoading}
                onClick={() => { setRejectConfirmRequestId(null); setError('') }}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 disabled:opacity-50 disabled:pointer-events-none"
              >
                Annuleren
              </button>
              <button
                type="button"
                disabled={modalLoading}
                onClick={confirmRejectTraining}
                className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50 disabled:pointer-events-none inline-flex items-center gap-2"
              >
                {modalLoading ? <Loader2 className="w-4 h-4 animate-spin shrink-0" aria-hidden /> : null}
                {modalLoading ? 'Bezig...' : 'Afwijzen'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Value for POST /api/hr/training-suggestions/discover `development_point_id`.
 * Must match the id used by the HR API for that development point (same as `point_id` / `id` from
 * GET /api/hr/development-points): UUID strings as-is; integer ids as decimal string without
 * scientific notation so the backend can bind BIGINT FKs when applicable.
 */
export function developmentPointIdForDiscoverApi(pointId) {
  if (pointId == null || pointId === '') return ''
  if (typeof pointId === 'number' && Number.isFinite(pointId)) return String(Math.trunc(pointId))
  return String(pointId).trim()
}

/** Child route /hr/training-suggestions — discovered resources, approve/reject, manual discover. */
export function TrainingSuggestionsTabContent() {
  const { authReady } = useAuthReady()
  const [statusFilter, setStatusFilter] = useState('pending')
  const [error, setError] = useState('')
  const [unavailable, setUnavailable] = useState(false)
  const [actionLoadingId, setActionLoadingId] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)

  const [discoverPointKey, setDiscoverPointKey] = useState('')
  const [discoverPattern, setDiscoverPattern] = useState('')
  const [discoverImpact, setDiscoverImpact] = useState('medium')
  const [discoverLoading, setDiscoverLoading] = useState(false)

  const [discoverAgentId, setDiscoverAgentId] = useState('')
  const [discoverAgentRole, setDiscoverAgentRole] = useState('')

  const [notesModal, setNotesModal] = useState(null)

  const {
    data: suggestions = [],
    isLoading: loading,
    refetch: refetchSuggestions,
  } = useQuery({
    queryKey: ['hr', 'training-suggestions', statusFilter],
    queryFn: async () => {
      const qs = new URLSearchParams({ status: statusFilter })
      const res = await apiFetch(`/api/hr/training-suggestions?${qs}`)
      if (res.status === 503) {
        setUnavailable(true)
        setError('')
        return []
      }
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Laden mislukt')
      setUnavailable(false)
      const data = await res.json()
      const list = data?.suggestions ?? []
      return Array.isArray(list) ? list : []
    },
    enabled: authReady,
    retry: false,
  })

  const { data: points = [], isLoading: pointsLoading } = useQuery({
    queryKey: ['hr', 'development-points', 'discover'],
    queryFn: async () => {
      const res = await apiFetch('/api/hr/development-points')
      if (!res.ok) return []
      const data = await res.json()
      const list = data.development_points ?? (Array.isArray(data) ? data : [])
      return Array.isArray(list) ? list : []
    },
    enabled: authReady,
    retry: false,
  })

  const selectedDiscoverPoint = points.find((p) => {
    const key = String(p.point_id ?? p.id ?? '')
    return key && key === discoverPointKey
  })

  const agentOptions = []
  const seenAgentIds = new Set()
  for (const p of points) {
    const id = String(p.agent_id ?? p.agentId ?? '').trim()
    if (!id || seenAgentIds.has(id)) continue
    seenAgentIds.add(id)
    agentOptions.push({
      agent_id: id,
      agent_role: String(p.agent_role ?? '').trim(),
    })
  }

  const agentRoleOptions = []
  const seenRoles = new Set()
  for (const o of agentOptions) {
    const role = o.agent_role
    if (!role || seenRoles.has(role)) continue
    seenRoles.add(role)
    agentRoleOptions.push(role)
  }

  useEffect(() => {
    if (!selectedDiscoverPoint) return
    setDiscoverAgentId(String(selectedDiscoverPoint.agent_id || '').trim())
    setDiscoverAgentRole(String(selectedDiscoverPoint.agent_role || '').trim())
  }, [discoverPointKey])

  function openNotesModal(suggestionId, mode) {
    setNotesModal({ suggestionId, mode, notes: '' })
    setError('')
  }

  async function submitSuggestionDecision() {
    if (!notesModal) return
    const { suggestionId, notes, mode } = notesModal
    const path = mode === 'approve' ? 'approve' : 'reject'
    setActionLoadingId(suggestionId)
    try {
      const res = await apiFetch(`/api/hr/training-suggestions/${suggestionId}/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approval_notes: notes?.trim() || null }),
      })
      if (res.status === 503) {
        setUnavailable(true)
        return
      }
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Actie mislukt')
      setNotesModal(null)
      setSuccessMsg(mode === 'approve' ? 'Suggestie goedgekeurd; training wordt op de achtergrond gestart.' : 'Suggestie afgewezen.')
      setTimeout(() => setSuccessMsg(null), 5000)
      await refetchSuggestions()
    } catch (err) {
      setError(err.message || 'Actie mislukt')
    } finally {
      setActionLoadingId(null)
    }
  }

  async function runManualDiscover() {
    const pattern = (discoverPattern || '').trim()
    if (!pattern) {
      setError('Vul een patroon / beschrijving in voor de zoekopdracht.')
      return
    }

    setDiscoverLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/hr/training-suggestions/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pattern_description: pattern,
          impact: discoverImpact,
          development_point_id: null,
          agent_id: '',
          agent_role: '',
        }),
      })
      if (res.status === 503) {
        setUnavailable(true)
        return
      }
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Discover mislukt')
      const data = await res.json()
      const n = data?.discovered ?? 0
      setSuccessMsg(n > 0 ? `${n} nieuwe suggestie(s) toegevoegd.` : 'Geen nieuwe unieke suggesties (of API leverde geen resultaten).')
      setTimeout(() => setSuccessMsg(null), 5000)
      await refetchSuggestions()
    } catch (err) {
      setError(err.message || 'Discover mislukt')
    } finally {
      setDiscoverLoading(false)
    }
  }

  if (!authReady) return null

  return (
    <div className="space-y-8">
      {unavailable && (
        <div className="p-4 rounded-lg bg-amber-50 text-amber-900 border border-amber-200 text-sm">
          Trainingssuggesties zijn in deze omgeving niet beschikbaar (database-tabel ontbreekt). Voer migratie 081 uit.
        </div>
      )}
      {error && (
        <div className="p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">{error}</div>
      )}
      {successMsg && (
        <div className="p-4 rounded-lg bg-green-50 text-green-700 border border-green-200 text-sm">{successMsg}</div>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900 mb-1">Handmatig bronnen zoeken</h2>
        <p className="text-sm text-slate-600 mb-4">
          Beschrijf het patroon / de gap die de agent moet leren. Deze actie start HR resource discovery.
        </p>
        <div className="flex flex-col gap-3 max-w-2xl">
          <label className="text-sm font-medium text-slate-700">Patroon / gap (zoekopdracht)</label>
          <textarea
            value={discoverPattern}
            onChange={(e) => setDiscoverPattern(e.target.value)}
            rows={3}
            disabled={unavailable}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="Beschrijf wat de agent moet leren…"
          />
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Impact</label>
              <select
                value={discoverImpact}
                onChange={(e) => setDiscoverImpact(e.target.value)}
                disabled={unavailable}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="critical">critical</option>
                <option value="high">high</option>
                <option value="medium">medium</option>
                <option value="low">low</option>
              </select>
            </div>
            <button
              type="button"
              disabled={discoverLoading || unavailable}
              onClick={runManualDiscover}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
            >
              {discoverLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              Zoek suggesties
            </button>
          </div>
        </div>
      </section>

      <section>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <span className="text-sm font-medium text-slate-700">Status:</span>
          {['pending', 'approved', 'rejected'].map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                statusFilter === s ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {s === 'pending' ? 'Openstaand' : s === 'approved' ? 'Goedgekeurd' : 'Afgewezen'}
            </button>
          ))}
          <button
            type="button"
            onClick={() => refetchSuggestions()}
            disabled={loading || unavailable}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Vernieuwen
          </button>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-slate-500 py-8">
            <Loader2 className="w-5 h-5 animate-spin shrink-0" />
            <span>Laden...</span>
          </div>
        ) : unavailable ? (
          <p className="text-sm text-slate-500 py-4">Suggestielijst niet beschikbaar in deze omgeving.</p>
        ) : suggestions.length === 0 ? (
          <div className="p-8 rounded-xl border border-slate-200 bg-slate-50 text-center text-slate-600">
            Geen suggesties voor deze filter.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-slate-700">Agent</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-700">Bron</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-700">Dev. point</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-700">Ontdekt</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-700">Besluit</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-700">Acties</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {suggestions.map((s) => {
                  const id = s.id
                  const st = (s.status || '').toLowerCase()
                  const busy = actionLoadingId === id
                  const dpRef = s.development_point_ref ?? s.development_point_id
                  const dpLabel = dpRef != null ? String(dpRef) : '—'
                  let decisionCell = '—'
                  if (st === 'approved' && (s.approved_by || s.reviewed_at)) {
                    decisionCell = `Goedgekeurd door ${s.approved_by || '—'}`
                    if (s.reviewed_at) decisionCell += ` · ${new Date(s.reviewed_at).toLocaleString('nl-NL')}`
                  } else if (st === 'rejected' && (s.approved_by || s.reviewed_at)) {
                    decisionCell = `Afgewezen door ${s.approved_by || '—'}`
                    if (s.reviewed_at) decisionCell += ` · ${new Date(s.reviewed_at).toLocaleString('nl-NL')}`
                  }
                  return (
                    <tr key={id} className="hover:bg-slate-50">
                      <td className="px-4 py-2 align-top">
                        <div>{s.agent_name ?? s.agent_id ?? '—'}</div>
                        {s.agent_role ? <div className="text-xs text-slate-500">{s.agent_role}</div> : null}
                      </td>
                      <td className="px-4 py-2 align-top max-w-xs">
                        <div className="font-medium text-slate-800">{s.title || '—'}</div>
                        {s.url ? (
                          <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-600 hover:underline break-all">
                            {s.url}
                          </a>
                        ) : null}
                        {s.rationale ? <p className="text-xs text-slate-600 mt-1">{s.rationale}</p> : null}
                      </td>
                      <td className="px-4 py-2 align-top font-mono text-xs text-slate-600 break-all max-w-[140px]" title={dpLabel}>
                        {dpLabel}
                      </td>
                      <td className="px-4 py-2 align-top text-slate-600 whitespace-nowrap">
                        {s.discovered_at ? new Date(s.discovered_at).toLocaleString('nl-NL') : '—'}
                      </td>
                      <td className="px-4 py-2 align-top text-slate-600 text-xs max-w-[220px]">
                        {decisionCell}
                        {s.approval_notes ? (
                          <div className="mt-1 text-slate-500 italic">Opmerking: {s.approval_notes}</div>
                        ) : null}
                      </td>
                      <td className="px-4 py-2 align-top">
                        {st === 'pending' ? (
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              disabled={busy || unavailable}
                              onClick={() => openNotesModal(id, 'approve')}
                              className="text-xs font-medium text-green-600 hover:underline disabled:opacity-50"
                            >
                              Goedkeuren
                            </button>
                            <button
                              type="button"
                              disabled={busy || unavailable}
                              onClick={() => openNotesModal(id, 'reject')}
                              className="text-xs font-medium text-red-600 hover:underline disabled:opacity-50"
                            >
                              Afwijzen
                            </button>
                            {busy ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : null}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {notesModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" role="dialog" aria-modal="true">
          <div className="bg-white rounded-xl shadow-lg max-w-md w-full p-6 border border-slate-200">
            <h2 className="text-lg font-semibold text-slate-900 mb-2">
              {notesModal.mode === 'approve' ? 'Suggestie goedkeuren' : 'Suggestie afwijzen'}
            </h2>
            <p className="text-sm text-slate-600 mb-3">
              {notesModal.mode === 'approve'
                ? 'Training start op de achtergrond na goedkeuring.'
                : 'Je kunt een interne opmerking toevoegen (optioneel).'}
            </p>
            <label className="block text-sm font-medium text-slate-700 mb-1">Opmerking (optioneel)</label>
            <textarea
              value={notesModal.notes}
              onChange={(e) => setNotesModal((m) => (m ? { ...m, notes: e.target.value } : m))}
              rows={3}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm mb-4"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setNotesModal(null)}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50"
              >
                Annuleren
              </button>
              <button
                type="button"
                disabled={
                  actionLoadingId != null &&
                  String(actionLoadingId) === String(notesModal.suggestionId)
                }
                onClick={() => submitSuggestionDecision()}
                className={`px-4 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-50 inline-flex items-center gap-2 ${
                  notesModal.mode === 'approve' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'
                }`}
              >
                {String(actionLoadingId) === String(notesModal.suggestionId) ? (
                  <Loader2 className="w-4 h-4 animate-spin shrink-0" aria-hidden />
                ) : null}
                {notesModal.mode === 'approve'
                  ? (String(actionLoadingId) === String(notesModal.suggestionId) ? 'Bezig...' : 'Goedkeuren')
                  : (String(actionLoadingId) === String(notesModal.suggestionId) ? 'Bezig...' : 'Afwijzen')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export function BlockedJobsTabContent() {
  const { authReady } = useAuthReady()
  const location = useLocation()
  const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

  const searchParams = new URLSearchParams(location.search || '')
  const jobId = searchParams.get('job_id')

  const {
    data: blockedJobs = [],
    isLoading: loading,
    error,
  } = useQuery({
    queryKey: ['hr', 'blocked-jobs', jobId || 'all'],
    queryFn: async () => {
      const url = jobId
        ? `/api/hr/blocked-jobs?job_id=${encodeURIComponent(jobId)}`
        : `/api/hr/blocked-jobs`
      const res = await apiFetch(url)
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Laden mislukt')
      const data = await res.json().catch(() => ({}))
      return Array.isArray(data?.blocked_jobs) ? data.blocked_jobs : []
    },
    enabled: authReady,
  })

  if (!authReady) return null

  return (
    <div className="pt-2">
      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
          {error?.message || 'Laden mislukt'}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-slate-500 py-8">
          <Loader2 className="w-5 h-5 animate-spin shrink-0" />
          <span>Laden...</span>
        </div>
      ) : blockedJobs.length === 0 ? (
        <div className="p-8 rounded-xl border border-slate-200 bg-slate-50 text-center">
          <p className="text-slate-600">Geen geblokkeerde jobs.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {blockedJobs.map((job) => {
            const safeMissingRoles = Array.isArray(job?.missing_roles) ? job.missing_roles : []
            return (
              <div key={job.job_id} className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="text-base font-semibold text-amber-950 truncate">Job {job.job_id}</h3>
                    {job.block_reason ? (
                      <p className="text-sm text-amber-900 whitespace-pre-wrap mt-1">{job.block_reason}</p>
                    ) : (
                      <p className="text-sm text-amber-900 whitespace-pre-wrap mt-1">Deze job is geblokkeerd.</p>
                    )}
                  </div>
                  <Link
                    to={`/jobs/${job.job_id}`}
                    className="self-start sm:self-auto inline-flex text-sm font-medium text-indigo-700 hover:text-indigo-900 underline"
                  >
                    Open job →
                  </Link>
                </div>

                {safeMissingRoles.length > 0 && (
                  <div className="mt-3">
                    <p className="text-sm font-medium text-amber-950 mb-2">Ontbrekende rollen</p>
                    <div className="space-y-2">
                      {safeMissingRoles.map((mr, idx) => {
                        const mrKey = mr?.missing_role_key ?? mr?.missing_role_label ?? `mr-${idx}`
                        const candidates = Array.isArray(mr?.candidates) ? mr.candidates : []
                        return (
                          <div key={mrKey} className="rounded-lg border border-amber-200 bg-amber-100/40 p-3">
                            <p className="text-sm font-medium text-amber-950">
                              {mr?.missing_role_label || mrKey}
                            </p>
                            {candidates.length > 0 ? (
                              <ul className="mt-2 text-sm text-amber-950 space-y-1">
                                {candidates.map((c) => (
                                  <li key={c.newbie_id} className="flex items-center justify-between gap-2">
                                    <span className="min-w-0 truncate">
                                      {c.newbie_name || c.newbie_id}
                                      {c.suggested_role ? (
                                        <span className="text-xs text-amber-900/80"> — {c.suggested_role}</span>
                                      ) : null}
                                    </span>
                                    <span className="flex-shrink-0 text-xs font-medium px-2 py-0.5 rounded bg-amber-200 text-amber-950">
                                      {c.readiness_score != null ? `${c.readiness_score}%` : '—'}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p className="text-sm text-amber-950/90 mt-2">Geen geschikte newbies gevonden.</p>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function HRDashboard() {
  const location = useLocation()
  const navigate = useNavigate()
  const { authReady } = useAuthReady()
  const isChildRoute = location.pathname !== '/hr'
  const isTrainingRoute = location.pathname === '/hr/training-requests'
  const isSuggestionsRoute = location.pathname === '/hr/training-suggestions'
  const isBlockedJobsRoute = location.pathname === '/hr/blocked-jobs'
  const [tab, setTab] = useState('points')
  const [points, setPoints] = useState([])
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [scanMessage, setScanMessage] = useState('')
  const [scanStep, setScanStep] = useState(0)
  const [scanOutcome, setScanOutcome] = useState(null)
  const [scanResultText, setScanResultText] = useState('')
  const [error, setError] = useState('')
  const [trainingUrlInput, setTrainingUrlInput] = useState({})
  const [crossProposals, setCrossProposals] = useState([])
  const [crossUrlInput, setCrossUrlInput] = useState({})
  const [filterImpact, setFilterImpact] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [report, setReport] = useState(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [resolveInput, setResolveInput] = useState({})
  const [expandedPointId, setExpandedPointId] = useState(null)
  const scanStepAnimRef = useRef(null)

  const {
    data: developmentPoints = [],
    isLoading: pointsLoading,
    refetch: refetchDevelopmentPoints,
  } = useQuery({
    queryKey: queryKeys.developmentPoints(),
    queryFn: async () => {
      const res = await apiFetch('/api/hr/development-points')
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Laden mislukt')
      const data = await res.json()
      return data.development_points ?? (Array.isArray(data) ? data : [])
    },
    enabled: authReady && tab === 'points',
    refetchInterval: authReady && tab === 'points' ? 60_000 : false,
  })

  const loadReport = useCallback(async () => {
    setReportLoading(true)
    try {
      const res = await apiFetch('/api/hr/report')
      if (res.ok) {
        const data = await res.json()
        setReport(data.agents != null ? data : { agents: {} })
      }
    } catch {
      setReport({ agents: {} })
    } finally {
      setReportLoading(false)
    }
  }, [])

  const {
    data: crossTrainingProposals = [],
    isLoading: crossLoading,
    refetch: refetchCrossProposals,
  } = useQuery({
    queryKey: queryKeys.hrReport(),
    queryFn: async () => {
      const res = await apiFetch('/api/hr/cross-training-proposals?status=pending')
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Laden mislukt')
      const data = await res.json()
      return Array.isArray(data) ? data : []
    },
    enabled: authReady && tab === 'cross',
  })

  useEffect(() => {
    setPoints(Array.isArray(developmentPoints) ? developmentPoints : [])
  }, [developmentPoints])

  useEffect(() => {
    setCrossProposals(Array.isArray(crossTrainingProposals) ? crossTrainingProposals : [])
  }, [crossTrainingProposals])

  useEffect(() => {
    if (!authReady) return
    if (tab === 'points') {
      setError('')
      setLoading(pointsLoading)
      return
    }
    if (tab === 'cross') {
      setError('')
      setLoading(crossLoading)
      return
    }
    setLoading(false)
  }, [authReady, tab, pointsLoading, crossLoading])

  // Mark CEO notifications as read when user lands on HR dashboard
  useEffect(() => {
    if (!authReady) return
    let cancelled = false
    const markAllRead = async () => {
      try {
        const res = await apiFetch('/api/hr/notifications')
        if (!res.ok || cancelled) return
        const list = await res.json()
        if (!Array.isArray(list) || cancelled) return
        for (const n of list) {
          if (n.notification_id) {
            await apiFetch(`/api/hr/notifications/${n.notification_id}/read`, { method: 'POST' })
          }
        }
      } catch {
        // ignore
      }
    }
    markAllRead()
    return () => { cancelled = true }
  }, [authReady])

  useEffect(() => {
    return () => {
      if (scanStepAnimRef.current) clearInterval(scanStepAnimRef.current)
    }
  }, [])

  const SCAN_STEP_LABELS = ['Scannen van job steps...', 'Development points aanmaken...', 'Scan afgerond']

  async function triggerScan() {
    setScanning(true)
    setScanMessage('')
    setScanOutcome(null)
    setScanResultText('')
    setScanStep(0)
    setError('')

    scanStepAnimRef.current = setInterval(() => {
      setScanStep((prev) => Math.min(prev + 1, 2))
    }, 1200)

    try {
      const res = await apiFetch('/api/hr/scan', { method: 'POST' })
      if (scanStepAnimRef.current) clearInterval(scanStepAnimRef.current)
      scanStepAnimRef.current = null
      setScanStep(2)

      const data = res.ok ? await res.json().catch(() => ({})) : {}
      const created = data.created ?? 0
      const incremented = data.incremented ?? 0
      const total = created + incremented

      setScanOutcome('success')
      setScanResultText(total > 0
        ? `${created} nieuwe development point${created !== 1 ? 's' : ''} gevonden${incremented > 0 ? `, ${incremented} bijgewerkt` : ''}`
        : 'Geen nieuwe patronen gevonden')
      await refetchDevelopmentPoints()

      setTimeout(() => {
        setScanning(false)
        setScanOutcome(null)
        setScanResultText('')
        setScanMessage('')
      }, 3000)
    } catch {
      if (scanStepAnimRef.current) clearInterval(scanStepAnimRef.current)
      scanStepAnimRef.current = null
      setScanStep(2)
      setScanOutcome('error')
      setScanResultText('Scan mislukt')
      setError('Scan mislukt')
      setTimeout(() => {
        setScanning(false)
        setScanOutcome(null)
        setScanResultText('')
      }, 3000)
    }
  }

  async function updatePointStatus(pointId, status) {
    try {
      await apiFetch(`/api/hr/development-points/${pointId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, approved_by: 'hr-dashboard' }),
      })
      await refetchDevelopmentPoints()
    } catch {
      setError('Status update mislukt')
    }
  }

  async function approveTraining(id) {
    const sourceUrl = trainingUrlInput[id] || ''
    try {
      const res = await apiFetch('/api/hr/approve-training', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ point_id: id, approved: true, source_url: sourceUrl || undefined, approved_by: 'hr-dashboard' }),
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Request failed')
      setTrainingUrlInput((prev) => { const n = { ...prev }; delete n[id]; return n })
      await refetchDevelopmentPoints()
    } catch (err) {
      setError(err?.message || 'Goedkeuren mislukt')
    }
  }

  async function approveCrossTrain(proposalId) {
    const sourceUrl = crossUrlInput[proposalId] || null
    try {
      await apiFetch('/api/hr/cross-train', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal_id: proposalId, approved: true, source_url: sourceUrl || undefined }),
      })
      setCrossUrlInput((prev) => { const n = { ...prev }; delete n[proposalId]; return n })
      await refetchCrossProposals()
    } catch {
      setError('Goedkeuren mislukt')
    }
  }

  async function resolvePoint(pointId, resolution) {
    try {
      const res = await apiFetch(`/api/hr/development-points/${pointId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolution: resolution || 'Opgelost via HR Dashboard' }),
      })
      setResolveInput((prev) => { const n = { ...prev }; delete n[pointId]; return n })
      if (res?.status === 404) {
        await refetchDevelopmentPoints()
        return
      }
      await refetchDevelopmentPoints()
    } catch {
      setError('Opgelost markeren mislukt')
    }
  }

  async function rejectCrossTrain(proposalId) {
    try {
      await apiFetch('/api/hr/cross-train', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal_id: proposalId, approved: false }),
      })
      await refetchCrossProposals()
    } catch {
      setError('Afwijzen mislukt')
    }
  }

  if (!authReady) return null

  return (
    <PageLayout size="wide" padded>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">HR Dashboard</h1>
        <div className="flex flex-col items-end gap-2">
          <button
            type="button"
            onClick={triggerScan}
            disabled={scanning}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-white font-medium disabled:opacity-50 text-sm"
            style={{
              background: scanning ? 'var(--color-text-muted)' : 'var(--color-brand-primary)',
            }}
          >
            <RefreshCw className={`w-4 h-4 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? 'Scannen...' : 'Scan nu'}
          </button>
          {(scanning || scanOutcome) && (
            <div
              className="w-64 rounded-[var(--radius-sm)] overflow-hidden border text-sm"
              style={{
                borderColor: scanOutcome === 'error' ? 'var(--color-status-error)' : scanOutcome === 'success' ? 'var(--color-status-success)' : 'var(--color-border)',
              }}
            >
              <div
                className="h-2 w-full overflow-hidden"
                style={{ background: 'var(--color-bg-input)' }}
              >
                <div
                  className="h-full w-full"
                  style={{
                    background: scanOutcome === 'error'
                      ? 'var(--color-status-error)'
                      : scanOutcome === 'success'
                        ? 'var(--color-status-success)'
                        : 'repeating-linear-gradient(90deg, var(--color-brand-primary), var(--color-brand-primary) 8px, var(--color-brand-primary-light) 8px, var(--color-brand-primary-light) 16px)',
                    backgroundSize: scanOutcome ? '100% 100%' : '32px 100%',
                    animation: scanOutcome ? 'none' : 'hr-scan-progress 0.8s linear infinite',
                  }}
                />
              </div>
              <div
                className="px-2 py-1.5"
                style={{
                  background: scanOutcome === 'error' ? 'var(--color-status-error-bg)' : scanOutcome === 'success' ? 'var(--color-status-success-bg)' : 'var(--color-bg-subtle)',
                  color: scanOutcome === 'error' ? '#991B1B' : scanOutcome === 'success' ? '#065F46' : 'var(--color-text-secondary)',
                }}
              >
                {scanOutcome ? scanResultText : SCAN_STEP_LABELS[scanStep]}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-2 mb-6">
        {TABS.map((t) => {
          const isImprovementsRoute = location.pathname === '/hr/improvements'
          const isActive =
            t.id === 'training'
              ? isTrainingRoute
              : t.id === 'suggestions'
                ? isSuggestionsRoute
                : t.id === 'improvements'
                  ? isImprovementsRoute
                  : t.id === 'blocked-jobs'
                    ? isBlockedJobsRoute
                    : tab === t.id
          if (t.id === 'training') {
            return (
              <Link
                key={t.id}
                to="/hr/training-requests"
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  isActive ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {t.label}
              </Link>
            )
          }
          if (t.id === 'suggestions') {
            return (
              <Link
                key={t.id}
                to="/hr/training-suggestions"
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  isActive ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {t.label}
              </Link>
            )
          }
          if (t.id === 'improvements') {
            return (
              <Link
                key={t.id}
                to="/hr/improvements"
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  isActive ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {t.label}
              </Link>
            )
          }
          if (t.id === 'blocked-jobs') {
            return (
              <Link
                key={t.id}
                to="/hr/blocked-jobs"
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  isActive ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {t.label}
              </Link>
            )
          }
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => { setTab(t.id); navigate('/hr') }}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                isActive ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {t.label}
            </button>
          )
        })}
      </div>

      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">{error}</div>
      )}
      {scanMessage && (
        <div className="mb-4 p-4 rounded-lg bg-green-50 text-green-700 border border-green-200 text-sm">{scanMessage}</div>
      )}

      {isChildRoute ? (
        <Outlet />
      ) : (
        <>
      {/* Weekly Report */}
      <section className="mb-8 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-slate-900">Weekly Report</h2>
          <button
            type="button"
            onClick={loadReport}
            disabled={reportLoading}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${reportLoading ? 'animate-spin' : ''}`} />
            Refresh rapport
          </button>
        </div>
        {report && report.agents && Object.keys(report.agents).length > 0 ? (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(report.agents).map(([agentId, data]) => (
              <div key={agentId} className="rounded-lg border border-slate-200 p-3 text-sm">
                <strong className="text-slate-900">{data.agent_name ?? agentId ?? '—'}</strong>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs">
                    {data.open_points_count != null ? data.open_points_count : '—'} open
                  </span>
                  <span className="text-slate-600">
                    Retry: {data.performance?.retry_rate != null ? ((data.performance.retry_rate) * 100).toFixed(1) : '—'}%
                  </span>
                  <span className="text-slate-600">
                    Jobs (7d): {data.performance?.jobs_touched_7d != null ? data.performance.jobs_touched_7d : '—'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : report ? (
          <p className="text-slate-500 text-sm">Geen data beschikbaar.</p>
        ) : (
          <p className="text-slate-500 text-sm">Klik "Refresh rapport" om te laden.</p>
        )}
      </section>

      {/* Tab 1: Development Points */}
      {tab === 'points' && (
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <select
              value={filterImpact}
              onChange={(e) => setFilterImpact(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Alle impact</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Alle statussen</option>
              <option value="OPEN">Open</option>
              <option value="AWAITING_APPROVAL">Wacht op goedkeuring</option>
              <option value="IN_TRAINING">In training</option>
              <option value="RESOLVED">Opgelost</option>
              <option value="DISMISSED">Afgewezen</option>
            </select>
          </div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : (() => {
            const filtered = points.filter((p) => {
              if (filterImpact && (p.impact || '').toLowerCase() !== filterImpact) return false
              if (filterStatus && (p.status || '').toUpperCase() !== filterStatus) return false
              return true
            })
            return filtered.length === 0 ? (
            <div className="p-8 rounded-xl border border-slate-200 bg-slate-50 text-center">
              <p className="text-slate-600">Geen development points gevonden.</p>
              <p className="text-slate-400 text-sm mt-1">Klik "Scan nu" om job_steps te analyseren.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Agent</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Issue</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Frequency</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Impact</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Status</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Acties</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {filtered.map((p) => {
                    const impactKey = (p.impact || 'medium').toLowerCase()
                    const statusKey = (p.status || 'OPEN').toUpperCase()
                    const pointId = p.point_id || p.id
                    const showResolveInput = resolveInput[pointId] !== undefined && (statusKey === 'IN_TRAINING' || statusKey === 'AWAITING_APPROVAL')
                    const isExpanded = expandedPointId === pointId
                    return (
                      <React.Fragment key={pointId}>
                        <tr className="hover:bg-slate-50">
                          <td className="px-4 py-2">{p.agent_name || p.agent_id || p.agent_role || '—'}</td>
                          <td
                            className="px-4 py-2 max-w-xs cursor-pointer hover:bg-slate-100 rounded"
                            role="button"
                            tabIndex={0}
                            onClick={() => setExpandedPointId(isExpanded ? null : pointId)}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpandedPointId(isExpanded ? null : pointId) } }}
                          >
                            {p.issue_description || '—'}
                          </td>
                          <td className="px-4 py-2">{p.frequency ?? '—'}</td>
                          <td className="px-4 py-2">
                            <span style={{ color: IMPACT_COLOR[impactKey] || IMPACT_COLOR.medium, fontWeight: 600 }} className={`px-2 py-0.5 text-xs font-medium rounded ${IMPACT_BADGE[impactKey] || IMPACT_BADGE.medium}`}>
                              {(p.impact || impactKey)}
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            <span className={`px-2 py-0.5 text-xs font-medium rounded ${STATUS_BADGE[statusKey] || 'bg-gray-100 text-gray-500'}`}>
                              {statusKey}
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <Link
                                to={`/hr/issues/${pointId}`}
                                className="text-xs font-medium text-indigo-600 hover:underline"
                              >
                                Detail →
                              </Link>
                              {(statusKey === 'IN_TRAINING' || statusKey === 'AWAITING_APPROVAL') && !showResolveInput && (
                                <button
                                  type="button"
                                  onClick={() => setResolveInput((prev) => ({ ...prev, [pointId]: '' }))}
                                  className="text-xs font-medium text-slate-600 hover:underline"
                                >
                                  Opgelost markeren
                                </button>
                              )}
                              {showResolveInput && (
                                <div className="flex items-center gap-1">
                                  <input
                                    type="text"
                                    placeholder="Oplossing (optioneel)"
                                    className="border border-slate-300 rounded px-2 py-1 text-xs w-48"
                                    value={resolveInput[pointId] ?? ''}
                                    onChange={(e) => setResolveInput((prev) => ({ ...prev, [pointId]: e.target.value }))}
                                  />
                                  <button
                                    type="button"
                                    onClick={() => resolvePoint(pointId, resolveInput[pointId])}
                                    className="text-xs font-medium text-green-600 hover:underline"
                                  >
                                    Bevestig
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setResolveInput((prev) => { const n = { ...prev }; delete n[pointId]; return n })}
                                    className="text-xs font-medium text-slate-400 hover:underline"
                                  >
                                    Annuleer
                                  </button>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr className="bg-slate-50">
                            <td colSpan={6} className="px-4 py-3 align-top">
                              <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm">
                                <p className="font-medium text-slate-700 mb-1">Issue</p>
                                <p className="text-slate-600 mb-3">{p.issue_description || '—'}</p>
                                <p className="font-medium text-slate-700 mb-1">Root cause</p>
                                <p className="text-slate-600 mb-3 whitespace-pre-wrap">{p.root_cause || 'Geen root cause beschikbaar'}</p>
                                <p className="font-medium text-slate-700 mb-1">Evidence</p>
                                <div className="text-slate-600 mb-3 rounded bg-slate-100 p-2 overflow-x-auto max-h-40 overflow-y-auto">
                                  {p.evidence_example == null ? (
                                    '—'
                                  ) : typeof p.evidence_example === 'string' ? (
                                    p.evidence_example
                                  ) : (
                                    <pre className="text-xs whitespace-pre-wrap m-0">{JSON.stringify(p.evidence_example, null, 2)}</pre>
                                  )}
                                </div>
                                <p className="text-slate-600 mb-2">
                                  Confidence: {p.confidence_score != null ? `${Math.round(Number(p.confidence_score) * 100)}%` : '—'}
                                  {' · '}
                                  Frequency: {p.frequency != null ? p.frequency : '—'}
                                  {' · '}
                                  Impact: {(p.impact || '—').toUpperCase()}
                                </p>
                                <p className="font-medium text-slate-700 mb-1">Aanbevolen trainings-URL</p>
                                <p className="text-slate-600 mb-3">
                                  {p.suggested_url ? (
                                    <a href={p.suggested_url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline break-all">
                                      {p.suggested_url}
                                    </a>
                                  ) : (
                                    'Geen URL beschikbaar'
                                  )}
                                </p>
                                <div className="flex justify-end">
                                  <button
                                    type="button"
                                    onClick={() => setExpandedPointId(null)}
                                    className="rounded-lg px-3 py-1.5 border border-slate-300 text-slate-700 text-xs font-medium hover:bg-slate-50"
                                  >
                                    Sluiten
                                  </button>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          );
          })()}
        </div>
      )}

      {/* Tab 3: Cross-Training */}
      {tab === 'cross' && (
        <div>
          {loading ? (
            <p className="text-slate-500">Laden...</p>
          ) : crossProposals.length === 0 ? (
            <div className="p-8 rounded-xl border border-slate-200 bg-slate-50 text-center">
              <p className="text-slate-600">Geen cross-training voorstellen.</p>
              <p className="text-slate-400 text-sm mt-1">HR Manager detecteert automatisch nieuwe kansen.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Lesson</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Bron agent</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Doel agents</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Reden</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-700">Acties</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {crossProposals.map((p) => {
                    const showInput = crossUrlInput[p.proposal_id] !== undefined
                    const targets = Array.isArray(p.target_agent_ids) ? p.target_agent_ids : []
                    return (
                      <tr key={p.proposal_id} className="hover:bg-slate-50">
                        <td className="px-4 py-2 max-w-xs">{p.lesson_id}</td>
                        <td className="px-4 py-2">{p.source_agent_id || '—'}</td>
                        <td className="px-4 py-2">
                          <div className="flex flex-wrap gap-1">
                            {targets.map((id) => (
                              <span key={id} className="px-2 py-0.5 text-xs font-medium rounded bg-slate-100 text-slate-700">
                                {id}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-4 py-2 max-w-xs text-slate-600">{p.reason || '—'}</td>
                        <td className="px-4 py-2">
                          {!showInput ? (
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                onClick={() => setCrossUrlInput((prev) => ({ ...prev, [p.proposal_id]: '' }))}
                                className="text-xs font-medium text-green-600 hover:underline"
                              >
                                Goedkeuren
                              </button>
                              <button
                                type="button"
                                onClick={() => rejectCrossTrain(p.proposal_id)}
                                className="text-xs font-medium text-red-600 hover:underline"
                              >
                                Afwijzen
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1">
                              <input
                                type="url"
                                placeholder="Source URL (optioneel)"
                                className="border border-slate-300 rounded px-2 py-1 text-xs w-48"
                                value={crossUrlInput[p.proposal_id] || ''}
                                onChange={(e) => setCrossUrlInput((prev) => ({ ...prev, [p.proposal_id]: e.target.value }))}
                              />
                              <button
                                type="button"
                                onClick={() => approveCrossTrain(p.proposal_id)}
                                className="text-xs font-medium text-green-600 hover:underline"
                              >
                                Bevestig
                              </button>
                              <button
                                type="button"
                                onClick={() => setCrossUrlInput((prev) => { const n = { ...prev }; delete n[p.proposal_id]; return n })}
                                className="text-xs font-medium text-slate-400 hover:underline"
                              >
                                Annuleer
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
        </>
      )}
    </PageLayout>
  )
}
