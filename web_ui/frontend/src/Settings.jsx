import { useState, useEffect } from 'react'
import Sidebar from './Sidebar'
import { Save, Eye, EyeOff, AlertCircle } from 'lucide-react'

export default function Settings() {
  const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
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

  // Load settings from backend
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await fetch(`${apiBase}/api/settings`, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        })
        console.log('Settings API response:', response);
        if (response.ok) {
          const data = await response.json()
          setSettings(data)
        } else {
          setMessage({ type: 'error', text: 'Failed to load settings (status ' + response.status + ')' })
        }
      } catch (error) {
        console.error('Error fetching settings:', error)
        setMessage({ type: 'error', text: 'Failed to load settings (exception)' })
      } finally {
        setLoading(false)
      }
    }
    fetchSettings()
  }, [apiBase])

  const handleChange = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const response = await fetch(`${apiBase}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      if (response.ok) {
        setMessage({ type: 'success', text: 'Settings saved successfully!' })
        setTimeout(() => setMessage({ type: '', text: '' }), 3000)
      } else {
        setMessage({ type: 'error', text: 'Failed to save settings' })
      }
    } catch (error) {
      console.error('Error saving settings:', error)
      setMessage({ type: 'error', text: 'Error saving settings' })
    } finally {
      setSaving(false)
    }
  }

  const toggleShowKey = (field) => {
    setShowKeys(prev => ({ ...prev, [field]: !prev[field] }))
  }

  if (loading) {
    return (
      <div className="dashboard-container">
        <Sidebar />
        <main className="content-area">
          <div className="flex items-center justify-center h-screen">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
              <p>Loading settings...</p>
            </div>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="dashboard-container">
      <Sidebar />
      <main className="content-area">
        <div className="max-w-4xl mx-auto px-4 py-8">
          <h1 className="text-3xl font-bold mb-8 text-gray-800">Settings</h1>

          {message.text && (
            <div className={`mb-6 p-4 rounded-lg flex items-start gap-3 ${
              message.type === 'success' 
                ? 'bg-green-50 border border-green-200' 
                : 'bg-red-50 border border-red-200'
            }`}>
              <AlertCircle className={`w-5 h-5 mt-0.5 flex-shrink-0 ${
                message.type === 'success' ? 'text-green-600' : 'text-red-600'
              }`} />
              <p className={message.type === 'success' ? 'text-green-800' : 'text-red-800'}>
                {message.text}
              </p>
            </div>
          )}

          <div className="bg-white rounded-lg shadow-lg p-8">
            <h2 className="text-2xl font-semibold mb-6 text-gray-800">API Keys & Configuration</h2>

            <div className="space-y-6">
              {/* Gemini API Key */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Gemini API Key
                </label>
                <div className="flex gap-2">
                  <input
                    type={showKeys.gemini_api_key ? 'text' : 'password'}
                    value={settings.gemini_api_key}
                    onChange={(e) => handleChange('gemini_api_key', e.target.value)}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    placeholder="Enter your Gemini API key"
                  />
                  <button
                    onClick={() => toggleShowKey('gemini_api_key')}
                    className="px-3 py-2 text-gray-600 hover:text-gray-800"
                  >
                    {showKeys.gemini_api_key ? (
                      <EyeOff className="w-5 h-5" />
                    ) : (
                      <Eye className="w-5 h-5" />
                    )}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Get your key from <a href="https://aistudio.google.com/app/apikeys" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">aistudio.google.com</a>
                </p>
              </div>

              {/* Anthropic API Key */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Anthropic API Key
                </label>
                <div className="flex gap-2">
                  <input
                    type={showKeys.anthropic_api_key ? 'text' : 'password'}
                    value={settings.anthropic_api_key}
                    onChange={(e) => handleChange('anthropic_api_key', e.target.value)}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    placeholder="Enter your Anthropic API key"
                  />
                  <button
                    onClick={() => toggleShowKey('anthropic_api_key')}
                    className="px-3 py-2 text-gray-600 hover:text-gray-800"
                  >
                    {showKeys.anthropic_api_key ? (
                      <EyeOff className="w-5 h-5" />
                    ) : (
                      <Eye className="w-5 h-5" />
                    )}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Get your key from <a href="https://console.anthropic.com" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">console.anthropic.com</a>
                </p>
              </div>

              {/* Supabase URL */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Supabase URL
                </label>
                <input
                  type="text"
                  value={settings.supabase_url}
                  onChange={(e) => handleChange('supabase_url', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="https://your-project.supabase.co"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Find your URL in <a href="https://supabase.com" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">supabase.com</a> project settings
                </p>
              </div>

              {/* Supabase Key */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Supabase API Key
                </label>
                <div className="flex gap-2">
                  <input
                    type={showKeys.supabase_key ? 'text' : 'password'}
                    value={settings.supabase_key}
                    onChange={(e) => handleChange('supabase_key', e.target.value)}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    placeholder="Enter your Supabase anon key"
                  />
                  <button
                    onClick={() => toggleShowKey('supabase_key')}
                    className="px-3 py-2 text-gray-600 hover:text-gray-800"
                  >
                    {showKeys.supabase_key ? (
                      <EyeOff className="w-5 h-5" />
                    ) : (
                      <Eye className="w-5 h-5" />
                    )}
                  </button>
                </div>
              </div>
            </div>

            <button
              onClick={handleSave}
              disabled={saving}
              className="mt-8 w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-3 px-6 rounded-lg font-semibold hover:from-indigo-700 hover:to-purple-700 transition-all shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              <Save className="w-5 h-5" />
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
