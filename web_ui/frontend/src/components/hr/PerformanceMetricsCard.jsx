/**
 * PerformanceMetricsCard — 4 tiles met progress bars: Success rate (groen), Retry rate (amber), Validation failures (rood), Avg cost per run (blauw).
 */
import { ProgressBar } from './shared'

export default function PerformanceMetricsCard({ perf, agent }) {
  if (!perf && !agent) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Agent performance</h3>
        <p className="text-sm text-[var(--color-text-muted)]">Geen performancegegevens.</p>
      </div>
    )
  }

  const successRate = perf?.success_rate ?? agent?.success_rate ?? null
  const retryRate = perf?.retry_rate ?? null
  const validationFailureRate = perf?.validation_failure_rate ?? null
  const avgCost = perf?.avg_cost_per_run ?? null

  const tile = (label, value, variant, isPct = true) => {
    const num = value != null ? Number(value) : null
    const v = num != null ? (isPct ? Math.min(1, Math.max(0, num)) : Math.min(1, num / 1)) : null
    const display = num != null ? (isPct ? `${(num <= 1 ? num * 100 : num).toFixed(1)}%` : `€${num.toFixed(2)}`) : '—'
    return (
      <div key={label} className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4 bg-[var(--color-bg-subtle)]">
        <div className="text-xs uppercase tracking-wide text-[var(--color-text-muted)] mb-2">{label}</div>
        <div className="text-xl font-bold text-[var(--color-text-primary)] mb-1">{display}</div>
        {v != null && <ProgressBar value={v} variant={variant} />}
      </div>
    )
  }

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Agent performance</h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {tile('Success rate', successRate, 'green')}
        {tile('Retry rate', retryRate, 'amber')}
        {tile('Validation failures', validationFailureRate, 'red')}
        {tile('Avg cost per run', avgCost, 'blue', false)}
      </div>
    </div>
  )
}
