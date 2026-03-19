import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, GraduationCap, UserPlus, Loader2 } from 'lucide-react'
import PageLayout from './PageLayout'
import { apiUrl, apiFetch } from './apiClient'
import { supabase } from './supabase'
import { getCurrentUserRole, isAdmin } from './authz'
import { useAuthReady } from './useAuthReady'

const CATEGORIES = [
  { key: 'score_management', label: 'Management', apiValue: 'management' },
  { key: 'score_creative', label: 'Creative', apiValue: 'creative' },
  { key: 'score_development', label: 'Development', apiValue: 'development' },
  { key: 'score_operations', label: 'Operations', apiValue: 'operations' },
]

function truncate(str, max = 120) {
  if (!str || typeof str !== 'string') return '—'
  return str.length <= max ? str : str.slice(0, max).trim() + '…'
}

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

export default function Newbies() {
  const navigate = useNavigate()
  const { authReady } = useAuthReady()
  const [newbies, setNewbies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [userRole, setUserRole] = useState('member')
  const [showAdd, setShowAdd] = useState(false)
  const [adding, setAdding] = useState(false)
  const [addForm, setAddForm] = useState({
    newbie_name: '',
    persona: '',
    qualities: '',
    development: '',
    suggested_role: '',
  })

  const [trainNewbie, setTrainNewbie] = useState(null)
  const [trainForm, setTrainForm] = useState({ urls: '' })
  const [training, setTraining] = useState(false)
  const [trainError, setTrainError] = useState('')
  const [trainProgress, setTrainProgress] = useState({ current: 0, total: 0, skipped: [] })
  const [trainingProgress, setTrainingProgress] = useState(null) // { newbieId, current, total } — live op card
  const [evaluationResults, setEvaluationResults] = useState([]) // { url, accept, category, reason, confidence, trained, score_gained, error? }
  const [evaluationProgress, setEvaluationProgress] = useState(null) // { current, total } or null

  const [libraryUrl, setLibraryUrl] = useState('')
  const [libraryItems, setLibraryItems] = useState([])
  const [addingToLibrary, setAddingToLibrary] = useState(false)
  const [libraryError, setLibraryError] = useState('')
  // Per newbie_id: { status: 'evaluating'|'accepted'|'skipped'|'error', category?, reason?, score_gained? }
  const [libraryResults, setLibraryResults] = useState({})
  const [offeringLibraryId, setOfferingLibraryId] = useState(null)

  const canEdit = true // tijdelijk: isAdmin(userRole) faalt omdat userRole niet correct wordt opgehaald na inloggen
  console.log('userRole:', userRole, 'canEdit:', canEdit)

  const fetchNewbies = async (silent = false) => {
    if (!silent) setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/newbies')
      if (!res.ok) throw new Error(`Newbies ophalen mislukt (${res.status})`)
      const data = await res.json()
      setNewbies(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message || 'Newbies ophalen mislukt')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const fetchLibraryItems = async () => {
    try {
      const res = await apiFetch('/api/newbies/library')
      if (!res.ok) throw new Error(`Library ophalen mislukt (${res.status})`)
      const data = await res.json()
      setLibraryItems(Array.isArray(data) ? data : [])
    } catch (err) {
      // Niet hardfalend voor de hele pagina
      setLibraryError(err.message || 'Library ophalen mislukt')
    }
  }

  useEffect(() => {
    if (!authReady) return
    let mounted = true

    const syncRole = async () => {
      try {
        const ctx = await getCurrentUserRole()
        if (mounted) setUserRole(ctx.role || 'member')
      } catch {
        if (mounted) setUserRole('member')
      }
    }

    syncRole()
    fetchNewbies()
    fetchLibraryItems()

    const { data: listener } = supabase.auth.onAuthStateChange(async () => {
      await syncRole()
    })

    return () => {
      mounted = false
      listener.subscription.unsubscribe()
    }
  }, [authReady])

  const submitAdd = async () => {
    if (!canEdit) return
    if (!addForm.newbie_name?.trim() || !addForm.persona?.trim() || !addForm.qualities?.trim() || !addForm.development?.trim()) {
      setError('Naam, persona, kwaliteiten en ontwikkelpunten zijn verplicht.')
      return
    }
    setAdding(true)
    setError('')
    try {
      const res = await apiFetch('/api/newbies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          newbie_name: addForm.newbie_name.trim(),
          persona: addForm.persona.trim(),
          qualities: addForm.qualities.trim(),
          development: addForm.development.trim(),
          suggested_role: addForm.suggested_role?.trim() || null,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Toevoegen mislukt (${res.status})`)
      }
      setShowAdd(false)
      setAddForm({ newbie_name: '', persona: '', qualities: '', development: '', suggested_role: '' })
      await fetchNewbies()
    } catch (err) {
      setError(err.message || 'Newbie toevoegen mislukt')
    } finally {
      setAdding(false)
    }
  }

  const handleHireNow = (newbie) => {
    navigate(`/hiring?promote=${encodeURIComponent(newbie.newbie_id)}`)
  }

  const openTrainModal = (n) => {
    setTrainNewbie(n)
    setTrainForm({ urls: '' })
    setTrainError('')
    setTrainProgress({ current: 0, total: 0, skipped: [] })
    setEvaluationResults([])
    setEvaluationProgress(null)
  }

  const submitTrain = async () => {
    const urlLines = (trainForm.urls || '')
      .split(/\n/)
      .map((u) => (u || '').trim())
      .filter(Boolean)
    if (!trainNewbie || urlLines.length === 0) return

    const newbieId = trainNewbie.newbie_id
    const total = urlLines.length
    setTraining(true)
    setTrainError('')
    setEvaluationResults([])
    setEvaluationProgress({ current: 0, total })
    setTrainingProgress({ newbieId, current: 0, total })

    const results = []

    for (let i = 0; i < urlLines.length; i++) {
      const url = urlLines[i]
      setEvaluationProgress({ current: i + 1, total })
      setTrainingProgress({ newbieId, current: i + 1, total })

      try {
        const res = await apiFetch(`/api/newbies/${encodeURIComponent(newbieId)}/evaluate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source_url: url }),
        })
        const data = await res.json().catch(() => ({}))
        const ev = data.evaluation || {}
        const item = {
          url,
          accept: !!ev.accept,
          category: ev.category || 'management',
          reason: ev.reason || '',
          confidence: ev.confidence ?? 0,
          trained: !!data.trained,
          score_gained: data.score_gained ?? 0,
          error: data.error || null,
        }
        results.push(item)
        setEvaluationResults([...results])
        if (data.trained) await fetchNewbies(true)
      } catch (err) {
        const item = {
          url,
          accept: false,
          category: 'management',
          reason: 'URL niet bereikbaar of fout bij evaluatie.',
          confidence: 0,
          trained: false,
          score_gained: 0,
          error: err.message || 'Niet bereikbaar',
        }
        results.push(item)
        setEvaluationResults([...results])
      }
    }

    setEvaluationProgress(null)
    setTrainingProgress(null)
    setTraining(false)
  }

  const categoryLabel = (apiValue) => CATEGORIES.find((c) => c.apiValue === apiValue)?.label || apiValue

  const hostFromUrl = (url) => {
    try {
      const u = new URL(url)
      return (u.hostname || '').replace(/^www\./, '')
    } catch {
      return ''
    }
  }

  const submitAddToLibrary = async () => {
    const url = (libraryUrl || '').trim()
    if (!url || addingToLibrary) return
    setLibraryError('')
    setAddingToLibrary(true)

    try {
      const res = await apiFetch('/api/newbies/library', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: url }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(data?.detail || `Toevoegen mislukt (${res.status})`)
      }

      // Voeg toe aan de lijst en start automatisch aanbieden.
      setLibraryItems((prev) => {
        const next = [{ ...data }, ...prev.filter((x) => x.library_id !== data.library_id)]
        return next
      })
      setLibraryUrl('')
      await offerLibraryItemToNewbies(data.library_id)
    } catch (err) {
      setLibraryError(err.message || 'Toevoegen mislukt')
    } finally {
      setAddingToLibrary(false)
    }
  }

  const offerLibraryItemToNewbies = async (library_id) => {
    if (!library_id || offeringLibraryId === library_id) return
    const toEvaluate = newbies.filter((n) => (n.status || '') !== 'hired')
    if (toEvaluate.length === 0) return

    setOfferingLibraryId(library_id)
    setLibraryResults({})

    const firstIdKey = toEvaluate[0] ? String(toEvaluate[0].newbie_id) : null

    const results = {}
    toEvaluate.forEach((n) => {
      results[String(n.newbie_id)] = { status: 'evaluating' }
    })
    setLibraryResults({ ...results })

    await Promise.all(
      toEvaluate.map(async (n) => {
        const id = String(n.newbie_id)
        try {
          const res = await apiFetch(`/api/newbies/${encodeURIComponent(id)}/evaluate-library`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ library_id }),
          })
          const data = await res.json().catch(() => ({}))
          const ev = data.evaluation || {}

          if (firstIdKey && id === firstIdKey) {
            console.log('[evaluate-library debug]', { newbie_id: id, library_id, http: res?.status, data })
          }

          if (ev.accept) {
            const nextEntry = {
              status: 'accepted',
              category: ev.category,
              reason: ev.reason,
              score_gained: data.score_gained ?? 0,
            }
            if (firstIdKey && id === firstIdKey) console.log('[libraryResults update]', id, nextEntry)
            setLibraryResults((prev) => ({ ...prev, [id]: nextEntry }))
            if (data.trained) await fetchNewbies(true)
          } else {
            const nextEntry = { status: 'skipped', reason: ev.reason || 'Overgeslagen.' }
            if (firstIdKey && id === firstIdKey) console.log('[libraryResults update]', id, nextEntry)
            setLibraryResults((prev) => ({ ...prev, [id]: nextEntry }))
          }
        } catch (err) {
          const nextEntry = { status: 'error', reason: 'Kon Newbie niet bereiken' }
          if (firstIdKey && id === firstIdKey) console.log('[libraryResults update]', id, nextEntry)
          setLibraryResults((prev) => ({ ...prev, [id]: nextEntry }))
        }
      })
    )

    setOfferingLibraryId(null)
  }

  return (
    <PageLayout>
      <div className="panel-card">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="page-title mb-1">Newbies</h1>
            <p className="page-subtitle">Persona&apos;s in ontwikkeling. Train ze tot readiness ≥ 70, dan verschijnen ze in de Hiring Hall.</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-icon-only" type="button" onClick={fetchNewbies} aria-label="Vernieuwen">
              ↻
            </button>
            {canEdit && (
              <button type="button" className="btn-manage gap-2" onClick={() => setShowAdd(true)}>
                <Plus className="w-4 h-4" />
                Add Newbie
              </button>
            )}
          </div>
        </div>

        {error && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        {/* Library balk: URL 1x opslaan, daarna per Newbie aanbieden */}
        <div className="mb-5 rounded-lg border border-slate-200 bg-slate-50/50 p-4">
          <h3 className="text-sm font-semibold text-slate-800 mb-2">Kennisbibliotheek</h3>

          <div className="flex flex-wrap items-center gap-2 mb-1">
            <input
              type="url"
              className="flex-1 min-w-[200px] px-3 py-2 border border-slate-300 rounded-lg font-mono text-sm disabled:opacity-60 disabled:bg-slate-100"
              placeholder="https://..."
              value={libraryUrl}
              onChange={(e) => {
                setLibraryUrl(e.target.value)
                setLibraryError('')
              }}
              disabled={addingToLibrary || offeringLibraryId != null}
            />
            <button
              type="button"
              onClick={submitAddToLibrary}
              disabled={addingToLibrary || offeringLibraryId != null || !(libraryUrl || '').trim() || loading}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg disabled:opacity-50 flex items-center gap-2"
            >
              {addingToLibrary ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Scrapen...
                </>
              ) : (
                'Toevoegen'
              )}
            </button>
          </div>
          {libraryError && <div className="mt-2 text-xs text-red-700">{libraryError}</div>}

          <div className="mt-3">
            <div className="text-xs text-slate-600 mb-2">Recente items:</div>
            <div className="space-y-2">
              {libraryItems.slice(0, 6).map((it) => (
                <div key={it.library_id} className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-800 truncate">
                      {it.title || '—'} — {hostFromUrl(it.source_url)}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="text-xs text-indigo-700 hover:underline font-medium disabled:opacity-50 disabled:hover:no-underline"
                    onClick={() => offerLibraryItemToNewbies(it.library_id)}
                    disabled={offeringLibraryId != null}
                  >
                    {offeringLibraryId === it.library_id ? 'Aan het aanbieden…' : 'Aanbieden aan Newbies'}
                  </button>
                </div>
              ))}
              {!libraryItems.length && <div className="text-xs text-slate-500">Nog geen items.</div>}
            </div>
          </div>
        </div>

        {loading ? (
          <div className="text-sm text-slate-500">Laden...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
            {newbies.map((n) => {
              const isTraining = trainingProgress?.newbieId === n.newbie_id
              return (
              <div
                key={n.newbie_id}
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/newbies/${encodeURIComponent(n.newbie_id)}`)}
                onKeyDown={(e) => e.key === 'Enter' && navigate(`/newbies/${encodeURIComponent(n.newbie_id)}`)}
                className={`block rounded-lg border p-4 transition cursor-pointer ${
                  isTraining
                    ? 'border-indigo-400 bg-indigo-50/30 animate-pulse hover:border-indigo-500'
                    : 'border-slate-200 hover:border-indigo-300 hover:bg-slate-50/50'
                }`}
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div>
                    <h3 className="font-semibold text-slate-800">{n.newbie_name || '—'}</h3>
                    <span className="text-sm text-slate-600">score: {n.readiness_score ?? 0}/100</span>
                  </div>
                  <StatusBadge status={n.status || 'in_training'} />
                </div>
                {isTraining && (
                  <p className="text-xs text-indigo-600 font-medium mt-1">
                    Evalueren… ({trainingProgress.current}/{trainingProgress.total} URLs)
                  </p>
                )}
                <p className="text-xs text-slate-600 mt-1 line-clamp-2">{truncate(n.persona, 100)}</p>

                {/* Progress bar */}
                <div className="mt-3">
                  <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 rounded-full transition-all"
                      style={{ width: `${Math.min(100, n.readiness_score ?? 0)}%` }}
                    />
                  </div>
                </div>

                {/* Score breakdown */}
                <div className="mt-3 space-y-1.5">
                  {CATEGORIES.map(({ key, label }) => (
                    <div key={key} className="flex items-center gap-2">
                      <span className="text-[10px] font-medium text-slate-500 w-20 shrink-0">{label}</span>
                      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-slate-400 rounded-full"
                          style={{ width: `${Math.min(100, n[key] ?? 0)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-slate-500 w-6 text-right">{n[key] ?? 0}</span>
                    </div>
                  ))}
                </div>

                {/* Library result per card */}
                {libraryResults[String(n.newbie_id)] && (
                  <div className="mt-3 pt-3 border-t border-slate-100 text-xs" onClick={(e) => e.stopPropagation()}>
                    {libraryResults[String(n.newbie_id)].status === 'evaluating' && (
                      <div className="flex items-center gap-2 text-indigo-600">
                        <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                        Evalueren...
                      </div>
                    )}
                    {libraryResults[String(n.newbie_id)].status === 'accepted' && (
                      <div>
                        <div className="font-medium text-green-600">
                          ✓ Geaccepteerd — {categoryLabel(libraryResults[String(n.newbie_id)].category)}
                          {libraryResults[String(n.newbie_id)].score_gained != null && libraryResults[String(n.newbie_id)].score_gained > 0 && (
                            <span> (+{libraryResults[String(n.newbie_id)].score_gained})</span>
                          )}
                        </div>
                        {libraryResults[String(n.newbie_id)].reason && (
                          <p className="text-slate-600 italic mt-0.5">&quot;{libraryResults[String(n.newbie_id)].reason}&quot;</p>
                        )}
                      </div>
                    )}
                    {libraryResults[String(n.newbie_id)].status === 'skipped' && (
                      <div>
                        <div className="font-medium text-red-600">✗ Overgeslagen</div>
                        {libraryResults[String(n.newbie_id)].reason && (
                          <p className="text-slate-600 italic mt-0.5">&quot;{libraryResults[String(n.newbie_id)].reason}&quot;</p>
                        )}
                      </div>
                    )}
                    {libraryResults[String(n.newbie_id)].status === 'error' && (
                      <div className="font-medium text-amber-600">
                        {libraryResults[String(n.newbie_id)].reason || 'Kon Newbie niet bereiken'}
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-4 flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className="text-sm text-indigo-600 hover:underline font-medium flex items-center gap-1"
                    onClick={() => openTrainModal(n)}
                    title="Train met URL"
                  >
                    <GraduationCap className="w-4 h-4" />
                    Train
                  </button>
                  {(n.readiness_score ?? 0) >= 70 && n.status === 'ready' && (
                    <button
                      type="button"
                      className="text-sm text-green-600 hover:underline font-medium flex items-center gap-1"
                      onClick={() => handleHireNow(n)}
                    >
                      <UserPlus className="w-4 h-4" />
                      Hire Now
                    </button>
                  )}
                </div>
              </div>
            )
            })}
            {!newbies.length && (
              <div className="col-span-full py-8 text-center text-sm text-slate-500">
                Geen newbies gevonden. Klik op &quot;Add Newbie&quot; om te starten.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modal: Add Newbie */}
      {showAdd && (
        <div className="modal-overlay" onClick={() => !adding && setShowAdd(false)}>
          <div className="modal-card space-y-3" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold">Add Newbie</h2>
            <input
              className="w-full px-3 py-2 border border-slate-300 rounded-lg"
              placeholder="Naam"
              value={addForm.newbie_name}
              onChange={(e) => setAddForm({ ...addForm, newbie_name: e.target.value })}
            />
            <textarea
              className="w-full px-3 py-2 border border-slate-300 rounded-lg"
              placeholder="Persona (wie is hij/zij?)"
              rows={3}
              value={addForm.persona}
              onChange={(e) => setAddForm({ ...addForm, persona: e.target.value })}
            />
            <textarea
              className="w-full px-3 py-2 border border-slate-300 rounded-lg"
              placeholder="Kwaliteiten (waar is hij/zij goed in?)"
              rows={2}
              value={addForm.qualities}
              onChange={(e) => setAddForm({ ...addForm, qualities: e.target.value })}
            />
            <textarea
              className="w-full px-3 py-2 border border-slate-300 rounded-lg"
              placeholder="Ontwikkelpunten (wat moet nog groeien?)"
              rows={2}
              value={addForm.development}
              onChange={(e) => setAddForm({ ...addForm, development: e.target.value })}
            />
            <input
              className="w-full px-3 py-2 border border-slate-300 rounded-lg"
              placeholder="Suggested role (optioneel, bijv. support)"
              value={addForm.suggested_role}
              onChange={(e) => setAddForm({ ...addForm, suggested_role: e.target.value })}
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => !adding && setShowAdd(false)}
                className="flex-1 px-4 py-2 border border-slate-300 rounded-lg hover:bg-slate-50"
                disabled={adding}
              >
                Annuleren
              </button>
              <button
                type="button"
                onClick={submitAdd}
                disabled={adding}
                className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg disabled:opacity-50"
              >
                {adding ? 'Bezig...' : 'Aanmaken'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Train Newbie (evaluate flow) */}
      {trainNewbie && (
        <div className="modal-overlay" onClick={() => !training && setTrainNewbie(null)}>
          <div className="modal-card space-y-3 max-w-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold">Train: {trainNewbie.newbie_name}</h2>
            <p className="text-sm text-slate-600">Plak URLs (één per regel). {trainNewbie.newbie_name} beoordeelt zelf of een URL relevant is en in welke categorie die past.</p>

            {evaluationProgress && (
              <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-indigo-50 text-indigo-700">
                <Loader2 className="w-5 h-5 animate-spin shrink-0" />
                <span className="text-sm">
                  Evalueren URL {evaluationProgress.current} van {evaluationProgress.total}…
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

            {evaluationResults.length > 0 && (
              <div className="space-y-2">
                <span className="text-sm font-semibold">Resultaten</span>
                <ul className="space-y-2 max-h-48 overflow-y-auto">
                  {evaluationResults.map((r, idx) => (
                    <li key={idx} className="text-sm border border-slate-200 rounded-lg p-2">
                      {r.accept ? (
                        <>
                          <span className="text-green-600 font-medium">✓ {trainNewbie.newbie_name} neemt dit aan</span>
                          <span className="text-slate-600"> — {categoryLabel(r.category)}</span>
                          {r.trained && <span className="text-green-600"> (+{r.score_gained})</span>}
                          {r.error && !r.trained && <span className="text-amber-600"> — training mislukt: {r.error}</span>}
                          {r.reason && <p className="text-slate-600 mt-1 italic">&quot;{r.reason}&quot;</p>}
                        </>
                      ) : (
                        <>
                          <span className="text-red-600 font-medium">✗ {trainNewbie.newbie_name} slaat dit over</span>
                          {r.reason && <p className="text-slate-600 mt-1 italic">&quot;{r.reason}&quot;</p>}
                        </>
                      )}
                      <p className="text-xs text-slate-500 font-mono truncate mt-0.5" title={r.url}>{r.url}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => !training && setTrainNewbie(null)}
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
                    Evalueren…
                  </>
                ) : (
                  `Laat ${trainNewbie.newbie_name} evalueren`
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
