import { User, Shield, Code, FileText, Zap, Container } from 'lucide-react'

const crewMembers = [
  {
    id: 'pm',
    name: 'Product Manager',
    role: 'Product Owner',
    icon: FileText,
    color: 'bg-blue-100 text-blue-700',
    status: 'active',
    currentTask: 'Catalog design',
    progress: 80,
  },
  {
    id: 'dev',
    name: 'Shopify Developer',
    role: 'Developer',
    icon: Code,
    color: 'bg-green-100 text-green-700',
    status: 'busy',
    currentTask: 'Implement Liquid templates',
    progress: 60,
  },
  {
    id: 'review',
    name: 'Reviewer',
    role: 'Reviewer',
    icon: Shield,
    color: 'bg-purple-100 text-purple-700',
    status: 'idle',
    currentTask: 'Waiting for review',
    progress: 0,
  },
  {
    id: 'devops',
    name: 'DevOps',
    role: 'DevOps',
    icon: Container,
    color: 'bg-orange-100 text-orange-700',
    status: 'active',
    currentTask: 'CI/CD setup',
    progress: 40,
  },
  {
    id: 'ai',
    name: 'AI Agent',
    role: 'AI',
    icon: Zap,
    color: 'bg-yellow-100 text-yellow-700',
    status: 'active',
    currentTask: 'Generating code',
    progress: 90,
  },
]

export default function CrewOverview() {
  return (
    <div className="bg-white rounded-xl shadow-lg p-8 mb-8">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">Crew Members</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {crewMembers.map(member => (
          <div key={member.id} className={`flex items-center gap-4 p-4 rounded-lg border ${member.color} shadow-sm`}>
            <div className="flex-shrink-0">
              <member.icon className="w-10 h-10" />
            </div>
            <div className="flex-1">
              <div className="font-semibold text-lg">{member.name}</div>
              <div className="text-xs font-medium mb-1">{member.role}</div>
              <div className="text-xs text-gray-500 mb-1">{member.currentTask}</div>
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
        ))}
      </div>
    </div>
  )
}
