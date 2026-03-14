/**
 * HR Development Point Detail — kennisbron toevoegen (URL / Tekst / Bestand) + Goedkeuren / Afwijzen.
 * GET /api/hr/development-points/:pointId; POST knowledge-source, submit-for-approval, approve.
 */
import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiFetch } from '../apiClient'
import PageLayout from '../PageLayout'
import { LoadingState, ErrorState, EmptyState } from '../components/hr/shared'

const IMPACT_COLORS = { high: '#DC2626', medium: '#D97706', low: '#6B7280' }
const STATUS_LABELS = {
  OPEN: 'Open',
  AWAITING_APPROVAL: 'Wacht op goedkeuring',
  IN_TRAINING: 'In training',
  RESOLVED: 'Opgelost',
  DISMISSED: 'Afgewezen',
}

export default function HRIssueDetail() {
  const { pointId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [sourceType, setSourceType] = useState('url')
  const [sourceUrl, setSourceUrl] = useState('')
  const [sourceText, setSourceText] = useState('')
  const [sourceFile, setSourceFile] = useState(null)
  const [savingSource, setSavingSource] = useState(false)
  const [sourceError, setSourceError] = useState(null)

  const [processing, setProcessing] = useState(false)
  const [rejectMode, setRejectMode] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [actionError, setActionError] = useState(null)

  const fetchPoint = useCallback(async () => {
    if (!pointId) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch(`/api/hr/development-points/${pointId}`)
      const raw = await res.text()
      const contentType = res.headers.get('content-type') || ''
      if (!res.ok) {
        let msg = raw || `HTTP ${res.status}`
        if (contentType.includes('application/json')) {
          try {
            const j = JSON.parse(raw)
            msg = j.detail ?? j.error ?? j.message ?? msg
          } catch (_) {}
        }
        throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
      }
      const json = raw ? JSON.parse(raw) : null
      setData(json)
      const pt = json?.point
      if (pt?.source_url && !pt.source_url.startsWith('data:')) {
        setSourceUrl(pt.source_url)
      }
    } catch (err) {
      setError(err.message || 'Kon development point niet laden.')
    } finally {
      setLoading(false)
    }
  }, [pointId])

  useEffect(() => {
    fetchPoint()
  }, [fetchPoint])

  const point = data?.point ? { ...data.point, agent_name: data.point.agent_name ?? data.agent?.agent_name ?? data.point.agent_id } : null

  const handleSaveSource = async () => {
    setSavingSource(true)
    setSourceError(null)
    try {
      if (sourceType === 'file' && sourceFile) {
        const formData = new FormData()
        formData.append('file', sourceFile)
        const res = await apiFetch(`/api/hr/development-points/${pointId}/knowledge-source/file`, {
          method: 'POST',
          body: formData,
        })
        if (!res.ok) throw new Error('Upload mislukt')
      } else {
        const res = await apiFetch(`/api/hr/development-points/${pointId}/knowledge-source`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_type: sourceType,
            source_url: sourceType === 'url' ? sourceUrl : undefined,
            source_text: sourceType === 'text' ? sourceText : undefined,
          }),
        })
        if (!res.ok) throw new Error('Opslaan mislukt')
      }
      await fetchPoint()
    } catch (err) {
      setSourceError('Opslaan mislukt. Probeer opnieuw.')
    } finally {
      setSavingSource(false)
    }
  }

  const handleApprove = async () => {
    setProcessing(true)
    setActionError(null)
    try {
      if (point?.status === 'OPEN') {
        const res = await apiFetch(`/api/hr/development-points/${pointId}/submit-for-approval`, { method: 'POST' })
        if (!res.ok) throw new Error('Submit mislukt')
      }
      const res = await apiFetch(`/api/hr/development-points/${pointId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved: true,
          source_url: sourceUrl || point?.source_url || null,
        }),
      })
      if (!res.ok) throw new Error('Goedkeuren mislukt')
      navigate('/hr')
    } catch (err) {
      setActionError('Goedkeuren mislukt. Probeer opnieuw.')
    } finally {
      setProcessing(false)
    }
  }

  const handleReject = async () => {
    setProcessing(true)
    setActionError(null)
    try {
      if (point?.status === 'OPEN') {
        const res = await apiFetch(`/api/hr/development-points/${pointId}/submit-for-approval`, { method: 'POST' })
        if (!res.ok) throw new Error('Submit mislukt')
      }
      const res = await apiFetch(`/api/hr/development-points/${pointId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved: false,
          rejection_reason: rejectReason || null,
        }),
      })
      if (!res.ok) throw new Error('Afwijzen mislukt')
      navigate('/hr')
    } catch (err) {
      setActionError('Afwijzen mislukt. Probeer opnieuw.')
    } finally {
      setProcessing(false)
    }
  }

  if (loading) {
    return (
      <PageLayout size="wide" padded>
        <LoadingState />
      </PageLayout>
    )
  }
  if (error) {
    return (
      <PageLayout size="wide" padded>
        <ErrorState message={error} onRetry={fetchPoint} />
      </PageLayout>
    )
  }
  if (!point) {
    return (
      <PageLayout size="wide" padded>
        <EmptyState message="Development point niet gevonden." />
      </PageLayout>
    )
  }

  const canAct = ['OPEN', 'AWAITING_APPROVAL'].includes(point.status)
  const statusKey = (point.status || 'OPEN').toUpperCase()

  return (
    <PageLayout size="wide" padded>
      <div className="hr-issue-detail" style={{ background: 'var(--color-bg-page)' }}>
        <button
          type="button"
          className="back-btn mb-4 text-sm text-gray-600 hover:text-gray-900"
          onClick={() => navigate('/hr')}
        >
          ← Terug naar HR Dashboard
        </button>

        <div className="issue-header mb-6">
          <div className="issue-meta flex flex-wrap items-center gap-3 text-sm text-gray-600 mb-2">
            <span className="agent-name font-medium">{point.agent_name || point.agent_id || '—'}</span>
            <span className="issue-status px-2 py-0.5 rounded bg-gray-100">
              {STATUS_LABELS[statusKey] || point.status}
            </span>
            <span
              className="impact-badge font-medium"
              style={{ color: IMPACT_COLORS[point.impact] || IMPACT_COLORS.low }}
            >
              {String(point.impact || 'low').toUpperCase()}
            </span>
            <span className="frequency">x{Number(point.frequency) || 0} keer gezien</span>
          </div>
          <h1 className="issue-description text-xl font-semibold text-gray-900">{point.issue_description || '—'}</h1>
          {point.root_cause && (
            <p className="root-cause mt-2 text-gray-700">
              <strong>Oorzaak:</strong> {point.root_cause}
            </p>
          )}
          {point.evidence_example && (
            <p className="evidence mt-1 text-gray-600 text-sm">
              <strong>Bewijs:</strong> {point.evidence_example}
            </p>
          )}
        </div>

        {canAct && (
          <div className="knowledge-source-section mb-8 p-4 rounded-lg border border-gray-200 bg-white">
            <h2 className="text-lg font-semibold mb-1">Kennisbron toevoegen</h2>
            <p className="section-subtitle text-sm text-gray-600 mb-4">
              Optioneel: voeg een bron toe die als trainingsmateriaal wordt gebruikt.
            </p>

            <div className="source-type-tabs flex gap-2 mb-4">
              {['url', 'text', 'file'].map((type) => (
                <button
                  key={type}
                  type="button"
                  className={`px-3 py-2 rounded border text-sm font-medium ${sourceType === type ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`}
                  onClick={() => setSourceType(type)}
                >
                  {type === 'url' ? 'URL' : type === 'text' ? 'Tekst plakken' : 'Bestand'}
                </button>
              ))}
            </div>

            {sourceType === 'url' && (
              <input
                type="url"
                className="source-input w-full max-w-md px-3 py-2 border border-gray-300 rounded mb-4"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://..."
              />
            )}
            {sourceType === 'text' && (
              <textarea
                className="source-textarea w-full max-w-2xl px-3 py-2 border border-gray-300 rounded mb-4"
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                placeholder="Plak hier de trainingstekst..."
                rows={8}
              />
            )}
            {sourceType === 'file' && (
              <input
                type="file"
                className="source-file block mb-4"
                accept=".txt,.pdf,.md,.docx"
                onChange={(e) => setSourceFile(e.target.files?.[0] || null)}
              />
            )}

            {sourceError && <p className="source-error text-red-600 text-sm mb-2">{sourceError}</p>}
            <button
              type="button"
              className="btn-save-source px-4 py-2 bg-gray-800 text-white rounded font-medium disabled:opacity-50"
              onClick={handleSaveSource}
              disabled={savingSource || (sourceType === 'url' && !sourceUrl.trim()) || (sourceType === 'text' && !sourceText.trim()) || (sourceType === 'file' && !sourceFile)}
            >
              {savingSource ? 'Opslaan...' : 'Bron opslaan'}
            </button>

            {point.source_url && !point.source_url.startsWith('data:') && (
              <p className="saved-source mt-3 text-sm text-gray-600">
                Huidige bron: <a href={point.source_url} target="_blank" rel="noreferrer" className="text-blue-600 underline">{point.source_url}</a>
              </p>
            )}
            {point.source_url && point.source_url.startsWith('data:') && (
              <p className="saved-source mt-3 text-sm text-gray-600">Huidige bron: bestand of tekst opgeslagen ✓</p>
            )}
          </div>
        )}

        {canAct && (
          <div className="issue-actions flex flex-wrap items-center gap-3">
            {actionError && <p className="action-error text-red-600 text-sm w-full">{actionError}</p>}
            {!rejectMode ? (
              <>
                <button
                  type="button"
                  className="btn-approve px-4 py-2 bg-green-600 text-white rounded font-medium disabled:opacity-50 flex items-center gap-2"
                  onClick={handleApprove}
                  disabled={processing}
                >
                  {processing ? (
                    <span className="inline-flex items-center gap-2">
                      <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Verwerken...
                    </span>
                  ) : (
                    'Goedkeuren'
                  )}
                </button>
                <button
                  type="button"
                  className="btn-reject-open px-4 py-2 border border-red-600 text-red-600 rounded font-medium hover:bg-red-50 disabled:opacity-50"
                  onClick={() => setRejectMode(true)}
                  disabled={processing}
                >
                  Afwijzen
                </button>
              </>
            ) : (
              <div className="reject-form flex flex-wrap items-center gap-2">
                <input
                  type="text"
                  className="px-3 py-2 border border-gray-300 rounded w-64"
                  placeholder="Reden voor afwijzing (optioneel)"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
                <button
                  type="button"
                  className="btn-reject-confirm px-4 py-2 bg-red-600 text-white rounded font-medium disabled:opacity-50"
                  onClick={handleReject}
                  disabled={processing}
                >
                  {processing ? 'Verwerken...' : 'Bevestig afwijzing'}
                </button>
                <button
                  type="button"
                  className="btn-cancel px-4 py-2 border border-gray-300 rounded font-medium"
                  onClick={() => setRejectMode(false)}
                  disabled={processing}
                >
                  Annuleer
                </button>
              </div>
            )}
          </div>
        )}

        {!canAct && (
          <div className="issue-closed p-4 rounded border border-gray-200 bg-gray-50 text-gray-700">
            <p>
              Dit punt heeft status <strong>{STATUS_LABELS[statusKey] || point.status}</strong> en kan niet meer worden bewerkt.
            </p>
          </div>
        )}
      </div>
    </PageLayout>
  )
}
