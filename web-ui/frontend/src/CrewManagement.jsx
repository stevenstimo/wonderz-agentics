import { useEffect, useState } from 'react'
import { Plus, Edit2, Trash2, User, Shield, Code, Container, RefreshCw, X, Check, AlertCircle, Loader } from 'lucide-react'
import Sidebar from './Sidebar'
import { ToastContainer, useToast } from './Toast'

const roleIcons = {
  'Product Owner': Shield,
  'Developer': Code,
  'Reviewer': Shield,
  'DevOps': Container,
  'HR': User,
  'Training': User,
}

const validRoles = ['Developer', 'Product Owner', 'Reviewer', 'DevOps', 'AI', 'HR', 'Training']

export default function CrewManagement() {
  const [crew, setCrew] = useState([])
  const [loading, setLoading] = useState(false)
  const [submitLoading, setSubmitLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(null)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [formValidation, setFormValidation] = useState({})
  const toast = useToast()
  
  const [formData, setFormData] = useState({
    name: '',
    role: '',
    specialization: '',
    system_instructions: '',
    knowledge_base_sources: '',
    tool_access_whitelist: '',
    hiring_logic: '',
  })

  const formatList = (items, delimiter) => Array.isArray(items) ? items.join(delimiter) : ''
  const parseLineList = (value) => value
    .split(/\r?\n/)
    .map(item => item.trim())
    .filter(Boolean)
  const parseCommaList = (value) => value
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)

  const fetchCrew = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/crew`)
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to fetch crew members')
      }
      const data = await res.json()
      setCrew(Array.isArray(data) ? data : [])
    } catch (err) {
      const errorMsg = err.message || 'Failed to load crew members'
      setError(errorMsg)
      toast.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const validateForm = () => {
    const errors = {}
    
    if (!formData.name || formData.name.trim() === '') {
      errors.name = 'Name is required'
    } else if (formData.name.length > 100) {
      errors.name = 'Name must be 100 characters or less'
    }
    
    if (!formData.role) {
      errors.role = 'Role is required'
    } else if (!validRoles.includes(formData.role)) {
      errors.role = `Invalid role. Must be one of: ${validRoles.join(', ')}`
    }
    
    if (formData.specialization && formData.specialization.length > 250) {
      errors.specialization = 'Specialization must be 250 characters or less'
    }

    if (!formData.system_instructions || formData.system_instructions.trim() === '') {
      errors.system_instructions = 'System instructions are required'
    } else if (formData.system_instructions.length > 4000) {
      errors.system_instructions = 'System instructions must be 4000 characters or less'
    }

    if (!formData.hiring_logic || formData.hiring_logic.trim() === '') {
      errors.hiring_logic = 'Hiring logic is required'
    } else if (formData.hiring_logic.length > 2000) {
      errors.hiring_logic = 'Hiring logic must be 2000 characters or less'
    }

    const knowledgeSources = parseLineList(formData.knowledge_base_sources)
    if (knowledgeSources.length > 50) {
      errors.knowledge_base_sources = 'Knowledge base sources must be 50 items or less'
    } else if (knowledgeSources.some(source => source.length > 2048)) {
      errors.knowledge_base_sources = 'Each knowledge source must be 2048 characters or less'
    }

    const toolWhitelist = parseCommaList(formData.tool_access_whitelist)
    if (toolWhitelist.length > 50) {
      errors.tool_access_whitelist = 'Tool access whitelist must be 50 items or less'
    } else if (toolWhitelist.some(tool => tool.length > 200)) {
      errors.tool_access_whitelist = 'Each tool entry must be 200 characters or less'
    }
    
    setFormValidation(errors)
    return Object.keys(errors).length === 0
  }

  useEffect(() => {
    fetchCrew()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!validateForm()) {
      toast.warning('Please fix the validation errors')
      return
    }

    setSubmitLoading(true)
    setError(null)

    try {
      const payload = {
        ...formData,
        knowledge_base_sources: parseLineList(formData.knowledge_base_sources),
        tool_access_whitelist: parseCommaList(formData.tool_access_whitelist),
      }
      const endpoint = editingId
        ? `${import.meta.env.VITE_API_URL}/api/crew/${editingId}`
        : `${import.meta.env.VITE_API_URL}/api/crew`
      
      const method = editingId ? 'PUT' : 'POST'
      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || errorData.error || 'Failed to save crew member')
      }
      
      const successMsg = editingId 
        ? `Successfully updated ${formData.name}` 
        : `Successfully created ${formData.name}`
      
      toast.success(successMsg)
      setFormData({
        name: '',
        role: '',
        specialization: '',
        system_instructions: '',
        knowledge_base_sources: '',
        tool_access_whitelist: '',
        hiring_logic: '',
      })
      setFormValidation({})
      setShowForm(false)
      setEditingId(null)
      setError(null)
      fetchCrew()
    } catch (err) {
      const errorMsg = err.message || 'Failed to save crew member'
      setError(errorMsg)
      toast.error(errorMsg)
    } finally {
      setSubmitLoading(false)
    }
  }

  const handleEdit = (member) => {
    setEditingId(member.id)
    setFormData({
      name: member.name,
      role: member.role,
      specialization: member.specialization || '',
      system_instructions: member.system_instructions || '',
      knowledge_base_sources: formatList(member.knowledge_base_sources, '\n'),
      tool_access_whitelist: formatList(member.tool_access_whitelist, ', '),
      hiring_logic: member.hiring_logic || '',
    })
    setShowForm(true)
  }

  const handleDelete = async (crew_id) => {
    if (!confirm(`Are you sure you want to deactivate this crew member?`)) return
    
    setDeleteLoading(crew_id)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/crew/${crew_id}`, {
        method: 'DELETE',
      })
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || errorData.error || 'Failed to delete crew member')
      }
      
      toast.success('Crew member deactivated')
      setError(null)
      fetchCrew()
    } catch (err) {
      const errorMsg = err.message || 'Failed to delete crew member'
      setError(errorMsg)
      toast.error(errorMsg)
    } finally {
      setDeleteLoading(null)
    }
  }

  const handleCancel = () => {
    setShowForm(false)
    setEditingId(null)
    setFormData({
      name: '',
      role: '',
      specialization: '',
      system_instructions: '',
      knowledge_base_sources: '',
      tool_access_whitelist: '',
      hiring_logic: '',
    })
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
                    setFormData({
                      name: '',
                      role: '',
                      specialization: '',
                      system_instructions: '',
                      knowledge_base_sources: '',
                      tool_access_whitelist: '',
                      hiring_logic: '',
                    })
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
                    Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="Enter name"
                    maxLength="100"
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                      formValidation.name ? 'border-red-500 bg-red-50' : ''
                    }`}
                  />
                  {formValidation.name && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      {formValidation.name}
                    </div>
                  )}
                  <div className="text-xs text-gray-500 mt-1">{formData.name.length}/100</div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Role <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                      formValidation.role ? 'border-red-500 bg-red-50' : ''
                    }`}
                  >
                    <option value="">Select a role</option>
                    {validRoles.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                  {formValidation.role && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      {formValidation.role}
                    </div>
                  )}
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
                    maxLength="250"
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                      formValidation.specialization ? 'border-red-500 bg-red-50' : ''
                    }`}
                  />
                  {formValidation.specialization && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      {formValidation.specialization}
                    </div>
                  )}
                  <div className="text-xs text-gray-500 mt-1">{formData.specialization.length}/250</div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    System Instructions <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={formData.system_instructions}
                    onChange={(e) => setFormData({ ...formData, system_instructions: e.target.value })}
                    placeholder="Define persona, tone, and working rules"
                    rows={5}
                    maxLength="4000"
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                      formValidation.system_instructions ? 'border-red-500 bg-red-50' : ''
                    }`}
                  />
                  {formValidation.system_instructions && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      {formValidation.system_instructions}
                    </div>
                  )}
                  <div className="text-xs text-gray-500 mt-1">{formData.system_instructions.length}/4000</div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Knowledge Base Sources (URL/File)
                  </label>
                  <textarea
                    value={formData.knowledge_base_sources}
                    onChange={(e) => setFormData({ ...formData, knowledge_base_sources: e.target.value })}
                    placeholder="One URL or file path per line"
                    rows={4}
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                      formValidation.knowledge_base_sources ? 'border-red-500 bg-red-50' : ''
                    }`}
                  />
                  {formValidation.knowledge_base_sources && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      {formValidation.knowledge_base_sources}
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Tool Access Whitelist
                  </label>
                  <input
                    type="text"
                    value={formData.tool_access_whitelist}
                    onChange={(e) => setFormData({ ...formData, tool_access_whitelist: e.target.value })}
                    placeholder="e.g., shopify.read_orders, ga4.reports"
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                      formValidation.tool_access_whitelist ? 'border-red-500 bg-red-50' : ''
                    }`}
                  />
                  {formValidation.tool_access_whitelist && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      {formValidation.tool_access_whitelist}
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Hiring Logic <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={formData.hiring_logic}
                    onChange={(e) => setFormData({ ...formData, hiring_logic: e.target.value })}
                    placeholder="Describe the goal and success criteria for this agent"
                    rows={4}
                    maxLength="2000"
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                      formValidation.hiring_logic ? 'border-red-500 bg-red-50' : ''
                    }`}
                  />
                  {formValidation.hiring_logic && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      {formValidation.hiring_logic}
                    </div>
                  )}
                  <div className="text-xs text-gray-500 mt-1">{formData.hiring_logic.length}/2000</div>
                </div>
                
                <div className="flex gap-2 pt-4">
                  <button
                    type="submit"
                    disabled={submitLoading}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {submitLoading ? (
                      <>
                        <Loader className="w-4 h-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Check className="w-4 h-4" />
                        Save
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={handleCancel}
                    disabled={submitLoading}
                    className="flex items-center gap-2 px-4 py-2 border rounded-lg hover:bg-gray-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
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
            {loading && (
              <div className="flex items-center justify-center py-8">
                <Loader className="w-5 h-5 animate-spin text-indigo-600 mr-2" />
                <span className="text-sm text-gray-500">Loading crew members...</span>
              </div>
            )}
            {!loading && crew.length === 0 && (
              <div className="py-8 text-center text-sm text-gray-500">No crew members found. Create one to get started!</div>
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
                        {member.specialization && (
                          <div className="text-xs text-gray-400 mt-1">{member.specialization}</div>
                        )}
                        {Array.isArray(member.knowledge_base_sources) && member.knowledge_base_sources.length > 0 && (
                          <div className="text-xs text-gray-400 mt-1">
                            KB: {member.knowledge_base_sources.join(', ')}
                          </div>
                        )}
                        {member.current_task && (
                          <div className="text-xs text-gray-500 mt-1">Task: {member.current_task}</div>
                        )}
                      </div>
                      {member.progress !== undefined && (
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-indigo-500 transition-all"
                              style={{ width: `${member.progress}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500 w-8">{member.progress}%</span>
                        </div>
                      )}
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
                        disabled={deleteLoading === member.id}
                        className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition disabled:opacity-50"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(member.id)}
                        disabled={deleteLoading !== null}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {deleteLoading === member.id ? (
                          <Loader className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </main>
      <ToastContainer toasts={toast.toasts} onRemove={toast.removeToast} />
    </div>
  )
}
