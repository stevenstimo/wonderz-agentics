import { useEffect } from 'react'
import { X } from 'lucide-react'

/**
 * Fullscreen celebration na hire of activatie van een agent.
 * Props: agentName, roleName, badge (nullable), onClose, visible
 */
export default function HireCelebration({
  agentName,
  roleName,
  badge,
  onClose,
  visible,
}) {
  useEffect(() => {
    if (!visible) return
    const id = window.setTimeout(() => {
      onClose()
    }, 4000)
    return () => window.clearTimeout(id)
  }, [visible, onClose])

  if (!visible) return null

  return (
    <>
      <style>{`
        @keyframes hire-celebration-backdrop {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes hire-celebration-card {
          from { opacity: 0; transform: scale(0.94) translateY(8px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
        .hire-celebration-backdrop-animate {
          animation: hire-celebration-backdrop 0.35s ease-out forwards;
        }
        .hire-celebration-card-animate {
          animation: hire-celebration-card 0.45s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        }
      `}</style>
      <div
        className="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-6 hire-celebration-backdrop-animate"
        role="dialog"
        aria-modal="true"
        aria-labelledby="hire-celebration-title"
      >
        <button
          type="button"
          className="absolute inset-0 bg-slate-950/70 backdrop-blur-[2px] cursor-default border-0 w-full h-full"
          aria-label="Sluit overlay"
          onClick={onClose}
        />
        <div
          className="relative w-full max-w-md rounded-2xl border border-slate-200/80 bg-white shadow-2xl shadow-slate-900/20 px-6 pt-8 pb-6 sm:px-8 hire-celebration-card-animate"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            onClick={onClose}
            className="absolute right-3 top-3 rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
            aria-label="Sluiten"
          >
            <X className="w-5 h-5" />
          </button>

          <p
            id="hire-celebration-title"
            className="text-center text-lg sm:text-xl font-semibold text-indigo-600 mb-1"
          >
            🎉 Welkom in het team
          </p>

          <h2 className="text-center text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight mt-3 break-words">
            {agentName || '—'}
          </h2>

          <p className="text-center text-base sm:text-lg font-medium text-slate-700 mt-2 break-words">
            {roleName || '—'}
          </p>

          {badge ? (
            <p className="text-center mt-3">
              <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 border border-slate-200/80">
                {badge}
              </span>
            </p>
          ) : null}

          <p className="text-center text-sm text-slate-500 mt-5 leading-relaxed">
            Een nieuwe crew member is aangenomen en klaar voor actie.
          </p>

          <p className="text-center text-xs text-slate-400 mt-4">
            Sluit automatisch over 4 seconden
          </p>
        </div>
      </div>
    </>
  )
}
