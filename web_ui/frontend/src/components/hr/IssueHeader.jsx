/**
 * IssueHeader — breadcrumb, badges, title, subtitle, header stats, Terug / Delen / Stuur naar CEO.
 * "Stuur naar CEO" calls PATCH with { action: "request_approval" }.
 */
import { Link } from 'react-router-dom'
import { Badge } from './shared'

function formatDate(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch (_) {
    return iso
  }
}

export default function IssueHeader({ point, agent, impactStats, onRequestApproval }) {
  const pointId = point?.point_id ?? '—'
  const status = (point?.status || 'OPEN').toUpperCase()
  const impact = (point?.impact || 'low').toLowerCase()
  const statusVariant = {
    OPEN: 'open',
    AWAITING_APPROVAL: 'pending',
    IN_TRAINING: 'pending',
    RESOLVED: 'resolved',
    DISMISSED: 'dismissed',
  }[status] || 'open'
  const impactVariant = impact === 'high' ? 'high' : impact === 'medium' ? 'medium' : 'low'
  const canRequestApproval = status === 'OPEN' && typeof onRequestApproval === 'function'

  const handleShare = () => {
    try {
      const url = window.location.href
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(url)
        // Could trigger toast "Link gekopieerd"
      }
    } catch (_) {}
  }

  return (
    <header className="pb-6 border-b border-[var(--color-border)] mb-6">
      <div className="flex items-center gap-2 text-sm text-[var(--color-text-muted)] mb-3">
        <Link to="/hr" className="text-[var(--color-text-secondary)] hover:text-[var(--color-brand-primary)]">
          HR Manager
        </Link>
        <span className="text-[var(--color-border)]">›</span>
        <Link to="/hr" className="text-[var(--color-text-secondary)] hover:text-[var(--color-brand-primary)]">
          Development Points
        </Link>
        <span className="text-[var(--color-border)]">›</span>
        <span className="text-[var(--color-brand-primary)] font-medium">{pointId}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--color-text-muted)] bg-[var(--color-bg-input)] border border-[var(--color-border)] px-2 py-1 rounded-[var(--radius-sm)]">
          {pointId}
        </span>
        <Badge variant={statusVariant}>{status}</Badge>
        <Badge variant={impactVariant}>{impact}</Badge>
      </div>
      <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mb-1" style={{ fontFamily: 'var(--font-primary)' }}>
        {point?.issue_description ?? '—'}
      </h1>
      {point?.root_cause && (
        <p className="text-sm text-[var(--color-text-muted)] mb-4">{point.root_cause}</p>
      )}
      {/* Header stat row */}
      <div className="flex flex-wrap items-center gap-6 text-sm mb-4">
        <div className="flex flex-col">
          <span className="text-xs uppercase tracking-wide text-[var(--color-text-muted)]">Detected by</span>
          <span className="font-medium text-[var(--color-text-primary)]">{point?.proposed_by ?? '—'}</span>
        </div>
        <div className="w-px h-7 bg-[var(--color-border)]" />
        <div className="flex flex-col">
          <span className="text-xs uppercase tracking-wide text-[var(--color-text-muted)]">First seen</span>
          <span className="font-medium text-[var(--color-text-primary)]">{formatDate(point?.created_at)}</span>
        </div>
        <div className="w-px h-7 bg-[var(--color-border)]" />
        <div className="flex flex-col">
          <span className="text-xs uppercase tracking-wide text-[var(--color-text-muted)]">Last seen</span>
          <span className="font-medium text-[var(--color-text-primary)]">{formatDate(point?.resolved_at) ?? '—'}</span>
        </div>
        <div className="w-px h-7 bg-[var(--color-border)]" />
        <div className="flex flex-col">
          <span className="text-xs uppercase tracking-wide text-[var(--color-text-muted)]">Frequency (30d)</span>
          <span className="font-medium text-[var(--color-text-primary)]">{point?.frequency ?? '—'}</span>
        </div>
        {(impactStats?.extra_cost_per_100 != null) && (
          <>
            <div className="w-px h-7 bg-[var(--color-border)]" />
            <div className="flex flex-col">
              <span className="text-xs uppercase tracking-wide text-[var(--color-text-muted)]">Extra cost</span>
              <span className="font-medium text-[var(--color-text-primary)]">€{Number(impactStats.extra_cost_per_100).toFixed(2)} / 100</span>
            </div>
          </>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Link
          to="/hr"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border)] text-sm font-medium text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-subtle)]"
        >
          ← Terug
        </Link>
        <button
          type="button"
          onClick={handleShare}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border)] text-sm font-medium text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-subtle)]"
        >
          Delen
        </button>
        {canRequestApproval && (
          <button
            type="button"
            onClick={() => onRequestApproval()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--color-brand-primary)] text-white text-sm font-semibold hover:opacity-90"
          >
            Stuur naar CEO
          </button>
        )}
      </div>
    </header>
  )
}
