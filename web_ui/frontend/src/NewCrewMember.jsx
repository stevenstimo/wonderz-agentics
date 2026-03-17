import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from './PageLayout'
import { apiUrl, apiFetch } from './apiClient'

import { VALID_TOOLS, VALID_CATEGORIES } from './agentConstants'

const ROLE_OPTIONS = [
  'copywriter', 'seo', 'hr-manager', 'support',
  'frontend-engineer', 'backend-engineer', 'custom',
]

const initialForm = {
  agent_name: '',
  role: '',
  category: 'Custom',
  goal: '',
  system_prompt: '',
  tool_whitelist: [],
}

/** Live preview: agent:<role> met role genormaliseerd (lowercase, spaties → streepjes). */
function agentIdPreview(role) {
  if (!role || !role.trim()) return 'agent:—'
  const normalized = role.trim().toLowerCase().replace(/\s+/g, '-')
  return `agent:${normalized}`
}

export default function NewCrewMember() {
  const navigate = useNavigate()
  const [presets, setPresets] = useState([])
  const [presetsLoading, setPresetsLoading] = useState(true)
  const [selectedPresetId, setSelectedPresetId] = useState(null)
  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})

  const isValid = useMemo(() => {
    return (
      form.agent_name.trim().length >= 2 &&
      form.role.trim() &&
      form.goal.trim().length >= 10 &&
      form.system_prompt.trim().length >= 20
    )
  }, [form])

  useEffect(() => {
    async function loadPresets() {
      setPresetsLoading(true)
      try {
        const res = await apiFetch('/api/agents/presets', {
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(data?.detail || 'Presets laden mislukt')
        setPresets(data.presets || [])
      } catch (err) {
        setPresets([])
      } finally {
        setPresetsLoading(false)
      }
    }
    loadPresets()
  }, [])

  function applyPreset(preset) {
    if (!preset) {
      setSelectedPresetId(null)
      setForm(initialForm)
      return
    }
    setSelectedPresetId(preset.preset_id)
    // suggested_tools → tool_whitelist (backend verwacht tool_whitelist in POST body)
    const tools = Array.isArray(preset.suggested_tools) ? [...preset.suggested_tools] : []
    setForm({
      agent_name: preset.display_name?.split(' — ')[0]?.trim() || preset.display_name || '',
      role: preset.role || '',
      category: preset.category || 'Custom',
      goal: preset.goal || '',
      system_prompt: preset.system_prompt || '',
      tool_whitelist: tools,
    })
  }

  function toggleTool(tool) {
    setForm((prev) => {
      const exists = prev.tool_whitelist.includes(tool)
      return {
        ...prev,
        tool_whitelist: exists
          ? prev.tool_whitelist.filter((t) => t !== tool)
          : [...prev.tool_whitelist, tool],
      }
    })
  }

  function validate() {
    const e = {}
    const name = form.agent_name?.trim() || ''
    if (!name) e.agent_name = ['Naam is verplicht']
    else if (name.length < 2) e.agent_name = ['Minimaal 2 tekens']
    if (!form.role?.trim()) e.role = ['Rol is verplicht']
    const goal = form.goal?.trim() || ''
    if (!goal) e.goal = ['Doel is verplicht']
    else if (goal.length < 10) e.goal = ['Minimaal 10 tekens']
    const sys = form.system_prompt?.trim() || ''
    if (!sys) e.system_prompt = ['System Instructions zijn verplicht']
    else if (sys.length < 20) e.system_prompt = ['Minimaal 20 tekens']
    setFieldErrors(e)
    return Object.keys(e).length === 0
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setFieldErrors({})
    if (!validate()) {
      setError('Vul alle verplichte velden in.')
      return
    }

    setLoading(true)
    try {
      const body = {
        agent_name: form.agent_name.trim(),
        role: form.role.trim(),
        category: form.category,
        goal: form.goal.trim(),
        system_prompt: form.system_prompt.trim(),
        tool_whitelist: form.tool_whitelist,
      }
      const res = await apiFetch('/api/agents', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      const data = await res.json().catch(() => ({}))

      if (!res.ok) {
        if (res.status === 422 && data.detail) {
          if (Array.isArray(data.detail)) {
            const byField = {}
            for (const item of data.detail) {
              const loc = item.loc
              const field = Array.isArray(loc) ? loc[loc.length - 1] : 'body'
              const key = field === 'agent_name' ? 'agent_name' : field === 'tool_whitelist' ? 'tool_whitelist' : field
              if (!byField[key]) byField[key] = []
              byField[key].push(item.msg || item.type)
            }
            setFieldErrors(byField)
            setError('Controleer de velden hieronder.')
          } else {
            setError(typeof data.detail === 'string' ? data.detail : 'Validatiefout.')
          }
        } else {
          setError(data?.detail || `Agent aanmaken mislukt (${res.status})`)
        }
        return
      }

      const agentId = data.agent_id || data.agentId
      if (agentId) {
        navigate(`/agents/${encodeURIComponent(agentId)}`)
      } else {
        setError('Agent aangemaakt maar redirect niet mogelijk (geen agent_id in response).')
      }
    } catch (err) {
      setError(err.message || 'Onbekende fout')
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageLayout>
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden max-w-3xl">
        <div className="p-6 border-b border-slate-200">
          <h1 className="text-2xl font-bold text-slate-900">Nieuwe agent</h1>
          <p className="text-slate-600 mt-0.5">Maak een nieuwe agent aan, optioneel vanuit een preset.</p>
        </div>

        {/* Stap 1 — Preset selectie */}
        <div className="p-6 border-b border-slate-200 bg-slate-50/50">
          <h2 className="text-sm font-semibold text-slate-800 mb-3">Preset (optioneel)</h2>
          {presetsLoading ? (
            <p className="text-sm text-slate-500">Presets laden...</p>
          ) : (
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => applyPreset(null)}
                className={`rounded-lg border-2 px-4 py-3 text-left transition ${
                  !selectedPresetId
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-800'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                <span className="font-medium">Leeg beginnen</span>
              </button>
              {presets.map((p) => (
                <button
                  key={p.preset_id}
                  type="button"
                  onClick={() => applyPreset(p)}
                  className={`rounded-lg border-2 px-4 py-3 text-left min-w-[200px] transition ${
                    selectedPresetId === p.preset_id
                      ? 'border-indigo-600 bg-indigo-50 text-indigo-800'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                  }`}
                >
                  <span className="font-medium block">{p.display_name}</span>
                  <span className="text-xs text-slate-500 mt-0.5 block">{p.category} · {p.description?.slice(0, 50)}…</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Stap 2 — Formulier */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {error && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 border border-red-100">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Naam *</label>
            <input
              className={`w-full rounded-lg border px-3 py-2 ${fieldErrors.agent_name ? 'border-red-500' : 'border-slate-300'}`}
              value={form.agent_name}
              onChange={(e) => setForm({ ...form, agent_name: e.target.value })}
              placeholder="Emma"
            />
            {fieldErrors.agent_name && (
              <span className="field-error mt-1 text-xs text-red-600 block">
                {Array.isArray(fieldErrors.agent_name) ? fieldErrors.agent_name.join(', ') : fieldErrors.agent_name}
              </span>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Rol *</label>
            <select
              className={`w-full rounded-lg border px-3 py-2 ${fieldErrors.role ? 'border-red-500' : 'border-slate-300'}`}
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              <option value="">— Selecteer rol —</option>
              {ROLE_OPTIONS.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <p className="mt-1 text-xs font-mono text-slate-500" aria-live="polite">
              Preview: {agentIdPreview(form.role)}
            </p>
            {fieldErrors.role && (
              <span className="field-error mt-1 text-xs text-red-600 block">
                {Array.isArray(fieldErrors.role) ? fieldErrors.role.join(', ') : fieldErrors.role}
              </span>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Categorie *</label>
            <select
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            >
              {VALID_CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Doel binnen crew *</label>
            <input
              className={`w-full rounded-lg border px-3 py-2 ${fieldErrors.goal ? 'border-red-500' : 'border-slate-300'}`}
              value={form.goal}
              onChange={(e) => setForm({ ...form, goal: e.target.value })}
              placeholder="Content optimaliseren voor zoekmachines"
            />
            {fieldErrors.goal && (
              <span className="field-error mt-1 text-xs text-red-600 block">
                {Array.isArray(fieldErrors.goal) ? fieldErrors.goal.join(', ') : fieldErrors.goal}
              </span>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">System Instructions *</label>
            <textarea
              rows={8}
              className={`w-full rounded-lg border px-3 py-2 font-mono text-sm ${fieldErrors.system_prompt ? 'border-red-500' : 'border-slate-300'}`}
              value={form.system_prompt}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
              placeholder="Je bent een SEO expert..."
            />
            {fieldErrors.system_prompt && (
              <span className="field-error mt-1 text-xs text-red-600 block">
                {Array.isArray(fieldErrors.system_prompt) ? fieldErrors.system_prompt.join(', ') : fieldErrors.system_prompt}
              </span>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Tool Access</label>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {VALID_TOOLS.map((tool) => (
                <label key={tool} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50">
                  <input
                    type="checkbox"
                    checked={form.tool_whitelist.includes(tool)}
                    onChange={() => toggleTool(tool)}
                  />
                  <span className="text-sm text-slate-700">{tool}</span>
                </label>
              ))}
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !isValid}
            className="rounded-lg px-4 py-2.5 bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-70 disabled:cursor-not-allowed transition"
          >
            {loading ? 'Aanmaken...' : 'Agent aanmaken'}
          </button>
        </form>
      </div>
    </PageLayout>
  )
}
