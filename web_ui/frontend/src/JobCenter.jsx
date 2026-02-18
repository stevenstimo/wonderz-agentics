import { apiBase } from './apiBase'
import { useEffect, useState } from 'react'
import PageLayout from './PageLayout';


export default function JobCenter() {
  const [crew, setCrew] = useState([])
  const [sections, setSections] = useState([])
  const [meta, setMeta] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true

    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        const [crewRes, explainerRes] = await Promise.all([
          fetch(`${apiBase}/api/crew`),
          fetch(`${apiBase}/api/explainer/sections`)
        ])

        if (!crewRes.ok) {
          throw new Error('Failed to load crew status')
        }
        if (!explainerRes.ok) {
          throw new Error('Failed to load updates')
        }

        const crewData = await crewRes.json()
        const explainerData = await explainerRes.json()

        if (!active) {
          return
        }

        setCrew(Array.isArray(crewData) ? crewData : [])
        setSections(Array.isArray(explainerData.sections) ? explainerData.sections : [])
        setMeta(explainerData.meta || null)
      } catch (err) {
        if (!active) {
          return
        }
        setError(err.message || 'Failed to load job center data')
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    fetchData()
    return () => {
      active = false
    }
  }, [])

  const updates = sections.map((section) => ({
    slug: section.slug,
    title: section.title,
    updated_at: section.updated_at
  }))

  return (
    <PageLayout size="wide" padded className="space-y-6">
          <div className="panel-card">
            <h2 className="page-title">Job Center</h2>
            <p className="page-subtitle">
              Live status and updates from the backend. Use this page to keep track of what changed.
            </p>
          </div>

          {loading && <div className="panel-card">Loading...</div>}
          {!loading && error && <div className="panel-card text-red-500">{error}</div>}

          {!loading && !error && (
            <>
              <div className="panel-card">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900">Latest updates</h3>
                    <p className="text-sm text-slate-500">Explainer sections refreshed from the backend.</p>
                  </div>
                  {meta && (
                    <div className="text-xs text-slate-400">
                      <div>Env: {meta.deploy_env}</div>
                      <div>SHA: {meta.build_sha}</div>
                      <div>Data: {new Date(meta.data_refreshed_at).toLocaleString()}</div>
                    </div>
                  )}
                </div>
                <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                  {updates.map((item) => (
                    <div key={item.slug} className="rounded-lg border border-slate-200 p-4">
                      <div className="text-sm font-semibold text-slate-800">{item.title}</div>
                      <div className="text-xs text-slate-500 mt-2">
                        Updated: {item.updated_at ? new Date(item.updated_at).toLocaleString() : 'Unknown'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel-card">
                <h3 className="text-lg font-semibold text-slate-900">Crew status</h3>
                <p className="text-sm text-slate-500">Current active crew members.</p>
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {crew.map((member) => (
                    <div key={member.id} className="rounded-lg border border-slate-200 p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-semibold text-slate-800">{member.name}</div>
                          <div className="text-xs text-slate-500">{member.role}</div>
                        </div>
                        <span className="text-xs uppercase tracking-wide text-slate-400">{member.status}</span>
                      </div>
                      <div className="mt-3 text-xs text-slate-500">{member.current_task || 'No active task'}</div>
                      {typeof member.progress === 'number' && (
                        <div className="mt-2 h-2 rounded-full bg-slate-100">
                          <div
                            className="h-2 rounded-full bg-indigo-500"
                            style={{ width: `${member.progress}%` }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
      </PageLayout>
  )
}
