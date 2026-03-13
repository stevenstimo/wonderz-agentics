/**
 * EmptyState — no data. Spec: message
 */
export default function EmptyState({ message = 'Geen data beschikbaar.', className = '' }) {
  return (
    <div
      className={`flex flex-col items-center justify-center min-h-[320px] rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] text-[var(--color-text-muted)] ${className}`}
    >
      <p className="text-sm">{message}</p>
    </div>
  )
}
