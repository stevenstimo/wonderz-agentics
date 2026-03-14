/**
 * IssueSummaryCard — Type, Sub-type, Status (badge), Impact (badge), Retries per run, Affected jobs.
 */
import { Badge, DataRow } from './shared'

export default function IssueSummaryCard({ point, impactStats }) {
  if (!point) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
        <p className="text-sm text-[var(--color-text-muted)]">Geen gegevens.</p>
      </div>
    )
  }

  const status = typeof point.status === 'string' ? point.status.toUpperCase() : 'OPEN'
  const impact = typeof point.impact === 'string' ? point.impact.toLowerCase() : 'low'
  const statusVariant = {
    OPEN: 'open',
    AWAITING_APPROVAL: 'pending',
    IN_TRAINING: 'pending',
    RESOLVED: 'resolved',
    DISMISSED: 'dismissed',
  }[status] || 'open'
  const impactVariant = impact === 'high' ? 'high' : impact === 'medium' ? 'medium' : 'low'

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Samenvatting</h3>
      <DataRow label="Type" value="Development point" />
      <DataRow label="Sub-type" value={point.root_cause ? 'Retry pattern' : '—'} />
      <div className="flex justify-between items-center py-2 border-b border-[var(--color-border-subtle)]">
        <span className="text-sm text-[var(--color-text-muted)]">Status</span>
        <Badge variant={statusVariant}>{status}</Badge>
      </div>
      <div className="flex justify-between items-center py-2 border-b border-[var(--color-border-subtle)]">
        <span className="text-sm text-[var(--color-text-muted)]">Impact</span>
        <Badge variant={impactVariant}>{impact}</Badge>
      </div>
      <DataRow label="Retries per run" value={point.frequency ?? '—'} />
      <DataRow label="Affected jobs" value={impactStats?.affected_jobs ?? '—'} />
    </div>
  )
}
