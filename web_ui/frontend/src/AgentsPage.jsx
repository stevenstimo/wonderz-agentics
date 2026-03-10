/**
 * AgentsPage.jsx — /agents (binnen AuthenticatedLayout)
 * Toont alle hired agents + knop om nieuwe aan te maken.
 * Spec: Product Spec v1.1, Sectie 2. Dark theme #0d0f14.
 */

import { useState, useEffect } from 'react'
import { apiFetch } from './apiClient'
import { useNavigate } from 'react-router-dom'
import PageLayout from './PageLayout'
import { useAuthReady } from './useAuthReady'


const API = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')

const ROLE_COLORS = {
  copywriter: '#4f8ef7',
  seo: '#3ecf8e',
  'hr-manager': '#a78bfa',
  support: '#fb923c',
  reviewer: '#f87171',
  researcher: '#fbbf24',
  developer: '#34d399',
  custom: '#6b7494',
}

export default function AgentsPage() {
  const authReady = useAuthReady()
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    if (!authReady) return
    apiFetch('/api/agents')
      .then((r) => r.json())
      .then((d) => {
        setAgents(d.agents || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [authReady])

  const deactivate = async (agentId) => {
    if (!confirm(`Agent ${agentId} deactiveren?`)) return
    try {
      await apiFetch(`/api/agents/${encodeURIComponent(agentId)}`, { method: 'DELETE' })
      setAgents((prev) =>
        prev.map((a) => (a.agent_id === agentId ? { ...a, is_active: false } : a))
      )
    } catch (err) {
      console.error('Deactivate failed:', err)
    }
  }

  return (
    <PageLayout>
      <div
        style={{
          padding: '32px 40px',
          background: '#0d0f14',
          minHeight: '100vh',
          fontFamily: "'DM Sans', sans-serif",
          color: '#e8eaf0',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 28,
          }}
        >
          <div>
            <h1
              style={{
                margin: 0,
                fontSize: 24,
                fontWeight: 700,
                letterSpacing: '-0.02em',
              }}
            >
              Agents
            </h1>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6b7494' }}>
              {agents.filter((a) => a.is_active !== false).length} actief
            </p>
          </div>
          <button
            onClick={() => navigate('/agents/new')}
            style={{
              background: '#4f8ef7',
              color: '#fff',
              border: 'none',
              padding: '9px 20px',
              borderRadius: 9,
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            + Nieuwe agent
          </button>
        </div>

        {loading ? (
          <p style={{ color: '#6b7494' }}>Laden…</p>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: 12,
            }}
          >
            {agents.map((agent) => (
              <div
                key={agent.agent_id}
                style={{
                  background: '#151820',
                  border: '1px solid #1e2330',
                  borderRadius: 12,
                  padding: '20px 22px',
                  opacity: agent.is_active === false ? 0.6 : 1,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    marginBottom: 10,
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontSize: 15,
                        fontWeight: 600,
                        color: '#e8eaf0',
                      }}
                    >
                      {agent.name}
                    </div>
                    <span
                      style={{
                        display: 'inline-block',
                        marginTop: 4,
                        fontSize: 11,
                        fontWeight: 600,
                        padding: '2px 8px',
                        borderRadius: 5,
                        background:
                          (ROLE_COLORS[agent.role] || '#6b7494') + '20',
                        color: ROLE_COLORS[agent.role] || '#6b7494',
                      }}
                    >
                      {agent.role}
                    </span>
                  </div>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background:
                        agent.is_active !== false ? '#3ecf8e' : '#6b7494',
                      display: 'inline-block',
                      marginTop: 4,
                    }}
                  />
                </div>
                {agent.goal && (
                  <p
                    style={{
                      margin: '0 0 12px',
                      fontSize: 13,
                      color: '#6b7494',
                      lineHeight: 1.5,
                    }}
                  >
                    {agent.goal}
                  </p>
                )}
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    onClick={() =>
                      navigate(`/agents/${encodeURIComponent(agent.agent_id)}/edit`)
                    }
                    style={{
                      fontSize: 11,
                      padding: '4px 10px',
                      borderRadius: 6,
                      border: '1px solid #252c3d',
                      background: 'transparent',
                      color: '#b0b6cc',
                      cursor: 'pointer',
                    }}
                  >
                    Bewerken
                  </button>
                  {agent.is_active !== false && (
                    <button
                      onClick={() => deactivate(agent.agent_id)}
                      style={{
                        fontSize: 11,
                        padding: '4px 10px',
                        borderRadius: 6,
                        border: '1px solid #7f1d1d',
                        background: '#3d1515',
                        color: '#f87171',
                        cursor: 'pointer',
                      }}
                    >
                      Deactiveer
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </PageLayout>
  )
}
