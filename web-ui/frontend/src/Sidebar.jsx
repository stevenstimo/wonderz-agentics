import { Home, Users, Layers, ClipboardList, Settings, PlusCircle } from 'lucide-react'

const menu = [
  { label: 'Personal Projects', icon: Home },
  { label: 'Main Workspace', icon: Layers, active: true },
  { label: 'Work Team Org', icon: Users },
  { label: 'Study', icon: ClipboardList },
  { label: 'AI Agents Description', icon: Users },
  { label: 'Product Management', icon: ClipboardList },
]

export default function Sidebar() {
  return (
    <aside className="bg-white border-r min-h-screen w-64 flex flex-col py-6 px-4">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center">
            <Users className="w-6 h-6 text-indigo-600" />
          </div>
          <span className="font-bold text-xl text-gray-800">MY WORKSPACE</span>
        </div>
        <nav className="space-y-2">
          {menu.map(item => (
            <div key={item.label} className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer ${item.active ? 'bg-indigo-50 text-indigo-700 font-semibold' : 'text-gray-700 hover:bg-gray-100'}`}>
              <item.icon className="w-5 h-5" />
              <span>{item.label}</span>
            </div>
          ))}
        </nav>
      </div>
      <div className="mt-auto">
        <button className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg w-full font-semibold hover:bg-indigo-700 transition-all">
          <PlusCircle className="w-5 h-5" />
          Add New
        </button>
        <div className="flex items-center gap-2 mt-6 text-gray-400 text-xs">
          <Settings className="w-4 h-4" />
          Settings
        </div>
      </div>
    </aside>
  )
}
