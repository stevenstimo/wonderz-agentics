import { apiBase } from './apiBase'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageLayout from './PageLayout'
import SherlockWidget from './SherlockWidget.jsx'
import { useAuthReady } from './useAuthReady'
import {
  Layers, ClipboardList, Users, Code, PlusCircle,
  Activity, Briefcase, ArrowRight, Zap, CheckCircle2,
  AlertTriangle, RefreshCw, Server, Database, Cpu, Globe, Bot,
  Terminal, Sparkles
} from 'lucide-react'


function ServiceCard({ label, ok, detail, icon: Icon }) {
  const cardStyle = ok === null
    ? { borderColor: 'var(--color-border)', background: 'var(--color-bg-subtle)' }
    : ok
      ? { borderColor: 'var(--color-status-success)', background: 'var(--color-status-success-bg)' }
      : { borderColor: 'var(--color-status-error)', background: 'var(--color-status-error-bg)' }

  const iconWrapStyle = ok === null
    ? { background: 'var(--color-bg-input)' }
    : ok
      ? { background: 'var(--color-status-success-bg)' }
      : { background: 'var(--color-status-error-bg)' }

  const iconStyle = ok === null
    ? { color: 'var(--color-text-placeholder)' }
    : ok
      ? { color: 'var(--color-status-success)' }
      : { color: 'var(--color-status-error)' }

  const statusIconStyle = ok === null
    ? { color: 'var(--color-text-placeholder)' }
    : ok
      ? { color: 'var(--color-status-success)' }
      : { color: 'var(--color-status-error)' }

  return (
    <div
      className="flex items-center border"
      style={{
        ...cardStyle,
        gap: 'var(--space-3)',
        padding: 'var(--space-4)',
        borderRadius: 'var(--radius-md)',
      }}
    >
      <div
        className="rounded-lg"
        style={{
          ...iconWrapStyle,
          padding: 'var(--space-2)',
          borderRadius: 'var(--radius-sm)',
        }}
      >
        <Icon className="w-5 h-5" style={iconStyle} />
      </div>
      <div className="flex-1 min-w-0">
        <div
          className="font-semibold"
          style={{ color: 'var(--color-text-primary)', fontSize: 'var(--text-sm)' }}
        >
          {label}
        </div>
        <div
          className="truncate"
          style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-xs)' }}
        >
          {detail || 'Checking...'}
        </div>
      </div>
      <div>
        {ok === null ? (
          <RefreshCw className="w-4 h-4 animate-spin" style={statusIconStyle} />
        ) : ok ? (
          <CheckCircle2 className="w-5 h-5" style={statusIconStyle} />
        ) : (
          <AlertTriangle className="w-5 h-5" style={statusIconStyle} />
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { authReady } = useAuthReady()
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
    if (!authReady) return
    fetchJobs()
    fetchStatus()
    const timer = setInterval(fetchStatus, 30000)
    return () => clearInterval(timer)
  }, [authReady])

  const statusStyle = (status) => {
    const styles = {
      JOB_READY: { background: 'var(--color-status-success-bg)', color: 'var(--color-status-success)' },
      COMPLETED: { background: 'var(--color-status-success-bg)', color: 'var(--color-status-success)' },
      RUNNING: { background: 'var(--color-status-running-bg)', color: 'var(--color-status-running)' },
      INTAKE_CLARIFICATION: { background: 'var(--color-status-warning-bg)', color: 'var(--color-status-warning)' },
      PLAN_PROPOSED: { background: 'var(--color-brand-primary-light)', color: 'var(--color-brand-primary)' },
      FAILED: { background: 'var(--color-status-error-bg)', color: 'var(--color-status-error)' },
    }
    return styles[status] || { background: 'var(--color-bg-subtle)', color: 'var(--color-text-muted)' }
  }

  const allHealthy = services && Object.values(services).every(s => s.ok)

  return (
    <PageLayout size="wide" padded>
      <div
        className="flex items-center justify-between"
        style={{ marginBottom: 'var(--space-8)' }}
      >
        <div>
          <h1
            className="font-bold"
            style={{ color: 'var(--color-text-primary)', fontSize: 'var(--text-3xl)' }}
          >
            Dashboard
          </h1>
          <p
            style={{
              color: 'var(--color-text-muted)',
              marginTop: 'var(--space-1)',
              fontSize: 'var(--text-sm)',
            }}
          >
            Wonderz Agentics — Platform Overview
          </p>
        </div>
        <div className="flex items-center" style={{ gap: 'var(--space-3)' }}>
          {allHealthy !== null && (
            <span
              className="wz-badge"
              style={{
                background: allHealthy ? 'var(--color-status-success-bg)' : 'var(--color-status-warning-bg)',
                color: allHealthy ? 'var(--color-status-success)' : 'var(--color-status-warning)',
              }}
            >
              {allHealthy ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
              {allHealthy ? 'All Systems Online' : 'Degraded'}
            </span>
          )}
          <button
            onClick={() => { fetchStatus(); fetchJobs() }}
            className="transition"
            title="Refresh"
            style={{
              padding: 'var(--space-2)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
              background: 'var(--color-bg-card)',
            }}
          >
            <RefreshCw
              className={`w-4 h-4 ${statusLoading ? 'animate-spin' : ''}`}
              style={{ color: 'var(--color-text-muted)' }}
            />
          </button>
        </div>
      </div>

      {/* Service Health */}
      <div style={{ marginBottom: 'var(--space-8)' }}>
        <h2
          className="flex items-center font-semibold"
          style={{
            fontSize: 'var(--text-lg)',
            color: 'var(--color-text-primary)',
            marginBottom: 'var(--space-4)',
            gap: 'var(--space-2)',
          }}
        >
          <Server className="w-5 h-5" style={{ color: 'var(--color-brand-primary)' }} /> Services
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3" style={{ gap: 'var(--space-3)' }}>
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
          <p
            style={{
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-placeholder)',
              marginTop: 'var(--space-2)',
            }}
          >
            Last updated: {lastRefresh.toLocaleTimeString()}
          </p>
        )}
      </div>

      {/* Systemd Services */}
      {systemd && (
        <div style={{ marginBottom: 'var(--space-8)' }}>
          <h2
            className="flex items-center font-semibold"
            style={{
              fontSize: 'var(--text-lg)',
              color: 'var(--color-text-primary)',
              marginBottom: 'var(--space-4)',
              gap: 'var(--space-2)',
            }}
          >
            <Activity className="w-5 h-5" style={{ color: 'var(--color-brand-primary)' }} /> Systemd Services
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4" style={{ gap: 'var(--space-3)' }}>
            {Object.entries(systemd).map(([name, info]) => (
              <div
                key={name}
                className="flex items-center border"
                style={{
                  gap: 'var(--space-2)',
                  padding: 'var(--space-3)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: 'var(--text-sm)',
                  borderColor: info.active ? 'var(--color-status-success)' : 'var(--color-status-error)',
                  background: info.active ? 'var(--color-status-success-bg)' : 'var(--color-status-error-bg)',
                }}
              >
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ background: info.active ? 'var(--color-status-success)' : 'var(--color-status-error)' }}
                />
                <div>
                  <div
                    className="font-medium"
                    style={{ color: 'var(--color-text-secondary)' }}
                  >
                    {name.replace('wonderz-', '')}
                  </div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
                    {info.state}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stats + Quick Actions */}
      <div
        className="grid grid-cols-1 md:grid-cols-3"
        style={{ gap: 'var(--space-6)', marginBottom: 'var(--space-8)' }}
      >
        <div
          className="wz-card"
          style={{
            background: 'linear-gradient(135deg, var(--color-brand-primary-light), var(--color-bg-subtle))',
          }}
        >
          <div className="flex items-center" style={{ gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
            <Briefcase className="w-5 h-5" style={{ color: 'var(--color-brand-primary)' }} />
            <span
              className="font-medium"
              style={{ fontSize: 'var(--text-sm)', color: 'var(--color-brand-primary)' }}
            >
              Total Missions
            </span>
          </div>
          <p
            className="font-bold"
            style={{ fontSize: 'var(--text-3xl)', color: 'var(--color-text-primary)' }}
          >
            {stats.total}
          </p>
        </div>
        <div
          className="wz-card"
          style={{
            background: 'linear-gradient(135deg, var(--color-status-running-bg), var(--color-bg-subtle))',
          }}
        >
          <div className="flex items-center" style={{ gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
            <Activity className="w-5 h-5" style={{ color: 'var(--color-status-running)' }} />
            <span
              className="font-medium"
              style={{ fontSize: 'var(--text-sm)', color: 'var(--color-status-running)' }}
            >
              In Progress
            </span>
          </div>
          <p
            className="font-bold"
            style={{ fontSize: 'var(--text-3xl)', color: 'var(--color-text-primary)' }}
          >
            {stats.running}
          </p>
        </div>
        <div
          className="wz-card"
          style={{
            background: 'linear-gradient(135deg, var(--color-status-success-bg), var(--color-bg-subtle))',
          }}
        >
          <div className="flex items-center" style={{ gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
            <Zap className="w-5 h-5" style={{ color: 'var(--color-status-success)' }} />
            <span
              className="font-medium"
              style={{ fontSize: 'var(--text-sm)', color: 'var(--color-status-success)' }}
            >
              Completed
            </span>
          </div>
          <p
            className="font-bold"
            style={{ fontSize: 'var(--text-3xl)', color: 'var(--color-text-primary)' }}
          >
            {stats.ready}
          </p>
        </div>
      </div>

      {/* Quick Actions */}
      <div
        className="grid grid-cols-1 md:grid-cols-2"
        style={{ gap: 'var(--space-6)', marginBottom: 'var(--space-8)' }}
      >
        <Link
          to="/jobs/new"
          className="wz-card wz-lift flex items-center transition-all hover:scale-[1.01]"
          style={{
            gap: 'var(--space-4)',
            background: 'linear-gradient(90deg, var(--color-brand-primary), var(--color-agent-worker))',
            color: 'var(--color-sidebar-active-text)',
          }}
        >
          <PlusCircle className="w-8 h-8" />
          <div>
            <h3 className="font-semibold" style={{ fontSize: 'var(--text-lg)' }}>New Mission</h3>
            <p style={{ color: 'var(--color-brand-primary-light)', fontSize: 'var(--text-sm)' }}>
              Start a new AI-powered job
            </p>
          </div>
          <ArrowRight className="w-5 h-5 ml-auto" />
        </Link>
        <Link
          to="/job-center"
          className="wz-card wz-lift flex items-center transition-all hover:scale-[1.01]"
          style={{
            gap: 'var(--space-4)',
            border: '2px solid var(--color-brand-primary-light)',
            color: 'var(--color-brand-primary)',
          }}
        >
          <ClipboardList className="w-8 h-8" />
          <div>
            <h3 className="font-semibold" style={{ fontSize: 'var(--text-lg)' }}>Job Center</h3>
            <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>
              View all missions and crew status
            </p>
          </div>
          <ArrowRight className="w-5 h-5 ml-auto" />
        </Link>
      </div>

      {/* Dev Tools */}
      <div
        className="grid grid-cols-1 md:grid-cols-2"
        style={{ gap: 'var(--space-6)', marginBottom: 'var(--space-8)' }}
      >
        <a
          href={`${window.location.protocol}//${window.location.hostname}:7681`}
          target="_blank"
          rel="noopener noreferrer"
          className="wz-card wz-lift flex items-center transition-all hover:scale-[1.01]"
          style={{
            gap: 'var(--space-4)',
            background: 'var(--color-text-primary)',
            color: 'var(--color-bg-card)',
          }}
        >
          <Terminal className="w-8 h-8" style={{ color: 'var(--color-status-success)' }} />
          <div>
            <h3 className="font-semibold" style={{ fontSize: 'var(--text-lg)' }}>Terminal</h3>
            <p style={{ color: 'var(--color-text-placeholder)', fontSize: 'var(--text-sm)' }}>
              Full shell access to the VM
            </p>
          </div>
          <ArrowRight className="w-5 h-5 ml-auto" style={{ color: 'var(--color-text-placeholder)' }} />
        </a>
        <a
          href={`${window.location.protocol}//${window.location.hostname}:8080`}
          target="_blank"
          rel="noopener noreferrer"
          className="wz-card wz-lift flex items-center transition-all hover:scale-[1.01]"
          style={{
            gap: 'var(--space-4)',
            background: 'var(--color-text-primary)',
            color: 'var(--color-bg-card)',
          }}
        >
          <Sparkles className="w-8 h-8" style={{ color: 'var(--color-status-warning)' }} />
          <div>
            <h3 className="font-semibold" style={{ fontSize: 'var(--text-lg)' }}>Codex Console</h3>
            <p style={{ color: 'var(--color-text-placeholder)', fontSize: 'var(--text-sm)' }}>
              AI coding assistant — give prompts to Codex
            </p>
          </div>
          <ArrowRight className="w-5 h-5 ml-auto" style={{ color: 'var(--color-text-placeholder)' }} />
        </a>
      </div>

      {/* Recent Missions */}
      <div className="grid grid-cols-1 lg:grid-cols-2" style={{ gap: 'var(--space-6)' }}>
        <div className="panel-card">
          <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-4)' }}>
            <h2
              className="font-bold"
              style={{ fontSize: 'var(--text-lg)', color: 'var(--color-text-primary)' }}
            >
              Recent Missions
            </h2>
            <Link
              to="/job-center"
              className="hover:underline"
              style={{ fontSize: 'var(--text-sm)', color: 'var(--color-brand-primary)' }}
            >
              View all →
            </Link>
          </div>
          {loading ? (
            <p
              className="text-center"
              style={{ color: 'var(--color-text-placeholder)', padding: 'var(--space-8)' }}
            >
              Loading...
            </p>
          ) : recentJobs.length === 0 ? (
            <div className="text-center" style={{ padding: 'var(--space-8)' }}>
              <p
                style={{ color: 'var(--color-text-placeholder)', marginBottom: 'var(--space-4)' }}
              >
                No missions yet
              </p>
              <Link
                to="/jobs/new"
                className="inline-flex items-center"
                style={{
                  gap: 'var(--space-2)',
                  padding: 'var(--space-2) var(--space-4)',
                  background: 'var(--color-brand-primary)',
                  color: 'var(--color-sidebar-active-text)',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <PlusCircle className="w-4 h-4" /> Start your first mission
              </Link>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 'var(--space-2)' }}>
              {recentJobs.map((job) => (
                <Link
                  key={job.id}
                  to={`/jobs/new?job_id=${job.id}`}
                  className="flex items-center justify-between transition"
                  style={{
                    padding: 'var(--space-3)',
                    background: 'var(--color-bg-subtle)',
                    borderRadius: 'var(--radius-md)',
                  }}
                >
                  <div className="min-w-0 flex-1">
                    <p
                      className="font-medium truncate"
                      style={{ color: 'var(--color-text-primary)', fontSize: 'var(--text-sm)' }}
                    >
                      {(() => {
                        try {
                          let raw = job.context;
                          if (raw == null) return job.job_type || 'Untitled';
                          const parsed = typeof raw === 'object' ? raw : JSON.parse(String(raw));
                          const c = typeof parsed === 'string' ? (() => { try { return JSON.parse(parsed); } catch { return {}; } })() : (parsed || {});
                          return c.brief?.project_description || c.brief?.raw_idea || job.job_type || 'Untitled';
                        } catch {
                          return job.job_type || 'Untitled';
                        }
                      })()}
                    </p>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-placeholder)' }}>
                      {new Date(job.created_at).toLocaleDateString('nl-NL', {
                        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
                      })}
                    </p>
                  </div>
                  <span
                    className="wz-badge whitespace-nowrap"
                    style={{
                      ...statusStyle(job.status),
                      marginLeft: 'var(--space-2)',
                    }}
                  >
                    {job.status}
                  </span>
                  {job.intake_source === 'email' && (
                    <span style={{
                      background: '#EBF5FB', color: '#1A5276',
                      borderRadius: '4px', padding: '2px 8px',
                      fontSize: '11px', marginLeft: '6px'
                    }}>✉ Via Email</span>
                  )}
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent Commits */}
        <div className="panel-card">
          <h2
            className="font-bold"
            style={{
              fontSize: 'var(--text-lg)',
              color: 'var(--color-text-primary)',
              marginBottom: 'var(--space-4)',
            }}
          >
            Recent Commits
          </h2>
          {commits.length === 0 ? (
            <p
              className="text-center"
              style={{ color: 'var(--color-text-placeholder)', padding: 'var(--space-8)' }}
            >
              No commit data
            </p>
          ) : (
            <div style={{ display: 'grid', gap: 'var(--space-2)' }}>
              {commits.map((c, i) => (
                <div
                  key={i}
                  className="font-mono"
                  style={{
                    fontSize: 'var(--text-sm)',
                    color: 'var(--color-text-secondary)',
                    background: 'var(--color-bg-subtle)',
                    padding: 'var(--space-2)',
                    borderRadius: 'var(--radius-sm)',
                  }}
                >
                  {c}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      <SherlockWidget />
    </PageLayout>
  )
}
