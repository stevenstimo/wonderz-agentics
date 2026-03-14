/**
 * Issue Detail page — GET /api/hr/development-points/:pointId.
 * Fase 2: data fetching, loading/error/empty, basis layout with SectionLabels and IssueHeader.
 * Fase 3+ fills in the card components.
 */
import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiFetch } from '../apiClient'
import PageLayout from '../PageLayout'
import IssueHeader from '../components/hr/IssueHeader'
import AgentInfoCard from '../components/hr/AgentInfoCard'
import ModelSettingsCard from '../components/hr/ModelSettingsCard'
import IssueSummaryCard from '../components/hr/IssueSummaryCard'
import RootCauseCard from '../components/hr/RootCauseCard'
import DiagnosisSignalsCard from '../components/hr/DiagnosisSignalsCard'
import FrequencyTrendCard from '../components/hr/FrequencyTrendCard'
import InputCard from '../components/hr/InputCard'
import OutputCard from '../components/hr/OutputCard'
import TimelineTable from '../components/hr/TimelineTable'
import PatternAnalysisCard from '../components/hr/PatternAnalysisCard'
import CrossAgentCard from '../components/hr/CrossAgentCard'
import ImpactCard from '../components/hr/ImpactCard'
import CostProjectionCard from '../components/hr/CostProjectionCard'
import FixRoadmapCard from '../components/hr/FixRoadmapCard'
import PerformanceMetricsCard from '../components/hr/PerformanceMetricsCard'
import ReproduceCard from '../components/hr/ReproduceCard'
import FeedbackCard from '../components/hr/FeedbackCard'
import EvidenceCard from '../components/hr/EvidenceCard'
import { SectionLabel, LoadingState, EmptyState, ErrorState } from '../components/hr/shared'
import { useToast, ToastContainer } from '../Toast'

