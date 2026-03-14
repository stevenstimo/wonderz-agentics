/**
 * OutputCard — summary (code block), validation_rules (✓/✗), problem_description (red alert).
 * Status badge "Failed validation" rechtsboven.
 */
import { Badge, AlertBox } from './shared'

export default function OutputCard({ output }) {
  if (!output) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Output</h3>
        <p className="text-sm text-[var(--color-text-muted)]">Geen outputgegevens beschikbaar.</p>
      </div>
    )
  }

  const summary = output.summary != null && typeof output.summary !== 'object' ? String(output.summary) : ''
  const rules = Array.isArray(output.validation_rules) ? output.validation_rules : []
  const problem = output.problem_description != null && typeof output.problem_description !== 'object' ? String(output.problem_description) : ''
  const hasFailed = rules.some((r) => r.passed === false)

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Output</h3>
        {hasFailed && (
          <Badge variant="fail">Failed validation</Badge>
        )}
      </div>

      {summary && (
        <div className="mb-4">
          <div className="text-xs uppercase tracking-wide text-[var(--color-text-muted)] mb-1">Output preview</div>
          <pre className="text-xs font-[family-name:var(--font-mono)] p-3 rounded-[var(--radius-sm)] bg-[var(--color-bg-subtle)] border border-[var(--color-border-subtle)] overflow-x-auto whitespace-pre-wrap max-h-32">
            {summary}
          </pre>
        </div>
      )}

      {rules.length > 0 && (
        <div className="mb-4">
          <div className="text-xs uppercase tracking-wide text-[var(--color-text-muted)] mb-2">Validatieregels — verwacht vs ontvangen</div>
          <ul className="space-y-1.5">
            {rules.map((r, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                <span className={r.passed ? 'text-[var(--color-status-success)]' : 'text-[var(--color-status-error)]'}>
                  {r.passed ? '✓' : '✗'}
                </span>
                <span className={r.passed ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-status-error)]'}>
                  {r.rule != null && typeof r.rule !== 'object' ? String(r.rule) : '—'}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {problem && (
        <AlertBox variant="red" title="Probleem">
          {problem}
        </AlertBox>
      )}
    </div>
  )
}
