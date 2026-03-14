/**
 * ReproduceCard — Run ID display + reproduce button.
 * POST /api/hr/development-points/:pointId/reproduce → navigate to /jobs/:job_id + toast.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../apiClient'

export default function ReproduceCard({ runId, pointId, onReproduce }) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)

  const handleReproduce = async () => {
    if (!pointId || !onReproduce) return
    setLoading(true)
    try {
      const res = await apiFetch(`/api/hr/development-points/${pointId}/reproduce`, {
        method: 'POST',
      })
      if (!res.ok) throw new Error('Reproduce mislukt')
      const json = await res.json()
      onReproduce(json.job_id)
      if (json.job_id) navigate(`/jobs/${json.job_id}`)
    } catch (e) {
      onReproduce(null, e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-5 bg-[var(--color-bg-card)] shadow-[var(--shadow-card)]">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Reproduce</h3>
      {runId != null && typeof runId !== 'object' && (
        <div className="font-[family-name:var(--font-mono)] text-xs text-[var(--color-text-muted)] mb-3 break-all">
          {String(runId)}
        </div>
      )}
      <button
        type="button"
        onClick={handleReproduce}
        disabled={loading || !pointId}
        className="w-full py-2.5 px-4 rounded-[var(--radius-sm)] bg-[var(--color-brand-primary)] text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Bezig...' : 'Run reproduceren'}
      </button>
    </div>
  )
}
