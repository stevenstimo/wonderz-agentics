import { useState } from 'react'
import { Link } from 'react-router-dom'

export default function MobileNav() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="md:hidden p-2 rounded-lg border border-gray-200 bg-white"
        aria-label="Open navigation"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="fixed inset-0 bg-black/50" onClick={() => setIsOpen(false)} />
          <div className="fixed right-0 top-0 h-full w-64 bg-white shadow-lg p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="font-semibold text-gray-900">Navigation</div>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="text-sm text-gray-500"
              >
                Close
              </button>
            </div>
            <nav className="space-y-4">
              <Link to="/agents" className="block py-2" onClick={() => setIsOpen(false)}>Agents</Link>
              <Link to="/job-center" className="block py-2" onClick={() => setIsOpen(false)}>Jobs</Link>
              <Link to="/hr" className="block py-2" onClick={() => setIsOpen(false)}>HR Dashboard</Link>
            </nav>
          </div>
        </div>
      )}
    </>
  )
}
