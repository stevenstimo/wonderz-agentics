/**
 * ImpactCard — 4 metric tiles: Affected jobs, Total retries, Extra cost / 100 runs, User impact.
 * Amber alert: beschrijving van de gebruikerservaring.
 */
import { MetricTile, AlertBox } from './shared'

export default function ImpactCard({ stats }) {
  if (!stats) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Impact</h3>
        <p className="text-sm text-[var(--color-text-muted)]">Geen impactgegevens.</p>
      </div>
    )
  }

  const affectedJobs = stats.affected_jobs ?? '—'
  const totalRetries = stats.total_retries ?? '—'
  const extraCost = stats.extra_cost_per_100 != null ? `€${Number(stats.extra_cost_per_100).toFixed(2)}` : '—'
  const userFacing = stats.user_facing === true ? 'Ja' : stats.user_facing === false ? 'Nee' : '—'

  const userExperienceText = stats.user_facing
    ? 'Dit issue heeft directe impact op de gebruikerservaring (vertraagde of mislukte runs).'
    : 'Geen directe gebruikersimpact; voornamelijk interne retries en kosten.'

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Impact</h3>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <MetricTile label="Affected jobs" value={affectedJobs} />
        <MetricTile label="Total retries" value={totalRetries} />
        <MetricTile label="Extra cost / 100 runs" value={extraCost} />
        <MetricTile label="User impact" value={userFacing} />
      </div>
      <AlertBox variant="amber">
        {userExperienceText}
      </AlertBox>
    </div>
  )
}
