import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageLayout from './PageLayout'
import {
  Layers, ClipboardList, Users, Code, PlusCircle,
  Activity, Briefcase, ArrowRight, Zap, CheckCircle2,
  AlertTriangle, RefreshCw, Server, Database, Cpu, Globe, Bot,
  Terminal, Sparkles
} from 'lucide-react'

const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8090'

function ServiceCard({ label, ok, detail, icon: Icon }) {
  return (
    <div className={`flex items-center gap-3 p-4 rounded-lg border ${
      ok === null ? 'border-gray-200 bg-gray-50' :
      ok ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
    }`}>
      <div className={`p-2 rounded-lg ${
        ok === null ? 'bg-gray-100' : ok ? 'bg-green-100' : 'bg-red-100'
      }`}>
        <Icon className={`w-5 h-5 ${
          ok === null ? 'text-gray-400' : ok ? 'text-green-600' : 'text-red-600'
        }`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-gray-800 text-sm">{label}</div>
        <div className="text-xs text-gray-500 truncate">{detail || 'Checking...'}</div>
      </div>
      <div>
        {ok === null ? (
          <RefreshCw className="w-4 h-4 text-gray-300 animate-spin" />
        ) : ok ? (
          <CheckCircle2 className="w-5 h-5 text-green-500" />
        ) : (
          <AlertTriangle className="w-5 h-5 text-red-500" />
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [recentJobs, setRecentJobs] = useState([])
  const [stats, setStats] = useState({ total: 0, running: 0, ready: 0 })
  const [services, setServices] = useState(null)
  const [systemd, setSystemd] = useState(null)
  const [settings, setSettings] = useState(null)
  const [commits, setCommits] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusLoading, setStatusLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)

  const fetchJobs = async () => {
    try {
      const res = await fetch(`${apiBase}/api/jobs`)
      if (res.ok) {
        const data = await res.json()
        const jobs = Array.isArray(data) ? data : data.jobs || []
        setRecentJobs(jobs.slice(0, 5))
        setStats({
          total: jobs.length,
          running: jobs.filter(j => ['RUNNING','INTAKE_CLARIFICATION','PLAN_PROPOSED'].includes(j.status)).length,
          ready: jobs.filter(j => ['JOB_READY','COMPLETED'].includes(j.status)).length,
        })
      }
    } catch (e) {
      console.error('Failed to fetch jobs:', e)
    } finally {
      setLoading(false)
    }
  }

  const fetchStatus = async () => {
    setStatusLoading(true)
    try {
      const res = await fetch(`${apiBase}/api/status/summary`)
      if (res.ok) {
        const data = await res.json()
        setServices(data.health?.checks || {})
        setSystemd(data.systemd || {})
        setSettings(data.settings || {})
        setCommits(data.recent?.recent_commits || [])
      }
    } catch (e) {
      console.error('Failed to fetch status:', e)
    } finally {
      setStatusLoading(false)
      setLastRefresh(new Date())
    }
  }

  useEffect(() => {
    fetchJobs()
    fetchStatus()
    const timer = setInterval(fetchStatus, 30000)
    return () => clearInterval(timer)
  }, [])

  const statusColor = (status) => {
    const colors = {
      JOB_READY: 'bg-green-100 text-green-700',
      COMPLETED: 'bg-green-100 text-green-700',
      RUNNING: 'bg-blue-100 text-blue-700',
      INTAKE_CLARIFICATION: 'bg-yellow-100 text-yellow-700',
      PLAN_PROPOSED: 'bg-purple-100 text-purple-700',
      FAILED: 'bg-red-100 text-red-700',
    }
    return colors[status] || 'bg-gray-100 text-gray-700'
  }

  const allHealthy = services && Object.values(services).every(s => s.ok)

  return (
    <PageLayout size="wide" padded>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">Wonderz Agentics — Platform Overview</p>
        </div>
        <div className="flex items-center gap-3">
          {allHealthy !== null && (
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${
              allHealthy ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
            }`}>
              {allHealthy ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
              {allHealthy ? 'All Systems Online' : 'Degraded'}
            </span>
          )}
          <button
            onClick={() => { fetchStatus(); fetchJobs() }}
            className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 text-gray-500 ${statusLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Service Health */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Server className="w-5 h-5 text-indigo-600" /> Services
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <ServiceCard
            label="Backend API"
            icon={Server}
            ok={services?.backend?.ok ?? null}
            detail={services?.backend?.detail || 'Port 8090'}
          />
          <ServiceCard
            label="Frontend"
            icon={Globe}
            ok={services?.frontend?.ok ?? null}
            detail={services?.frontend?.detail || 'Port 3000'}
          />
          <ServiceCard
            label="PostgreSQL"
            icon={Database}
            ok={services?.database?.ok ?? null}
            detail={services?.database?.detail || 'Port 5432'}
          />
          <ServiceCard
            label="Redis"
            icon={Database}
            ok={services?.redis?.ok ?? null}
            detail={services?.redis?.detail || 'Port 6379'}
          />
          <ServiceCard
            label="Celery Worker"
            icon={Cpu}
            ok={services?.celery_worker?.ok ?? null}
            detail={services?.celery_worker?.detail || 'Task queue'}
          />
          <ServiceCard
            label="Terminal (ttyd)"
            icon={Terminal}
            ok={services?.terminal?.ok ?? null}
            detail={services?.terminal?.detail || 'Port 7681'}
          />
          <ServiceCard
            label="Codex Console"
            icon={Sparkles}
            ok={services?.codex_web?.ok ?? null}
            detail={services?.codex_web?.detail || 'Port 7682'}
          />
          <ServiceCard
            label="LLM Providers"
            icon={Bot}
            ok={settings?.ok ?? null}
            detail={settings?.active_providers?.length > 0
              ? `Active: ${settings.active_providers.join(', ')}`
              : 'No API keys configured'}
          />
        </div>
        {lastRefresh && (
          <p className="text-xs text-gray-400 mt-2">Last updated: {lastRefresh.toLocaleTimeString()}</p>
        )}
      </div>

      {/* Systemd Services */}
      {systemd && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-indigo-600" /> Systemd Services
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(systemd).map(([name, info]) => (
              <div key={name} className={`flex items-center gap-2 p-3 rounded-lg border text-sm ${
                info.active ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
              }`}>
                <div className={`w-2 h-2 rounded-full ${info.active ? 'bg-green-500' : 'bg-red-500'}`} />
                <div>
                  <div className="font-medium text-gray-700">{name.replace('wonderz-', '')}</div>
                  <div className="text-xs text-gray-500">{info.state}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stats + Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <Briefcase className="w-5 h-5 text-indigo-600" />
            <span className="text-sm font-medium text-indigo-600">Total Missions</span>
          </div>
          <p className="text-3xl font-bold text-indigo-900">{stats.total}</p>
        </div>
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-5 h-5 text-blue-600" />
            <span className="text-sm font-medium text-blue-600">In Progress</span>
          </div>
          <p className="text-3xl font-bold text-blue-900">{stats.running}</p>
        </div>
        <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <Zap className="w-5 h-5 text-green-600" />
            <span className="text-sm font-medium text-green-600">Completed</span>
          </div>
          <p className="text-3xl font-bold text-green-900">{stats.ready}</p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <Link
          to="/jobs/new"
          className="flex items-center gap-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl p-6 shadow-lg hover:shadow-xl transition-all hover:scale-[1.01]"
        >
          <PlusCircle className="w-8 h-8" />
          <div>
            <h3 className="text-lg font-semibold">New Mission</h3>
            <p className="text-indigo-100 text-sm">Start a new AI-powered job</p>
          </div>
          <ArrowRight className="w-5 h-5 ml-auto" />
        </Link>
        <Link
          to="/job-center"
          className="flex items-center gap-4 bg-white border-2 border-indigo-200 text-indigo-700 rounded-xl p-6 shadow-sm hover:shadow-md transition-all hover:scale-[1.01]"
        >
          <ClipboardList className="w-8 h-8" />
          <div>
            <h3 className="text-lg font-semibold">Job Center</h3>
            <p className="text-gray-500 text-sm">View all missions and crew status</p>
          </div>
          <ArrowRight className="w-5 h-5 ml-auto" />
        </Link>
      </div>

      {/* Dev Tools */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <a
          href={`${window.location.protocol}//${window.location.hostname}:7681`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-4 bg-gray-900 text-white rounded-xl p-6 shadow-lg hover:shadow-xl transition-all hover:scale-[1.01]"
        >
          <Terminal className="w-8 h-8 text-green-400" />
          <div>
            <h3 className="text-lg font-semibold">Terminal</h3>
            <p className="text-gray-400 text-sm">Full shell access to the VM</p>
          </div>
          <ArrowRight className="w-5 h-5 ml-auto text-gray-500" />
        </a>
        <a
          href={`${window.location.protocol}//${window.location.hostname}:8080`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-4 bg-gray-900 text-white rounded-xl p-6 shadow-lg hover:shadow-xl transition-all hover:scale-[1.01]"
        >
          <Sparkles className="w-8 h-8 text-yellow-400" />
          <div>
            <h3 className="text-lg font-semibold">Codex Console</h3>
            <p className="text-gray-400 text-sm">AI coding assistant — give prompts to Codex</p>
          </div>
          <ArrowRight className="w-5 h-5 ml-auto text-gray-500" />
        </a>
      </div>

      {/* Recent Missions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="panel-card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-gray-800">Recent Missions</h2>
            <Link to="/job-center" className="text-indigo-600 hover:underline text-sm">View all →</Link>
          </div>
          {loading ? (
            <p className="text-gray-400 text-center py-8">Loading...</p>
          ) : recentJobs.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-400 mb-4">No missions yet</p>
              <Link to="/jobs/new" className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
                <PlusCircle className="w-4 h-4" /> Start your first mission
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {recentJobs.map((job) => (
                <Link
                  key={job.id}
                  to={`/jobs/new?job_id=${job.id}`}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-gray-800 text-sm truncate">
                      {job.context?.brief?.project_description ||
                       job.context?.brief?.raw_idea ||
                       job.job_type || 'Untitled'}
                    </p>
                    <p className="text-xs text-gray-400">
                      {new Date(job.created_at).toLocaleDateString('nl-NL', {
                        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
                      })}
                    </p>
                  </div>
                  <span className={`ml-2 px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${statusColor(job.status)}`}>
                    {job.status}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent Commits */}
        <div className="panel-card">
          <h2 className="text-lg font-bold text-gray-800 mb-4">Recent Commits</h2>
          {commits.length === 0 ? (
            <p className="text-gray-400 text-center py-8">No commit data</p>
          ) : (
            <div className="space-y-2">
              {commits.map((c, i) => (
                <div key={i} className="text-sm text-gray-600 font-mono bg-gray-50 p-2 rounded">
                  {c}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </PageLayout>
  )
}
