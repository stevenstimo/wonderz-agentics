/**
 * Centered loading spinner for route-level data loading.
 * Matches existing UI (panel-card / Client laden... style).
 */
export default function PageLoader() {
  return (
    <div className="min-h-[40vh] flex items-center justify-center p-6">
      <div className="panel-card bg-white shadow-sm border border-slate-200 p-8 rounded-xl">
        <div className="flex flex-col items-center gap-3">
          <div
            className="w-8 h-8 border-2 border-slate-200 border-t-indigo-600 rounded-full animate-spin"
            aria-hidden
          />
          <p className="text-sm text-slate-500">Laden...</p>
        </div>
      </div>
    </div>
  )
}
