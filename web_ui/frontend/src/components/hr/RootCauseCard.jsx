/**
 * RootCauseCard — SVG confidence ring, Likely cause (amber), Suggested fix (blue) with Option A/B.
 * circumference = 2 * π * r (r=26 ≈ 163.4), dashoffset = circumference * (1 - confidence)
 */
import { AlertBox } from './shared'

const R = 26
const CIRCUMFERENCE = 2 * Math.PI * R // ≈ 163.4

export default function RootCauseCard({ point }) {
  if (!point) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
        <p className="text-sm text-[var(--color-text-muted)]">Geen gegevens.</p>
      </div>
    )
  }

  const confidence = point.confidence_score != null ? Math.min(1, Math.max(0, Number(point.confidence_score))) : null
  const dashOffset = confidence != null ? CIRCUMFERENCE * (1 - confidence) : CIRCUMFERENCE
  const confidencePct = confidence != null ? Math.round(confidence * 100) : null
  const rootCause = point.root_cause != null && typeof point.root_cause === 'string' ? point.root_cause : null

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Root cause</h3>

      {/* SVG confidence ring */}
      <div className="flex justify-center mb-5">
        <svg width="80" height="80" className="overflow-visible">
          <circle
            cx="40"
            cy="40"
            r={R}
            fill="none"
            stroke="var(--color-bg-input)"
            strokeWidth="6"
          />
          <circle
            cx="40"
            cy="40"
            r={R}
            fill="none"
            stroke="var(--color-status-warning)"
            strokeWidth="6"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
            transform="rotate(-90 40 40)"
          />
          <text
            x="40"
            y="44"
            textAnchor="middle"
            className="text-sm font-bold fill-[var(--color-text-primary)]"
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {confidencePct != null ? `${confidencePct}%` : '—'}
          </text>
        </svg>
      </div>

      {rootCause && (
        <AlertBox variant="amber" title="Likely cause" className="mb-3">
          {rootCause}
        </AlertBox>
      )}

      <AlertBox variant="blue" title="Suggested fix">
        <ul className="list-disc list-inside space-y-1 text-sm">
          <li><strong>Option A:</strong> Pas de prompt aan op het specifieke retry-gedrag (subheadings, format).</li>
          <li><strong>Option B:</strong> Verlaag de validatiestrictie tijdelijk en monitor of het probleem verdwijnt.</li>
        </ul>
      </AlertBox>
    </div>
  )
}
