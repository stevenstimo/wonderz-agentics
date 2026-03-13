/**
 * FixRoadmapCard — v1: statische lijst van 5 acties met badge (Quick win / Medium term / Longer term).
 * Actie 1 actief/highlight. Genummerd icoon, titel + badge, beschrijving.
 */
const ACTIONS = [
  {
    title: 'Prompt updaten',
    badge: 'Quick win',
    badgeVariant: 'ok',
    description: 'Pas de agent-prompt aan op het specifieke retry-gedrag (bijv. subheadings of format vereisten).',
  },
  {
    title: 'Cross-training andere agents',
    badge: 'Quick win',
    badgeVariant: 'ok',
    description: 'Deel de les met andere agents die hetzelfde patroon kunnen vertonen.',
  },
  {
    title: 'Workflow-level format template',
    badge: 'Medium term',
    badgeVariant: 'medium',
    description: 'Introduceer een gedeeld format-template op workflowniveau.',
  },
  {
    title: 'Validatieregel threshold herzien',
    badge: 'Medium term',
    badgeVariant: 'medium',
    description: 'Verlaag of verfijn de validatiestrictie zodat valide output niet wordt afgekeurd.',
  },
  {
    title: 'A/B validatie na training',
    badge: 'Longer term',
    badgeVariant: 'high',
    description: 'Voer A/B validatie uit na training om effect te meten.',
  },
]

export default function FixRoadmapCard() {
  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Aanbevolen fix roadmap</h3>
      <ol className="space-y-4">
        {ACTIONS.map((action, i) => (
          <li
            key={i}
            className={`flex gap-3 ${i === 0 ? 'rounded-[var(--radius-sm)] bg-[var(--color-brand-primary-light)] border border-[var(--color-brand-primary)] p-3 -m-1' : ''}`}
          >
            <span
              className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold bg-[var(--color-bg-subtle)] text-[var(--color-text-primary)] border border-[var(--color-border)]"
              aria-hidden
            >
              {i + 1}
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="font-medium text-[var(--color-text-primary)]">{action.title}</span>
                <span
                  className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold ${
                    action.badgeVariant === 'ok'
                      ? 'bg-[var(--color-status-success-bg)] text-[#065F46] border border-[var(--color-status-success)]'
                      : action.badgeVariant === 'medium'
                        ? 'bg-[var(--color-status-warning-bg)] text-[#92400E] border border-[var(--color-status-warning)]'
                        : 'bg-[var(--color-status-error-bg)] text-[#991B1B] border border-[var(--color-status-error)]'
                  }`}
                >
                  {action.badge}
                </span>
              </div>
              <p className="text-sm text-[var(--color-text-muted)]">{action.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
