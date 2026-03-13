/**
 * FeedbackCard — feedback quote + actieknoppen (Approve & train, False positive, Improve prompt, Adjust validator).
 * onAction(patchBody) for PATCH; Improve prompt → navigate to agent edit; Adjust validator → toast "Binnenkort beschikbaar".
 */
import { Link } from 'react-router-dom'

export default function FeedbackCard({ feedback, pointId, agentId, onAction, onToast }) {
  const handleApprove = () => onAction && onAction({ action: 'approve' })
  const handleDismiss = () => onAction && onAction({ action: 'dismiss', reason: 'false_positive' })
  const handleAdjustValidator = () => onToast && onToast('Binnenkort beschikbaar')

  const formatDate = (iso) => {
    if (!iso) return ''
    try {
      return new Date(iso).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    } catch (_) {
      return iso
    }
  }

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Feedback</h3>
      {feedback?.text && (
        <blockquote className="italic text-sm text-[var(--color-text-secondary)] mb-2 border-l-2 border-[var(--color-border)] pl-3">
          {feedback.text}
        </blockquote>
      )}
      {(feedback?.author || feedback?.created_at) && (
        <p className="text-xs text-[var(--color-text-muted)] mb-4">
          {feedback.author ?? '—'} {feedback.created_at && ` · ${formatDate(feedback.created_at)}`}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleApprove}
          className="px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--color-status-success-bg)] text-[#065F46] border border-[var(--color-status-success)] text-sm font-medium hover:opacity-90"
        >
          Approve & train
        </button>
        <button
          type="button"
          onClick={handleDismiss}
          className="px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--color-status-error-bg)] text-[#991B1B] border border-[var(--color-status-error)] text-sm font-medium hover:opacity-90"
        >
          False positive
        </button>
        {agentId && (
          <Link
            to={`/agents/${agentId}/edit`}
            className="px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--color-status-warning-bg)] text-[#92400E] border border-[var(--color-status-warning)] text-sm font-medium hover:opacity-90 inline-block"
          >
            Improve prompt
          </Link>
        )}
        <button
          type="button"
          onClick={handleAdjustValidator}
          className="px-3 py-1.5 rounded-[var(--radius-sm)] bg-[var(--color-bg-subtle)] text-[var(--color-text-secondary)] border border-[var(--color-border)] text-sm font-medium hover:bg-[var(--color-bg-input)]"
        >
          Adjust validator
        </button>
      </div>
    </div>
  )
}
