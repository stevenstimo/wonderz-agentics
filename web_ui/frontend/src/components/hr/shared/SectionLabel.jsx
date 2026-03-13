/**
 * SectionLabel — section heading with line. Spec: children
 */
export default function SectionLabel({ children, className = '' }) {
  return (
    <div
      className={`flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--color-text-muted)] mb-3 ${className}`}
    >
      <span>{children}</span>
      <span className="flex-1 h-px bg-[var(--color-border-subtle)]" />
    </div>
  )
}
