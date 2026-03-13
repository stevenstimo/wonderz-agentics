/**
 * ModelSettingsCard — Model (mono), Max tokens (mono), Temperature & Top-P sliders with tooltips.
 * Tooltips: Temperature, Top-P, Max tokens per spec.
 */
import { useState } from 'react'
import { DataRow } from './shared'

const TOOLTIPS = {
  temperature: 'Bepaalt willekeur en creativiteit van het model',
  top_p: 'Beperkt tokenselectie tot de meest waarschijnlijke tokens',
  max_tokens: 'Maximale outputlengte van de agent',
}

function SliderRow({ label, value, variant, tooltip, valueLabel }) {
  const [showTooltip, setShowTooltip] = useState(false)
  const v = value != null ? Number(value) : 0
  const pct = Math.min(1, Math.max(0, v)) * 100
  const trackColor = variant === 'amber' ? 'var(--color-status-warning)' : 'var(--color-brand-primary)'

  return (
    <div className="grid grid-cols-[120px_1fr_44px] items-center gap-3 py-2 border-b border-[var(--color-border-subtle)] last:border-b-0">
      <div className="relative">
        <span className="text-sm text-[var(--color-text-secondary)]">{label}</span>
        {tooltip && (
          <>
            <button
              type="button"
              className="ml-1 text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
              aria-label={tooltip}
            >
              ℹ️
            </button>
            {showTooltip && (
              <span className="absolute left-0 top-6 z-10 w-48 rounded bg-[var(--color-text-primary)] px-2 py-1 text-xs text-white shadow">
                {tooltip}
              </span>
            )}
          </>
        )}
      </div>
      <div className="h-1.5 w-full rounded-full bg-[var(--color-bg-input)] overflow-hidden">
        <div
          className="h-full rounded-full transition-[width]"
          style={{ width: `${pct}%`, background: trackColor }}
        />
      </div>
      <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--color-text-primary)]">
        {valueLabel ?? (value != null ? String(value) : '—')}
      </span>
    </div>
  )
}

export default function ModelSettingsCard({ agent }) {
  if (!agent) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
        <p className="text-sm text-[var(--color-text-muted)]">Geen modelgegevens.</p>
      </div>
    )
  }

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Modelinstellingen</h3>
      <DataRow label="Model" value={agent.model} mono />
      <DataRow label="Max tokens" value={agent.max_tokens != null ? String(agent.max_tokens) : '—'} mono />
      <SliderRow
        label="Temperature"
        value={agent.temperature}
        variant="amber"
        tooltip={TOOLTIPS.temperature}
        valueLabel={agent.temperature != null ? Number(agent.temperature).toFixed(2) : '—'}
      />
      <SliderRow
        label="Top-P"
        value={agent.top_p}
        variant="blue"
        tooltip={TOOLTIPS.top_p}
        valueLabel={agent.top_p != null ? Number(agent.top_p).toFixed(2) : '—'}
      />
    </div>
  )
}
