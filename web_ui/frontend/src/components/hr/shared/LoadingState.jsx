/**
 * LoadingState — skeleton/spinner for issue detail
 */
export default function LoadingState({ className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center min-h-[320px] gap-4 ${className}`}>
      <div className="w-10 h-10 rounded-full border-2 border-[var(--color-brand-primary)] border-t-transparent animate-spin" />
      <p className="text-sm text-[var(--color-text-muted)]">Laden...</p>
    </div>
  )
}
