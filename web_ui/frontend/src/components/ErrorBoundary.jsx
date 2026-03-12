import React from 'react'

/**
 * Catches render errors in the component tree and shows a fallback UI
 * instead of a white screen. Used globally and per dynamic route.
 */
class ErrorBoundary extends React.Component {
  state = {
    hasError: false,
    error: null,
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo)
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    const { error } = this.state
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
        <div className="panel-card bg-white shadow-sm border border-slate-200 rounded-xl p-8 max-w-md w-full text-center">
          <h1 className="text-xl font-semibold text-slate-900 mb-2">
            Er ging iets mis
          </h1>
          <p className="text-slate-600 text-sm mb-6">
            Een onderdeel kon niet worden geladen. Dit is geen probleem met je data.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition"
            >
              Probeer opnieuw
            </button>
            <a
              href="/dashboard"
              className="px-4 py-2.5 rounded-lg border border-slate-300 text-slate-700 font-medium hover:bg-slate-50 transition inline-block"
            >
              Terug naar dashboard
            </a>
          </div>
          {process.env.NODE_ENV === 'development' && error?.message && (
            <pre className="mt-6 p-4 bg-slate-100 rounded-lg text-left text-xs text-slate-700 overflow-auto max-h-32">
              {error.message}
            </pre>
          )}
        </div>
      </div>
    )
  }
}

export default ErrorBoundary
