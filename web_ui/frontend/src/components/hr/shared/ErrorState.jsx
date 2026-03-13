/**
 * ErrorState — error message + optional retry
 */
export default function ErrorState({ message, onRetry, className = '' }) {
  return (
    <div
      className={`flex flex-col items-center justify-center min-h-[320px] gap-4 rounded-[var(--radius-md)] border border-[var(--color-status-error)] bg-[var(--color-status-error-bg)] text-[#991B1B] ${className}`}
    >
      <p className="text-sm font-medium">{message ?? 'Er is een fout opgetreden.'}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="px-4 py-2 rounded-[var(--radius-sm)] border border-[var(--color-status-error)] text-sm font-medium hover:opacity-90"
        >
          Opnieuw proberen
        </button>
      )}
    </div>
  )
}
