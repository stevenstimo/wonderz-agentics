/**
 * AlertBox — variant 'amber'|'green'|'red'|'blue', optional title
 */
export default function AlertBox({ variant = 'amber', title, children, className = '' }) {
  const styles = {
    amber: 'bg-[var(--color-status-warning-bg)] border-[var(--color-status-warning)] text-[#92400E]',
    green: 'bg-[var(--color-status-success-bg)] border-[var(--color-status-success)] text-[#065F46]',
    red: 'bg-[var(--color-status-error-bg)] border-[var(--color-status-error)] text-[#991B1B]',
    blue: 'bg-[var(--color-brand-primary-light)] border-[var(--color-brand-primary)] text-[var(--color-brand-primary)]',
  }
  const s = styles[variant] || styles.amber
  return (
    <div className={`rounded-[var(--radius-sm)] border p-3 ${s} ${className}`}>
      {title && <div className="font-semibold text-sm mb-1">{title}</div>}
      <div className="text-sm">{children}</div>
    </div>
  )
}
