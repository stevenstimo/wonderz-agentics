/**
 * Hiring Hall — entry point for hiring new crew.
 * Crew Intelligent: zie docs/cursor/02_dashboard_newbies_navigation.md.
 */
import { Link } from 'react-router-dom'
import PageLayout from './PageLayout'
import { UserPlus } from 'lucide-react'

export default function HiringHall() {
  return (
    <PageLayout size="medium" padded>
      <div className="panel-card">
        <h1 className="page-title flex items-center gap-2">
          <UserPlus className="w-6 h-6" />
          Hiring Hall
        </h1>
        <p className="text-slate-600 mt-2">
          Beheer kandidaten (NewBies) en promoveer ze naar actieve agents.
        </p>
        <Link
          to="/newbies"
          className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium"
        >
          Naar Newbies →
        </Link>
      </div>
    </PageLayout>
  )
}
