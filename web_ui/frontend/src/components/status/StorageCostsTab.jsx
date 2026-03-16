import React, { useEffect, useState } from 'react'
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, BarChart, Bar } from 'recharts'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { apiFetch } from '../../apiClient'

function sizeColor(sizeMb) {
  if (sizeMb < 100) return 'bg-emerald-100 text-emerald-700'
  if (sizeMb < 500) return 'bg-amber-100 text-amber-700'
  return 'bg-rose-100 text-rose-700'
}

export default function StorageCostsTab() {
  const [data, setData] = useState(null)
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    const fetchData = async () => {
      setLoading(true)
      setError('')
      try {
        const res = await apiFetch(`/api/status/storage-costs?days=${days}`)
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail || `Kon storage-costs niet laden (${res.status})`)
        }
        const json = await res.json()
        if (active) setData(json)
      } catch (err) {
        if (active) {
          setError(err.message || 'Storage & costs laden mislukt')
          setData(null)
        }
      } finally {
        if (active) setLoading(false)
      }
    }
    fetchData()
    return () => {
      active = false
    }
  }, [days])

  const tableSizes = Array.isArray(data?.table_sizes) ? data.table_sizes : []
  const embeddingStats = data?.embedding_stats || {}
  const perClient = Array.isArray(embeddingStats?.per_client) ? embeddingStats.per_client : []
  const tokenCosts = data?.token_costs || {}
  const tokenTrend = Array.isArray(tokenCosts?.daily_trend) ? tokenCosts.daily_trend : []
  const directChat = data?.direct_chat_stats || {}

  const totalTokenCost = tokenCosts?.estimated_cost_usd ?? 0

  const sortedClients = [...perClient].sort((a, b) => {
    if ((a.chunk_count || 0) === 0 && (b.chunk_count || 0) > 0) return -1
    if ((b.chunk_count || 0) === 0 && (a.chunk_count || 0) > 0) return 1
    return (b.chunk_count || 0) - (a.chunk_count || 0)
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-900">Storage &amp; Costs</h2>
        <div className="inline-flex items-center gap-1 text-xs text-slate-500">
          Periode:
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDays(d)}
              className={`ml-1 px-2 py-0.5 rounded-full border text-[11px] ${
                days === d
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
              }`}
            >
              {d}d
            </button>
          ))}
          {loading && <Loader2 className="w-3 h-3 ml-1 animate-spin text-slate-400" />}
        </div>
      </div>

      {error && (
        <div className="panel-card border-amber-200 bg-amber-50 text-amber-800 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {/* Blok 1: Database Tabelgroottes */}
      <div className="panel-card">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">Database tabelgroottes</h3>
        {tableSizes.length === 0 ? (
          <p className="text-sm text-slate-500">Geen tabeldata beschikbaar.</p>
        ) : (
          <div className="space-y-3">
            {tableSizes.map((t) => (
              <div key={t.table_name} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-slate-700">{t.table_name}</span>
                  <span className="text-slate-500">
                    {t.row_count.toLocaleString()} rows · {t.size_mb.toFixed(1)} MB
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full ${sizeColor(t.size_mb)} rounded-full`}
                    style={{ width: `${Math.min(100, (t.size_mb / 1000) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Blok 2: Knowledge Hub Coverage */}
      <div className="panel-card">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">Knowledge Hub Coverage (client_knowledge)</h3>
        {sortedClients.length === 0 ? (
          <p className="text-sm text-slate-500">Nog geen client-embeddings aangemaakt.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              {sortedClients.map((c) => {
                const hasEmbeddings = (c.chunk_count || 0) > 0
                return (
                  <div key={c.company_id || c.company_name} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-slate-700">
                        {c.company_name || c.company_id || 'Onbekende client'}
                      </span>
                      <span className="text-slate-500">
                        {c.chunk_count} chunks · {c.source_count} sources
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className={`h-full ${
                          hasEmbeddings ? 'bg-indigo-500' : 'bg-amber-400'
                        } rounded-full`}
                        style={{ width: `${Math.min(100, (c.chunk_count || 0) / 50) * 100}%` }}
                      />
                    </div>
                    {!hasEmbeddings && (
                      <p className="text-[11px] text-amber-600">
                        Deze client heeft nog geen Knowledge Hub embeddings.
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
            <div className="border border-dashed border-slate-200 rounded-lg p-3 bg-slate-50">
              <p className="text-xs text-slate-600 mb-2">
                Totaal actieve chunks: <strong>{(embeddingStats.total_chunks || 0).toLocaleString()}</strong>
              </p>
              <p className="text-xs text-slate-600 mb-2">
                Geschatte storage: <strong>{(embeddingStats.total_size_mb || 0).toFixed(1)} MB</strong>
              </p>
              <p className="text-xs text-slate-500">
                Clients zonder embeddings worden bovenaan getoond met een waarschuwing. Gebruik dit overzicht om
                Knowledge Hub coverage gaten te identificeren.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Blok 3: Token Spend per Client (platform-breed) */}
      <div className="panel-card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-800">Token spend (platform)</h3>
          {tokenCosts?.data_available === false && (
            <span className="text-[11px] text-slate-500">
              Token-data wordt verzameld zodra jobs token-gebruik rapporteren.
            </span>
          )}
        </div>
        {tokenCosts?.data_available === false ? (
          <div className="border border-dashed border-slate-200 rounded-md p-3 bg-slate-50 text-xs text-slate-600">
            Token-data wordt verzameld zodra jobs token-gebruik rapporteren. Tot die tijd zijn kosteninschattingen niet
            beschikbaar.
          </div>
        ) : (
          <div className="space-y-3">
            <div className="text-xs text-slate-600">
              Totaal tokens ({days}d):{' '}
              <strong>{(tokenCosts.total_tokens || 0).toLocaleString()}</strong> · Geschatte kosten:{' '}
              <strong>${totalTokenCost.toFixed(2)}</strong>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-500 border-b border-slate-100">
                    <th className="py-2 pr-3">Client</th>
                    <th className="py-2 pr-3">Jobs</th>
                    <th className="py-2 pr-3">Tokens</th>
                    <th className="py-2 pr-3">Kosten (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {/* Momenteel geen betrouwbare client-mapping — tabel blijft leeg maar struktureel aanwezig */}
                  {(Array.isArray(tokenCosts.per_client) ? tokenCosts.per_client : []).map((c) => (
                    <tr key={c.company_id || c.company_name} className="border-b last:border-b-0">
                      <td className="py-1.5 pr-3 text-slate-800">{c.company_name || c.company_id || 'Onbekend'}</td>
                      <td className="py-1.5 pr-3 text-slate-700">{c.job_count || 0}</td>
                      <td className="py-1.5 pr-3 text-slate-700">
                        {(c.total_tokens || 0).toLocaleString()}
                      </td>
                      <td className="py-1.5 pr-3 text-slate-700">
                        ${Number(c.estimated_cost_usd || 0).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                  {(!tokenCosts.per_client || tokenCosts.per_client.length === 0) && (
                    <tr>
                      <td colSpan={4} className="py-2 text-slate-500">
                        Geen client-specifieke token-data beschikbaar. Analyse is op platform-niveau.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Blok 4: Kosten trendlijn */}
      <div className="panel-card">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">Kosten trendlijn (USD per dag)</h3>
        {tokenCosts?.data_available === false || tokenTrend.length === 0 ? (
          <p className="text-sm text-slate-500">Nog geen token-kostendata beschikbaar.</p>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={tokenTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis tickFormatter={(v) => `$${v.toFixed(2)}`} />
                <Tooltip formatter={(v) => `$${Number(v).toFixed(4)}`} />
                <Line type="monotone" dataKey="estimated_cost_usd" stroke="#6366f1" dot={false} name="Kosten" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Blok 5: Direct Chat volume */}
      <div className="panel-card flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Direct Chat volume</h3>
          <p className="text-xs text-slate-500 mt-1">
            Totaal berichten: <strong>{(directChat.total_messages || 0).toLocaleString()}</strong>
          </p>
          <p className="text-xs text-slate-500">
            Berichten in de afgelopen {days} dagen:{' '}
            <strong>{(directChat.period_messages || 0).toLocaleString()}</strong>
          </p>
        </div>
        <div className="h-24 w-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={[
                {
                  label: 'All time',
                  value: directChat.total_messages || 0,
                },
                {
                  label: `${days}d`,
                  value: directChat.period_messages || 0,
                },
              ]}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" />
              <YAxis hide />
              <Tooltip formatter={(v) => `${v.toLocaleString()} messages`} />
              <Bar dataKey="value" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

