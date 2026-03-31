/**
 * Hiring Hall — promote flow for hiring ready newbies via presets.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, UserPlus } from 'lucide-react'
import PageLayout from './PageLayout'
import { apiFetch } from './apiClient'

export default function HiringHall() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const promoteNewbieId = useMemo(() => (searchParams.get('promote') || '').trim(), [searchParams])

  const [presets, setPresets] = useState([])
  const [presetsLoading, setPresetsLoading] = useState(true)
  const [promoteNewbieName, setPromoteNewbieName] = useState('')
  const [promoteLoading, setPromoteLoading] = useState(false)
  const [hiringPresetId, setHiringPresetId] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadPresets() {
      setPresetsLoading(true)
      setError('')
      try {
        const res = await apiFetch('/api/agents/presets')
        const data = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(data?.detail || 'Presets laden mislukt')
        setPresets(Array.isArray(data.presets) ? data.presets : [])
      } catch (err) {
        setError(err.message || 'Presets laden mislukt')
        setPresets([])
      } finally {
        setPresetsLoading(false)
      }
    }
    loadPresets()
  }, [])

  useEffect(() => {
    if (!promoteNewbieId) {
      setPromoteNewbieName('')
      return
    }
    let active = true
    async function loadPromoteNewbie() {
      setPromoteLoading(true)
      setError('')
      try {
        const res = await apiFetch(`/api/newbies/${encodeURIComponent(promoteNewbieId)}`)
        const data = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(data?.detail || 'Newbie niet gevonden voor promote-flow')
        if (active) setPromoteNewbieName(data?.newbie_name || '')
      } catch (err) {
        if (active) {
          setPromoteNewbieName('')
          setError(err.message || 'Promote newbie laden mislukt')
        }
      } finally {
        if (active) setPromoteLoading(false)
      }
    }
    loadPromoteNewbie()
    return () => {
      active = false
    }
  }, [promoteNewbieId])

  async function handlePresetClick(preset) {
    setError('')
    if (!promoteNewbieId) {
      navigate('/newbies')
      return
    }
    setHiringPresetId(preset.preset_id)
    try {
      const res = await apiFetch(`/api/newbies/${encodeURIComponent(promoteNewbieId)}/hire`, {
        method: 'POST',
        body: JSON.stringify({
          role: preset.role || undefined,
          system_prompt: preset.system_prompt || undefined,
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const detail = data?.detail
        const msg = typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((x) => x?.msg || x).join(', ')
            : `Aannemen mislukt (${res.status})`
        throw new Error(msg)
      }
      if (!data?.agent_id) throw new Error('Aannemen gelukt maar geen agent_id in response')
      navigate(`/agents/${encodeURIComponent(data.agent_id)}`)
    } catch (err) {
      setError(err.message || 'Aannemen mislukt')
    } finally {
      setHiringPresetId(null)
    }
  }

  return (
    <PageLayout size="medium" padded>
      <div className="panel-card">
        <h1 className="page-title flex items-center gap-2">
          <UserPlus className="w-6 h-6" />
          Hiring Hall
        </h1>
        <p className="text-slate-600 mt-2">
          Kies een preset om een ready newbie direct aan te nemen.
        </p>

        {promoteNewbieId && (
          <div className="mt-4 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-800">
            {promoteLoading
              ? 'Promote newbie laden...'
              : `Je neemt ${promoteNewbieName || promoteNewbieId} aan. Kies een preset om mee te starten.`}
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mt-5">
          <h2 className="text-sm font-semibold text-slate-800 mb-3">Beschikbare presets</h2>
          {presetsLoading ? (
            <div className="inline-flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              Presets laden...
            </div>
          ) : presets.length === 0 ? (
            <p className="text-sm text-slate-500">Geen presets gevonden.</p>
          ) : (
            <div className="flex flex-wrap gap-3">
              {presets.map((preset) => {
                const isHiring = hiringPresetId === preset.preset_id
                return (
                  <button
                    key={preset.preset_id}
                    type="button"
                    onClick={() => handlePresetClick(preset)}
                    disabled={!!hiringPresetId}
                    className="rounded-lg border-2 border-slate-200 bg-white px-4 py-3 text-left min-w-[220px] transition hover:border-slate-300 disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    <span className="font-medium block text-slate-900">{preset.display_name || preset.role}</span>
                    <span className="text-xs text-slate-500 mt-0.5 block">
                      {preset.category || 'Custom'} · {(preset.description || '').slice(0, 70)}
                    </span>
                    {isHiring && (
                      <span className="mt-2 inline-flex items-center gap-1 text-xs text-indigo-700">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Aannemen...
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="mt-6 flex items-center gap-3">
          <Link
            to="/newbies"
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 font-medium"
          >
            Naar Newbies
          </Link>
          <Link
            to="/agents/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium"
          >
            Nieuwe agent
          </Link>
        </div>
      </div>
    </PageLayout>
  )
}
