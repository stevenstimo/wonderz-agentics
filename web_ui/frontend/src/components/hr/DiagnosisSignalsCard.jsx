/**
 * DiagnosisSignalsCard — signals array: icon, name, description, weight (0–1).
 * Per signal: icon + name + description left, weight bar + percentage right.
 * Fallback: "Geen diagnosesignalen beschikbaar."
 */
import { ProgressBar } from './shared'

export default function DiagnosisSignalsCard({ signals }) {
  const list = Array.isArray(signals) ? signals : []

  if (list.length === 0) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Diagnosesignalen</h3>
        <div className="rounded-[var(--radius-sm)] border border-[var(--color-border-subtle)] p-4 bg-[var(--color-bg-subtle)] text-center">
          <p className="text-sm text-[var(--color-text-muted)]">Geen diagnosesignalen beschikbaar.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Diagnosesignalen</h3>
      <div className="space-y-4">
        {list.map((sig, i) => {
          const weight = sig.weight != null ? Math.min(1, Math.max(0, Number(sig.weight))) : 0
          const pct = Math.round(weight * 100)
          return (
            <div key={i} className="flex items-start gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-[var(--radius-sm)] bg-[var(--color-bg-subtle)] flex items-center justify-center text-base">
                {sig.icon ?? '📌'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm text-[var(--color-text-primary)]">{sig.name ?? '—'}</div>
                {sig.description && (
                  <div className="text-xs text-[var(--color-text-muted)] mt-0.5">{sig.description}</div>
                )}
                <div className="mt-2 flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <ProgressBar value={weight} variant="amber" />
                  </div>
                  <span className="flex-shrink-0 font-[family-name:var(--font-mono)] text-xs text-[var(--color-text-secondary)]">
                    {pct}%
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
