/**
 * ClientPdfDocument.jsx
 * PDF export voor het client dashboard.
 * Ontvangt alle data als props — fetcht niets zelf.
 */
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

function hasRenderableData(obj) {
  if (!obj || typeof obj !== 'object') return false
  return Object.values(obj).some((value) => value !== null && value !== undefined && value !== '')
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

export function ClientPdfDocument({ client, metrics, generatedAt }) {
  const ga4 = metrics?.ga4 || {}
  const ads = metrics?.ads || {}
  const meta = metrics?.meta || {}

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

        {hasRenderableData(ga4) && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>Website performance (GA4)</Text>
            <View style={s.kpiGrid}>
              <KpiCard label="Sessies" value={ga4.sessions} change={ga4.sessions_change} />
              <KpiCard label="Gebruikers" value={ga4.users} change={ga4.users_change} />
              <KpiCard label="Bounce rate" value={ga4.bounce_rate} change={ga4.bounce_rate_change} />
              <KpiCard label="Gem. sessieduur" value={ga4.avg_session_duration} />
            </View>
          </View>
        )}

        {hasRenderableData(ads) && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>Google Ads</Text>
            <View style={s.kpiGrid}>
              <KpiCard label="Vertoningen" value={ads.impressions} />
              <KpiCard label="Klikken" value={ads.clicks} />
              <KpiCard label="CTR" value={ads.ctr} />
              <KpiCard label="Kosten" value={ads.cost} />
            </View>
          </View>
        )}

        {hasRenderableData(meta) && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>Meta Ads</Text>
            <View style={s.kpiGrid}>
              <KpiCard label="Bereik" value={meta.reach} />
              <KpiCard label="Vertoningen" value={meta.impressions} />
              <KpiCard label="Klikken" value={meta.clicks} />
              <KpiCard label="Besteed" value={meta.spend} />
            </View>
          </View>
        )}

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
export async function downloadClientPdf({ client, metrics, generatedAt }) {
  const blob = await pdf(<ClientPdfDocument client={client} metrics={metrics} generatedAt={generatedAt} />).toBlob()
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
