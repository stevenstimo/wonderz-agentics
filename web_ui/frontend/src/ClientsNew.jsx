import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Building, ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { buildAuthHeaders } from './authz'
import { apiUrl } from './apiClient'

function slugFromName(name) {
  const s = (name || '').trim().toLowerCase()
  return s.replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'client'
}

export default function ClientsNew() {
  const navigate = useNavigate()
  const location = useLocation()
  const [clientName, setClientName] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const slug = slugFromName(clientName)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!clientName.trim()) return
    setSaving(true)
    setError('')
    try {
      const res = await fetch(apiUrl('/api/clients'), {
        method: 'POST',
        headers: await buildAuthHeaders(),
        body: JSON.stringify({ client_name: clientName.trim() }),
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        navigate(`/clients/${data.slug}`)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Aanmaken mislukt')
      }
    } catch (err) {
      console.error('Failed to create client:', err)
      setError(err.message || 'Aanmaken mislukt')
    } finally {
      setSaving(false)
    }
  }

  return (
    <PageLayout size="narrow" padded>
      <Link
        to="/clients"
        className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Terug naar clients
      </Link>
      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
          {error}
        </div>
      )}
      <h1 className="page-title flex items-center gap-2">
        <Building className="w-8 h-8" />
        Nieuwe client
      </h1>
      <p className="page-subtitle mb-8">
        De slug wordt automatisch gegenereerd uit de clientnaam (voor @mention in jobs)
      </p>

      <form onSubmit={handleSubmit} className="panel-card bg-white shadow-sm border border-slate-200 p-6 rounded-xl max-w-md">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Client naam</label>
          <input
            type="text"
            value={clientName}
            onChange={(e) => setClientName(e.target.value)}
            placeholder="bijv. Vitbliss"
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            required
          />
        </div>
        {clientName && (
          <p className="mt-2 text-sm text-slate-500">
            Slug: <code className="bg-slate-100 px-1.5 py-0.5 rounded">@{slug}</code>
          </p>
        )}
        <p className="mt-4 flex gap-3">
          <button
            type="submit"
            disabled={saving || !clientName.trim()}
            className="px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Aanmaken...' : 'Aanmaken'}
          </button>
          <Link
            to="/clients"
            className="px-4 py-2.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
          >
            Annuleren
          </Link>
        </p>
      </form>
    </PageLayout>
  )
}
