/**
 * FrequencyTrendCard — SVG line chart (failures amber, successes green) + 4 metric tiles.
 * trend: { daily: [{ date, failures, successes }], total_failures, peak_day: { date, count }, daily_avg, vs_prev_period_pct }
 * Fallback when trend.daily empty: "Trenddata niet beschikbaar."; tiles still shown when trend has totals.
 */
import { MetricTile } from './shared'

const CHART_HEIGHT = 120
const GRID_Y = [5, 10, 15]

function formatDateLabel(dateStr) {
  if (dateStr == null || typeof dateStr === 'object') return '—'
  try {
    const d = new Date(dateStr)
    const s = d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })
    return typeof s === 'string' ? s : '—'
  } catch (_) {
    return '—'
  }
}

export default function FrequencyTrendCard({ trend }) {
  const daily = trend?.daily && Array.isArray(trend.daily) ? trend.daily : []
  const hasChartData = daily.length > 0
  const totalFailures = trend?.total_failures ?? 0
  const peakDay = trend?.peak_day
  const dailyAvg = trend?.daily_avg ?? null
  const vsPrev = trend?.vs_prev_period_pct

  // SVG coordinates: failures and successes lines
  const chartWidth = 800
  const maxVal = hasChartData
    ? Math.max(1, ...daily.map((d) => (d.failures || 0) + (d.successes || 0)))
    : 1
  const failurePoints = hasChartData
    ? daily.map((d, i) => {
        const x = (daily.length <= 1 ? 0 : i / (daily.length - 1)) * chartWidth
        const y = CHART_HEIGHT - (Number(d.failures || 0) / maxVal) * CHART_HEIGHT
        return `${x},${y}`
      }).join(' ')
    : ''
  const successPoints = hasChartData
    ? daily.map((d, i) => {
        const x = (daily.length <= 1 ? 0 : i / (daily.length - 1)) * chartWidth
        const y = CHART_HEIGHT - (Number(d.successes || 0) / maxVal) * CHART_HEIGHT
        return `${x},${y}`
      }).join(' ')
    : ''
  const firstDate = daily[0]?.date
  const midDate = daily.length >= 2 ? daily[Math.floor(daily.length / 2)]?.date : null
  const lastDate = daily.length >= 1 ? daily[daily.length - 1]?.date : null

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Frequentie — 30 dagen</h3>

      {!hasChartData ? (
        <div className="rounded-[var(--radius-sm)] border border-[var(--color-border-subtle)] p-6 bg-[var(--color-bg-subtle)] text-center mb-4">
          <p className="text-sm text-[var(--color-text-muted)]">Trenddata niet beschikbaar.</p>
        </div>
      ) : (
        <div className="w-full overflow-x-auto">
          <svg
            viewBox={`0 0 ${chartWidth} ${CHART_HEIGHT}`}
            className="w-full min-h-[120px]"
            preserveAspectRatio="none"
          >
            <defs>
              <linearGradient id="failGrad" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="var(--color-status-warning-bg)" />
                <stop offset="100%" stopColor="var(--color-status-warning)" stopOpacity="0.2" />
              </linearGradient>
              <linearGradient id="successGrad" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="var(--color-status-success-bg)" />
                <stop offset="100%" stopColor="var(--color-status-success)" stopOpacity="0.2" />
              </linearGradient>
            </defs>
            {/* Grid */}
            {GRID_Y.map((gy) => (
              <line
                key={gy}
                x1={0}
                y1={CHART_HEIGHT - (gy / maxVal) * CHART_HEIGHT}
                x2={chartWidth}
                y2={CHART_HEIGHT - (gy / maxVal) * CHART_HEIGHT}
                stroke="var(--color-border)"
                strokeDasharray="2,2"
                strokeWidth="0.5"
              />
            ))}
            {/* Failures fill + line */}
            {failurePoints && (
              <>
                <polygon
                  points={`0,${CHART_HEIGHT} ${failurePoints} ${chartWidth},${CHART_HEIGHT}`}
                  fill="url(#failGrad)"
                />
                <polyline
                  points={failurePoints}
                  fill="none"
                  stroke="var(--color-status-warning)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </>
            )}
            {/* Successes fill + line */}
            {successPoints && (
              <>
                <polygon
                  points={`0,${CHART_HEIGHT} ${successPoints} ${chartWidth},${CHART_HEIGHT}`}
                  fill="url(#successGrad)"
                />
                <polyline
                  points={successPoints}
                  fill="none"
                  stroke="var(--color-status-success)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </>
            )}
            {/* Today vertical dashed line (last point) */}
            {daily.length >= 2 && (
              <line
                x1={chartWidth}
                y1={0}
                x2={chartWidth}
                y2={CHART_HEIGHT}
                stroke="var(--color-border)"
                strokeDasharray="4,4"
                strokeWidth="1"
              />
            )}
          </svg>
          <div className="flex justify-between text-xs text-[var(--color-text-muted)] mt-1 px-0.5">
            <span>{formatDateLabel(firstDate)}</span>
            {midDate && <span>{formatDateLabel(midDate)}</span>}
            <span>{formatDateLabel(lastDate)} (vandaag)</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
        <MetricTile
          label="Total failures"
          value={totalFailures}
          sub={hasChartData ? '30 dagen' : null}
        />
        <MetricTile
          label="Piekdag"
          value={peakDay?.count ?? '—'}
          sub={peakDay?.date ? formatDateLabel(peakDay.date) : null}
        />
        <MetricTile
          label="Dagelijks gem."
          value={dailyAvg != null ? dailyAvg : '—'}
        />
        <MetricTile
          label="Trend"
          value={vsPrev != null ? `${vsPrev > 0 ? '+' : ''}${vsPrev}%` : '—'}
          trend={vsPrev != null && vsPrev > 0 ? `+${vsPrev}% t.o.v. vorige periode` : null}
        />
      </div>
    </div>
  )
}
