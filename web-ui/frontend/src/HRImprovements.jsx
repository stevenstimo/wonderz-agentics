import { useEffect, useMemo, useState } from 'react'
import { MessageSquare, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import Sidebar from './Sidebar'

const commandList = new Set([
  'laat verbeter punten zien',
  'laat verbeterpunten zien',
])

export default function HRImprovements() {
  const [command, setCommand] = useState('')
  const [commandMessage, setCommandMessage] = useState('')
  const [improvements, setImprovements] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState({})

  const grouped = useMemo(() => {
    return improvements.reduce((acc, item) => {
      if (!acc[item.agent_id]) {
        acc[item.agent_id] = {
          agent_id: item.agent_id,
          agent_name: item.agent_name,
          items: [],
        }
      }
      acc[item.agent_id].items.push(item)
      return acc
    }, {})
  }, [improvements])

  const fetchImprovements = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/improvements`)
      if (!res.ok) throw new Error('Failed to fetch improvements')
      const data = await res.json()
      setImprovements(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchImprovements()
  }, [])

  const onSubmitCommand = (e) => {
    e.preventDefault()
    const normalized = command.trim().toLowerCase().replace(/\s+/g, ' ')
    if (commandList.has(normalized)) {
      setCommandMessage('HR manager: verbeterpunten worden getoond.')
      fetchImprovements()
    } else if (!normalized) {
      setCommandMessage('')
    } else {
      setCommandMessage('HR manager: commando niet herkend.')
    }
  }

  const toggleItem = (id) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const groupList = Object.values(grouped)

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex">
      <Sidebar />
      <main className="flex-1 px-8 py-8">
        <div className="max-w-6xl mx-auto">
          <div className="bg-white rounded-xl shadow-lg p-8 mb-8">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <h2 className="text-2xl font-bold text-gray-800">HR Verbeterpunten</h2>
                <p className="text-sm text-gray-500">Vraag de HR manager om verbeterpunten te tonen per agent.</p>
              </div>
              <button
                onClick={fetchImprovements}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
            </div>
            <form onSubmit={onSubmitCommand} className="mt-6 flex gap-3 flex-wrap">
              <div className="flex-1 min-w-[240px] relative">
                <MessageSquare className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  placeholder="Typ: laat verbeter punten zien"
                  className="w-full pl-9 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
              <button
                type="submit"
                className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm hover:bg-gray-800 transition"
              >
                Stuur naar HR
              </button>
            </form>
            {commandMessage && (
              <div className="mt-3 text-sm text-indigo-700">{commandMessage}</div>
            )}
          </div>

          <div className="bg-white rounded-xl shadow-lg p-8">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-semibold text-gray-800">Verbeterpunten per agent</h3>
              {loading && <span className="text-sm text-gray-400">Loading...</span>}
            </div>
            {error && <div className="text-sm text-red-600">Error: {error}</div>}
            {!error && !loading && groupList.length === 0 && (
              <div className="text-sm text-gray-500">Geen verbeterpunten gevonden.</div>
            )}
            <div className="space-y-6">
              {groupList.map(group => (
                <div key={group.agent_id} className="border rounded-lg p-5">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <div className="text-lg font-semibold text-gray-800">{group.agent_name}</div>
                      <div className="text-xs text-gray-500">Agent ID: {group.agent_id}</div>
                    </div>
                    <div className="text-xs font-semibold px-2 py-1 rounded-full bg-indigo-50 text-indigo-700">
                      {group.items.length} verbeterpunt(en)
                    </div>
                  </div>
                  <div className="space-y-3">
                    {group.items.map(item => {
                      const isOpen = !!expanded[item.id]
                      return (
                        <div key={item.id} className="bg-gray-50 rounded-lg p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="font-semibold text-gray-800">{item.title}</div>
                              {item.summary && (
                                <div className="text-sm text-gray-600 mt-1">{item.summary}</div>
                              )}
                              <div className="flex items-center gap-2 mt-2">
                                {item.severity && (
                                  <span className="text-xs px-2 py-1 rounded-full bg-red-50 text-red-700">
                                    {item.severity}
                                  </span>
                                )}
                                {item.status && (
                                  <span className="text-xs px-2 py-1 rounded-full bg-gray-200 text-gray-700">
                                    {item.status}
                                  </span>
                                )}
                              </div>
                            </div>
                            <button
                              onClick={() => toggleItem(item.id)}
                              className="text-xs px-3 py-2 rounded-lg bg-white border hover:bg-gray-100 transition"
                            >
                              {isOpen ? 'Lees minder' : 'Lees meer'}
                              {isOpen ? (
                                <ChevronUp className="inline w-3 h-3 ml-1" />
                              ) : (
                                <ChevronDown className="inline w-3 h-3 ml-1" />
                              )}
                            </button>
                          </div>
                          {isOpen && (
                            <div className="mt-3 text-sm text-gray-700 whitespace-pre-line">
                              {item.details || 'Geen extra details beschikbaar.'}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
