import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageLayout from './PageLayout'
import {
  Layers, ClipboardList, Users, Code, PlusCircle,
  Activity, Briefcase, ArrowRight, Zap
} from 'lucide-react'

const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8090'

export default function Dashboard() {
  const [recentJobs, setRecentJobs] = useState([])
  const [stats, setStats] = useState({ total: 0, running: 0, ready: 0 })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await fetch(`${apiBase}/api/jobs`)
        if (res.ok) {
          const data = await res.json()
          const jobs = Array.isArray(data) ? data : data.jobs || []
          setRecentJobs(jobs.slice(0, 5))
          setStats({
            total: jobs.length,
            running: jobs.filter(j => j.status === 'RUNNING' || j.status === 'INTAKE_CLARIFICATION').length,
            ready: jobs.filter(j => j.status === 'JOB_READY' || j.status === 'COMPLETED').length,
          })
        }
      } catch (e) {
        console.error('Failed to fetch jobs:', e)
      } finally {
        setLoading(false)
      }
    }
    fetchJobs()
  }, [])

  const statusColor = (status) => {
    const colors = {
      JOB_READY: 'bg-green-100 text-green-700',
      COMPLETED: 'bg-green-100 text-green-700',
      RUNNING: 'bg-blue-100 text-blue-700',
      INTAKE_CLARIFICATION: 'bg-yellow-100 text-yellow-700',
      PLAN_PROPOSED: 'bg-purple-100 text-purple-700',
      FAILED: 'bg-red-100 text-red-700',
    }
    return colors[status] || 'bg-gray-100 text-gray-700'
  }

  return (
    <PageLayout size="wide" padded>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">Welcome to Wonderz Agentics — your AI crew management platform</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <Briefcase className="w-5 h-5 text-indigo-600" />
            <span className="text-sm font-medium text-indigo-600">Total Missions</span>
          </div>
          <p className="text-3xl font-bold text-indigo-900">{stats.total}</p>
        </div>
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-5 h-5 text-blue-600" />
            <span className="text-sm font-medium text-blue-600">In Progress</span>
          </div>
          <p className="text-3xl font-bold text-blue-900">{stats.running}</p>
        </div>
        <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <Zap className="w-5 h-5 text-green-600" />
            <span className="text-sm font-medium text-green-600">Completed</span>
          </div>
          <p className="text-3xl font-bold text-green-900">{stats.ready}</p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <Link
          to="/jobs/new"
          className="flex items-center gap-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl p-6 shadow-lg hover:shadow-xl transition-all hover:scale-[1.01]"
        >
          <PlusCircle className="w-8 h-8" />
          <div>
            <h3 className="text-lg font-semibold">New Mission</h3>
            <p className="text-indigo-100 text-sm">Start a new AI-powered job</p>
          </div>
          <ArrowRight className="w-5 h-5 ml-auto" />
        </Link>
        <Link
          to="/job-center"
          className="flex items-center gap-4 bg-white border-2 border-indigo-200 text-indigo-700 rounded-xl p-6 shadow-sm hover:shadow-md transition-all hover:scale-[1.01]"
        >
          <ClipboardList className="w-8 h-8" />
          <div>
            <h3 className="text-lg font-semibold">Job Center</h3>
            <p className="text-gray-500 text-sm">View all missions and crew status</p>
          </div>
          <ArrowRight className="w-5 h-5 ml-auto" />
        </Link>
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Agents', icon: Users, path: '/agents', color: 'text-blue-600 bg-blue-50' },
          { label: 'Crew', icon: Users, path: '/crew', color: 'text-purple-600 bg-purple-50' },
          { label: 'Dev Bot', icon: Code, path: '/devbot', color: 'text-green-600 bg-green-50' },
          { label: 'Settings', icon: Layers, path: '/settings', color: 'text-gray-600 bg-gray-50' },
        ].map((item) => (
          <Link
            key={item.label}
            to={item.path}
            className={`flex flex-col items-center gap-2 rounded-xl p-4 ${item.color} hover:shadow-md transition-all`}
          >
            <item.icon className="w-6 h-6" />
            <span className="text-sm font-medium">{item.label}</span>
          </Link>
        ))}
      </div>

      {/* Recent Missions */}
      <div className="panel-card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-800">Recent Missions</h2>
          <Link to="/job-center" className="text-indigo-600 hover:underline text-sm font-medium">
            View all →
          </Link>
        </div>
        {loading ? (
          <p className="text-gray-400 text-center py-8">Loading...</p>
        ) : recentJobs.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-400 mb-4">No missions yet</p>
            <Link
              to="/jobs/new"
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              <PlusCircle className="w-4 h-4" />
              Start your first mission
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {recentJobs.map((job) => (
              <Link
                key={job.id}
                to={`/jobs/new?job_id=${job.id}`}
                className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition"
              >
                <div>
                  <p className="font-medium text-gray-800">
                    {job.context?.brief?.project_description ||
                     job.context?.brief?.raw_idea ||
                     job.job_type || 'Untitled Mission'}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(job.created_at).toLocaleDateString('nl-NL', {
                      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
                    })}
                  </p>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColor(job.status)}`}>
                  {job.status}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </PageLayout>
  )
}
