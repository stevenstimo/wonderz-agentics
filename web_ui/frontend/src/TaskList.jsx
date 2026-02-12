import { User, Shield, Code, FileText, Zap, Container } from 'lucide-react'

// Demo data: taken met crewleden en hun aandeel (%)
const tasks = [
  {
    id: 't1',
    title: 'Catalogus Structuur Ontwerpen',
    status: 'in_progress',
    crew: [
      { id: 'pm', name: 'Product Manager', role: 'Product Owner', icon: FileText, color: 'bg-blue-100 text-blue-700', share: 60 },
      { id: 'dev', name: 'Shopify Developer', role: 'Developer', icon: Code, color: 'bg-green-100 text-green-700', share: 40 },
    ],
  },
  {
    id: 't2',
    title: 'Liquid Templates Bouwen',
    status: 'completed',
    crew: [
      { id: 'dev', name: 'Shopify Developer', role: 'Developer', icon: Code, color: 'bg-green-100 text-green-700', share: 80 },
      { id: 'ai', name: 'AI Agent', role: 'AI', icon: Zap, color: 'bg-yellow-100 text-yellow-700', share: 20 },
    ],
  },
  {
    id: 't3',
    title: 'SEO Optimalisatie',
    status: 'pending',
    crew: [
      { id: 'review', name: 'Reviewer', role: 'Reviewer', icon: Shield, color: 'bg-purple-100 text-purple-700', share: 50 },
      { id: 'ai', name: 'AI Agent', role: 'AI', icon: Zap, color: 'bg-yellow-100 text-yellow-700', share: 50 },
    ],
  },
]

export default function TaskList() {
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
              {task.crew.map(member => (
                <div key={member.id} className={`flex items-center gap-2 px-3 py-2 rounded-lg ${member.color} shadow-sm`}>
                  <member.icon className="w-5 h-5" />
                  <span className="font-medium text-sm">{member.name}</span>
                  <span className="text-xs text-gray-500">({member.role})</span>
                  <span className="ml-2 text-xs font-bold text-indigo-700">{member.share}%</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
