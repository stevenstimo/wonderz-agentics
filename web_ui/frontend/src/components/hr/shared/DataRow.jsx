/**
 * DataRow — label + value, optional mono, accentColor
 */
export default function DataRow({ label, value, mono = false, accentColor, className = '' }) {
  return (
    <div className={`flex justify-between items-center py-2 border-b border-[var(--color-border-subtle)] last:border-b-0 ${className}`}>
      <span className="text-[var(--color-text-muted)] text-sm">{label}</span>
      <span
        className={`text-sm font-medium text-[var(--color-text-primary)] ${mono ? 'font-[family-name:var(--font-mono)] text-xs' : ''}`}
        style={accentColor ? { color: accentColor } : undefined}
      >
        {value ?? '—'}
      </span>
    </div>
  )
}
