import { Document, Page, Text, View, pdf } from '@react-pdf/renderer'
import { pdfStyles as s } from './PdfBase'

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('nl-NL', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  })
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('nl-NL', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function valueOrDash(value) {
  return value ?? '—'
}

function fmtNum(value) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  return n.toLocaleString('nl-NL')
}

function fmtPct(value) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  return `${n.toFixed(1).replace('.', ',')}%`
}

function fmtEur(value) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  return new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' }).format(n)
}

function hasRenderableData(obj) {
  if (!obj || typeof obj !== 'object') return false
  return Object.values(obj).some((value) => value !== null && value !== undefined && value !== '')
}

function chunkRows(rows, size = 12) {
  if (!Array.isArray(rows) || rows.length === 0) return []
  const chunks = []
  for (let i = 0; i < rows.length; i += size) {
    chunks.push(rows.slice(i, i + size))
  }
  return chunks
}

function KpiCard({ label, value, change }) {
  const numericChange = Number.parseFloat(change)
  const hasChange = Number.isFinite(numericChange)
  const positive = hasChange && numericChange > 0
  const negative = hasChange && numericChange < 0
  return (
    <View style={s.kpiCard}>
      <Text style={s.kpiLabel}>{label}</Text>
      <Text style={s.kpiValue}>{valueOrDash(value)}</Text>
      {change != null && (
        <Text style={[s.kpiChange, { color: positive ? '#16a34a' : negative ? '#dc2626' : '#6b7280' }]}>
          {positive ? '▲' : negative ? '▼' : ''} {change}
        </Text>
      )}
    </View>
  )
}

function OverviewGrid({ overview }) {
  return (
    <View style={s.section} wrap={false}>
      <Text style={s.sectionTitle}>Marketing overzicht</Text>
      <View style={s.kpiGrid}>
        <KpiCard label="Users" value={fmtNum(overview?.users)} />
        <KpiCard label="Sessions" value={fmtNum(overview?.sessions)} />
        <KpiCard label="Conversions" value={fmtNum(overview?.conversions)} />
        <KpiCard label="Conv. Value" value={fmtEur(overview?.conversion_value)} />
        <KpiCard label="Total Cost" value={fmtEur(overview?.total_cost)} />
        <KpiCard label="CPA" value={fmtEur(overview?.cpa)} />
      </View>
    </View>
  )
}

function GenericTable({ title, rows, columns, rowKeyPrefix }) {
  if (!Array.isArray(rows) || rows.length === 0) return null
  const chunks = chunkRows(rows, 12)
  return (
    <>
      {chunks.map((chunk, chunkIdx) => (
        <View key={`${rowKeyPrefix}-chunk-${chunkIdx}`} style={s.section} wrap={false}>
          <Text style={s.sectionTitle}>{chunkIdx === 0 ? title : `${title} (vervolg)`}</Text>
          <View style={s.table}>
            <View style={s.tableHeader}>
              {columns.map((col) => (
                <Text
                  key={`${rowKeyPrefix}-head-${col.key}`}
                  style={[s.tableCell, { width: col.width, textAlign: col.align || 'left' }]}
                >
                  {col.label}
                </Text>
              ))}
            </View>
            {chunk.map((row, idx) => (
              <View key={`${rowKeyPrefix}-${chunkIdx}-${idx}`} style={s.tableRow}>
                {columns.map((col) => (
                  <Text
                    key={`${rowKeyPrefix}-${chunkIdx}-${idx}-${col.key}`}
                    style={[s.tableCell, { width: col.width, textAlign: col.align || 'left' }]}
                  >
                    {col.render(row)}
                  </Text>
                ))}
              </View>
            ))}
          </View>
        </View>
      ))}
    </>
  )
}

