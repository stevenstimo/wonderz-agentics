import { useMemo, useState } from 'react'

const apiBase = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')

const roleOptions = [
  { value: 'copywriter', label: 'Copywriter' },
  { value: 'seo', label: 'SEO Specialist' },
  { value: 'reviewer', label: 'Reviewer' },
  { value: 'hr-manager', label: 'HR Manager' },
  { value: 'custom', label: 'Custom' },
]

const toolOptions = [
  'read_product',
  'write_copy',
  'read_analytics',
  'update_description',
  'search_web',
]

export default function NewCrewMember() {
  const [form, setForm] = useState({
    agent_name: '',
    role: '',
    goal: '',
    system_prompt: '',
    tool_whitelist: [],
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const isValid = useMemo(() => {
    return (
      form.agent_name.trim() &&
      form.role.trim() &&
      form.goal.trim() &&
      form.system_prompt.trim()
    )
  }, [form])

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

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (!isValid) {
      setError('Vul alle verplichte velden in.')
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/api/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(data.detail || 'Agent aanmaken mislukt')
      }
      setSuccess(`Agent aangemaakt: ${data.agent_id}`)
      setForm({
        agent_name: '',
        role: '',
        goal: '',
        system_prompt: '',
        tool_whitelist: [],
      })
    } catch (err) {
      setError(err.message || 'Onbekende fout')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel-card max-w-3xl">
      <h1 className="page-title mb-2">Nieuwe Crew Member</h1>
      <p className="page-subtitle mb-6">Maak een nieuwe agent aan voor de Wonderz-Agentic crew.</p>

      {error && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {success && <div className="mb-4 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">{success}</div>}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Naam *</label>
          <input
            className="w-full rounded-lg border border-gray-300 px-3 py-2"
            value={form.agent_name}
            onChange={(e) => setForm({ ...form, agent_name: e.target.value })}
            placeholder="Emma - SEO Specialist"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Rol *</label>
          <select
            className="w-full rounded-lg border border-gray-300 px-3 py-2"
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
          >
            <option value="">Selecteer rol</option>
            {roleOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Doel binnen crew *</label>
          <input
            className="w-full rounded-lg border border-gray-300 px-3 py-2"
            value={form.goal}
            onChange={(e) => setForm({ ...form, goal: e.target.value })}
            placeholder="Optimaliseer content voor zoekmachines"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">System Instructions *</label>
          <textarea
            rows={8}
            className="w-full rounded-lg border border-gray-300 px-3 py-2"
            value={form.system_prompt}
            onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
            placeholder="Je bent een SEO expert..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Tool Access</label>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {toolOptions.map((tool) => (
              <label key={tool} className="flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2">
                <input
                  type="checkbox"
                  checked={form.tool_whitelist.includes(tool)}
                  onChange={() => toggleTool(tool)}
                />
                <span className="text-sm text-gray-700">{tool}</span>
              </label>
            ))}
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="btn-manage disabled:opacity-70 disabled:cursor-not-allowed"
        >
          {loading ? 'Aanmaken...' : 'Agent aanmaken'}
        </button>
      </form>
    </div>
  )
}
