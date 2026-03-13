/**
 * Badge — status/impact badge. Spec: variant 'open'|'ok'|'fail'|'low'|'medium'|'high'|'resolved'|'dismissed'|'pending'
 */
export default function Badge({ variant = 'open', children, className = '' }) {
  const base = 'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wide font-[family-name:var(--font-mono)]'
  const variants = {
    open: 'bg-[var(--color-status-warning-bg)] text-[#92400E] border border-[var(--color-status-warning)]',
    ok: 'bg-[var(--color-status-success-bg)] text-[#065F46] border border-[var(--color-status-success)]',
    resolved: 'bg-[var(--color-status-success-bg)] text-[#065F46] border border-[var(--color-status-success)]',
    fail: 'bg-[var(--color-status-error-bg)] text-[#991B1B] border border-[var(--color-status-error)]',
    low: 'bg-[var(--color-status-running-bg)] text-[#1E40AF] border border-[var(--color-status-running)]',
    medium: 'bg-[var(--color-status-warning-bg)] text-[#92400E] border border-[var(--color-status-warning)]',
    high: 'bg-[var(--color-status-error-bg)] text-[#991B1B] border border-[var(--color-status-error)]',
    dismissed: 'bg-[var(--color-bg-subtle)] text-[var(--color-text-muted)] border border-[var(--color-border)]',
    pending: 'bg-[var(--color-brand-primary-light)] text-[var(--color-brand-primary)] border border-[var(--color-brand-primary)]',
  }
  const v = variants[variant] || variants.open
  return <span className={`${base} ${v} ${className}`}>{children}</span>
}