export function ClientPdfDocument({ client, dashboardData, generatedAt }) {
  const overview = dashboardData?.overview || {}
  const ga4 = dashboardData?.ga4 || {}
  const ads = dashboardData?.google_ads || {}
  const gsc = dashboardData?.gsc || {}
  const metaAds = dashboardData?.meta?.ads || {}
  const ga4Kpis = ga4?.kpis || {}

  return (
    <Document>
      <Page size="A4" orientation="portrait" style={s.page}>
        <View style={s.header}>
          <Text style={s.headerTitle}>{client?.name ?? 'Client rapport'}</Text>
          <View>
            <Text style={s.headerMeta}>{client?.domain ?? ''}</Text>
            <Text style={s.headerMeta}>
              Gegenereerd: {formatDate(generatedAt)} {formatTime(generatedAt)}
            </Text>
          </View>
        </View>

        {hasRenderableData(overview) && <OverviewGrid overview={overview} />}

        {hasRenderableData(ga4Kpis) && (
          <View style={s.section} wrap={false}>
            <Text style={s.sectionTitle}>Website performance (GA4)</Text>
            <View style={s.kpiGrid}>
              <KpiCard label="Sessies" value={fmtNum(ga4Kpis?.sessions)} change={ga4Kpis?.sessions_change} />
              <KpiCard label="Gebruikers" value={fmtNum(ga4Kpis?.users)} change={ga4Kpis?.users_change} />
              <KpiCard label="Engagement rate" value={fmtPct(ga4Kpis?.engagement_rate)} change={ga4Kpis?.engagement_rate_change} />
              <KpiCard label="Conv. rate" value={fmtPct(ga4Kpis?.conversion_rate)} />
            </View>
          </View>
        )}

        {hasRenderableData(ads?.summary || {}) && (
          <View style={s.section} wrap={false}>
            <Text style={s.sectionTitle}>Google Ads</Text>
            <View style={s.kpiGrid}>
              <KpiCard label="Vertoningen" value={fmtNum(ads?.summary?.impressions)} />
              <KpiCard label="Klikken" value={fmtNum(ads?.summary?.clicks)} />
              <KpiCard label="CTR" value={fmtPct(Number(ads?.summary?.ctr || 0) * 100)} />
              <KpiCard label="Kosten" value={fmtEur(ads?.summary?.cost)} />
            </View>
          </View>
        )}

        {hasRenderableData(metaAds) && (
          <View style={s.section} wrap={false}>
            <Text style={s.sectionTitle}>Meta Ads</Text>
            <View style={s.kpiGrid}>
              <KpiCard label="Bereik" value={fmtNum(metaAds?.total_reach)} />
              <KpiCard label="Vertoningen" value={fmtNum(metaAds?.total_impressions)} />
              <KpiCard label="Klikken" value={fmtNum(metaAds?.total_clicks)} />
              <KpiCard label="Besteed" value={fmtEur(metaAds?.total_spend)} />
            </View>
          </View>
        )}

        <GenericTable
          title="SEO — Top zoekwoorden"
          rows={gsc?.top_queries || []}
          rowKeyPrefix="seo-queries"
          columns={[
            { key: 'query', label: 'Zoekwoord', width: '46%', render: (row) => row?.query || '—' },
            { key: 'clicks', label: 'Clicks', width: '13%', align: 'right', render: (row) => fmtNum(row?.clicks) },
            { key: 'impressions', label: 'Impr.', width: '14%', align: 'right', render: (row) => fmtNum(row?.impressions) },
            { key: 'ctr', label: 'CTR', width: '12%', align: 'right', render: (row) => fmtPct(Number(row?.ctr || 0) * 100) },
            { key: 'position', label: 'Positie', width: '15%', align: 'right', render: (row) => fmtNum(Number(row?.position || 0).toFixed(1)) },
          ]}
        />

        <GenericTable
          title="SEO — Top pagina's"
          rows={gsc?.top_pages || []}
          rowKeyPrefix="seo-pages"
          columns={[
            { key: 'page', label: 'Pagina', width: '46%', render: (row) => row?.page || '—' },
            { key: 'clicks', label: 'Clicks', width: '13%', align: 'right', render: (row) => fmtNum(row?.clicks) },
            { key: 'impressions', label: 'Impr.', width: '14%', align: 'right', render: (row) => fmtNum(row?.impressions) },
            { key: 'ctr', label: 'CTR', width: '12%', align: 'right', render: (row) => fmtPct(Number(row?.ctr || 0) * 100) },
            { key: 'position', label: 'Positie', width: '15%', align: 'right', render: (row) => fmtNum(Number(row?.position || 0).toFixed(1)) },
          ]}
        />

        <GenericTable
          title="Google Ads — Campagnes"
          rows={ads?.campaigns || []}
          rowKeyPrefix="ads-campaigns"
          columns={[
            { key: 'campaign_name', label: 'Campagne', width: '34%', render: (row) => row?.campaign_name || '—' },
            { key: 'clicks', label: 'Klikken', width: '11%', align: 'right', render: (row) => fmtNum(row?.clicks) },
            { key: 'impressions', label: 'Impr.', width: '13%', align: 'right', render: (row) => fmtNum(row?.impressions) },
            { key: 'conversions', label: 'Conv.', width: '11%', align: 'right', render: (row) => fmtNum(row?.conversions) },
            { key: 'conversion_value', label: 'Conv. value', width: '15%', align: 'right', render: (row) => fmtEur(row?.conversion_value) },
            { key: 'cost', label: 'Kosten', width: '16%', align: 'right', render: (row) => fmtEur(row?.cost) },
          ]}
        />

        <GenericTable
          title="Meta Ads — Campagnes"
          rows={metaAds?.campaigns || []}
          rowKeyPrefix="meta-campaigns"
          columns={[
            { key: 'name', label: 'Campagne', width: '34%', render: (row) => row?.name || '—' },
            { key: 'impressions', label: 'Impr.', width: '13%', align: 'right', render: (row) => fmtNum(row?.impressions) },
            { key: 'clicks', label: 'Klikken', width: '11%', align: 'right', render: (row) => fmtNum(row?.clicks) },
            { key: 'conversions', label: 'Conv.', width: '11%', align: 'right', render: (row) => fmtNum(row?.conversions) },
            { key: 'ctr', label: 'CTR', width: '12%', align: 'right', render: (row) => fmtPct(Number(row?.ctr || 0) * 100) },
            { key: 'spend', label: 'Uitgaven', width: '19%', align: 'right', render: (row) => fmtEur(row?.spend) },
          ]}
        />

        <GenericTable
          title="GA4 — Traffic bronnen"
          rows={ga4?.traffic_by_channel || []}
          rowKeyPrefix="ga4-traffic"
          columns={[
            { key: 'channel', label: 'Kanaal', width: '34%', render: (row) => row?.channel || '—' },
            { key: 'users', label: 'Users', width: '14%', align: 'right', render: (row) => fmtNum(row?.users) },
            { key: 'sessions', label: 'Sessions', width: '14%', align: 'right', render: (row) => fmtNum(row?.sessions) },
            { key: 'conversions', label: 'Conv.', width: '14%', align: 'right', render: (row) => fmtNum(row?.conversions) },
            { key: 'conversion_rate', label: 'Conv. rate', width: '24%', align: 'right', render: (row) => fmtPct(row?.conversion_rate) },
          ]}
        />

        <View style={s.footer} fixed>
          <Text style={s.footerText}>Wonderz Agentics — {client?.name ?? 'Client'}</Text>
          <Text
            style={s.footerText}
            render={({ pageNumber, totalPages }) => `Pagina ${pageNumber} van ${totalPages}`}
          />
        </View>
      </Page>
    </Document>
  )
}

function formatFileDate(date) {
  const year = date.getFullYear().toString().slice(-2)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}${month}${day}`
}

function sanitizeClientName(name) {
  return (name || 'client')
    .trim()
    .replace(/\s+/g, '_')
    .replace(/[^A-Za-z0-9_-]/g, '')
}

/**
 * Trigger een PDF download vanuit een onClick handler.
 * Gebruik: await downloadClientPdf({ client, metrics, generatedAt })
 */
export async function downloadClientPdf({ client, dashboardData, generatedAt }) {
  const blob = await pdf(<ClientPdfDocument client={client} dashboardData={dashboardData} generatedAt={generatedAt} />).toBlob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const date = generatedAt ? new Date(generatedAt) : new Date()
  const datum = formatFileDate(date)
  const naam = sanitizeClientName(client?.name)
  link.href = url
  link.download = `${datum}_${naam}_rapport.pdf`
  link.click()
  URL.revokeObjectURL(url)
}
