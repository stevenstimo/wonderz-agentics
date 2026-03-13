/**
 * AgentInfoCard — Naam, Versie, Skill tier, Workflow, Success rate (groen).
 */
import { DataRow } from './shared'

export default function AgentInfoCard({ agent }) {
  if (!agent) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
        <p className="text-sm text-[var(--color-text-muted)]">Geen agentgegevens.</p>
      </div>
    )
  }

  const successRate = agent.success_rate != null ? `${(Number(agent.success_rate) * 100).toFixed(1)}%` : '—'

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Agent</h3>
      <DataRow label="Naam" value={agent.agent_name} />
      <DataRow label="Versie" value={agent.agent_version} mono />
      <DataRow label="Skill tier" value={agent.role ?? agent.workflow ?? '—'} />
      <DataRow label="Workflow" value={agent.workflow} />
      <DataRow
        label="Success rate"
        value={successRate}
        accentColor={agent.success_rate != null && agent.success_rate >= 0.8 ? 'var(--color-status-success)' : undefined}
      />
    </div>
  )
}
