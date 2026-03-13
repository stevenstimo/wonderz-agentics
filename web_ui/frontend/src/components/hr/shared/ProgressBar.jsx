/**
 * ProgressBar — value 0–1, variant 'green'|'amber'|'red'|'blue'
 */
export default function ProgressBar({ value = 0, variant = 'green', className = '' }) {
  const pct = Math.min(1, Math.max(0, Number(value))) * 100
  const fillClass = {
    green: 'bg-[var(--color-status-success)]',
    amber: 'bg-[var(--color-status-warning)]',
    red: 'bg-[var(--color-status-error)]',
    blue: 'bg-[var(--color-brand-primary)]',
  }[variant] || 'bg-[var(--color-status-success)]'
  return (
    <div className={`h-1.5 w-full rounded-full bg-[var(--color-bg-input)] overflow-hidden ${className}`}>
      <div
        className={`h-full rounded-full transition-[width] ${fillClass}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}
