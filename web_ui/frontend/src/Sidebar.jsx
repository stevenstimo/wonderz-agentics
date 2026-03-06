import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Briefcase,
  Users,
  UsersRound,
  BookOpen,
  GraduationCap,
  FileText,
  Activity,
  Settings,
  Zap,
  Menu,
  X,
} from 'lucide-react'
import { supabase } from './supabase'
import { getCurrentUserRole, isSuperAdmin } from './authz'

const WORKSPACE = [
  { label: 'Dashboard', icon: LayoutDashboard, path: '/' },
  { label: 'Job Center', icon: Briefcase, path: '/job-center' },
]

const MANAGEMENT = [
  { label: 'Agents', icon: Users, path: '/agents' },
  { label: 'Crew', icon: UsersRound, path: '/crew' },
  { label: 'Skills Library', icon: BookOpen, path: '/skills-library' },
  { label: 'Training Hub', icon: GraduationCap, path: '/training/management' },
]

const KNOWLEDGE = [
  { label: 'Explainer', icon: FileText, path: '/explainer/how-it-works' },
]

const SYSTEM = [
  { label: 'Status', icon: Activity, path: '/status' },
  { label: 'Settings', icon: Settings, path: '/settings' },
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
  const name = displayName(user).trim()
  if (!name) return '?'
  const parts = name.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  return name.charAt(0).toUpperCase()
}

function NavItem({ item }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.path}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2 rounded-lg text-slate-300 transition-colors ${
          isActive
            ? 'bg-slate-800 text-white border-l-2 border-indigo-500 pl-[10px]'
            : 'hover:bg-slate-800 hover:text-white'
        }`
      }
    >
      <Icon className="w-[18px] h-[18px] flex-shrink-0" />
      <span className="text-sm font-medium">{item.label}</span>
    </NavLink>
  )
}

export default function Sidebar() {
  const [user, setUser] = useState(null)
  const [role, setRole] = useState('member')
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

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
    <>
      {/* Mobile toggle */}
      <button
        type="button"
        onClick={() => setMobileOpen((o) => !o)}
        className="lg:hidden fixed top-[60px] left-3 z-40 p-2 rounded-lg bg-slate-800 text-white border border-slate-700"
        aria-label="Toggle menu"
      >
        {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      <aside
        className={`fixed top-[var(--top-header-height,56px)] left-0 z-30 w-56 h-[calc(100vh-var(--top-header-height,56px))] bg-slate-900 flex flex-col overflow-y-auto overflow-x-hidden border-r border-slate-800 transition-transform duration-200 lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex flex-col flex-1 min-h-0 p-3">
          {/* Logo */}
          <div className="flex items-center gap-2 mb-6 px-2 pt-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="text-white font-semibold text-base">Wonderz</div>
              <div className="text-xs text-slate-400">AI Content Bureau</div>
            </div>
          </div>

          <nav className="space-y-1 flex-1">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 px-3 mb-2">Workspace</div>
            {WORKSPACE.map((item) => (
              <NavItem key={item.label} item={item} isActive={isActive(item.path)} />
            ))}

            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 px-3 mt-4 mb-2">Management</div>
            {MANAGEMENT.map((item) => (
              <NavItem key={item.label} item={item} isActive={isActive(item.path)} />
            ))}

            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 px-3 mt-4 mb-2">Knowledge</div>
            {KNOWLEDGE.map((item) => (
              <NavItem key={item.label} item={item} isActive={isActive(item.path)} />
            ))}

            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 px-3 mt-4 mb-2">System</div>
            <NavItem item={SYSTEM[0]} isActive={isActive(SYSTEM[0].path)} />
            {canManageSettings && <NavItem item={SYSTEM[1]} isActive={isActive(SYSTEM[1].path)} />}
          </nav>

          {/* User profile at bottom */}
          <div className="mt-auto pt-4 border-t border-slate-800">
            <Link
              to="/my-account"
              onClick={() => setMobileOpen(false)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-800 transition-colors"
            >
              <div className="w-9 h-9 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-semibold flex-shrink-0">
                {initials(user)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-white truncate">{displayName(user)}</div>
                <div className="text-xs text-slate-400 truncate">{user?.email || 'Not signed in'}</div>
                <div className="text-[10px] text-slate-500 uppercase tracking-wide">{role}</div>
              </div>
            </Link>
          </div>
        </div>
      </aside>
    </>
  )
}
