import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, User, Settings, TrendingUp } from 'lucide-react'
import PageLayout from './PageLayout'
import { InlineEditField } from './components/InlineEditField'

export default function AgentsOverview() {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadAgents()
  }, [])

  async function loadAgents() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/agents')
      if (!res.ok) throw new Error('Failed to load agents')
      const data = await res.json()
      const list = Array.isArray(data) ? data : (data.agents || [])
      setAgents(list)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageLayout title="Agents Overview">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">AI Crew</h1>
            <p className="text-gray-600 mt-2">Manage your AI agents and their skills</p>
          </div>
          <button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            <Plus size={20} />
            New Agent
          </button>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
            <p className="text-gray-600 mt-4">Loading agents...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {agents.map(agent => (
              <AgentCard key={agent.agent_id} agent={agent} onUpdate={loadAgents} />
            ))}
          </div>
        )}

        {showCreateForm && (
          <CreateAgentModal
            onClose={() => setShowCreateForm(false)}
            onSuccess={() => {
              setShowCreateForm(false)
              loadAgents()
            }}
          />
        )}
      </div>
    </PageLayout>
  )
}

function AgentCard({ agent, onUpdate }) {
  const statusColor = agent.status === 'active'
    ? 'bg-green-100 text-green-800'
    : 'bg-gray-100 text-gray-800'

  const performancePercent = Math.round((agent.performance_score || 0) * 100)

  async function handleNameSave(newName) {
    const res = await fetch(`/api/agents/${agent.agent_id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName })
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Failed to update agent name')
    }
    if (onUpdate) onUpdate()
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center">
            <User className="text-indigo-600" size={24} />
          </div>
          <div>
            <InlineEditField label="Name" value={agent.name} onSave={handleNameSave} />
            <p className="text-sm text-gray-600 capitalize">{agent.role}</p>
          </div>
        </div>
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColor}`}>
          {agent.status}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <p className="text-xs text-gray-600">Performance</p>
          <p className="text-lg font-semibold text-gray-900">{performancePercent}%</p>
        </div>
        <div>
          <p className="text-xs text-gray-600">Tasks Done</p>
          <p className="text-lg font-semibold text-gray-900">{agent.completed_tasks || 0}</p>
        </div>
      </div>

      <div className="flex gap-2">
        <Link
          to={`/agents/${agent.agent_id}`}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm"
        >
          <Settings size={16} />
          Manage
        </Link>
        <Link
          to={`/agents/${agent.agent_id}/training`}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200 text-sm"
        >
          <TrendingUp size={16} />
          Train
        </Link>
        <Link
          to={`/agents/${agent.agent_id}/analytics`}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-emerald-100 text-emerald-700 rounded-lg hover:bg-emerald-200 text-sm"
        >
          <TrendingUp size={16} />
          Analytics
        </Link>
      </div>
    </div>
  )
}

function CreateAgentModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    name: '',
    role: 'copywriter',
    system_instructions: '',
    tool_access_whitelist: []
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      const res = await fetch('/api/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_name: formData.name,
          role: formData.role,
          system_prompt: formData.system_instructions,
          tool_whitelist: formData.tool_access_whitelist
        })
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to create agent')
      }

      onSuccess()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-xl font-bold mb-4">Create New Agent</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={e => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              required
              minLength={3}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
            <select
              value={formData.role}
              onChange={e => setFormData({ ...formData, role: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              <option value="copywriter">Copywriter</option>
              <option value="reviewer">Reviewer</option>
              <option value="seo">SEO Specialist</option>
              <option value="support">Support Agent</option>
              <option value="custom">Custom</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">System Instructions</label>
            <textarea
              value={formData.system_instructions}
              onChange={e => setFormData({ ...formData, system_instructions: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              rows={4}
              required
              minLength={20}
              placeholder="You are a helpful agent who..."
            />
          </div>

          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
              disabled={submitting}
            >
              {submitting ? 'Creating...' : 'Create Agent'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
