import { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Building, Plus } from 'lucide-react'

import { apiUrl, apiFetch } from './apiClient'
import { useAuthReady } from './useAuthReady'

export default function ClientsOverview() {
  const authReady = useAuthReady()
  const navigate = useNavigate()
  const location = useLocation()
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const fetchClients = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/clients', {
      })
      if (res.status === 401) {
        navigate('/login', { state: { from: location } })
        return
      }
      if (res.ok) {
        const data = await res.json()
        setClients(data)
      } else {
        const j = await res.json().catch(() => ({}))
        const detail = j.detail
        if (typeof detail === 'string') {
          setError(detail)
        } else if (Array.isArray(detail)) {
          setError(detail.map(d => d.msg || JSON.stringify(d)).join(', '))
        } else if (detail && typeof detail === 'object') {
          setError(JSON.stringify(detail))
        } else {
          setError('Laden mislukt')
        }
      }
    } catch (err) {
      console.error('Failed to load clients:', err)
      setError(typeof err?.message === 'string' ? err.message : 'Laden mislukt')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!authReady) return
    fetchClients()
  }, [authReady, navigate, location])

  const handleCreateVitbliss = async () => {
    setCreatingVitbliss(true)
    setError('')
    try {
      const res = await apiFetch('/api/clients', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_name: 'Vitbliss' }),
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
        const detail = j.detail
        if (typeof detail === 'string') {
          setError(detail)
        } else if (Array.isArray(detail)) {
          setError(detail.map(d => d.msg || JSON.stringify(d)).join(', '))
        } else if (detail && typeof detail === 'object') {
          setError(JSON.stringify(detail))
        } else {
          setError('Aanmaken mislukt')
        }
      }
    } catch (err) {
      console.error('Failed to create Vitbliss:', err)
      setError(typeof err?.message === 'string' ? err.message : 'Aanmaken mislukt')
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
          {typeof error === 'string' ? error : JSON.stringify(error)}
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
