/**
 * Issue Detail page — GET /api/hr/development-points/:pointId.
 * Fase 2: data fetching, loading/error/empty, basis layout with SectionLabels and IssueHeader.
 * Fase 3+ fills in the card components.
 */
import React, { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
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
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const { toasts, removeToast, success, error: toastError, info } = useToast()

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

  const handleRequestApproval = useCallback(() => {
    handleAction({ action: 'request_approval' })
  }, [handleAction])

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
      </div>
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </PageLayout>
  )
}
