import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apiBase } from './apiBase'
import PageLayout from './PageLayout'
import { ArrowLeft, User, Shield, Code, Container, Sparkles, Activity } from 'lucide-react'

const roleIcons = {
  'Product Owner': Shield,
  Developer: Code,
  Reviewer: Shield,
  DevOps: Container,
  HR: User,
  Training: User,
  CIO: Shield,
  copywriter: Sparkles,
  reviewer: Shield,
  seo: Activity,
}

export default function CrewDetail() {
  const { memberId } = useParams()
  const [member, setMember] = useState(null)
  const [skills, setSkills] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadMember()
  }, [memberId])

  async function loadMember() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiBase}/api/crew/${memberId}`)
      if (!res.ok) throw new Error('Crew member not found')
      const data = await res.json()
      setMember(data)

      // Try loading skills for this agent
      if (data.agent_id) {
        await loadSkills(data.agent_id)
      } else {
        // Try matching via hired_agents
        await loadSkillsByName(data.name)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadSkills(agentId) {
    try {
      const res = await fetch(`${apiBase}/api/skills`)
      if (!res.ok) return
      const data = await res.json()
      const allSkills = data.skills || []

      // For each skill, check if this agent has it
      const agentSkills = []
      for (const skill of allSkills) {
        try {
          const agentsRes = await fetch(`${apiBase}/api/skills/${encodeURIComponent(skill.skill_id)}/agents`)
          if (!agentsRes.ok) continue
          const agentsData = await agentsRes.json()
          const match = (agentsData.agents || []).find(a => a.agent_id === agentId)
          if (match) {
            agentSkills.push({ ...skill, proficiency: match.proficiency })
          }
        } catch { /* skip */ }
      }
      setSkills(agentSkills)
    } catch { /* skip */ }
  }

  async function loadSkillsByName(name) {
    // Match crew member name to hired_agents by partial name match
    try {
      const res = await fetch(`${apiBase}/api/skills`)
      if (!res.ok) return
      const data = await res.json()
      const allSkills = data.skills || []

      const agentSkills = []
      for (const skill of allSkills) {
        try {
          const agentsRes = await fetch(`${apiBase}/api/skills/${encodeURIComponent(skill.skill_id)}/agents`)
          if (!agentsRes.ok) continue
          const agentsData = await agentsRes.json()
          const match = (agentsData.agents || []).find(a =>
            a.name.toLowerCase().includes(name.toLowerCase().split(' ')[0]) ||
            name.toLowerCase().includes(a.name.toLowerCase().split(' ')[0])
          )
          if (match) {
            agentSkills.push({ ...skill, proficiency: match.proficiency })
          }
        } catch { /* skip */ }
      }
      setSkills(agentSkills)
    } catch { /* skip */ }
  }

  if (loading) {
    return (
      <PageLayout size="wide" padded>
        <div className="text-center py-12 text-gray-500">Laden...</div>
      </PageLayout>
    )
  }

  if (error || !member) {
    return (
      <PageLayout size="wide" padded>
        <div className="text-center py-12">
          <p className="text-red-500 mb-4">{error || 'Niet gevonden'}</p>
          <Link to="/crew" className="text-indigo-600 hover:underline">← Terug naar Crew</Link>
        </div>
      </PageLayout>
    )
  }

  const Icon = roleIcons[member.role] || roleIcons[member.role?.toLowerCase()] || User

  return (
    <PageLayout size="wide" padded>
      <Link to="/crew" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-indigo-600 mb-6">
        <ArrowLeft className="w-4 h-4" /> Terug naar Crew
      </Link>

      {/* Header */}
      <div className="panel-card mb-6">
        <div className="flex items-start gap-6">
          <img
            src={member.avatar_url || `https://api.dicebear.com/7.x/personas/svg?seed=${encodeURIComponent(member.name || 'crew')}`}
            alt={member.name}
            className="w-20 h-20 rounded-full border-2 border-gray-200 object-cover"
          />
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-2xl font-bold text-gray-900">{member.name}</h1>
              <span className={`text-xs font-semibold px-2 py-1 rounded-full ${
                member.status === 'active' ? 'bg-green-100 text-green-800' :
                member.status === 'busy' ? 'bg-yellow-100 text-yellow-800' :
                'bg-gray-100 text-gray-800'
              }`}>{member.status}</span>
            </div>
            <div className="flex items-center gap-3 mb-3">
              <span className="flex items-center gap-1 text-sm text-gray-500">
                <Icon className="w-4 h-4" /> {member.role}
              </span>
              {member.specialization && (
                <span className="text-sm text-gray-400">• {member.specialization}</span>
              )}
            </div>
            <div className="flex gap-6 text-sm">
              <div>
                <span className="text-gray-400">Performance</span>
                <span className="ml-2 font-semibold">{((member.performance_score || 0) * 100).toFixed(0)}%</span>
              </div>
              <div>
                <span className="text-gray-400">Completed Tasks</span>
                <span className="ml-2 font-semibold">{member.completed_tasks || 0}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Instructions */}
        <div className="panel-card">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">System Instructions</h3>
          <pre className="text-sm text-gray-600 whitespace-pre-wrap font-sans leading-relaxed bg-gray-50 p-4 rounded-lg max-h-64 overflow-y-auto">
            {member.system_instructions || 'Geen instructies ingesteld.'}
          </pre>
        </div>

        {/* Persona */}
        <div className="panel-card">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Persona</h3>
          <pre className="text-sm text-gray-600 whitespace-pre-wrap font-sans leading-relaxed bg-gray-50 p-4 rounded-lg max-h-64 overflow-y-auto">
            {member.persona || 'Geen persona ingesteld.'}
          </pre>
        </div>

        {/* Skills */}
        <div className="panel-card">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">
            <Sparkles className="w-5 h-5 inline mr-2 text-indigo-500" />
            Skills ({skills.length})
          </h3>
          {skills.length === 0 ? (
            <p className="text-sm text-gray-400 italic">Geen skills toegewezen.</p>
          ) : (
            <div className="space-y-2">
              {skills.map(skill => (
                <div key={skill.skill_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <span className="font-medium text-gray-800 text-sm">{skill.name}</span>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-gray-400">{skill.domain}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded font-semibold ${
                        skill.skill_type === 'technique' ? 'bg-blue-100 text-blue-700' :
                        skill.skill_type === 'voice' ? 'bg-pink-100 text-pink-700' :
                        skill.skill_type === 'anti-patterns' ? 'bg-red-100 text-red-700' :
                        'bg-green-100 text-green-700'
                      }`}>{skill.skill_type}</span>
                    </div>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded font-semibold ${
                    skill.proficiency === 'expert' ? 'bg-green-100 text-green-700' :
                    skill.proficiency === 'competent' ? 'bg-blue-100 text-blue-700' :
                    'bg-yellow-100 text-yellow-700'
                  }`}>{skill.proficiency}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Details */}
        <div className="panel-card">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Details</h3>
          <div className="space-y-4 text-sm">
            {member.hiring_logic && (
              <div>
                <span className="font-medium text-gray-500">Hiring Logic</span>
                <p className="text-gray-700 mt-1">{member.hiring_logic}</p>
              </div>
            )}
            {member.quality_notes && (
              <div>
                <span className="font-medium text-gray-500">Quality Notes</span>
                <p className="text-gray-700 mt-1">{member.quality_notes}</p>
              </div>
            )}
            {member.development_notes && (
              <div>
                <span className="font-medium text-gray-500">Development Notes</span>
                <p className="text-gray-700 mt-1">{member.development_notes}</p>
              </div>
            )}
            {(member.knowledge_base_sources || []).length > 0 && (
              <div>
                <span className="font-medium text-gray-500">Knowledge Sources</span>
                <ul className="list-disc list-inside mt-1 text-gray-700">
                  {member.knowledge_base_sources.map((src, i) => (
                    <li key={i}>{typeof src === 'string' ? src : (src.url || JSON.stringify(src))}</li>
                  ))}
                </ul>
              </div>
            )}
            {(member.tool_access_whitelist || []).length > 0 && (
              <div>
                <span className="font-medium text-gray-500">Tool Access</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {member.tool_access_whitelist.map((tool, i) => (
                    <span key={i} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{typeof tool === 'string' ? tool : JSON.stringify(tool)}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
