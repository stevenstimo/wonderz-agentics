/**
 * DataResultView — toont het resultaat van een data_query job als gestructureerde tabel.
 * Gebruikt wanneer pipeline_type === 'direct_response' (geen content diff-view).
 * Afsluiten roept het bestaande approve endpoint aan (alleen COMPLETED, geen deploy).
 */
export default function DataResultView({ proposedData, onApprove, approvingDeploy = false }) {
  if (!proposedData) {
    return (
      <div className="p-4 text-slate-500 text-sm">
        Geen data beschikbaar.
      </div>
    )
  }

  const { gevonden, resultaat, volledigheid, volgende_actie } = proposedData
  const rows = Array.isArray(resultaat) ? resultaat : []
  const headers = rows.length > 0 ? Object.keys(rows[0]) : []

  const formatCellValue = (key, val) => {
    if (val == null || val === '') return '—'
    const keyNorm = String(key || '').toLowerCase()

    if (keyNorm === 'ctr') {
      const num = Number(val)
      if (!Number.isFinite(num)) return String(val)
      return `${(num * 100).toFixed(1)}%`
    }

    if (keyNorm === 'position') {
      const num = Number(val)
      if (!Number.isFinite(num)) return String(val)
      return num.toFixed(1)
    }

    if (keyNorm === 'clicks' || keyNorm === 'impressions') {
      const num = Number(val)
      if (!Number.isFinite(num)) return String(val)
      return Math.round(num).toLocaleString('nl-NL')
    }

    return String(val)
  }

  return (
    <div className="space-y-4">
      {/* Bron & periode */}
      {gevonden && (
        <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-sm text-slate-800">
          {gevonden}
        </div>
      )}

      {/* Resultaattabel */}
      {rows.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100 text-slate-700">
                {headers.map((key) => (
                  <th
                    key={key}
                    className="border border-slate-200 px-3 py-2 text-left font-medium"
                  >
                    {key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={i}
                  className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}
                >
                  {headers.map((key) => (
                    <td
                      key={key}
                      className="border border-slate-200 px-3 py-2 text-slate-800"
                    >
                      {formatCellValue(key, row?.[key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-slate-500 text-sm italic">Geen resultaten.</div>
      )}

      {/* Volledigheidsmelding */}
      {volledigheid && (
        <div className="text-xs text-slate-500">{volledigheid}</div>
      )}

      {/* Volgende actie */}
      {volgende_actie && (
        <div className="text-xs text-slate-400 italic">{volgende_actie}</div>
      )}

      {/* Afsluiten knop — roept bestaande approve endpoint aan (alleen COMPLETED voor data jobs) */}
      {typeof onApprove === 'function' && (
        <div className="pt-2 border-t border-slate-200">
          <button
            type="button"
            onClick={onApprove}
            disabled={approvingDeploy}
            className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
          >
            {approvingDeploy ? 'Afsluiten…' : 'Afsluiten'}
          </button>
        </div>
      )}
    </div>
  )
}
