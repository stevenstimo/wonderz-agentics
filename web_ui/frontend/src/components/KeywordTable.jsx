import { Download } from 'lucide-react'

export default function KeywordTable({ data }) {
  if (!data || !Array.isArray(data.keywords) || data.keywords.length === 0) return null

  const keywords = data.keywords

  const downloadCSV = () => {
    // Excel (NL locale) opens semicolon-separated CSV more reliably.
    const separator = ';'
    const headers = ['Keyword', 'Zoekvolume', 'KD', 'Omschrijving']
    const rows = keywords.map((k) => [
      `"${String(k.keyword || '').replace(/"/g, '""')}"`,
      k.search_volume || '',
      k.kd || '',
      `"${String(k.description || '').replace(/"/g, '""')}"`,
    ])
    const csv = [headers, ...rows].map((r) => r.join(separator)).join('\r\n')
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `keywords_${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const avgVolume = Math.round(
    keywords.reduce((acc, k) => acc + (Number(k.search_volume) || 0), 0) / keywords.length
  )
  const avgKd = Math.round(
    keywords.reduce((acc, k) => acc + (Number(k.kd) || 0), 0) / keywords.length
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Keyword Research</h3>
          {data.focus_keyword && (
            <p className="text-sm text-slate-500">
              Focus keyword: <span className="font-medium">{data.focus_keyword}</span>
            </p>
          )}
        </div>
        <button
          onClick={downloadCSV}
          className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Download size={14} />
          Download CSV
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              <th className="text-left px-4 py-3 font-semibold text-slate-700 w-1/4">Keyword</th>
              <th className="text-right px-4 py-3 font-semibold text-slate-700 w-24">Zoekvolume</th>
              <th className="text-right px-4 py-3 font-semibold text-slate-700 w-16">KD</th>
              <th className="text-left px-4 py-3 font-semibold text-slate-700">Omschrijving</th>
            </tr>
          </thead>
          <tbody>
            {keywords.map((kw, idx) => {
              const kd = Number(kw.kd) || 0
              const kdClass = kd <= 20
                ? 'bg-green-100 text-green-700'
                : kd <= 40
                  ? 'bg-yellow-100 text-yellow-700'
                  : 'bg-red-100 text-red-700'
              return (
                <tr
                  key={`${kw.keyword || 'kw'}-${idx}`}
                  className={`border-b border-slate-100 hover:bg-slate-50 transition-colors ${idx === keywords.length - 1 ? 'border-0' : ''}`}
                >
                  <td className="px-4 py-3 font-medium text-slate-900">{kw.keyword}</td>
                  <td className="px-4 py-3 text-right text-slate-700 tabular-nums">
                    {kw.search_volume ? Number(kw.search_volume).toLocaleString('nl-NL') : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${kdClass}`}>
                      {kw.kd || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600 leading-relaxed">{kw.description || ''}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="flex gap-4 text-xs text-slate-500">
        <span>{keywords.length} keywords</span>
        <span>Gem. zoekvolume: {Number.isFinite(avgVolume) ? avgVolume.toLocaleString('nl-NL') : '0'}</span>
        <span>Gem. KD: {Number.isFinite(avgKd) ? avgKd : '0'}</span>
      </div>
    </div>
  )
}

