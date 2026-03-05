import { useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import JobSplitView from './JobSplitView'

/**
 * Route: /jobs/new
 * - Redirects /jobs/new?job_id=X to /jobs/X
 * - Otherwise renders JobSplitView with no jobId (first message creates job and navigates to /jobs/:id)
 */
export default function NewJob() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const jobIdParam = searchParams.get('job_id')

  useEffect(() => {
    if (jobIdParam) navigate(`/jobs/${jobIdParam}`, { replace: true })
  }, [jobIdParam, navigate])

  if (jobIdParam) return null

  return <JobSplitView />
}
