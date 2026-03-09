import { useEffect, useState, useCallback } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, GraduationCap, UserPlus, Loader2, BookOpen, Target, Activity } from 'lucide-react'
import PageLayout from './PageLayout'
import { apiUrl } from './apiClient'

const CATEGORIES = [
  { key: 'score_management', label: 'Management', apiValue: 'management' },
  { key: 'score_creative', label: 'Creative', apiValue: 'creative' },
  { key: 'score_development', label: 'Development', apiValue: 'development' },
  { key: 'score_operations', label: 'Operations', apiValue: 'operations' },
]

function StatusBadge({ status }) {
  const styles = {
    in_training: 'bg-slate-200 text-slate-700',
    ready: 'bg-green-100 text-green-800',
    hired: 'bg-blue-100 text-blue-800',
    inactive: 'bg-slate-100 text-slate-600',
  }
  const labels = {
    in_training: 'In Training',
    ready: 'Ready ✓',
    hired: 'Hired',
    inactive: 'Inactive',
  }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status] || styles.in_training}`}>
      {labels[status] || status}
    </span>
  )
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function NewbieDetail() {
  const { newbieId } = useParams()
  const navigate = useNavigate()
  const [newbie, setNewbie] = useState(null)
  const [trainings, setTrainings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [showTrain, setShowTrain] = useState(false)
  const [trainForm, setTrainForm] = useState({ urls: '', category: 'management' })
  const [training, setTraining] = useState(false)
  const [trainError, setTrainError] = useState('')
  const [trainProgress, setTrainProgress] = useState({ current: 0, total: 0, skipped: [] })

  const loadDetail = useCallback(async () => {
    if (!newbieId) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(apiUrl(`/api/newbies/${encodeURIComponent(newbieId)}`))
      if (!res.ok) {
        if (res.status === 404) throw new Error('Newbie not found')
        throw new Error((await res.json()).detail || 'Failed to load')
      }
      const data = await res.json()
      setNewbie(data)

      const trainRes = await fetch(apiUrl(`/api/newbies/${encodeURIComponent(newbieId)}/trainings`))
      if (trainRes.ok) {
        const trainData = await trainRes.json()
        setTrainings(Array.isArray(trainData) ? trainData : [])
      } else {
        setTrainings([])
      }
    } catch (err) {
      setError(err.message || 'Failed to load newbie')
      setNewbie(null)
      setTrainings([])
    } finally {
      setLoading(false)
    }
  }, [newbieId])

  useEffect(() => {
    loadDetail()
  }, [loadDetail])

  const openTrainModal = () => {
    setShowTrain(true)
    setTrainForm({ urls: '', category: 'management' })
    setTrainError('')
    setTrainProgress({ current: 0, total: 0, skipped: [] })
  }

  const submitTrain = async () => {
    const urlLines = (trainForm.urls || '')
      .split(/\n/)
      .map((u) => (u || '').trim())
      .filter(Boolean)
    if (!newbieId || urlLines.length === 0) return

    const total = urlLines.length
    setTraining(true)
    setTrainError('')
    setTrainProgress({ current: 0, total, skipped: [] })

    const skipped = []
    let processed = 0

    for (let i = 0; i < urlLines.length; i++) {
      const url = urlLines[i]
      setTrainProgress((p) => ({ ...p, current: i + 1, skipped: [...skipped] }))

      try {
        const res = await fetch(apiUrl('/api/newbies/train'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            newbie_id: newbieId,
            source_url: url,
            category: trainForm.category,
          }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          skipped.push({ index: i + 1, url, reason: data.detail || `HTTP ${res.status}` })
          continue
        }
        processed++
        await loadDetail()
      } catch (err) {
        skipped.push({ index: i + 1, url, reason: err.message || 'Niet bereikbaar' })
      }
    }

    setTrainProgress((p) => ({ ...p, skipped }))
    if (skipped.length > 0) {
      setTrainError(
        `Verwerkt: ${processed} van ${total}. Overgeslagen: ${skipped.map((s) => `URL ${s.index} (${s.reason})`).join('; ')}`
      )
    } else {
      setShowTrain(false)
      setTrainForm({ urls: '', category: 'management' })
      setTrainProgress({ current: 0, total: 0, skipped: [] })
      await loadDetail()
    }
    setTraining(false)
  }

  const handleHireNow = () => {
    navigate(`/hiring?promote=${encodeURIComponent(newbieId)}`)
  }

  const readiness = newbie?.readiness_score ?? 0
  const canHire = readiness >= 70 && (newbie?.status || '') === 'ready'

  if (loading && !newbie) {
    return (
      <PageLayout size="wide" padded>
        <div className="flex items-center justify-center py-16 text-slate-500 text-sm">Loading newbie…</div>
      </PageLayout>
    )
  }

  if (error || !newbie) {
    return (
      <PageLayout size="wide" padded>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm text-center">
          <p className="text-red-600 mb-4">{error || 'Newbie not found'}</p>
          <Link to="/newbies" className="inline-flex items-center gap-2 text-sm font-medium text-indigo-600 hover:text-indigo-800">
            <ArrowLeft className="w-4 h-4" /> Back to Newbies
          </Link>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout size="wide" padded className="!max-w-none">
      <div className="mb-4 flex items-center gap-2">
        <Link
          to="/newbies"
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Newbies
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[40%_60%] gap-6">
        {/* LEFT: Profile & Info */}
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-xl font-bold text-slate-900">{newbie.newbie_name || '—'}</h1>
                <StatusBadge status={newbie.status || 'in_training'} />
              </div>
              <p className="text-xs text-slate-500 font-mono">{newbie.newbie_id}</p>
            </div>

            <div className="mt-4">
              <h3 className="text-sm font-semibold text-slate-900 mb-1">Readiness</h3>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-3 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all"
                    style={{ width: `${Math.min(100, readiness)}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-slate-700">{readiness}/100</span>
              </div>
            </div>

            <div className="mt-4 space-y-2">
              <h3 className="text-sm font-semibold text-slate-900">Score breakdown</h3>
              {CATEGORIES.map(({ key, label }) => (
                <div key={key} className="flex items-center gap-2">
                  <span className="text-xs font-medium text-slate-500 w-24 shrink-0">{label}</span>
                  <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-slate-400 rounded-full"
                      style={{ width: `${Math.min(100, newbie[key] ?? 0)}%` }}
                    />
                  </div>
                  <span className="text-xs text-slate-600 w-6 text-right">{newbie[key] ?? 0}</span>
                </div>
              ))}
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={openTrainModal}
                disabled={newbie.status === 'hired'}
                className="btn-manage gap-2"
              >
                <GraduationCap className="w-4 h-4" />
                Train
              </button>
              {canHire && (
                <button type="button" onClick={handleHireNow} className="btn-manage gap-2 text-green-700 border-green-300 hover:bg-green-50">
                  <UserPlus className="w-4 h-4" />
                  Hire Now
                </button>
              )}
            </div>
          </div>

          {newbie.suggested_role && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">Suggested role</h3>
              <p className="text-sm text-slate-700">{newbie.suggested_role}</p>
            </div>
          )}
        </div>

        {/* RIGHT: Persona, Qualities, Development, Trainings */}
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <BookOpen className="w-4 h-4" /> Persona
            </h3>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{newbie.persona || '—'}</p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <Target className="w-4 h-4" /> Kwaliteiten
            </h3>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{newbie.qualities || '—'}</p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <Target className="w-4 h-4" /> Ontwikkelpunten
            </h3>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{newbie.development || '—'}</p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <Activity className="w-4 h-4" /> Trainingshistorie ({trainings.length})
            </h3>
            {trainings.length === 0 ? (
              <p className="text-xs text-slate-500">Geen trainingen nog. Klik op Train om URLs toe te voegen.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200">
                      <th className="text-left py-2 px-2 font-medium text-slate-600">Datum</th>
                      <th className="text-left py-2 px-2 font-medium text-slate-600">URL</th>
                      <th className="text-left py-2 px-2 font-medium text-slate-600">Categorie</th>
                      <th className="text-right py-2 px-2 font-medium text-slate-600">Score</th>
                      <th className="text-left py-2 px-2 font-medium text-slate-600">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trainings.map((t) => (
                      <tr key={t.training_id} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="py-2 px-2 text-slate-600">{formatDate(t.completed_at || t.created_at)}</td>
                        <td className="py-2 px-2 text-slate-700 truncate max-w-[200px]" title={t.source_url}>
                          <a href={t.source_url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">
                            {t.source_url || '—'}
                          </a>
                        </td>
                        <td className="py-2 px-2 text-slate-600 capitalize">{t.category || '—'}</td>
                        <td className="py-2 px-2 text-right font-medium text-slate-700">+{t.score_gained ?? 0}</td>
                        <td className="py-2 px-2">
                          <span
                            className={`inline-flex px-1.5 py-0.5 rounded text-xs ${
                              t.status === 'completed' ? 'bg-green-100 text-green-800' : t.status === 'failed' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-700'
                            }`}
                          >
                            {t.status || '—'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modal: Train Newbie */}
      {showTrain && (
        <div className="modal-overlay" onClick={() => !training && setShowTrain(false)}>
          <div className="modal-card space-y-3 max-w-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold">Train: {newbie.newbie_name}</h2>
            <p className="text-sm text-slate-600">Voeg URLs toe (één per regel) om de score te verhogen.</p>

            {training && (
              <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-indigo-50 text-indigo-700">
                <Loader2 className="w-5 h-5 animate-spin shrink-0" />
                <span className="text-sm">
                  {trainProgress.total > 1
                    ? `Verwerkt ${trainProgress.current} van ${trainProgress.total} URLs...`
                    : 'URL wordt opgehaald en verwerkt...'}
                </span>
              </div>
            )}

            {trainError && (
              <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{trainError}</div>
            )}

            <div>
              <label className="block text-sm font-semibold mb-1">URLs (één per regel)</label>
              <textarea
                className="w-full px-3 py-2 border border-slate-300 rounded-lg disabled:opacity-60 disabled:bg-slate-50 min-h-[120px] font-mono text-sm"
                placeholder={'https://...\nhttps://...\nhttps://...'}
                value={trainForm.urls}
                onChange={(e) => setTrainForm({ ...trainForm, urls: e.target.value })}
                disabled={training}
                rows={5}
              />
            </div>
            <div>
              <label className="block text-sm font-semibold mb-1">Categorie</label>
              <select
                className="w-full px-3 py-2 border border-slate-300 rounded-lg disabled:opacity-60 disabled:bg-slate-50"
                value={trainForm.category}
                onChange={(e) => setTrainForm({ ...trainForm, category: e.target.value })}
                disabled={training}
              >
                {CATEGORIES.map(({ key, label, apiValue }) => (
                  <option key={key} value={apiValue}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => !training && setShowTrain(false)}
                className="flex-1 px-4 py-2 border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-60"
                disabled={training}
              >
                Annuleren
              </button>
              <button
                type="button"
                onClick={submitTrain}
                disabled={training || !(trainForm.urls || '').trim()}
                className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {training ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Training...
                  </>
                ) : (
                  'Train'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
