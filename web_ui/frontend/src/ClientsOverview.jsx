import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Building, Plus, Zap } from 'lucide-react'
import { buildAuthHeaders } from './authz'
import { apiUrl } from './apiClient'

export default function ClientsOverview() {
  console.log('ClientsOverview mounted')
  const navigate = useNavigate()
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [creatingVitbliss, setCreatingVitbliss] = useState(false)

  const fetchClients = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(apiUrl('/api/clients'), {
        headers: await buildAuthHeaders(),
      })
      if (res.status === 401) {
        navigate('/login')
        return
      }
      if (res.ok) {
        const data = await res.json()
        setClients(data)
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || 'Laden mislukt')
      }
    } catch (err) {
      console.error('Failed to load clients:', err)
      setError(err.message || 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchClients()
  }, [navigate])

  const handleCreateVitbliss = async () => {
    setCreatingVitbliss(true)
    setError('')
    try {
      const res = await fetch(apiUrl('/api/clients'), {
        method: 'POST',
        headers: await buildAuthHeaders(),
        body: JSON.stringify({ client_name: 'Vitbliss' }),
      })
      if (res.status === 401) {
        navigate('/login')
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
      console.error('Failed to create Vitbliss:', err)
      setError(err.message || 'Aanmaken mislukt')
    } finally {
      setCreatingVitbliss(false)
    }
  }

  const hasVitbliss = clients.some((c) => c.slug === 'vitbliss')

  if (loading) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card bg-white shadow-sm border border-slate-200 p-6 rounded-xl">
          Clients laden...
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout size="narrow" padded>
      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
          {error}
        </div>
      )}
      <h1 className="page-title flex items-center gap-2">
        <Building className="w-8 h-8" />
        Clients
      </h1>
      <p className="page-subtitle mb-6">
        Beheer je clients en koppel platform-specifieke IDs per client
      </p>

      <div className="flex flex-wrap gap-3 mb-6">
        <Link
          to="/clients/new"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Nieuwe client
        </Link>
        {!hasVitbliss && (
          <button
            type="button"
            onClick={handleCreateVitbliss}
            disabled={creatingVitbliss}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Zap className="w-4 h-4" />
            {creatingVitbliss ? 'Aanmaken...' : 'Maak Vitbliss aan'}
          </button>
        )}
      </div>

      {clients.length === 0 ? (
        <div className="panel-card bg-white shadow-sm border border-slate-200 p-8 rounded-xl text-center text-slate-300">
          <Building className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>Nog geen clients. Maak een nieuwe aan of gebruik de Vitbliss-knop.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {clients.map((client) => (
            <Link
              key={client.client_id}
              to={`/clients/${client.slug}`}
              className="panel-card bg-white shadow-sm border border-slate-200 p-5 rounded-xl hover:border-indigo-300 hover:shadow-md transition-all block"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-slate-800">{client.client_name}</h3>
                <span className="text-sm text-slate-500 font-mono">@{client.slug}</span>
              </div>
              {client.description && (
                <p className="text-sm text-slate-500 mt-1 line-clamp-2">{client.description}</p>
              )}
            </Link>
          ))}
        </div>
      )}
    </PageLayout>
  )
}
