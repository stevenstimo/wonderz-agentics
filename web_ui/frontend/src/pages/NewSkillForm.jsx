import { useEffect, useMemo, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../PageLayout'
import { apiFetch } from '../apiClient'
import { useAuthReady } from '../useAuthReady'

const VALID_NAME_RE = /^[a-z0-9_]+$/

const KNOWN_TOOLS = [
  'knowledge_retrieval',
  'search_internal_docs',
  'read_lessons',
  'write_copy',
  'write_report',
  'write_feedback',
  'read_brief',
  'read_product',
  'read_analytics',
  'read_artifact',
  'validate_output',
  'check_evidence',
  'score_confidence',
  'approve_artifact',
  'web_search',
  'search_web',
  'read_url',
  'submit_artifact',
  'flag_escalation',
  'create_development_point',
  'read_logs',
  'read_metrics',
  'execute_query',
]

function normalizeSkillName(input) {
  return (input || '')
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_]/g, '_')
    .replace(/^_+/, '')
    .replace(/_+$/, '')
}

function validateSkillName(name) {
  const v = (name || '').trim()
  if (!v) return 'Naam is verplicht'
  if (!VALID_NAME_RE.test(v)) return 'Gebruik alleen lowercase letters, cijfers en underscores'
  if (v.startsWith('_') || v.endsWith('_')) return 'Naam mag niet starten of eindigen met underscore'
  return null
}

function formatError(error) {
  if (!error) return ''
  if (typeof error === 'string') return error
  return error.detail || error.message || 'Onbekende fout'
}

