import { useEffect, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { Home, Users, Layers, ClipboardList, Settings, PlusCircle, BookOpen, Shield, Code, Activity } from 'lucide-react'
import { supabase } from './supabase'
import { getCurrentUserRole, isSuperAdmin } from './authz'

const primaryMenu = [
  { label: 'Mission Control', icon: Layers, path: '/dashboard' },
  { label: 'Job Center', icon: ClipboardList, path: '/job-center' },
]

const managementMenu = [
  { label: 'Crew', icon: Users, path: '/crew' },
  { label: 'Talents', icon: Users, path: '/talents' },
  { label: 'Training Hub', icon: ClipboardList, path: '/training' },
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

function displayName(user) {
  return (
    user?.user_metadata?.full_name ||
    user?.user_metadata?.name ||
    user?.email ||
    'Guest'
  )
}

function initials(user) {
  return displayName(user).trim().charAt(0).toUpperCase()
}

export default function Sidebar() {
  const [user, setUser] = useState(null)
  const [role, setRole] = useState('member')

  useEffect(() => {
    let active = true

    const sync = async () => {
      const { data } = await supabase.auth.getSession()
      const sessionUser = data?.session?.user || null
      if (!active) return
      setUser(sessionUser)

      try {
        const ctx = await getCurrentUserRole()
        if (active) setRole(ctx.role || 'member')
      } catch {
        if (active) setRole('member')
      }
    }

    sync()

    const { data: listener } = supabase.auth.onAuthStateChange(async (_event, session) => {
      setUser(session?.user || null)
      try {
        const ctx = await getCurrentUserRole()
        setRole(ctx.role || 'member')
      } catch {
        setRole('member')
      }
    })

    return () => {
      active = false
      listener.subscription.unsubscribe()
    }
  }, [])

  const canManageSettings = isSuperAdmin(role)

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
          {primaryMenu.map((item) => (
            <NavLink
              key={item.label}
              to={item.path}
              className={({ isActive }) => `nav-item ${isActive ? 'nav-item-active' : ''}`}
            >
              <item.icon className="w-5 h-5" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="nav-section-title">Management</div>
        <nav className="space-y-2">
          {managementMenu.map((item) => (
            item.path ? (
              <NavLink
                key={item.label}
                to={item.path}
                className={({ isActive }) => `nav-item ${isActive ? 'nav-item-active' : ''}`}
              >
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </NavLink>
            ) : (
              <div key={item.label} className="nav-item">
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </div>
            )
          ))}
        </nav>

        <div className="nav-section-title">Knowledge</div>
        <nav className="space-y-2">
          {secondaryMenu.map((item) => (
            item.children ? (
              <div key={item.label} className="space-y-1">
                <div className="nav-item">
                  <item.icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </div>
                <div className="space-y-1 pl-4">
                  {item.children.map((child) => (
                    <NavLink
                      key={child.label}
                      to={child.path}
                      className={({ isActive }) => `nav-item text-sm ${isActive ? 'nav-item-active' : ''}`}
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
                className={({ isActive }) => `nav-item ${isActive ? 'nav-item-active' : ''}`}
              >
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </NavLink>
            ) : (
              <div key={item.label} className="nav-item">
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </div>
            )
          ))}
        </nav>
      </div>

      <div className="mt-auto space-y-3">
        <Link to="/my-account" className="block rounded-lg border border-gray-200 bg-white p-3 hover:bg-gray-50 transition">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-sm font-semibold">
              {initials(user)}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-gray-900 truncate">{displayName(user)}</div>
              <div className="text-xs text-gray-500 truncate">{user?.email || 'Not signed in'} - {role}</div>
            </div>
          </div>
        </Link>

        <NavLink
          to="/status"
          className={({ isActive }) => `nav-item ${isActive ? 'nav-item-active' : ''}`}
        >
          <Activity className="w-5 h-5" />
          <span>Status</span>
        </NavLink>

        <NavLink to="/jobs/new" className="btn-manage w-full gap-2 flex items-center justify-center">
          <PlusCircle className="w-5 h-5" />
          New Mission
        </NavLink>

        <NavLink to="/crew/new" className="btn-manage w-full gap-2 flex items-center justify-center">
          <PlusCircle className="w-5 h-5" />
          New Crew Member
        </NavLink>

        {canManageSettings && (
          <NavLink
            to="/settings"
            className={({ isActive }) => `nav-item ${isActive ? 'nav-item-active' : ''}`}
          >
            <Settings className="w-4 h-4" />
            <span>Settings</span>
          </NavLink>
        )}
      </div>
    </aside>
  )
}
