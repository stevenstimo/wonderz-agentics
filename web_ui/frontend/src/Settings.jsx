import { useState, useEffect } from 'react'
import PageLayout from './PageLayout'
import { Save, Eye, EyeOff, AlertCircle, Pencil, Check } from 'lucide-react'
import { apiFetch } from './apiClient'
import { useAuthReady } from './useAuthReady'


const apiBase = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')

export default function Settings() {
  const authReady = useAuthReady()
  const [settings, setSettings] = useState({
    gemini_api_key: '',
    anthropic_api_key: '',
    supabase_url: '',
    supabase_key: '',
  })
  const [showKeys, setShowKeys] = useState({
    gemini_api_key: false,
    anthropic_api_key: false,
    supabase_url: false,
    supabase_key: false,
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })

  useEffect(() => {
    if (!authReady) return
    const fetchSettings = async () => {
      setLoading(true)
      try {
        const response = await apiFetch('/api/settings')

        if (response.ok) {
          const data = await response.json()
          setSettings((prev) => ({ ...prev, ...data }))
        } else if (response.status === 401 || response.status === 403) {
          setMessage({ type: 'error', text: 'Geen toegang. Alleen super admin kan settings bekijken.' })
        } else {
          setMessage({ type: 'error', text: `Failed to load settings (status ${response.status})` })
        }
      } catch (error) {
        setMessage({ type: 'error', text: 'Failed to load settings (network error)' })
      } finally {
        setLoading(false)
      }
    }

    fetchSettings()
  }, [authReady])

  const handleChange = (field, value) => {
    setSettings((prev) => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    setMessage({ type: '', text: '' })

    try {
      const response = await apiFetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })

      if (response.ok) {
        setMessage({ type: 'success', text: 'Settings saved successfully.' })
      } else if (response.status === 401 || response.status === 403) {
        setMessage({ type: 'error', text: 'Geen toegang. Alleen super admin kan settings opslaan.' })
      } else {
        setMessage({ type: 'error', text: 'Failed to save settings' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Error saving settings' })
    } finally {
      setSaving(false)
    }
  }

  const toggleShowKey = (field) => {
    setShowKeys((prev) => ({ ...prev, [field]: !prev[field] }))
  }

  if (loading) {
    return (
      <PageLayout>
        <div className="flex items-center justify-center h-screen">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4" />
            <p>Loading settings...</p>
          </div>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout size="narrow" padded>
      <h1 className="text-3xl font-bold mb-8 text-gray-800">Settings</h1>

      {message.text && (
        <div className={`mb-6 p-4 rounded-lg flex items-start gap-3 ${message.type === 'success' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
          <AlertCircle className={`w-5 h-5 mt-0.5 flex-shrink-0 ${message.type === 'success' ? 'text-green-600' : 'text-red-600'}`} />
          <p className={message.type === 'success' ? 'text-green-800' : 'text-red-800'}>{message.text}</p>
        </div>
      )}



      {/* Server Configuratie — env vars */}
      <ServerConfigSection />
    </PageLayout>
  )
}

function ServerConfigSection() {
  const authReady = useAuthReady()
  const [envVars, setEnvVars] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingKey, setEditingKey] = useState(null)
  const [editValue, setEditValue] = useState('')
  const [savingKey, setSavingKey] = useState(null)
  const [savedKey, setSavedKey] = useState(null)

  const fetchEnvVars = async () => {
    setLoading(true)
    try {
      const res = await apiFetch('/api/settings/env-vars')
      if (res.ok) {
        const data = await res.json()
        setEnvVars(data)
      } else {
        setEnvVars([])
      }
    } catch {
      setEnvVars([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!authReady) return
    fetchEnvVars()
  }, [authReady])

  const handleEdit = (item) => {
    setEditingKey(item.key)
    setEditValue('')
  }

  const handleSave = async () => {
    if (!editingKey || !editValue.trim()) return
    setSavingKey(editingKey)
    try {
      const res = await apiFetch('/api/settings/env-vars', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: editingKey, value: editValue.trim() }),
      })
      if (res.ok) {
        const data = await res.json()
        setEnvVars((prev) =>
          prev.map((v) =>
            v.key === editingKey
              ? { ...v, configured: true, preview: data.preview }
              : v
          )
        )
        setEditingKey(null)
        setEditValue('')
        setSavedKey(editingKey)
        setTimeout(() => setSavedKey(null), 2000)
        fetchEnvVars()
      }
    } catch {
      setSavedKey(null)
    } finally {
      setSavingKey(null)
    }
  }

  const handleCancel = () => {
    setEditingKey(null)
    setEditValue('')
  }

  if (loading) {
    return (
      <div className="mt-8 bg-white rounded-lg shadow-lg p-8">
        <h2 className="text-2xl font-semibold mb-6 text-gray-800">Server Configuratie</h2>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
        </div>
      </div>
    )
  }

  return (
    <div className="mt-8 bg-white rounded-lg shadow-lg p-8">
      <h2 className="text-2xl font-semibold mb-6 text-gray-800">Server Configuratie</h2>
      <p className="text-sm text-gray-600 mb-8">
        Beheer environment variabelen op de server. Waarden worden opgeslagen in systemd en de service wordt herstart.
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="pb-3 pr-4 font-medium text-gray-700">Label</th>
              <th className="pb-3 pr-4 font-medium text-gray-700">Beschrijving</th>
              <th className="pb-3 pr-4 font-medium text-gray-700">Status</th>
              <th className="pb-3 pr-4 font-medium text-gray-700">Preview</th>
              <th className="pb-3 font-medium text-gray-700 w-24">Acties</th>
            </tr>
          </thead>
          <tbody>
            {envVars.map((item) => (
              <tr
                key={item.key}
                className={`border-b border-gray-100 py-6 ${
                  item.required && !item.configured ? 'bg-red-50' : ''
                }`}
              >
                <td className="py-3 pr-4 font-medium text-gray-800">
                  {item.label}
                </td>
                <td className="py-3 pr-4 text-sm text-gray-600">
                  {item.description || item.label || '—'}
                </td>
                <td className="py-3 pr-4">
                  {item.configured ? (
                    <span className="text-green-600 font-medium">✅ Geconfigureerd</span>
                  ) : (
                    <span className="text-amber-600 font-medium">⚠️ Ontbreekt</span>
                  )}
                </td>
                <td className="py-3 pr-4 font-mono text-sm text-gray-500">
                  {item.preview ?? '—'}
                </td>
                <td className="py-3">
                  {editingKey === item.key ? (
                    <div className="flex flex-col gap-2">
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        placeholder="Nieuwe waarde..."
                        className="px-3 py-1.5 border border-gray-300 rounded text-sm"
                        autoComplete="off"
                        autoFocus
                      />
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={handleSave}
                          disabled={savingKey === item.key || !editValue.trim()}
                          className="px-2 py-1 bg-indigo-600 text-white rounded text-xs font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1"
                        >
                          <Check className="w-3 h-3" />
                          {savingKey === item.key ? 'Opslaan...' : 'Opslaan'}
                        </button>
                        <button
                          type="button"
                          onClick={handleCancel}
                          className="px-2 py-1 border border-gray-300 rounded text-xs hover:bg-gray-50"
                        >
                          Annuleren
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleEdit(item)}
                        className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded"
                        title="Bewerken"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      {savedKey === item.key && (
                        <span className="text-green-600 text-sm font-medium">Opgeslagen</span>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
