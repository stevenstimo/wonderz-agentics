/**
 * InputCard — task_prompt (code block), briefing (data rows), extra_params (conflicting field marked).
 * format: 'scan friendly' rood/amber als conflicterend veld.
 */
import { DataRow } from './shared'

const CONFLICT_FIELDS = ['format', 'scan friendly']

export default function InputCard({ input }) {
  if (!input) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Input</h3>
        <p className="text-sm text-[var(--color-text-muted)]">Geen inputgegevens beschikbaar.</p>
      </div>
    )
  }

  const taskPrompt = input.task_prompt || ''
  const briefing = input.briefing && typeof input.briefing === 'object' ? input.briefing : {}
  const extraParams = input.extra_params && typeof input.extra_params === 'object' ? input.extra_params : {}

  const isConflictValue = (key, val) => {
    const v = String(val || '').toLowerCase()
    return CONFLICT_FIELDS.some((c) => key.toLowerCase().includes(c) || v.includes('scan') || v.includes('friendly'))
  }

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Input</h3>

      <div className="mb-4">
        <div className="text-xs uppercase tracking-wide text-[var(--color-text-muted)] mb-1">Task prompt</div>
        <pre className="text-xs font-[family-name:var(--font-mono)] p-3 rounded-[var(--radius-sm)] bg-[var(--color-bg-subtle)] border border-[var(--color-border-subtle)] overflow-x-auto whitespace-pre-wrap">
          {typeof taskPrompt === 'string' ? taskPrompt : (taskPrompt != null && typeof taskPrompt !== 'object' ? String(taskPrompt) : '—')}
        </pre>
      </div>

      {Object.keys(briefing).length > 0 && (
        <div className="mb-4">
          <div className="text-xs uppercase tracking-wide text-[var(--color-text-muted)] mb-2">Input briefing</div>
          {Object.entries(briefing).map(([k, v]) => (
            <DataRow key={k} label={k} value={v} />
          ))}
        </div>
      )}

      {Object.keys(extraParams).length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--color-text-muted)] mb-2">Extra parameters</div>
          {Object.entries(extraParams).map(([k, v]) => {
            const conflict = isConflictValue(k, v)
            return (
              <div
                key={k}
                className={`flex justify-between items-center py-2 border-b border-[var(--color-border-subtle)] last:border-b-0 ${conflict ? 'text-[var(--color-status-warning)]' : ''}`}
              >
                <span className="text-sm text-[var(--color-text-muted)]">{k}</span>
                <span className={`text-sm font-medium font-[family-name:var(--font-mono)] ${conflict ? 'text-[var(--color-status-warning)]' : 'text-[var(--color-text-primary)]'}`}>
                  {String(v ?? '—')}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
