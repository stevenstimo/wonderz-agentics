import { useEffect, useState } from 'react'
import PageLayout from '../PageLayout'
import { apiFetch } from '../apiClient'

const IMPACT_COLORS = { high: '#DC2626', medium: '#D97706', low: '#6B7280' }

function ApprovalCard({ item, isProcessing, onDecision }) {
  const [sourceUrl, setSourceUrl] = useState(item.source_url || '')
  const [showRejectInput, setShowRejectInput] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm mb-4">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <span className="font-medium text-slate-800">{item.agent_name || item.agent_id}</span>
        <span className="text-sm text-slate-500">{item.role}</span>
        <span
          className="text-xs font-semibold uppercase px-2 py-0.5 rounded"
          style={{ color: IMPACT_COLORS[item.impact] || '#6B7280' }}
        >
          {item.impact}
        </span>
        <span className="text-xs text-slate-400">x{item.frequency} keer gezien</span>
      </div>

      <p className="text-slate-700 mb-2">{item.issue_description}</p>

      {item.root_cause && (
        <p className="text-sm text-slate-600 mb-1"><strong>Oorzaak:</strong> {item.root_cause}</p>
      )}
      {item.evidence_example && (
        <p className="text-sm text-slate-600 mb-2"><strong>Bewijs:</strong> {item.evidence_example}</p>
      )}

      <div className="mb-3">
        <label className="block text-xs font-medium text-slate-500 mb-1">Training URL (optioneel)</label>
        <input
          type="url"
          value={sourceUrl}
          onChange={(e) => setSourceUrl(e.target.value)}
          placeholder="https://..."
          disabled={isProcessing}
          className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {isProcessing ? (
          <span className="text-sm text-slate-500">Verwerken...</span>
        ) : (
          <>
            <button
              type="button"
              onClick={() => onDecision(item.point_id, true, sourceUrl || null)}
              className="px-3 py-1.5 text-sm font-medium rounded-lg bg-green-600 text-white hover:bg-green-700"
            >
              Goedkeuren
            </button>
            {!showRejectInput ? (
              <button
                type="button"
                onClick={() => setShowRejectInput(true)}
                className="px-3 py-1.5 text-sm font-medium rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Afwijzen
              </button>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="text"
                  placeholder="Reden (optioneel)"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm w-48"
                />
                <button
                  type="button"
                  onClick={() => onDecision(item.point_id, false, null, rejectReason)}
                  className="px-3 py-1.5 text-sm font-medium rounded-lg bg-red-600 text-white hover:bg-red-700"
                >
                  Bevestig afwijzing
                </button>
                <button
                  type="button"
                  onClick={() => setShowRejectInput(false)}
                  className="px-3 py-1.5 text-sm text-slate-600 hover:underline"
                >
                  Annuleer
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function HRApprovalPage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [processingId, setProcessingId] = useState(null)

  const fetchItems = async () => {
    try {
      const res = await apiFetch('/api/hr/development-points/awaiting-approval')
      if (!res.ok) {
        setItems([])
        return
      }
      const data = await res.json()
      setItems(data.items || [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchItems()
  }, [])

  const handleDecision = async (pointId, approved, sourceUrl = null, rejectionReason = null) => {
    setProcessingId(pointId)
    try {
      const res = await apiFetch(`/api/hr/development-points/${pointId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved,
          source_url: sourceUrl || undefined,
          rejection_reason: rejectionReason || undefined,
          approved_by: 'ceo',
        }),
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Request failed')
      await fetchItems()
    } catch (err) {
      setProcessingId(null)
      return
    }
    setProcessingId(null)
  }

  return (
    <PageLayout>
      <div className="max-w-3xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-800">CEO Training Approval</h1>
          <p className="text-slate-600 mt-1">
            Trainingsverzoeken van de HR Manager wachten op jouw goedkeuring.
          </p>
        </div>

        {loading && <p className="text-slate-500">Laden...</p>}
        {!loading && items.length === 0 && (
          <p className="text-slate-500">Geen openstaande verzoeken.</p>
        )}

        {items.map((item) => (
          <ApprovalCard
            key={item.point_id}
            item={item}
            isProcessing={processingId === item.point_id}
            onDecision={handleDecision}
          />
        ))}
      </div>
    </PageLayout>
  )
}
