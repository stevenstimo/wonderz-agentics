import { useState, useRef, useEffect } from 'react'
import { FileText, Copy, Download } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import DataResultView from './DataResultView'
import KeywordTable from './KeywordTable'

/**
 * Live document viewer (Claude-style artifact panel). Renders document_preview from GET /api/jobs/{id}.
 * For data_query jobs (pipeline_type === 'direct_response'): shows DataResultView with proposed_data
 * from the same parsed context; pipelineType and proposedData must come from that context, not raw job.context.
 */
export default function DocumentViewer({
  documentPreview,
  jobId,
  jobStatus,
  jobTitle,
  pipelineType,
  proposedData,
  payloadFinalContent = null,
  onApprove,
  onApprovePlan,
  onRequestChanges,
  approvingDeploy = false,
  approvingPlan = false,
}) {
  const [copied, setCopied] = useState(false)
  const [fadeKey, setFadeKey] = useState(0)
  const prevTypeRef = useRef(documentPreview?.type)

  const type = documentPreview?.type ?? 'empty'
  const title = documentPreview?.title ?? 'Document'
  const subtitle = documentPreview?.subtitle ?? ''
  const hasAnalysisContent = typeof payloadFinalContent === 'string' && payloadFinalContent.trim().length > 0
  const content = typeof documentPreview?.content === 'string'
    ? documentPreview.content
    : (hasAnalysisContent ? payloadFinalContent : '')
  const steps = Array.isArray(documentPreview?.steps) ? documentPreview.steps : []

  // Fade-in when type changes (opacity 0 → 1, 300ms)
  useEffect(() => {
    if (prevTypeRef.current !== type) {
      prevTypeRef.current = type
      setFadeKey((k) => k + 1)
    }
  }, [type])

  const copyToClipboard = async () => {
    let text = ''
    if (type === 'plan' && steps.length > 0) {
      text = steps.map((s, i) => `${i + 1}. ${s.description || s.step_name || s.name || ''}`).join('\n')
    } else {
      text = content
    }
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (_) {}
  }

  const downloadAsTxt = () => {
    if (!content) return
    const name = (jobTitle || title || 'document').replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 80) + '.txt'
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadAsCsv = () => {
    const data = parsedProposedData
    if (!data || typeof data !== 'object') return

    let headers = []
    let rows = []

    const toIntIfNumeric = (v) => {
      const n = Number(v)
      return Number.isFinite(n) ? Math.round(n) : v
    }

    const toOneDecimalIfNumeric = (v) => {
      const n = Number(v)
      return Number.isFinite(n) ? n.toFixed(1) : v
    }

    if (data.output_type === 'keyword_table' && Array.isArray(data.keywords)) {
      headers = ['Keyword', 'Zoekvolume', 'KD', 'Omschrijving']
      rows = data.keywords.map((k) => [
        String(k?.keyword ?? ''),
        toIntIfNumeric(k?.search_volume ?? ''),
        toIntIfNumeric(k?.kd ?? ''),
        String(k?.description ?? ''),
      ])
    } else if (Array.isArray(data.resultaat) && data.resultaat.length > 0) {
      headers = Object.keys(data.resultaat[0])
      rows = data.resultaat.map((r) =>
        headers.map((h) => {
          const key = String(h || '').toLowerCase()
          const val = r?.[h] ?? ''
          if (key === 'ctr') return toOneDecimalIfNumeric(Number(val) * 100)
          if (key === 'position') return toOneDecimalIfNumeric(val)
          if (key === 'clicks' || key === 'impressions' || key === 'search_volume' || key === 'volume' || key === 'kd') {
            return toIntIfNumeric(val)
          }
          return val
        })
      )
    } else {
      return
    }

    const escapeCsv = (v) => `"${String(v).replace(/"/g, '""')}"`
    const separator = ';'
    const csv = [headers, ...rows]
      .map((r) => r.map(escapeCsv).join(separator))
      .join('\r\n')
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = (jobTitle || title || 'document').replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 80) + '.csv'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const isDataResult = pipelineType === 'direct_response' && proposedData != null
  const showDataResult = isDataResult && !hasAnalysisContent && (jobStatus === 'JOB_READY' || jobStatus === 'COMPLETED')
  const parsedProposedData = typeof proposedData === 'string'
    ? (() => { try { return JSON.parse(proposedData) } catch { return null } })()
    : proposedData
  const showKeywordTable = parsedProposedData?.output_type === 'keyword_table'
    && (jobStatus === 'JOB_READY' || jobStatus === 'COMPLETED')
  const canDownloadCsv = showKeywordTable || showDataResult
  const showApproveButtons = type === 'final' && jobStatus === 'JOB_READY' && !showDataResult
  const showPlanAction = type === 'plan' && jobStatus === 'PLAN_PROPOSED'
  const hasCopyableContent = type === 'plan' ? steps.length > 0 : content.length > 0

  return (
    <div className="flex flex-col h-full min-h-0 bg-white border-l border-slate-200">
      {/* Sticky header */}
      <div className="flex-shrink-0 flex items-center justify-between gap-2 px-4 py-3 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="w-5 h-5 text-slate-500 shrink-0" aria-hidden />
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-slate-900 truncate">{title}</h2>
            <div className="flex items-baseline gap-2 flex-wrap">
              {subtitle && <span className="text-xs text-slate-500 truncate">{subtitle}</span>}
              {jobId && <span className="text-xs text-slate-400 shrink-0">#{jobId}</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {hasCopyableContent && (
            <button
              type="button"
              onClick={copyToClipboard}
              className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              title="Kopiëren"
            >
              {copied ? (
                <span className="text-xs font-medium text-green-600">Gekopieerd ✓</span>
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </button>
          )}
          {canDownloadCsv && (
            <button
              type="button"
              onClick={downloadAsCsv}
              className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              title="Download als .csv"
            >
              <Download className="w-4 h-4" />
            </button>
          )}
          {type === 'final' && content && !canDownloadCsv && (
            <button
              type="button"
              onClick={downloadAsTxt}
              className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              title="Download als .txt"
            >
              <Download className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Content area with fade on type change */}
      <div
        key={fadeKey}
        className="flex-1 min-h-0 overflow-y-auto px-4 py-4 leading-[1.7]"
        style={{ animation: 'documentViewerFadeIn 0.3s ease-out' }}
      >
        {type === 'empty' && !showDataResult && (
          <div className="flex flex-col items-center justify-center py-12 text-slate-500">
            <FileText className="w-12 h-12 mb-3 opacity-50" aria-hidden />
            <p className="text-sm font-medium">Wacht op agent...</p>
          </div>
        )}

        {showDataResult && (
          <DataResultView
            proposedData={proposedData}
            onApprove={onApprove}
            approvingDeploy={approvingDeploy}
          />
        )}

        {showKeywordTable && (
          <KeywordTable data={parsedProposedData} />
        )}

        {type === 'brief' && (
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-4 text-slate-800">
            {content ? (
              <div className="prose prose-sm max-w-none [&_p]:mb-2 [&_p:last-child]:mb-0">
                <ReactMarkdown>{content}</ReactMarkdown>
              </div>
            ) : (
              <p className="text-slate-500 text-sm">Nog geen brief.</p>
            )}
          </div>
        )}

        {type === 'plan' && (
          <div className="space-y-3">
            {steps.length === 0 ? (
              <p className="text-slate-500 text-sm">Nog geen plan.</p>
            ) : (
              steps.map((step, i) => (
                <div
                  key={i}
                  className="flex gap-3 p-3 rounded-xl border border-slate-200 bg-white shadow-sm"
                >
                  <span className="flex-shrink-0 w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-sm font-semibold">
                    {i + 1}
                  </span>
                  <div className="min-w-0 text-sm text-slate-700">
                    {step.description || step.step_name || step.name || 'Stap'}
                  </div>
                </div>
              ))
            )}
            {showPlanAction && typeof onApprovePlan === 'function' && (
              <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-200">
                <button
                  type="button"
                  onClick={onApprovePlan}
                  disabled={approvingPlan}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
                >
                  {approvingPlan ? 'Starting…' : 'Start Execution'}
                </button>
              </div>
            )}
          </div>
        )}

        {type === 'draft' && (
          <div className="text-slate-800">
            {!content ? (
              <div className="flex items-center gap-2 text-slate-500">
                <span className="text-sm">Agent is aan het schrijven...</span>
                <span className="cursor-blink font-bold text-indigo-600" style={{ animation: 'blink 1s step-end infinite' }}>|</span>
              </div>
            ) : (
              <>
                <div className="prose prose-sm max-w-none [&_p]:mb-2 [&_p:last-child]:mb-0">
                  <ReactMarkdown>{content}</ReactMarkdown>
                </div>
                <span className="cursor-blink inline-block font-bold text-indigo-600 ml-0.5" style={{ animation: 'blink 1s step-end infinite' }}>|</span>
              </>
            )}
          </div>
        )}

        {type === 'final' && !showDataResult && !showKeywordTable && (
          <div className="space-y-4">
            <div className="prose prose-slate prose-sm max-w-none text-slate-800 [&_p]:mb-2 [&_p:last-child]:mb-0 [&_strong]:font-semibold [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4">
              {content ? <ReactMarkdown>{content}</ReactMarkdown> : <p className="text-slate-500">Geen content.</p>}
            </div>
            {showApproveButtons && (
              <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-200">
                {typeof onApprove === 'function' && (
                  <button
                    type="button"
                    onClick={onApprove}
                    disabled={approvingDeploy}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
                  >
                    {approvingDeploy ? 'Deploying…' : 'Approve & Publish'}
                  </button>
                )}
                {typeof onRequestChanges === 'function' && (
                  <button
                    type="button"
                    onClick={onRequestChanges}
                    className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg font-medium hover:bg-slate-50"
                  >
                    Request changes
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes documentViewerFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </div>
  )
}
