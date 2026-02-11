import { useEffect, useState } from 'react'
import { Plus, Edit2, Trash2, User, Shield, Code, Container, RefreshCw, X, Check } from 'lucide-react'
import Sidebar from './Sidebar'

const roleIcons = {
  'Product Owner': Shield,
  'Developer': Code,
  'Reviewer': Shield,
  'DevOps': Container,
  'HR': User,
  'Training': User,
}

export default function CrewManagement() {
  const [crew, setCrew] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    role: '',
    specialization: '',
  })

  const fetchCrew = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/crew`)
      if (!res.ok) throw new Error('Failed to fetch crew')
      const data = await res.json()
      setCrew(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCrew()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formData.name || !formData.role) {
      setError('Name and role are required')
      return
    }

    try {
      const endpoint = editingId
        ? `${import.meta.env.VITE_API_URL}/api/crew/${editingId}`
        : `${import.meta.env.VITE_API_URL}/api/crew`
      
      const method = editingId ? 'PUT' : 'POST'
      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })

      if (!res.ok) throw new Error('Failed to save crew member')
      
      setFormData({ name: '', role: '', specialization: '' })
      setShowForm(false)
      setEditingId(null)
      setError(null)
      fetchCrew()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleEdit = (member) => {
    setEditingId(member.id)
    setFormData({
      name: member.name,
      role: member.role,
      specialization: member.specialization || '',
    })
    setShowForm(true)
  }

  const handleDelete = async (crew_id) => {
    if (!confirm(`Delete ${crew_id}?`)) return
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/crew/${crew_id}`, {
        method: 'DELETE',
      })
      if (!res.ok) throw new Error('Failed to delete crew member')
      fetchCrew()
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleCancel = () => {
    setShowForm(false)
    setEditingId(null)
    setFormData({ name: '', role: '', specialization: '' })
  }

  const roles = ['Product Owner', 'Developer', 'Reviewer', 'DevOps', 'HR', 'Training']

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex">
      <Sidebar />
      <main className="flex-1 px-8 py-8">
        <div className="max-w-6xl mx-auto">
          <div className="bg-white rounded-xl shadow-lg p-8 mb-8">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <h2 className="text-2xl font-bold text-gray-800">Crew Management</h2>
                <p className="text-sm text-gray-500">Manage your team members and their roles</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={fetchCrew}
                  className="flex items-center gap-2 px-4 py-2 text-sm bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition"
                >
                  <RefreshCw className="w-4 h-4" />
                  Refresh
                </button>
                <button
                  onClick={() => {
                    setShowForm(true)
                    setEditingId(null)
                    setFormData({ name: '', role: '', specialization: '' })
                  }}
                  className="flex items-center gap-2 px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
                >
                  <Plus className="w-4 h-4" />
                  Add Member
                </button>
              </div>
            </div>

            {error && (
              <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            )}
          </div>

          {showForm && (
            <div className="bg-white rounded-xl shadow-lg p-8 mb-8">
              <h3 className="text-lg font-semibold mb-6 text-gray-800">
                {editingId ? 'Edit Crew Member' : 'New Crew Member'}
              </h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Name
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="Enter name"
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Role
                  </label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  >
                    <option value="">Select a role</option>
                    {roles.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Specialization
                  </label>
                  <input
                    type="text"
                    value={formData.specialization}
                    onChange={(e) => setFormData({ ...formData, specialization: e.target.value })}
                    placeholder="Optional specialization"
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <div className="flex gap-2 pt-4">
                  <button
                    type="submit"
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
                  >
                    <Check className="w-4 h-4" />
                    Save
                  </button>
                  <button
                    type="button"
                    onClick={handleCancel}
                    className="flex items-center gap-2 px-4 py-2 border rounded-lg hover:bg-gray-100 transition"
                  >
                    <X className="w-4 h-4" />
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          <div className="bg-white rounded-xl shadow-lg p-8">
            <h3 className="text-lg font-semibold mb-6 text-gray-800">Team Members</h3>
            {loading && <div className="text-sm text-gray-400">Loading...</div>}
            {!loading && crew.length === 0 && (
              <div className="text-sm text-gray-500">No crew members found. Create one to get started!</div>
            )}
            <div className="space-y-3">
              {crew.map(member => {
                const Icon = roleIcons[member.role] || User
                return (
                  <div key={member.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition">
                    <div className="flex items-center gap-4 flex-1">
                      <div className="flex-shrink-0">
                        <Icon className="w-8 h-8 text-indigo-500" />
                      </div>
                      <div className="flex-1">
                        <div className="font-semibold text-gray-800">{member.name}</div>
                        <div className="text-xs text-gray-500">{member.role}</div>
                        {member.current_task && (
                          <div className="text-xs text-gray-500 mt-1">Task: {member.current_task}</div>
                        )}
                      </div>
                      <div className="text-right">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                          member.status === 'active'
                            ? 'bg-green-100 text-green-800'
                            : member.status === 'busy'
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {member.status}
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-2 ml-4">
                      <button
                        onClick={() => handleEdit(member)}
                        className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(member.id)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
