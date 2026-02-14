import { useEffect, useState } from 'react'
import { User, Shield, Code, FileText, Zap, Container } from 'lucide-react'
import { fetchJsonStrict } from './apiClient'

const roleIcons = {
  'Product Owner': FileText,
  'Developer': Code,
  'Reviewer': Shield,
  'DevOps': Container,
  'AI': Zap,
}

export default function CrewOverviewLive() {
  const [crew, setCrew] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchJsonStrict('/api/crew')
      .then(setCrew)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div>Loading crew...</div>
  if (error) return <div className="text-red-600">Error: {error}</div>

  return (
    <div className="bg-white rounded-xl shadow-lg p-8 mb-8">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">Crew Members</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {crew.map(member => {
          const Icon = roleIcons[member.role] || User
          return (
            <div key={member.id} className={`flex items-center gap-4 p-4 rounded-lg border shadow-sm bg-gray-50`}>
              <div className="flex-shrink-0">
                <Icon className="w-10 h-10 text-indigo-500" />
              </div>
              <div className="flex-1">
                <div className="font-semibold text-lg">{member.name}</div>
                <div className="text-xs font-medium mb-1">{member.role}</div>
                <div className="text-xs text-gray-500 mb-1">{member.current_task}</div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-indigo-400 to-indigo-600"
                    style={{ width: `${member.progress}%` }}
                  ></div>
                </div>
                <div className="text-xs text-gray-400 mt-1">Progress: {member.progress}%</div>
              </div>
              <div>
                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${member.status === 'active' ? 'bg-green-200 text-green-800' : member.status === 'busy' ? 'bg-yellow-200 text-yellow-800' : 'bg-gray-200 text-gray-800'}`}>{member.status}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
