import { NavLink } from 'react-router-dom'
import { Home, Users, Layers, ClipboardList, Settings, PlusCircle, BookOpen, Shield, Code, Activity } from 'lucide-react'

const primaryMenu = [
  { label: 'Mission Control', icon: Layers, path: '/' },
  { label: 'Job Center', icon: ClipboardList, path: '/job-center' },
]

const managementMenu = [
  { label: 'Crew', icon: Users, path: '/crew/management' },
  { label: 'Talents', icon: Users, path: '/talents' },
  { label: 'Training Hub', icon: ClipboardList, path: '/training/management' },
  { label: 'Improvements', icon: ClipboardList, path: '/hr/improvements' },
  { label: 'Hiring Hall', icon: ClipboardList, path: '/hiring' },
  { label: 'Developer Bot', icon: Code, path: '/devbot' },
  { label: 'HR Feedback', icon: ClipboardList },
  { label: 'Safety Gate', icon: Shield, path: '/approvals' },
]

const secondaryMenu = [
  {
    label: 'Explainer',
    icon: BookOpen,
    children: [
      { label: 'How it works', path: '/explainer/how-it-works' },
      { label: 'Persona', path: '/explainer/persona' },
      { label: 'Crew', path: '/explainer/crew' },
    ],
  },
  { label: 'Personal Projects', icon: Home },
  { label: 'Work Team Org', icon: Users },
  { label: 'Study', icon: ClipboardList },
  { label: 'Product Management', icon: ClipboardList },
]

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div>
        <div className="flex items-center gap-3 mb-8">
          <div className="brand-mark">W</div>
          <div>
            <div className="text-lg font-semibold text-gray-900">Wonderz</div>
            <div className="text-xs text-gray-400">Unified Crew</div>
          </div>
        </div>

        <nav className="space-y-2">
          {primaryMenu.map(item => (
            <NavLink
              key={item.label}
              to={item.path}
              className={({ isActive }) => (
                `nav-item ${isActive ? 'nav-item-active' : ''}`
              )}
            >
              <item.icon className="w-5 h-5" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="nav-section-title">Management</div>
        <nav className="space-y-2">
          {managementMenu.map(item => (
            item.path ? (
              <NavLink
                key={item.label}
                to={item.path}
                className={({ isActive }) => (
                  `nav-item ${isActive ? 'nav-item-active' : ''}`
                )}
              >
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </NavLink>
            ) : (
              <div
                key={item.label}
                onClick={() => console.log(`Clicked: ${item.label}`)}
                className="nav-item"
              >
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </div>
            )
          ))}
        </nav>

        <div className="nav-section-title">Knowledge</div>
        <nav className="space-y-2">
          {secondaryMenu.map(item => (
            item.children ? (
              <div key={item.label} className="space-y-1">
                <div className="nav-item">
                  <item.icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </div>
                <div className="space-y-1 pl-4">
                  {item.children.map(child => (
                    <NavLink
                      key={child.label}
                      to={child.path}
                      className={({ isActive }) => (
                        `nav-item text-sm ${isActive ? 'nav-item-active' : ''}`
                      )}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-300" />
                      <span>{child.label}</span>
                    </NavLink>
                  ))}
                </div>
              </div>
            ) : item.path ? (
              <NavLink
                key={item.label}
                to={item.path}
                className={({ isActive }) => (
                  `nav-item ${isActive ? 'nav-item-active' : ''}`
                )}
              >
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </NavLink>
            ) : (
              <div
                key={item.label}
                onClick={() => console.log(`Clicked: ${item.label}`)}
                className="nav-item"
              >
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </div>
            )
          ))}
        </nav>
      </div>

      <div className="mt-auto">
        <NavLink
          to="/status"
          className={({ isActive }) => (
            `nav-item ${isActive ? 'nav-item-active' : ''}`
          )}
        >
          <Activity className="w-5 h-5" />
          <span>Status</span>
        </NavLink>
        <button
          onClick={() => console.log('Add New clicked')}
          className="btn-manage w-full gap-2"
        >
          <PlusCircle className="w-5 h-5" />
          New Mission
        </button>
        <NavLink
          to="/settings"
          className={({ isActive }) => (
            `nav-item mt-4 ${isActive ? 'nav-item-active' : ''}`
          )}
        >
          <Settings className="w-4 h-4" />
          <span>Settings</span>
        </NavLink>
      </div>
    </aside>
  )
}
