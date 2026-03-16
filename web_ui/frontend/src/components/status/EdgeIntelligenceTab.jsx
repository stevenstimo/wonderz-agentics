import React, { useEffect, useState } from 'react'
import { AlertTriangle, Brain, Loader2, RefreshCw } from 'lucide-react'
import { apiFetch } from '../../apiClient'
import ProgressBar from '../hr/shared/ProgressBar'

const STORAGE_KEY = 'wonderz_edge_intelligence_result'

function scoreVariant(score) {
  if (score == null) return 'blue'
  if (score < 50) return 'red'
  if (score < 75) return 'amber'
  return 'green'
}

function priorityBadgeClass(priority) {
  if (priority === 'easy_win') return 'bg-emerald-100 text-emerald-700'
  if (priority === 'medium') return 'bg-amber-100 text-amber-700'
  if (priority === 'strategic') return 'bg-purple-100 text-purple-700'
  return 'bg-slate-100 text-slate-700'
}

export default function EdgeIntelligenceTab() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const cached = localStorage.getItem(STORAGE_KEY)
    if (cached) {
      try {
        const parsed = JSON.parse(cached)
        setResult(parsed)
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      }
    }
  }, [])

  const runAnalysis = async () => {
    localStorage.removeItem(STORAGE_KEY)
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await apiFetch('/api/status/edge-intelligence', {
        method: 'POST',
        body: JSON.stringify({ days: 7 }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Edge intelligence call failed (${res.status})`)
      }
      const json = await res.json()
      const generatedAt = new Date().toLocaleString('nl-NL')
      const toStore = { ...json, generated_at: generatedAt }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(toStore))
      setResult(toStore)
    } catch (err) {
      setError(err.message || 'Analyse uitvoeren mislukt')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const healthScore = result?.health_score
  const architectureScores = result?.architecture_scores || {}
  const problems = Array.isArray(result?.problems) ? result.problems : []
  const rootCauses = Array.isArray(result?.root_causes) ? result.root_causes : []
  const suggestions = Array.isArray(result?.fix_suggestions) ? result.fix_suggestions : []

  // State A: Geen analyse uitgevoerd
  if (!result && !loading && !error) {
    return (
      <div className="panel-card space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-indigo-600" />
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Platform Intelligence</h2>
              <p className="text-xs text-slate-500">
                Analyseer het volledige Wonderz platform op patronen, bottlenecks en verbeterpunten.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={runAnalysis}
            className="btn-primary flex items-center gap-1.5"
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Bezig...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4" />
                Analyse uitvoeren
              </>
            )}
          </button>
        </div>
        <div className="border border-dashed border-slate-200 rounded-lg p-4 bg-slate-50">
          <p className="text-sm text-slate-600 mb-1">
            Analyseer het platform op basis van jobs, agent performance, fouten en Knowledge Hub coverage.
          </p>
          <p className="text-xs text-slate-500">
            De analyse duurt meestal 10–20 seconden. Er worden geen wijzigingen in het platform aangebracht; dit is
            puur diagnostisch.
          </p>
        </div>
      </div>
    )
  }

  // State B: Loading
  if (loading) {
    return (
      <div className="panel-card flex flex-col items-center justify-center py-12 gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
        <p className="text-sm text-slate-600">Platform wordt geanalyseerd...</p>
        <p className="text-xs text-slate-500">
          Dit kan 10–20 seconden duren, afhankelijk van de hoeveelheid diagnostische data.
        </p>
      </div>
    )
  }

  // State D: Error
  if (error || result?.error) {
    return (
      <div className="panel-card space-y-4">
        <div className="flex items-center gap-2 text-amber-700">
          <AlertTriangle className="w-4 h-4" />
          <span className="text-sm font-medium">
            Analyse tijdelijk niet beschikbaar: {error || result?.error || 'onbekende fout'}
          </span>
        </div>
        <button
          type="button"
          onClick={runAnalysis}
          className="btn-primary flex items-center gap-1.5"
        >
          <RefreshCw className="w-4 h-4" />
          Opnieuw proberen
        </button>
      </div>
    )
  }

  // State C: Resultaat
  return (
    <div className="space-y-6">
      <div className="panel-card flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain className="w-6 h-6 text-indigo-600" />
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Platform Health</h2>
            <p className="text-xs text-slate-500">
              AI-gegenereerd health rapport op basis van jobs, agents, fouten en kennisdekking.
            </p>
            {(result?.generated_at) && (
              <p className="text-[11px] text-slate-400 mt-1">
                Analyse uitgevoerd op: {result.generated_at}
              </p>
            )}
          </div>
        </div>
        <div className="flex flex-col items-center justify-center w-28 h-28 rounded-full border-4 border-slate-100 relative">
          <div
            className={`absolute inset-1 rounded-full flex items-center justify-center ${
              scoreVariant(healthScore) === 'green'
                ? 'bg-emerald-50'
                : scoreVariant(healthScore) === 'amber'
                  ? 'bg-amber-50'
                  : scoreVariant(healthScore) === 'red'
                    ? 'bg-rose-50'
                    : 'bg-slate-50'
            }`}
          >
            <span
              className={`text-xl font-semibold ${
                scoreVariant(healthScore) === 'green'
                  ? 'text-emerald-600'
                  : scoreVariant(healthScore) === 'amber'
                    ? 'text-amber-600'
                    : scoreVariant(healthScore) === 'red'
                      ? 'text-rose-600'
                      : 'text-slate-500'
              }`}
            >
              {healthScore != null ? Math.round(healthScore) : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* Architecture scores */}
      {architectureScores && (
        <div className="panel-card">
          <h3 className="text-sm font-semibold text-slate-800 mb-3">Architecture scores</h3>
          <div className="space-y-3">
            {[
              ['NEXUS Pipeline', architectureScores.nexus_pipeline],
              ['Agent Reliability', architectureScores.agent_reliability],
              ['Knowledge Coverage', architectureScores.knowledge_coverage],
              ['Cost Efficiency', architectureScores.cost_efficiency],
            ].map(([label, value]) => (
              <div key={label} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-600">{label}</span>
                  <span className="text-slate-500">{value != null ? `${value}/100` : '—'}</span>
                </div>
                <ProgressBar value={(Number(value) || 0) / 100} variant={scoreVariant(value)} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Problemen */}
      <div className="panel-card">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">Problemen</h3>
        {problems.length === 0 ? (
          <p className="text-sm text-slate-500">Geen expliciete problemen gerapporteerd door de analyse.</p>
        ) : (
          <div className="space-y-3">
            {problems.map((p, idx) => (
              <div key={`${p.type}-${idx}`} className="border border-slate-100 rounded-lg p-3 bg-slate-50">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="text-xs font-semibold text-slate-800">{p.type || 'Onbekend probleem'}</div>
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${
                      p.severity === 'critical'
                        ? 'bg-rose-100 text-rose-700'
                        : p.severity === 'warning'
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-sky-100 text-sky-700'
                    }`}
                  >
                    {p.severity || 'info'}
                  </span>
                </div>
                <p className="text-xs text-slate-600 mb-1.5">{p.description}</p>
                {Array.isArray(p.affected_components) && p.affected_components.length > 0 && (
                  <p className="text-[11px] text-slate-500">
                    Components:{' '}
                    {p.affected_components.map((c, i) => (
                      <span key={`${c}-${i}`} className="inline-block mr-1">
                        {c}
                        {i < p.affected_components.length - 1 ? ',' : ''}
                      </span>
                    ))}
                  </p>
                )}
                {p.metric && (
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Metric: <span className="font-mono">{p.metric}</span>
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Root causes */}
      <div className="panel-card">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">Root causes</h3>
        {rootCauses.length === 0 ? (
          <p className="text-sm text-slate-500">Geen root causes gerapporteerd.</p>
        ) : (
          <div className="space-y-2">
            {rootCauses.map((rc, idx) => (
              <details key={`${rc.problem_type}-${idx}`} className="border border-slate-100 rounded-lg p-3 bg-slate-50">
                <summary className="flex items-center justify-between cursor-pointer">
                  <div className="text-xs font-semibold text-slate-800">
                    {rc.problem_type || 'Onbekend probleem'}
                  </div>
                  <span className="text-[11px] text-slate-500">
                    Confidence: {rc.confidence != null ? `${Math.round(rc.confidence * 100)}%` : '—'}
                  </span>
                </summary>
                <div className="mt-2 space-y-1">
                  <p className="text-xs text-slate-600">{rc.analysis}</p>
                  {rc.evidence && (
                    <p className="text-[11px] text-slate-500">
                      Evidence: <span className="font-mono">{rc.evidence}</span>
                    </p>
                  )}
                  <div className="mt-1">
                    <ProgressBar
                      value={Number(rc.confidence || 0)}
                      variant={scoreVariant((rc.confidence || 0) * 100)}
                    />
                  </div>
                </div>
              </details>
            ))}
          </div>
        )}
      </div>

      {/* Fix suggesties */}
      <div className="panel-card">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">Fix suggesties</h3>
        {suggestions.length === 0 ? (
          <p className="text-sm text-slate-500">Geen verbeter-suggesties gerapporteerd.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {suggestions
              .slice()
              .sort((a, b) => (a.priority || '').localeCompare(b.priority || ''))
              .map((s, idx) => (
                <div
                  key={`${s.title || 'suggest'}-${idx}`}
                  className="border border-slate-100 rounded-lg p-3 bg-slate-50 flex flex-col gap-1.5"
                >
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-semibold text-slate-800">{s.title || 'Suggestie'}</div>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${priorityBadgeClass(
                        s.priority,
                      )}`}
                    >
                      {s.priority || 'medium'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600">{s.description}</p>
                  {s.implementation && (
                    <p className="text-[11px] text-slate-500">
                      Implementatie:{' '}
                      <span className="font-mono whitespace-pre-wrap">{s.implementation}</span>
                    </p>
                  )}
                  {s.estimated_impact && (
                    <p className="text-[11px] text-slate-500">
                      Verwachte impact: <span className="font-mono">{s.estimated_impact}</span>
                    </p>
                  )}
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  )
}

