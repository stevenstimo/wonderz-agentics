/**
 * MetricTile — label, value, sub, trend, accentColor
 */
export default function MetricTile({ label, value, sub, trend, accentColor, className = '' }) {
  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--color-border)] p-4 bg-[var(--color-bg-subtle)] ${className}`}
    >
      <div className="text-xs uppercase tracking-wide text-[var(--color-text-muted)] mb-1">{label}</div>
      <div
        className="text-2xl font-bold text-[var(--color-text-primary)] leading-tight"
        style={accentColor ? { color: accentColor } : undefined}
      >
        {value ?? '—'}
      </div>
      {sub != null && sub !== '' && <div className="text-xs text-[var(--color-text-muted)] mt-1">{sub}</div>}
      {trend != null && trend !== '' && (
        <div className="text-xs mt-1 text-[var(--color-status-error)]">{trend}</div>
      )}
    </div>
  )
}
