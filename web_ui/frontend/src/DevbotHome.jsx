import { useSearchParams } from 'react-router-dom'
import { Brain, Sparkles, Hammer, Target } from 'lucide-react'
import Sidebar from './Sidebar'
import DaveDevConsole from './DaveDevConsole'
import AlexDevConsole from './AlexDevConsole'

const agents = [
  {
    id: 'alex',
    name: 'Alex Dev',
    description: 'Frontend Engineer',
    persona:
      'Pragmatic frontend specialist focused on stable layouts, clean components, and consistent UX.',
    quality:
      'Strong at UI consistency, component refactors, and practical frontend debugging with clear code-level fixes.',
    development:
      'Should continue improving cross-agent communication for coordinated frontend/backend execution.',
  },
  {
    id: 'dave',
    name: 'Dave Dev',
    description: 'Technical Consultant & Chief Architect',
    persona:
      'Direct, pragmatic engineer focused on shipping robust systems with clear tradeoffs and maintainable architecture.',
    quality:
      'Strong at root-cause analysis, API/frontend alignment, and translating requirements into concrete implementation plans.',
    development:
      'Should continue improving communication for non-technical stakeholders when presenting deep technical decisions.',
  },
]

export default function DevbotHome() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedAgent = searchParams.get('agent')

  const handleSelectAgent = (agentId) => {
    setSearchParams({ agent: agentId })
  }

  const agent = agents.find(a => a.id === selectedAgent)

  return (
    <div className="dashboard-container">
      <Sidebar />
      <main className="content-area">
        <div className="max-w-5xl mx-auto space-y-6">
          {!selectedAgent ? (
            <div className="space-y-6">
              <div className="panel-card">
                <h1 className="page-title">Devbot Agents</h1>
                <p className="page-subtitle">Selecteer een agent om te starten.</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {agents.map(a => (
                  <button
                    key={a.id}
                    onClick={() => handleSelectAgent(a.id)}
                    className="panel-card hover:shadow-lg transition-all text-left cursor-pointer space-y-4"
                  >
                    <div>
                      <h2 className="page-title mb-1">{a.name}</h2>
                      <p className="text-sm text-slate-600">{a.description}</p>
                    </div>
                    <div className="grid grid-cols-1 gap-2 text-xs text-slate-600">
                      <div className="rounded-lg bg-slate-50 px-3 py-2">
                        <div className="font-semibold text-slate-800 flex items-center gap-1"><Brain className="w-3 h-3" /> Persona</div>
                        <p className="mt-1 line-clamp-2">{a.persona}</p>
                      </div>
                      <div className="rounded-lg bg-slate-50 px-3 py-2">
                        <div className="font-semibold text-slate-800 flex items-center gap-1"><Sparkles className="w-3 h-3" /> Kwaliteiten</div>
                        <p className="mt-1 line-clamp-2">{a.quality}</p>
                      </div>
                      <div className="rounded-lg bg-slate-50 px-3 py-2">
                        <div className="font-semibold text-slate-800 flex items-center gap-1"><Target className="w-3 h-3" /> Ontwikkeling</div>
                        <p className="mt-1 line-clamp-2">{a.development}</p>
                      </div>
                    </div>
                    <div className="inline-flex items-center gap-1 text-indigo-600 text-sm font-semibold">
                      <Hammer className="w-4 h-4" /> Open Agent
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : agent ? (
            <div className="space-y-4">
              <div className="panel-card flex items-center justify-between">
                <div>
                  <h1 className="page-title">{agent.name}</h1>
                  <p className="page-subtitle">{agent.description}</p>
                </div>
                <button
                  onClick={() => setSearchParams({})}
                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg text-sm font-semibold"
                >
                  ← Back
                </button>
              </div>

              {agent.id === 'dave' && <DaveDevConsole />}
              {agent.id === 'alex' && <AlexDevConsole />}
            </div>
          ) : (
            <div className="panel-card">
              <p className="text-slate-600">Agent not found</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
