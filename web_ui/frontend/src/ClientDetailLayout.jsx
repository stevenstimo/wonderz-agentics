import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate, useLocation, NavLink, Outlet } from 'react-router-dom'
import PageLayout from './PageLayout'
import { Building, ArrowLeft, BarChart3, Link2 } from 'lucide-react'
import { apiFetch } from './apiClient'

export default function ClientDetailLayout() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [client, setClient] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchClient = async () => {
      setLoading(true)
      setError('')
      try {
        const res = await apiFetch(`/api/clients/${slug}`)
        if (res.status === 401) {
          navigate('/login', { state: { from: location } })
          return
        }
        if (res.ok) {
          setClient(await res.json())
        } else {
          const j = await res.json().catch(() => ({}))
          setError(j.detail || 'Client niet gevonden')
        }
      } catch (err) {
        setError(err.message || 'Laden mislukt')
      } finally {
        setLoading(false)
      }
    }
    fetchClient()
  }, [slug, navigate, location])

  if (loading) {
    return (
      <PageLayout size="narrow" padded>
        <div className="panel-card bg-white shadow-sm border border-slate-200 p-6 rounded-xl">
          Client laden...
        </div>
      </PageLayout>
    )
  }

  if (!client) {
    return (
      <PageLayout size="narrow" padded>
        {error && (
          <div className="mb-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
            {error}
          </div>
        )}
        <Link to="/clients" className="text-indigo-600 hover:underline">
          Terug naar clients
        </Link>
      </PageLayout>
    )
  }

  const base = `/clients/${slug}`

  return (
    <PageLayout size="wide" padded>
      <Link
        to="/clients"
        className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Terug naar clients
      </Link>
      <div className="mb-6">
        <h1 className="page-title flex items-center gap-2">
          <Building className="w-8 h-8" />
          {client.client_name}
        </h1>
        <div className="mt-3 p-4 rounded-xl bg-indigo-50 border border-indigo-100">
          <p className="text-sm text-indigo-800 font-medium mb-1">@mention voor jobs</p>
          <code className="text-lg font-mono text-indigo-900 bg-white px-2 py-1 rounded border border-indigo-200">
            @{client.slug}
          </code>
          <p className="text-xs text-indigo-600 mt-2">
            Gebruik dit in job posts om de client te adresseren
          </p>
        </div>
      </div>

      <nav className="flex gap-1 border-b border-slate-200 mb-6">
        <NavLink
          to={`${base}/dashboard`}
          end
          className={({ isActive }) =>
            `px-4 py-2.5 text-sm font-medium rounded-t-lg transition ${
              isActive
                ? 'bg-white border border-slate-200 border-b-0 -mb-px text-indigo-600'
                : 'text-slate-600 hover:text-slate-800 hover:bg-slate-50'
            }`
          }
        >
          <span className="inline-flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            Dashboard
          </span>
        </NavLink>
        <NavLink
          to={`${base}/integrations`}
          className={({ isActive }) =>
            `px-4 py-2.5 text-sm font-medium rounded-t-lg transition ${
              isActive
                ? 'bg-white border border-slate-200 border-b-0 -mb-px text-indigo-600'
                : 'text-slate-600 hover:text-slate-800 hover:bg-slate-50'
            }`
          }
        >
          <span className="inline-flex items-center gap-2">
            <Link2 className="w-4 h-4" />
            Integraties
          </span>
        </NavLink>
      </nav>

      <Outlet />
    </PageLayout>
  )
}
