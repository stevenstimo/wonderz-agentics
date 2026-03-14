/**
 * TimelineTable — kolommen: Tijd | Stap | Status | Duur | Notities.
 * Status badge: ok → groen, fail → rood. Run ID monospace + kopieerknop.
 */
import { useState, useCallback } from 'react'
import { Badge } from './shared'

export default function TimelineTable({ timeline, runId, onCopy }) {
  const [copied, setCopied] = useState(false)
  const list = Array.isArray(timeline) ? timeline : []

  const copyRunId = useCallback(() => {
    if (!runId) return
    try {
      navigator.clipboard.writeText(runId)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      onCopy?.()
    } catch (_) {}
  }, [runId, onCopy])

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Execution timeline</h3>

      {runId && (
        <div className="flex items-center gap-2 mb-4">
          <code className="flex-1 min-w-0 text-xs font-[family-name:var(--font-mono)] p-2 rounded-[var(--radius-sm)] bg-[var(--color-bg-subtle)] border border-[var(--color-border-subtle)] truncate">
            {typeof runId === 'string' || typeof runId === 'number' ? String(runId) : '—'}
          </code>
          <button
            type="button"
            onClick={copyRunId}
            className="flex-shrink-0 px-2 py-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border)] text-xs font-medium text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-subtle)]"
          >
            {copied ? 'Gekopieerd' : 'Kopiëren'}
          </button>
        </div>
      )}

      {list.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)]">Geen timelinestappen.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-muted)]">Tijd</th>
                <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-muted)]">Stap</th>
                <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-muted)]">Status</th>
                <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-muted)]">Duur</th>
                <th className="text-left py-2 font-medium text-[var(--color-text-muted)]">Notities</th>
              </tr>
            </thead>
            <tbody>
              {list.map((row, i) => (
                <tr key={i} className="border-b border-[var(--color-border-subtle)] last:border-b-0">
                  <td className="py-2 pr-4 font-[family-name:var(--font-mono)] text-xs text-[var(--color-text-primary)]">
                    {row.time != null && typeof row.time !== 'object' ? String(row.time) : '—'}
                  </td>
                  <td className="py-2 pr-4 text-[var(--color-text-primary)]">
                    {row.step != null && typeof row.step !== 'object' ? String(row.step) : '—'}
                  </td>
                  <td className="py-2 pr-4">
                    <Badge variant={row.status === 'ok' ? 'ok' : 'fail'}>{row.status === 'ok' ? 'ok' : 'fail'}</Badge>
                  </td>
                  <td className="py-2 pr-4 font-[family-name:var(--font-mono)] text-xs">
                    {row.duration_s != null && typeof row.duration_s !== 'object' ? `${Number(row.duration_s)}s` : '—'}
                  </td>
                  <td className="py-2 text-[var(--color-text-muted)]">
                    {row.notes != null && typeof row.notes !== 'object' ? String(row.notes) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
