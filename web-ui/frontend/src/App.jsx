import { supabase } from './supabase'
import { useState, useEffect, useRef } from 'react'
import UnifiedProducts from './UnifiedProducts'
import CrewOverviewLive from './CrewOverviewLive'
import TaskListLive from './TaskListLive'
import Sidebar from './Sidebar'
import { 
  Sparkles, Code, FileText, Shield, Container, 
  Loader2, CheckCircle, XCircle, Download, Zap 
} from 'lucide-react'

function App() {
  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const wsBase = (import.meta.env.VITE_WS_URL || apiBase).replace(/^http/, 'ws').replace(/\/$/, '')
  const stages = [
    { id: 'initialization', name: 'Initialization', icon: Sparkles, color: 'text-indigo-600' },
    { id: 'requirements', name: 'Requirements', icon: FileText, color: 'text-blue-600' },
    { id: 'development', name: 'Development', icon: Code, color: 'text-green-600' },
    { id: 'review', name: 'Review', icon: Shield, color: 'text-yellow-600' },
    { id: 'devops', name: 'DevOps', icon: Container, color: 'text-purple-600' },
  ]
  // State declarations
  const [projectIdea, setProjectIdea] = useState('')
  const [language, setLanguage] = useState('')
  const [platform, setPlatform] = useState('web')
  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState([])
  const [results, setResults] = useState(null)
  const [currentStage, setCurrentStage] = useState('')
  const ws = useRef(null)

  useEffect(() => {
    return () => {
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [])

useEffect(() => {
  const testConnection = async () => {
    const { data, error } = await supabase.from('test').select('*')
    console.log('Supabase test:', data, error)
  }

  testConnection()
}, [])



  const startWorkflow = async () => {
    if (!projectIdea.trim()) {
      alert('Please enter a project idea!')
      return
    }

await supabase.from('projects').insert([
  {
    project_idea: projectIdea,
    language: language,
    platform: platform,
    status: 'started'
  }
])

    setIsRunning(true)
    setProgress([])
    setResults(null)
    setCurrentStage('initialization')

    // Connect WebSocket
    ws.current = new WebSocket(`${wsBase}/ws`)

    ws.current.onopen = () => {
      // Send project data
      ws.current.send(JSON.stringify({
        type: 'start_workflow',
        data: {
          project_idea: projectIdea,
          language: language || null,
          platform: platform,
          max_review_iterations: 2
        }
      }))
    }

    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data)
      
      if (message.type === 'progress') {
        setProgress(prev => [...prev, message])
        setCurrentStage(message.stage)

        if (message.stage === 'complete' && message.status === 'success') {
          setResults(message.data.results)
          setIsRunning(false)
        }

        if (message.status === 'failed') {
          setIsRunning(false)
        }
      }
    }

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error)
      alert('Connection error. Make sure the backend is running.')
      setIsRunning(false)
    }

    ws.current.onclose = () => {
      console.log('WebSocket closed')
    }
  }

  const getStageStatus = (stageId) => {
    const stageProgress = progress.filter(p => p.stage === stageId)
    if (stageProgress.length === 0) return 'pending'
    const latest = stageProgress[stageProgress.length - 1]
    return latest.status
  }

  const downloadFile = (filename, content) => {
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex">
      {/* Sidebar */}
      <Sidebar />
      {/* Main content */}
      <main className="flex-1 px-8 py-8">
        <CrewOverviewLive />
        <TaskListLive />
        <UnifiedProducts />

        <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Input Section */}
        {!isRunning && !results && (
          <div className="bg-white rounded-xl shadow-lg p-8 mb-8">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">Start New Project</h2>
            
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Project Idea
                </label>
                <textarea
                  value={projectIdea}
                  onChange={(e) => setProjectIdea(e.target.value)}
                  placeholder="Describe your project idea... (e.g., A RESTful API for a todo-list app with user authentication)"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                  rows={4}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Programming Language
                  </label>
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  >
                    <option value="Python">Python</option>
                    <option value="JavaScript">JavaScript</option>
                    <option value="TypeScript">TypeScript</option>
                    <option value="Go">Go</option>
                    <option value="Rust">Rust</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Deployment Platform
                  </label>
                  <select
                    value={platform}
                    onChange={(e) => setPlatform(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  >
                    <option value="docker">Docker</option>
                    <option value="kubernetes">Kubernetes</option>
                    <option value="aws">AWS</option>
                    <option value="gcp">Google Cloud</option>
                    <option value="azure">Azure</option>
                  </select>
                </div>
              </div>

              <button
                onClick={startWorkflow}
                className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-4 px-6 rounded-lg font-semibold text-lg hover:from-indigo-700 hover:to-purple-700 transition-all shadow-lg hover:shadow-xl"
              >
                <Sparkles className="inline w-5 h-5 mr-2" />
                Generate Project
              </button>
            </div>
          </div>
        )}

        {/* Progress Section */}
        {isRunning && (
          <div className="bg-white rounded-xl shadow-lg p-8 mb-8">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">Building Your Project...</h2>
            
            <div className="space-y-4">
              {stages.map((stage) => {
                const status = getStageStatus(stage.id)
                const Icon = stage.icon
                
                return (
                  <div
                    key={stage.id}
                    className={`flex items-center gap-4 p-4 rounded-lg transition-all ${
                      currentStage === stage.id ? 'bg-indigo-50 border-2 border-indigo-300' : 'bg-gray-50'
                    }`}
                  >
                    <div className={`${stage.color}`}>
                      <Icon className="w-6 h-6" />
                    </div>
                    
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-800">{stage.name}</h3>
                      {status === 'in_progress' && (
                        <p className="text-sm text-gray-600">Working...</p>
                      )}
                      {status === 'completed' && (
                        <p className="text-sm text-green-600">Completed</p>
                      )}
                    </div>

                    <div>
                      {status === 'in_progress' && (
                        <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
                      )}
                      {status === 'completed' && (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      )}
                      {status === 'failed' && (
                        <XCircle className="w-5 h-5 text-red-500" />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Results Section */}
        {results && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-lg p-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-800">
                  <CheckCircle className="inline w-8 h-8 text-green-500 mr-2" />
                  Project Generated Successfully!
                </h2>
                <button
                  onClick={() => {
                    setResults(null)
                    setProgress([])
                    setIsRunning(false)
                  }}
                  className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  New Project
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="bg-gradient-to-br from-blue-50 to-blue-100 p-4 rounded-lg">
                  <p className="text-sm text-blue-600 font-medium">Total Tokens</p>
                  <p className="text-2xl font-bold text-blue-900">{results.total_tokens?.toLocaleString()}</p>
                </div>
                <div className="bg-gradient-to-br from-green-50 to-green-100 p-4 rounded-lg">
                  <p className="text-sm text-green-600 font-medium">Code Files</p>
                  <p className="text-2xl font-bold text-green-900">
                    {Object.keys(results.stages?.development?.code_files || {}).length}
                  </p>
                </div>
                <div className="bg-gradient-to-br from-purple-50 to-purple-100 p-4 rounded-lg">
                  <p className="text-sm text-purple-600 font-medium">Review Status</p>
                  <p className="text-2xl font-bold text-purple-900">
                    {results.stages?.review?.status || 'N/A'}
                  </p>
                </div>
              </div>

              {/* Code Files */}
              {results.stages?.development?.code_files && (
                <div className="mb-6">
                  <h3 className="text-lg font-semibold mb-3 text-gray-800">Generated Code Files</h3>
                  <div className="space-y-2">
                    {Object.entries(results.stages.development.code_files).map(([filename, content]) => (
                      <div key={filename} className="flex items-center justify-between bg-gray-50 p-3 rounded-lg">
                        <span className="font-mono text-sm text-gray-700">{filename}</span>
                        <button
                          onClick={() => downloadFile(filename, content)}
                          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 text-sm"
                        >
                          <Download className="w-4 h-4" />
                          Download
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Deployment Files */}
              {results.stages?.devops?.deployment_files && (
                <div>
                  <h3 className="text-lg font-semibold mb-3 text-gray-800">Deployment Files</h3>
                  <div className="space-y-2">
                    {Object.entries(results.stages.devops.deployment_files).map(([filename, content]) => (
                      <div key={filename} className="flex items-center justify-between bg-gray-50 p-3 rounded-lg">
                        <span className="font-mono text-sm text-gray-700">{filename}</span>
                        <button
                          onClick={() => downloadFile(filename, content)}
                          className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700 text-sm"
                        >
                          <Download className="w-4 h-4" />
                          Download
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        </div>
      </main>
    </div>
  )
}

export default App
