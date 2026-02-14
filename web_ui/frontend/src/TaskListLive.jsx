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

export default function TaskListLive() {
  const [tasks, setTasks] = useState([])
  const [crew, setCrew] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      fetchJsonStrict('/api/tasks'),
      fetchJsonStrict('/api/crew'),
    ])
      .then(([tasks, crew]) => {
        setTasks(tasks)
        setCrew(crew)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div>Loading tasks...</div>
  if (error) return <div className="text-red-600">Error: {error}</div>

  // Helper to get crew info by id
  const getCrew = id => crew.find(c => c.id === id) || {}

  return (
    <div className="bg-white rounded-xl shadow-lg p-8 mb-8">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">Taken & Crew Inzet</h2>
      <div className="space-y-6">
        {tasks.map(task => (
          <div key={task.id} className="border rounded-lg p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold text-lg text-gray-800">{task.title}</div>
              <span className={`px-3 py-1 rounded-full text-xs font-semibold ${task.status === 'completed' ? 'bg-green-200 text-green-800' : task.status === 'in_progress' ? 'bg-yellow-200 text-yellow-800' : 'bg-gray-200 text-gray-800'}`}>{task.status.replace('_', ' ')}</span>
            </div>
            <div className="flex flex-wrap gap-4 items-center mt-2">
              {task.crew.map(member => {
                const crewInfo = getCrew(member.crew_id)
                const Icon = roleIcons[crewInfo.role] || User
                return (
                  <div key={member.crew_id} className={`flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-100 shadow-sm`}>
                    <Icon className="w-5 h-5 text-indigo-500" />
                    <span className="font-medium text-sm">{crewInfo.name || member.crew_id}</span>
                    <span className="text-xs text-gray-500">({crewInfo.role})</span>
                    <span className="ml-2 text-xs font-bold text-indigo-700">{member.share}%</span>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
