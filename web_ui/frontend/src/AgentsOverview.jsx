import { Navigate } from 'react-router-dom'

/**
 * Agents is now unified with Crew.
 * Redirect /agents → /crew for backward compatibility.
 */
export default function AgentsOverview() {
  return <Navigate to="/crew" replace />
}
