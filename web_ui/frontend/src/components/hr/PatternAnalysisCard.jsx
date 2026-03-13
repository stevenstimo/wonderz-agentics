/**
 * PatternAnalysisCard — pattern data rows + two progress bars:
 * Success rate workflow (green), Failure rate bij trigger-conditie (amber).
 */
import { DataRow, ProgressBar } from './shared'

export default function PatternAnalysisCard({ pattern }) {
  if (!pattern) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Patroon</h3>
        <p className="text-sm text-[var(--color-text-muted)]">Geen patroongegevens.</p>
      </div>
    )
  }

  const successRate = pattern.workflow_success_rate != null ? Number(pattern.workflow_success_rate) : null
  const failureRate = pattern.failure_rate_condition != null ? Number(pattern.failure_rate_condition) : null

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Patroonanalyse</h3>
      <DataRow label="Workflow" value={pattern.workflow} />
      <DataRow label="Triggerconditie" value={pattern.trigger_condition ?? '—'} />
      <DataRow label="Getroffen versie" value={pattern.affected_version} mono />

      <div className="mt-4 space-y-3">
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-[var(--color-text-muted)]">Success rate workflow</span>
            <span className="font-[family-name:var(--font-mono)] text-xs">
              {successRate != null ? `${(successRate * 100).toFixed(0)}%` : '—'}
            </span>
          </div>
          <ProgressBar value={successRate} variant="green" />
        </div>
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-[var(--color-text-muted)]">Failure rate bij trigger</span>
            <span className="font-[family-name:var(--font-mono)] text-xs">
              {failureRate != null ? `${(failureRate * 100).toFixed(0)}%` : '—'}
            </span>
          </div>
          <ProgressBar value={failureRate} variant="amber" />
        </div>
      </div>
    </div>
  )
}
