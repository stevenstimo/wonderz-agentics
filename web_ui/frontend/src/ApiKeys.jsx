import { useState, useEffect } from 'react'
import PageLayout from './PageLayout'
import { Save, Plus, Trash2, Eye, EyeOff, Key } from 'lucide-react'
import { buildAuthHeaders } from './authz'

const apiBase = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')

const INTEGRATION_TYPES = [
  { id: 'anthropic', label: 'Anthropic (Claude)', placeholder: 'sk-ant-...' },
  { id: 'openai', label: 'OpenAI (GPT)', placeholder: 'sk-...' },
  { id: 'gemini', label: 'Google Gemini', placeholder: 'AIza...' },
]

export default function ApiKeys() {
  const [integrations, setIntegrations] = useState([])
  const [editing, setEditing] = useState(null)
  const [formValues, setFormValues] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showKey, setShowKey] = useState({})

  useEffect(() => {
    const fetchIntegrations = async () => {
      setLoading(true)
      try {
        const res = await fetch(`${apiBase}/api/integrations`, {
          headers: await buildAuthHeaders(),
        })
        if (res.ok) {
          const data = await res.json()
          setIntegrations(data)
        }
      } catch (err) {
        console.error('Failed to load integrations:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchIntegrations()
  }, [])

  const handleEdit = (type) => {
    setEditing(type)
    const existing = integrations.find((i) => i.integration_type === type)
    setFormValues({ api_key: existing ? '' : '', integration_type: type })
  }

  const handleSave = async () => {
    if (!editing) return
    setSaving(true)
    try {
      const body = {}
      if (formValues.api_key) body.api_key = formValues.api_key
      const res = await fetch(`${apiBase}/api/integrations/${editing}`, {
        method: 'PUT',
        headers: await buildAuthHeaders(),
        body: JSON.stringify(body),
      })
      if (res.ok) {
        const listRes = await fetch(`${apiBase}/api/integrations`, {
          headers: await buildAuthHeaders(),
        })
        if (listRes.ok) {
          setIntegrations(await listRes.json())
        }
        setEditing(null)
      }
    } catch (err) {
      console.error('Failed to save:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (type) => {
    if (!confirm(`API key ${type} verwijderen?`)) return
    try {
      const res = await fetch(`${apiBase}/api/integrations/${type}`, {
        method: 'DELETE',
        headers: await buildAuthHeaders(),
      })
      if (res.ok) {
        setIntegrations((prev) => prev.filter((i) => i.integration_type !== type))
      }
    } catch (err) {
      console.error('Failed to delete:', err)
    }
  }

  if (loading) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card">API keys laden...</div>
      </PageLayout>
    )
  }

  return (
    <PageLayout size="narrow" padded>
      <h1 className="page-title flex items-center gap-2">
        <Key className="w-8 h-8" />
        API Keys
      </h1>
      <p className="page-subtitle mb-8">
        Beheer je AI provider API-sleutels. Deze worden per gebruiker opgeslagen.
      </p>

      <div className="space-y-4">
        {INTEGRATION_TYPES.map(({ id, label, placeholder }) => {
          const existing = integrations.find((i) => i.integration_type === id)
          const isEditing = editing === id

          return (
            <div key={id} className="panel-card">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h3 className="font-semibold text-slate-800">{label}</h3>
                  {existing && !isEditing && (
                    <p className="text-sm text-slate-500 mt-1">
                      Sleutel: {existing.api_key_masked || 'niet ingesteld'}
                    </p>
                  )}
                </div>
                {!isEditing ? (
                  <div className="flex gap-2 flex-shrink-0">
                    <button
                      type="button"
                      onClick={() => handleEdit(id)}
                      className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 flex items-center gap-2"
                    >
                      <Plus className="w-4 h-4" />
                      {existing ? 'Wijzigen' : 'Toevoegen'}
                    </button>
                    {existing && (
                      <button
                        type="button"
                        onClick={() => handleDelete(id)}
                        className="px-4 py-2 rounded-lg border border-red-300 text-red-700 hover:bg-red-50 flex items-center gap-2"
                      >
                        <Trash2 className="w-4 h-4" />
                        Verwijderen
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
                    <div className="flex gap-2 flex-1">
                      <input
                        type={showKey[id] ? 'text' : 'password'}
                        value={formValues.api_key || ''}
                        onChange={(e) =>
                          setFormValues((prev) => ({ ...prev, api_key: e.target.value }))
                        }
                        placeholder={placeholder}
                        className="px-4 py-2 border rounded-lg flex-1 min-w-0"
                      />
                      <button
                        type="button"
                        onClick={() => setShowKey((prev) => ({ ...prev, [id]: !prev[id] }))}
                        className="p-2 text-slate-500 hover:text-slate-700 flex-shrink-0"
                      >
                        {showKey[id] ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={handleSave}
                        disabled={saving}
                        className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 flex items-center gap-2 disabled:opacity-50"
                      >
                        <Save className="w-4 h-4" />
                        Opslaan
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditing(null)}
                        className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
                      >
                        Annuleren
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </PageLayout>
  )
}
