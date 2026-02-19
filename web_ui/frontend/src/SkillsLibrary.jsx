import { useState, useEffect } from 'react'
import { apiBase } from './apiBase'
import './SkillsLibrary.css'

export default function SkillsLibrary() {
  const [skills, setSkills] = useState([])
  const [selectedSkill, setSelectedSkill] = useState(null)
  const [skillAgents, setSkillAgents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSkills()
  }, [])

  useEffect(() => {
    if (selectedSkill) {
      loadSkillAgents(selectedSkill.skill_id)
    }
  }, [selectedSkill])

  async function loadSkills() {
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/api/skills`)
      const data = await res.json()
      setSkills(data.skills || [])
    } catch (err) {
      console.error('Failed to load skills:', err)
    } finally {
      setLoading(false)
    }
  }

  async function loadSkillAgents(skillId) {
    try {
      const res = await fetch(`${apiBase}/api/skills/${encodeURIComponent(skillId)}/agents`)
      const data = await res.json()
      setSkillAgents(data.agents || [])
    } catch (err) {
      console.error('Failed to load skill agents:', err)
    }
  }

  if (loading) {
    return <div className="loading">Laden...</div>
  }

  return (
    <div className="skills-library">
      <h1>Skills Library</h1>
      <p className="subtitle">
        Domain-specific expertise modules voor agents
      </p>

      {/* Skills Grid */}
      <div className="skills-grid">
        {skills.map(skill => (
          <div
            key={skill.skill_id}
            className="skill-card"
            onClick={() => setSelectedSkill(skill)}
          >
            <div className="skill-header">
              <h3>{skill.name}</h3>
              <span className={`skill-type ${skill.skill_type}`}>
                {skill.skill_type}
              </span>
            </div>

            <div className="skill-meta">
              <span className="domain">{skill.domain}</span>
              <span className="success-rate">
                {skill.success_rate != null ? (skill.success_rate * 100).toFixed(0) : 50}% success
              </span>
              <span className="usage">
                {skill.usage_count || 0} uses
              </span>
            </div>

            <p className="skill-preview">
              {(skill.content || '').substring(0, 150)}...
            </p>
          </div>
        ))}
      </div>

      {/* Skill Detail Modal */}
      {selectedSkill && (
        <div className="modal-overlay" onClick={() => setSelectedSkill(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <button
              className="modal-close"
              onClick={() => setSelectedSkill(null)}
            >
              ✕
            </button>

            <div className="skill-detail">
              <div className="skill-detail-header">
                <h2>{selectedSkill.name}</h2>
                <span className={`skill-type-badge ${selectedSkill.skill_type}`}>
                  {selectedSkill.skill_type}
                </span>
              </div>

              <div className="skill-stats-grid">
                <div className="stat-card">
                  <label>Domain</label>
                  <span>{selectedSkill.domain}</span>
                </div>
                <div className="stat-card">
                  <label>Success Rate</label>
                  <span>{selectedSkill.success_rate != null ? (selectedSkill.success_rate * 100).toFixed(1) : '50.0'}%</span>
                </div>
                <div className="stat-card">
                  <label>Usage Count</label>
                  <span>{selectedSkill.usage_count || 0}</span>
                </div>
                <div className="stat-card">
                  <label>Version</label>
                  <span>v{selectedSkill.version || 1}</span>
                </div>
              </div>

              <div className="skill-content-section">
                <h3>Skill Content</h3>
                <pre className="markdown-content">
                  {selectedSkill.content}
                </pre>
              </div>

              <div className="skill-agents-section">
                <h3>Agents met deze skill ({skillAgents.length})</h3>
                {skillAgents.length === 0 ? (
                  <p className="no-agents">Nog geen agents met deze skill</p>
                ) : (
                  <div className="agents-list">
                    {skillAgents.map(agent => (
                      <div key={agent.agent_id} className="agent-item">
                        <span className="agent-name">{agent.name}</span>
                        <span className="agent-role">{agent.role}</span>
                        <span className={`proficiency ${agent.proficiency}`}>
                          {agent.proficiency}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
