import { useEffect, useMemo, useState } from 'react'
import { Plus, Edit2, Trash2, User, Shield, Code, Container, RefreshCw, X, Check, AlertCircle, Loader } from 'lucide-react'
import PageLayout from './PageLayout'
import { getCurrentUserRole, isSuperAdmin } from './authz'

const roleIcons = {
  'Product Owner': Shield,
  Developer: Code,
  Reviewer: Shield,
  DevOps: Container,
  HR: User,
  Training: User,
  CIO: Shield,
}

const validRoles = ['Developer', 'Product Owner', 'Reviewer', 'DevOps', 'AI', 'HR', 'Training', 'CIO']
const apiBase = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '')

const initialFormData = {
  name: '',
  role: '',
  avatar_url: '',
  specialization: '',
  system_instructions: '',
  knowledge_base_sources: '',
  tool_access_whitelist: '',
  hiring_logic: '',
  persona: '',
  quality_notes: '',
  development_notes: '',
}

export default function CrewManagement() {
  const [crew, setCrew] = useState([])
  const [loading, setLoading] = useState(false)
  const [submitLoading, setSubmitLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(null)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [formValidation, setFormValidation] = useState({})
  const [formData, setFormData] = useState(initialFormData)
  const [userRole, setUserRole] = useState('member')

  const canEdit = useMemo(() => isSuperAdmin(userRole), [userRole])

  const formatList = (items, delimiter) => (Array.isArray(items) ? items.join(delimiter) : '')
  const parseLineList = (value) => value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
  const parseCommaList = (value) => value.split(',').map((item) => item.trim()).filter(Boolean)

  const fetchCrew = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiBase}/api/crew`)
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to fetch crew members')
      }
      const data = await res.json()
      setCrew(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message || 'Failed to load crew members')
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

    if (formData.persona && formData.persona.length > 2000) {
      errors.persona = 'Persona must be 2000 characters or less'
    }

    if (formData.quality_notes && formData.quality_notes.length > 2000) {
      errors.quality_notes = 'Quality notes must be 2000 characters or less'
    }

    if (formData.development_notes && formData.development_notes.length > 2000) {
      errors.development_notes = 'Development notes must be 2000 characters or less'
    }

    const knowledgeSources = parseLineList(formData.knowledge_base_sources)
    if (knowledgeSources.length > 50) {
      errors.knowledge_base_sources = 'Knowledge base sources must be 50 items or less'
    }

    const toolWhitelist = parseCommaList(formData.tool_access_whitelist)
    if (toolWhitelist.length > 50) {
      errors.tool_access_whitelist = 'Tool access whitelist must be 50 items or less'
    }

    setFormValidation(errors)
    return Object.keys(errors).length === 0
  }

  useEffect(() => {
    ;(async () => {
      try {
        const ctx = await getCurrentUserRole()
        setUserRole(ctx.role || 'member')
      } catch {
        setUserRole('member')
      }
      fetchCrew()
    })()
  }, [])

  const openCreate = () => {
    setShowForm(true)
    setEditingId(null)
    setFormData(initialFormData)
    setFormValidation({})
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!canEdit) {
      setError('Alleen super admin kan crew wijzigen')
      return
    }

    if (!validateForm()) return

    setSubmitLoading(true)
    setError(null)

    try {
      const payload = {
        ...formData,
        knowledge_base_sources: parseLineList(formData.knowledge_base_sources),
        tool_access_whitelist: parseCommaList(formData.tool_access_whitelist),
      }
      const endpoint = editingId ? `${apiBase}/api/crew/${editingId}` : `${apiBase}/api/crew`
      const method = editingId ? 'PUT' : 'POST'

      const res = await fetch(endpoint, {
        method,
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || errorData.error || 'Failed to save crew member')
      }

      setFormData(initialFormData)
      setShowForm(false)
      setEditingId(null)
      await fetchCrew()
    } catch (err) {
      setError(err.message || 'Failed to save crew member')
    } finally {
      setSubmitLoading(false)
    }
  }

  const handleEdit = (member) => {
    if (!canEdit) return
    setEditingId(member.id)
    setFormData({
      name: member.name,
      role: member.role,
      avatar_url: member.avatar_url || '',
      specialization: member.specialization || '',
      system_instructions: member.system_instructions || '',
      knowledge_base_sources: formatList(member.knowledge_base_sources, '\n'),
      tool_access_whitelist: formatList(member.tool_access_whitelist, ', '),
      hiring_logic: member.hiring_logic || '',
      persona: member.persona || '',
      quality_notes: member.quality_notes || '',
      development_notes: member.development_notes || '',
    })
    setShowForm(true)
  }

  const handleDelete = async (crewId) => {
    if (!canEdit) return
    if (!confirm('Are you sure you want to deactivate this crew member?')) return

    setDeleteLoading(crewId)
    try {
      const res = await fetch(`${apiBase}/api/crew/${crewId}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || errorData.error || 'Failed to delete crew member')
      }
      await fetchCrew()
    } catch (err) {
      setError(err.message || 'Failed to delete crew member')
    } finally {
      setDeleteLoading(null)
    }
  }

  return (
    <PageLayout size="wide" padded>
      <div className="panel-card mb-8">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="page-title">The Crew</h2>
            <p className="page-subtitle">Unified workforce across specialized operational layers.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={fetchCrew} className="btn-icon-only" aria-label="Refresh" type="button">
              <RefreshCw className="w-4 h-4" />
            </button>
            {canEdit && (
              <button onClick={openCreate} className="btn-manage gap-2" type="button">
                <Plus className="w-4 h-4" />
                Add Member
              </button>
            )}
          </div>
        </div>

        {error && <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}
        {!canEdit && <div className="mt-4 p-3 bg-blue-50 text-blue-700 rounded-lg text-sm">Alleen super admin kan crew wijzigen. Je hebt read-only toegang.</div>}
      </div>

      {showForm && (
        <div className="panel-card mb-8">
          <h3 className="text-lg font-semibold mb-6 text-gray-800">{editingId ? 'Edit Crew Member' : 'New Crew Member'}</h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name <span className="text-red-500">*</span></label>
              <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="Enter name" maxLength="100" className={`w-full px-3 py-2 border rounded-lg ${formValidation.name ? 'border-red-500 bg-red-50' : ''}`} />
              {formValidation.name && <div className="flex items-center gap-1 mt-1 text-xs text-red-600"><AlertCircle className="w-3 h-3" />{formValidation.name}</div>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Role <span className="text-red-500">*</span></label>
              <select value={formData.role} onChange={(e) => setFormData({ ...formData, role: e.target.value })} className={`w-full px-3 py-2 border rounded-lg ${formValidation.role ? 'border-red-500 bg-red-50' : ''}`}>
                <option value="">Select a role</option>
                {validRoles.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              {formValidation.role && <div className="flex items-center gap-1 mt-1 text-xs text-red-600"><AlertCircle className="w-3 h-3" />{formValidation.role}</div>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Avatar URL</label>
              <input type="text" value={formData.avatar_url} onChange={(e) => setFormData({ ...formData, avatar_url: e.target.value })} placeholder="https://..." className="w-full px-3 py-2 border rounded-lg" />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Specialization</label>
              <input type="text" value={formData.specialization} onChange={(e) => setFormData({ ...formData, specialization: e.target.value })} placeholder="Optional specialization" maxLength="250" className={`w-full px-3 py-2 border rounded-lg ${formValidation.specialization ? 'border-red-500 bg-red-50' : ''}`} />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">System Instructions <span className="text-red-500">*</span></label>
              <textarea value={formData.system_instructions} onChange={(e) => setFormData({ ...formData, system_instructions: e.target.value })} placeholder="Define persona, tone, and working rules" rows={5} maxLength="4000" className={`w-full px-3 py-2 border rounded-lg ${formValidation.system_instructions ? 'border-red-500 bg-red-50' : ''}`} />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Knowledge Base Sources (URL/File)</label>
              <textarea value={formData.knowledge_base_sources} onChange={(e) => setFormData({ ...formData, knowledge_base_sources: e.target.value })} placeholder="One URL or file path per line" rows={4} className={`w-full px-3 py-2 border rounded-lg ${formValidation.knowledge_base_sources ? 'border-red-500 bg-red-50' : ''}`} />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Tool Access Whitelist</label>
              <input type="text" value={formData.tool_access_whitelist} onChange={(e) => setFormData({ ...formData, tool_access_whitelist: e.target.value })} placeholder="e.g., shopify.read_orders, ga4.reports" className={`w-full px-3 py-2 border rounded-lg ${formValidation.tool_access_whitelist ? 'border-red-500 bg-red-50' : ''}`} />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Hiring Logic <span className="text-red-500">*</span></label>
              <textarea value={formData.hiring_logic} onChange={(e) => setFormData({ ...formData, hiring_logic: e.target.value })} placeholder="Describe the goal and success criteria for this agent" rows={4} maxLength="2000" className={`w-full px-3 py-2 border rounded-lg ${formValidation.hiring_logic ? 'border-red-500 bg-red-50' : ''}`} />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Persona</label>
              <textarea value={formData.persona} onChange={(e) => setFormData({ ...formData, persona: e.target.value })} placeholder="How this crew member communicates and decides" rows={4} maxLength="2000" className={`w-full px-3 py-2 border rounded-lg ${formValidation.persona ? 'border-red-500 bg-red-50' : ''}`} />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Quality Notes</label>
              <textarea value={formData.quality_notes} onChange={(e) => setFormData({ ...formData, quality_notes: e.target.value })} placeholder="What this crew member does well today" rows={4} maxLength="2000" className={`w-full px-3 py-2 border rounded-lg ${formValidation.quality_notes ? 'border-red-500 bg-red-50' : ''}`} />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Development Notes</label>
              <textarea value={formData.development_notes} onChange={(e) => setFormData({ ...formData, development_notes: e.target.value })} placeholder="Where this crew member should improve next" rows={4} maxLength="2000" className={`w-full px-3 py-2 border rounded-lg ${formValidation.development_notes ? 'border-red-500 bg-red-50' : ''}`} />
            </div>

            <div className="flex gap-2 pt-4">
              <button type="submit" disabled={submitLoading} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition disabled:opacity-50">
                {submitLoading ? <><Loader className="w-4 h-4 animate-spin" />Saving...</> : <><Check className="w-4 h-4" />Save</>}
              </button>
              <button type="button" onClick={() => { setShowForm(false); setEditingId(null); setFormData(initialFormData) }} disabled={submitLoading} className="flex items-center gap-2 px-4 py-2 border rounded-lg hover:bg-gray-100 transition disabled:opacity-50">
                <X className="w-4 h-4" />
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="panel-card">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-gray-800">Team Members</h3>
          <span className="text-xs text-gray-400">{crew.length} agents synchronized</span>
        </div>
        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader className="w-5 h-5 animate-spin text-indigo-600 mr-2" />
            <span className="text-sm text-gray-500">Loading crew members...</span>
          </div>
        )}
        {!loading && crew.length === 0 && (
          <div className="py-8 text-center text-sm text-gray-500">No crew members found.</div>
        )}

        <div className="agent-grid">
          {crew.map((member) => {
            const Icon = roleIcons[member.role] || User
            return (
              <div key={member.id} className="agent-card card-management">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <img
                      src={member.avatar_url || `https://api.dicebear.com/7.x/personas/svg?seed=${encodeURIComponent(member.name || 'crew')}`}
                      alt={member.name}
                      className="w-12 h-12 rounded-full border object-cover"
                    />
                    <div className="agent-icon-container">
                      <Icon className="w-5 h-5" />
                    </div>
                  </div>
                  {canEdit && (
                    <div className="flex gap-2">
                      <button onClick={() => handleEdit(member)} disabled={deleteLoading === member.id} className="btn-icon-only" aria-label="Edit member" type="button">
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleDelete(member.id)} disabled={deleteLoading !== null} className="btn-icon-only text-red-500" aria-label="Remove member" type="button">
                        {deleteLoading === member.id ? <Loader className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                      </button>
                    </div>
                  )}
                </div>
                <div>
                  <div className="text-lg font-semibold text-gray-900">{member.name}</div>
                  <div className="text-xs uppercase tracking-[0.2em] text-gray-400">{member.role}</div>
                  {member.specialization && <div className="text-sm text-gray-500 mt-2">{member.specialization}</div>}
                  {member.current_task && <div className="text-xs text-gray-400 mt-2">Current: {member.current_task}</div>}
                </div>
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-semibold px-2 py-1 rounded-full ${member.status === 'active' ? 'bg-green-100 text-green-800' : member.status === 'busy' ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-800'}`}>
                    {member.status}
                  </span>
                  {member.progress !== undefined && <span className="text-xs text-gray-400">{member.progress}%</span>}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </PageLayout>
  )
}