export default function NewSkillForm() {
  const { authReady } = useAuthReady()
  const navigate = useNavigate()

  const [form, setForm] = useState(() => ({
    name: '',
    display_name: '',
    description: '',
    trigger_condition: '',
    requires_tools: [],
    requires_skills: [],
    agent_ids: [],
    status: 'active',
  }))

  const [fieldErrors, setFieldErrors] = useState({})
  const [errorBanner, setErrorBanner] = useState('')
  const [loading, setLoading] = useState(false)

  const [agentOptions, setAgentOptions] = useState([])
  const [skillOptions, setSkillOptions] = useState([])

  const fetchAgents = useCallback(async () => {
    try {
      const res = await apiFetch('/api/agents')
      const data = await res.json().catch(() => ({}))
      setAgentOptions(data?.agents || [])
    } catch {
      setAgentOptions([])
    }
  }, [])

  const fetchSkillsOptions = useCallback(async () => {
    try {
      const res = await apiFetch('/api/skill-factory')
      const data = await res.json().catch(() => ({}))
      const skills = data?.skills || []
      // Autocomplete by `name` (snake_case). It's what the backend uses for linking/matching.
      setSkillOptions(skills.map((s) => s?.name).filter(Boolean))
    } catch {
      setSkillOptions([])
    }
  }, [])

  useEffect(() => {
    if (!authReady) return
    fetchAgents()
    fetchSkillsOptions()
  }, [authReady, fetchAgents, fetchSkillsOptions])

  const nameError = useMemo(() => validateSkillName(form.name), [form.name])
  const canSubmit = !nameError

  function toggleTool(tool) {
    setForm((prev) => {
      const exists = prev.requires_tools.includes(tool)
      return {
        ...prev,
        requires_tools: exists ? prev.requires_tools.filter((t) => t !== tool) : [...prev.requires_tools, tool],
      }
    })
  }

  function addRequireSkill(skill) {
    const v = (skill || '').trim()
    if (!v) return
    setForm((prev) => {
      if (prev.requires_skills.includes(v)) return prev
      return { ...prev, requires_skills: [...prev.requires_skills, v] }
    })
  }

  function removeRequireSkill(skill) {
    setForm((prev) => ({ ...prev, requires_skills: prev.requires_skills.filter((s) => s !== skill) }))
  }

  const [skillInput, setSkillInput] = useState('')
  const filteredSkillSuggestions = useMemo(() => {
    const q = (skillInput || '').trim().toLowerCase()
    if (!q) return []
    const out = skillOptions
      .filter((s) => s && s.toLowerCase().includes(q) && !form.requires_skills.includes(s))
      .slice(0, 8)
    return out
  }, [skillInput, skillOptions, form.requires_skills])

  function onSkillInputKeyDown(e) {
    if (e.key !== 'Enter' && e.key !== ',') return
    e.preventDefault()
    addRequireSkill(skillInput)
    setSkillInput('')
  }

  function toggleAgent(agentId) {
    setForm((prev) => {
      const exists = prev.agent_ids.includes(agentId)
      return {
        ...prev,
        agent_ids: exists ? prev.agent_ids.filter((id) => id !== agentId) : [...prev.agent_ids, agentId],
      }
    })
  }

  function handleCancel() {
    navigate('/knowledge/skills')
  }

  function syncDisplayNameIfEmpty() {
    setForm((prev) => {
      if (prev.display_name?.trim()) return prev
      return { ...prev, display_name: normalizeSkillName(prev.name) }
    })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setErrorBanner('')
    setFieldErrors({})

    const err = validateSkillName(form.name)
    if (err) {
      setFieldErrors({ name: err })
      return
    }

    setLoading(true)
    try {
      const payload = {
        name: normalizeSkillName(form.name),
        display_name: (form.display_name || '').trim() || undefined,
        description: (form.description || '').trim() || undefined,
        trigger_condition: (form.trigger_condition || '').trim() || undefined,
        requires_tools: form.requires_tools || [],
        requires_skills: form.requires_skills || [],
        agent_ids: form.agent_ids || [],
        status: form.status,
      }

      const res = await apiFetch('/api/skill-factory', {
        method: 'POST',
        body: JSON.stringify(payload),
      })

      const data = await res.json().catch(() => ({}))

      if (!res.ok) {
        if (res.status === 409) {
          setFieldErrors({ name: data?.detail || 'Skill bestaat al' })
          return
        }
        setErrorBanner(data?.detail || `Opslaan mislukt (${res.status})`)
        return
      }

      navigate('/knowledge/skills')
    } catch (err2) {
      setErrorBanner(formatError(err2))
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageLayout size="wide" padded>
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden max-w-3xl">
        <div className="p-6 border-b border-slate-200">
          <h1 className="text-2xl font-bold text-slate-900">Nieuwe skill</h1>
          <p className="text-slate-600 mt-0.5">Maak een nieuwe Skill Factory skill aan.</p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {errorBanner && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 border border-red-100">
              {errorBanner}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Naam *</label>
            <input
              className={`w-full rounded-lg border px-3 py-2 ${fieldErrors.name ? 'border-red-500' : 'border-slate-300'}`}
              value={form.name}
              onChange={(e) => {
                const next = e.target.value
                setForm((prev) => ({ ...prev, name: next }))
                // Keep display_name in sync only when empty.
                setTimeout(syncDisplayNameIfEmpty, 0)
              }}
              onBlur={() => {
                setForm((prev) => ({ ...prev, name: normalizeSkillName(prev.name) }))
              }}
              placeholder="write_landing_page"
              autoComplete="off"
            />
            {fieldErrors.name && <span className="field-error mt-1 text-xs text-red-600 block">{fieldErrors.name}</span>}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Weergavenaam</label>
            <input
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              value={form.display_name}
              onChange={(e) => setForm((prev) => ({ ...prev, display_name: e.target.value }))}
              placeholder="Write Landing Page"
              autoComplete="off"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Beschrijving</label>
            <textarea
              rows={4}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              value={form.description}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="Wat doet deze skill?"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Trigger-conditie</label>
            <textarea
              rows={3}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              value={form.trigger_condition}
              onChange={(e) => setForm((prev) => ({ ...prev, trigger_condition: e.target.value }))}
              placeholder="Wanneer activeert de CEO deze skill?"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Vereiste tools</label>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {KNOWN_TOOLS.map((tool) => (
                <label key={tool} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50">
                  <input
                    type="checkbox"
                    checked={form.requires_tools.includes(tool)}
                    onChange={() => toggleTool(tool)}
                  />
                  <span className="text-sm text-slate-700">{tool}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Vereiste skills</label>
            <div className="rounded-lg border border-slate-200 p-3">
              <input
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                value={skillInput}
                placeholder="Typ een skill (of selecteer suggestie), Enter om toe te voegen"
                autoComplete="off"
                list="skillOptions"
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={onSkillInputKeyDown}
              />
              <datalist id="skillOptions">
                {skillOptions.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>

              {filteredSkillSuggestions.length > 0 && (
                <div className="mt-2 space-y-1">
                  {filteredSkillSuggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className="block w-full text-left px-2 py-1 rounded-md bg-slate-50 hover:bg-slate-100 text-sm text-slate-700"
                      onClick={() => {
                        addRequireSkill(s)
                        setSkillInput('')
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}

              {form.requires_skills.length > 0 ? (
                <div className="flex flex-wrap gap-2 mt-3">
                  {form.requires_skills.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => removeRequireSkill(s)}
                      className="px-2 py-1 text-xs rounded-full bg-slate-100 text-slate-700 hover:bg-slate-200"
                      aria-label={`Verwijder skill ${s}`}
                    >
                      {s} <span className="text-slate-500">×</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="mt-3 text-sm text-slate-500">Geen vereiste skills geselecteerd.</div>
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Koppel aan agent</label>
            <div className="rounded-lg border border-slate-200 p-3 max-h-64 overflow-auto">
              {agentOptions.length === 0 ? (
                <div className="text-sm text-slate-500">Geen agents beschikbaar.</div>
              ) : (
                <div className="space-y-2">
                  {agentOptions.map((a) => {
                    const id = a.agent_id || a.role || a.name
                    return (
                      <label key={id} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={form.agent_ids.includes(id)}
                          onChange={() => toggleAgent(id)}
                        />
                        <span className="text-sm text-slate-700 truncate">
                          {a.agent_id || a.name}
                        </span>
                      </label>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Status</label>
            <select
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              value={form.status}
              onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}
            >
              <option value="active">active</option>
              <option value="draft">draft</option>
              <option value="inactive">inactive</option>
            </select>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              onClick={handleCancel}
              className="rounded-lg px-4 py-2.5 bg-slate-100 text-slate-800 font-medium hover:bg-slate-200"
              disabled={loading}
            >
              Annuleren
            </button>
            <button
              type="submit"
              disabled={loading || !canSubmit}
              className="rounded-lg px-4 py-2.5 bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-70 disabled:cursor-not-allowed transition"
            >
              {loading ? 'Aanmaken...' : 'Opslaan'}
            </button>
          </div>
        </form>
      </div>
    </PageLayout>
  )
}

