import { safeDisplay } from './safeDisplay'

/**
 * MetricTile — label, value, sub, trend, accentColor.
 * All displayed values coerced via safeDisplay to avoid React #31.
 */
export default function MetricTile({ label, value, sub, trend, accentColor, className = '' }) {
  const subStr = safeDisplay(sub)
  const trendStr = safeDisplay(trend)
  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--color-border)] p-4 bg-[var(--color-bg-subtle)] ${className}`}
    >
      <div className="text-xs uppercase tracking-wide text-[var(--color-text-muted)] mb-1">{safeDisplay(label)}</div>
      <div
        className="text-2xl font-bold text-[var(--color-text-primary)] leading-tight"
        style={accentColor ? { color: accentColor } : undefined}
      >
        {safeDisplay(value)}
      </div>
      {subStr !== '—' && <div className="text-xs text-[var(--color-text-muted)] mt-1">{subStr}</div>}
      {trendStr !== '—' && (
        <div className="text-xs mt-1 text-[var(--color-status-error)]">{trendStr}</div>
      )}
    </div>
  )
}
