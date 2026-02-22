import { useEffect, useState } from 'react'
import { apiBase as API } from '../apiBase'

export function HiringRequestBanner({ jobId }) {
  const [hiringRequest, setHiringRequest] = useState(null)

  useEffect(() => {
    if (!jobId) return

    fetch(API + '/api/jobs/' + jobId)
      .then(r => r.json())
      .then(data => {
        let context = data.job?.context
        if (typeof context === 'string') {
          try { context = JSON.parse(context) } catch { context = {} }
        }
        if (context?.hiring_request) {
          setHiringRequest(context.hiring_request)
        } else {
          setHiringRequest(null)
        }
      })
      .catch(() => setHiringRequest(null))
  }, [jobId])

  if (!hiringRequest) return null

  return (
    <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4 rounded">
      <div className="flex">
        <div className="flex-shrink-0">
          <svg className="h-5 w-5 text-yellow-500" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
        </div>
        <div className="ml-3">
          <h3 className="text-sm font-medium text-yellow-800">
            Missing Agent Capability
          </h3>
          <div className="mt-2 text-sm text-yellow-700">
            <p>{hiringRequest.message}</p>
            <p className="mt-1">
              Required role: <strong>{hiringRequest.required_role}</strong>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
