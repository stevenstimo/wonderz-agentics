import { useParams } from 'react-router-dom'
import ErrorBoundary from './ErrorBoundary'

/**
 * Wraps a route's element in an ErrorBoundary with key from route param,
 * so the boundary resets when navigating to a different :param value.
 */
export function RouteErrorBoundary({ paramKey, children }) {
  const params = useParams()
  const keyValue = params[paramKey] ?? 'default'
  return (
    <ErrorBoundary key={keyValue}>
      {children}
    </ErrorBoundary>
  )
}
