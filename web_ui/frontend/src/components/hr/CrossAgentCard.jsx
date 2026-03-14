/**
 * CrossAgentCard — correlations table: Agent | Versie | Failures (30d) | Impact.
 * First row = current agent ("Dit issue"). Blue alert when 2+ correlations: cross-training kans.
 */
import { Badge, AlertBox } from './shared'

export default function CrossAgentCard({ correlations }) {
  const list = Array.isArray(correlations) ? correlations : []

  if (list.length === 0) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Cross-agent</h3>
        <p className="text-sm text-[var(--color-text-muted)]">Geen andere agents met dit patroon gevonden.</p>
      </div>
    )
  }

  const impactVariant = (impact) => (impact === 'high' ? 'high' : impact === 'medium' ? 'medium' : 'low')
  const showCrossTrainingAlert = list.length >= 2

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Cross-agent</h3>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)]">
              <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-muted)]">Agent</th>
              <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-muted)]">Versie</th>
              <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-muted)]">Failures (30d)</th>
              <th className="text-left py-2 font-medium text-[var(--color-text-muted)]">Impact</th>
            </tr>
          </thead>
          <tbody>
            {list.map((row, i) => (
              <tr key={typeof row.agent_id === 'string' ? row.agent_id : i} className="border-b border-[var(--color-border-subtle)] last:border-b-0">
                <td className="py-2 pr-4">
                  <span className="text-[var(--color-text-primary)]">
                    {row.agent_name != null && typeof row.agent_name !== 'object' ? String(row.agent_name) : '—'}
                  </span>
                  {row.is_current && (
                    <span className="ml-2 text-xs text-[var(--color-brand-primary)] font-medium">(Dit issue)</span>
                  )}
                </td>
                <td className="py-2 pr-4 font-[family-name:var(--font-mono)] text-xs">
                  {row.version != null && typeof row.version !== 'object' ? String(row.version) : '—'}
                </td>
                <td className="py-2 pr-4">
                  {row.failures_30d != null && typeof row.failures_30d !== 'object' ? String(row.failures_30d) : '—'}
                </td>
                <td className="py-2">
                  <Badge variant={impactVariant(typeof row.impact === 'string' ? row.impact : 'low')}>
                    {row.impact != null && typeof row.impact !== 'object' ? String(row.impact) : 'low'}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {showCrossTrainingAlert && (
        <AlertBox variant="blue" className="mt-4">
          Cross-training kans gedetecteerd door HR Manager.
        </AlertBox>
      )}
    </div>
  )
}
