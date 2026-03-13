/**
 * EvidenceCard — job IDs as links to /jobs/:id, data rows (Patroon aanwezig since, v2.2.0 affected?, Gerelateerde lesson), link to HR overzicht.
 */
import { Link } from 'react-router-dom'
import { DataRow } from './shared'

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch (_) {
    return iso
  }
}

export default function EvidenceCard({ evidence, point }) {
  const list = Array.isArray(evidence) ? evidence : []
  const pointId = point?.point_id

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Evidence</h3>
      {list.length > 0 ? (
        <ul className="space-y-1 mb-4">
          {list.map((jobId, i) => (
            <li key={jobId || i}>
              <Link
                to={`/jobs/${jobId}`}
                className="font-[family-name:var(--font-mono)] text-xs text-[var(--color-brand-primary)] hover:underline break-all"
              >
                {jobId}
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-[var(--color-text-muted)] mb-4">Geen evidence runs.</p>
      )}
      <DataRow label="Patroon aanwezig since" value={point ? formatDate(point.created_at) : '—'} />
      <DataRow label="v2.2.0 affected?" value="—" mono />
      <DataRow label="Gerelateerde lesson" value="—" mono />
      {pointId && (
        <Link
          to="/hr"
          className="inline-block mt-3 text-sm font-medium text-[var(--color-brand-primary)] hover:underline"
        >
          Alle evidence runs bekijken →
        </Link>
      )}
    </div>
  )
}
