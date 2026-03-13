/**
 * CostProjectionCard — projectie 1m / 3m / 12m op basis van extra_cost_per_100 en trend.
 * Horizontale progress bars per tijdspan (breedte relatief aan max). Amber alert: cross-agent schatting.
 */
import { AlertBox } from './shared'

function projectCosts(stats, trend) {
  const monthlyFailures = Number(trend?.total_failures ?? 0) || 0
  const growthRate = (Number(trend?.vs_prev_period_pct ?? 0) || 0) / 100
  const costPer100 = Number(stats?.extra_cost_per_100 ?? 0) || 0

  const thisMonth = (monthlyFailures / 100) * costPer100
  const nextMonth = thisMonth * (1 + growthRate)
  const month3 = nextMonth * (1 + growthRate)
  const threeMonths = thisMonth + nextMonth + month3
  let twelveMonths = thisMonth
  let m = thisMonth
  for (let i = 0; i < 11; i++) {
    m = m * (1 + growthRate)
    twelveMonths += m
  }

  return { thisMonth, nextMonth, threeMonths, twelveMonths }
}

export default function CostProjectionCard({ stats, trend }) {
  const hasData = stats && trend && (stats.extra_cost_per_100 != null || (trend.total_failures ?? 0) > 0)
  const { thisMonth, nextMonth, threeMonths, twelveMonths } = hasData
    ? projectCosts(stats, trend)
    : { thisMonth: 0, nextMonth: 0, threeMonths: 0, twelveMonths: 0 }

  const maxVal = Math.max(1, twelveMonths, threeMonths, nextMonth, thisMonth)

  const bar = (value, label) => (
    <div key={label} className="mb-3">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-[var(--color-text-muted)]">{label}</span>
        <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--color-text-primary)]">
          €{value.toFixed(2)}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-[var(--color-bg-input)] overflow-hidden">
        <div
          className="h-full rounded-full bg-[var(--color-status-warning)]"
          style={{ width: `${(value / maxVal) * 100}%` }}
        />
      </div>
    </div>
  )

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Kostenprojectie</h3>
      {bar(thisMonth, '1 maand')}
      {bar(nextMonth, '2e maand')}
      {bar(threeMonths, '3 maanden')}
      {bar(twelveMonths, '12 maanden')}
      <AlertBox variant="amber" className="mt-4">
        Gecombineerde cross-agent schatting: bij meerdere agents met hetzelfde patroon kunnen de kosten oplopen.
      </AlertBox>
    </div>
  )
}