export default function IssueDetail() {
  const { pointId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const { toasts, removeToast, success, error: toastError, info } = useToast()

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

  const fetchIssue = useCallback(async () => {
    if (!pointId) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch(`/api/hr/development-points/${pointId}`)
      const contentType = res.headers.get('content-type') || ''
      const raw = await res.text()
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
    } catch (err) {
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }, [pointId])

  useEffect(() => {
    fetchIssue()
  }, [fetchIssue])

  useEffect(() => {
    const pt = data?.point
    if (pt?.source_url && !pt.source_url.startsWith('data:')) {
      setSourceUrl(pt.source_url)
    }
  }, [data?.point?.source_url])

  const handleSaveSource = useCallback(async () => {
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
      await fetchIssue()
    } catch (err) {
      setSourceError('Opslaan mislukt. Probeer opnieuw.')
    } finally {
      setSavingSource(false)
    }
  }, [pointId, sourceType, sourceUrl, sourceText, sourceFile, fetchIssue])

  const handleApprove = useCallback(async () => {
    const point = data?.point
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
      success('Development point goedgekeurd. Training wordt gestart.')
      navigate('/hr')
    } catch (err) {
      setActionError('Goedkeuren mislukt. Probeer opnieuw.')
    } finally {
      setProcessing(false)
    }
  }, [pointId, data?.point, sourceUrl, navigate, success])

  const handleReject = useCallback(async () => {
    const point = data?.point
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
      success('Development point afgewezen.')
      navigate('/hr')
    } catch (err) {
      setActionError('Afwijzen mislukt. Probeer opnieuw.')
    } finally {
      setProcessing(false)
    }
  }, [pointId, data?.point, rejectReason, navigate, success])

  const handleAction = useCallback(async (patchBody) => {
    try {
      const res = await apiFetch(`/api/hr/development-points/${pointId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patchBody),
      })
      if (!res.ok) throw new Error('Actie mislukt')
      await fetchIssue()
      const action = patchBody?.action
      if (action === 'approve') success('Development point goedgekeurd. Training wordt gestart.')
      else if (action === 'dismiss') success('Development point gesloten als false positive.')
    } catch (e) {
      setError(e.message || 'Actie mislukt')
      toastError('Actie mislukt. Probeer opnieuw.')
    }
  }, [pointId, fetchIssue, success, toastError])

  const handleRequestApproval = useCallback(() => {
    handleAction({ action: 'request_approval' })
  }, [handleAction])

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
        <ErrorState message={error} onRetry={fetchIssue} />
      </PageLayout>
    )
  }

  if (!data) {
    return (
      <PageLayout size="wide" padded>
        <EmptyState message="Development point niet gevonden." />
      </PageLayout>
    )
  }

  return (
    <PageLayout size="wide" padded>
      <div className="issue-detail-page" style={{ background: 'var(--color-bg-page)' }}>
        <IssueHeader
          point={data.point}
          agent={data.agent}
          impactStats={data.impact_stats}
          onRequestApproval={handleRequestApproval}
        />

        <section className="section-group">
          <SectionLabel>Agent & configuratie</SectionLabel>
          <div className="grid-3">
            <AgentInfoCard agent={data.agent} />
            <ModelSettingsCard agent={data.agent} />
            <IssueSummaryCard point={data.point} impactStats={data.impact_stats} />
          </div>
        </section>

        <section className="section-group">
          <SectionLabel>Diagnose</SectionLabel>
          <div className="grid-2">
            <RootCauseCard point={data.point} />
            <DiagnosisSignalsCard signals={data.signals} />
          </div>
        </section>

        <section className="section-group">
          <SectionLabel>Frequentietrend — afgelopen 30 dagen</SectionLabel>
          <FrequencyTrendCard trend={data.trend} />
        </section>

        <section className="section-group">
          <SectionLabel>Run evidence</SectionLabel>
          <div className="grid-2">
            <InputCard input={data.input} />
            <OutputCard output={data.output} />
          </div>
        </section>

        <section className="section-group">
          <SectionLabel>Execution timeline</SectionLabel>
          <TimelineTable timeline={data.timeline} runId={data.run_id} onCopy={() => info('Run ID gekopieerd.')} />
        </section>

        <section className="section-group">
          <SectionLabel>Patroon & correlatie</SectionLabel>
          <div className="grid-2">
            <PatternAnalysisCard pattern={data.pattern} />
            <CrossAgentCard correlations={data.cross_agent} />
          </div>
        </section>

        <section className="section-group">
          <SectionLabel>Impact & kosten</SectionLabel>
          <div className="grid-2">
            <ImpactCard stats={data.impact_stats} />
            <CostProjectionCard stats={data.impact_stats} trend={data.trend} />
          </div>
        </section>

        <section className="section-group">
          <SectionLabel>Aanbevolen fix roadmap</SectionLabel>
          <FixRoadmapCard />
        </section>

        <section className="section-group">
          <SectionLabel>Agent performance</SectionLabel>
          <PerformanceMetricsCard perf={data.performance} agent={data.agent} />
        </section>

        <section className="section-group">
          <SectionLabel>Acties</SectionLabel>
          <div className="grid-3">
            <ReproduceCard
              runId={data.run_id}
              pointId={pointId}
              onReproduce={(jobId, errMsg) => {
                if (errMsg) toastError('Actie mislukt. Probeer opnieuw.')
                else if (jobId) success('Run gestart. Navigeren naar job…')
              }}
            />
            <FeedbackCard
              feedback={data.feedback}
              pointId={pointId}
              agentId={data.agent?.agent_id}
              onAction={handleAction}
              onToast={(msg) => info(msg)}
            />
            <EvidenceCard evidence={data.evidence} point={data.point} />
          </div>
        </section>

        {['OPEN', 'AWAITING_APPROVAL'].includes((data.point?.status || '').toUpperCase()) && (
          <section className="section-group">
            <SectionLabel>Kennisbron & goedkeuring</SectionLabel>
            <div className="knowledge-source-section" style={{ maxWidth: '42rem' }}>
              <p className="section-subtitle" style={{ marginBottom: '1rem', color: 'var(--color-text-muted)' }}>
                Optioneel: voeg een bron toe die als trainingsmateriaal wordt gebruikt.
              </p>
              <div className="source-type-tabs" style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                {['url', 'text', 'file'].map((type) => (
                  <button
                    key={type}
                    type="button"
                    className={sourceType === type ? 'active' : ''}
                    style={{
                      padding: '0.5rem 0.75rem',
                      border: '1px solid var(--color-border)',
                      borderRadius: '6px',
                      background: sourceType === type ? 'var(--color-primary)' : 'var(--color-bg)',
                      color: sourceType === type ? 'white' : 'var(--color-text)',
                      cursor: 'pointer',
                      fontWeight: 500,
                    }}
                    onClick={() => setSourceType(type)}
                  >
                    {type === 'url' ? 'URL' : type === 'text' ? 'Tekst plakken' : 'Bestand'}
                  </button>
                ))}
              </div>
              {sourceType === 'url' && (
                <input
                  type="url"
                  className="source-input"
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  placeholder="https://..."
                  style={{ width: '100%', maxWidth: '28rem', padding: '0.5rem 0.75rem', marginBottom: '1rem', border: '1px solid var(--color-border)', borderRadius: '6px' }}
                />
              )}
              {sourceType === 'text' && (
                <textarea
                  className="source-textarea"
                  value={sourceText}
                  onChange={(e) => setSourceText(e.target.value)}
                  placeholder="Plak hier de trainingstekst..."
                  rows={8}
                  style={{ width: '100%', maxWidth: '42rem', padding: '0.5rem 0.75rem', marginBottom: '1rem', border: '1px solid var(--color-border)', borderRadius: '6px' }}
                />
              )}
              {sourceType === 'file' && (
                <input
                  type="file"
                  className="source-file"
                  accept=".txt,.pdf,.md,.docx"
                  onChange={(e) => setSourceFile(e.target.files?.[0] || null)}
                  style={{ display: 'block', marginBottom: '1rem' }}
                />
              )}
              {sourceError && <p className="source-error" style={{ color: 'var(--color-error)', fontSize: '0.875rem', marginBottom: '0.5rem' }}>{sourceError}</p>}
              <button
                type="button"
                className="btn-save-source"
                disabled={savingSource || (sourceType === 'url' && !sourceUrl.trim()) || (sourceType === 'text' && !sourceText.trim()) || (sourceType === 'file' && !sourceFile)}
                onClick={handleSaveSource}
                style={{ padding: '0.5rem 1rem', background: 'var(--color-bg-inverse)', color: 'var(--color-text-inverse)', border: 'none', borderRadius: '6px', fontWeight: 500, cursor: 'pointer' }}
              >
                {savingSource ? 'Opslaan...' : 'Bron opslaan'}
              </button>
              {data.point?.source_url && !data.point.source_url.startsWith('data:') && (
                <p style={{ marginTop: '0.75rem', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                  Huidige bron: <a href={data.point.source_url} target="_blank" rel="noreferrer">{data.point.source_url}</a>
                </p>
              )}
              {data.point?.source_url && data.point.source_url.startsWith('data:') && (
                <p style={{ marginTop: '0.75rem', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Huidige bron: bestand of tekst opgeslagen ✓</p>
              )}
            </div>
            <div className="issue-actions" style={{ marginTop: '1.5rem', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem' }}>
              {actionError && <p style={{ width: '100%', color: 'var(--color-error)', fontSize: '0.875rem' }}>{actionError}</p>}
              {!rejectMode ? (
                <>
                  <button
                    type="button"
                    className="btn-approve"
                    onClick={handleApprove}
                    disabled={processing}
                    style={{
                      padding: '0.5rem 1rem',
                      background: 'var(--color-success, #16a34a)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      fontWeight: 500,
                      cursor: processing ? 'not-allowed' : 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                    }}
                  >
                    {processing ? (
                      <>
                        <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Verwerken...
                      </>
                    ) : (
                      'Goedkeuren'
                    )}
                  </button>
                  <button
                    type="button"
                    className="btn-reject-open"
                    onClick={() => setRejectMode(true)}
                    disabled={processing}
                    style={{ padding: '0.5rem 1rem', border: '1px solid var(--color-error, #dc2626)', color: 'var(--color-error, #dc2626)', background: 'transparent', borderRadius: '6px', fontWeight: 500, cursor: 'pointer' }}
                  >
                    Afwijzen
                  </button>
                </>
              ) : (
                <div className="reject-form" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="text"
                    placeholder="Reden voor afwijzing (optioneel)"
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    style={{ padding: '0.5rem 0.75rem', border: '1px solid var(--color-border)', borderRadius: '6px', width: '16rem' }}
                  />
                  <button
                    type="button"
                    className="btn-reject-confirm"
                    onClick={handleReject}
                    disabled={processing}
                    style={{ padding: '0.5rem 1rem', background: 'var(--color-error, #dc2626)', color: 'white', border: 'none', borderRadius: '6px', fontWeight: 500, cursor: 'pointer' }}
                  >
                    {processing ? 'Verwerken...' : 'Bevestig afwijzing'}
                  </button>
                  <button
                    type="button"
                    className="btn-cancel"
                    onClick={() => setRejectMode(false)}
                    disabled={processing}
                    style={{ padding: '0.5rem 1rem', border: '1px solid var(--color-border)', borderRadius: '6px', fontWeight: 500, cursor: 'pointer' }}
                  >
                    Annuleer
                  </button>
                </div>
              )}
            </div>
          </section>
        )}
      </div>
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </PageLayout>
  )
}
