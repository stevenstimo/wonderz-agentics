import { apiBase } from './apiBase'
import { useState, useEffect } from 'react'
import PageLayout from './PageLayout'
import { Save, Eye, EyeOff, AlertCircle } from 'lucide-react'
import { buildAuthHeaders, getAccessToken } from './authz'


export default function Settings() {
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
    const fetchSettings = async () => {
      setLoading(true)
      try {
        const response = await fetch(`${apiBase}/api/settings`, {
          method: 'GET',
          headers: await buildAuthHeaders(),
        })

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
  }, [])

  const handleChange = (field, value) => {
    setSettings((prev) => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    setMessage({ type: '', text: '' })

    try {
      const response = await fetch(`${apiBase}/api/settings`, {
        method: 'POST',
        headers: await buildAuthHeaders(),
        body: JSON.stringify(settings),
      })

      if (response.ok) {
        setMessage({ type: 'success', text: 'Settings saved successfully.' })
      } else {
        const detail = await response.json().catch(() => ({}))
        const msg = detail?.detail || (response.status === 401 ? 'Niet ingelogd — log opnieuw in.' : response.status === 403 ? 'Geen toegang (alleen super admin).' : `Save failed (${response.status})`)
        setMessage({ type: 'error', text: msg })
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

      <div className="bg-white rounded-lg shadow-lg p-8">
        <h2 className="text-2xl font-semibold mb-6 text-gray-800">API Keys & Configuration</h2>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Gemini API Key</label>
            <div className="flex gap-2">
              <input
                type={showKeys.gemini_api_key ? 'text' : 'password'}
                value={settings.gemini_api_key}
                onChange={(e) => handleChange('gemini_api_key', e.target.value)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg"
                placeholder="Enter your Gemini API key"
              />
              <button type="button" onClick={() => toggleShowKey('gemini_api_key')} className="px-3 py-2 text-gray-600 hover:text-gray-800">
                {showKeys.gemini_api_key ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Anthropic API Key</label>
            <div className="flex gap-2">
              <input
                type={showKeys.anthropic_api_key ? 'text' : 'password'}
                value={settings.anthropic_api_key}
                onChange={(e) => handleChange('anthropic_api_key', e.target.value)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg"
                placeholder="Enter your Anthropic API key"
              />
              <button type="button" onClick={() => toggleShowKey('anthropic_api_key')} className="px-3 py-2 text-gray-600 hover:text-gray-800">
                {showKeys.anthropic_api_key ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Supabase URL</label>
            <input
              type="text"
              value={settings.supabase_url}
              onChange={(e) => handleChange('supabase_url', e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg"
              placeholder="https://your-project.supabase.co"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Supabase API Key</label>
            <div className="flex gap-2">
              <input
                type={showKeys.supabase_key ? 'text' : 'password'}
                value={settings.supabase_key}
                onChange={(e) => handleChange('supabase_key', e.target.value)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg"
                placeholder="Enter your Supabase anon key"
              />
              <button type="button" onClick={() => toggleShowKey('supabase_key')} className="px-3 py-2 text-gray-600 hover:text-gray-800">
                {showKeys.supabase_key ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="mt-8 w-full bg-indigo-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2"
        >
          <Save className="w-5 h-5" />
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </PageLayout>
  )
}
