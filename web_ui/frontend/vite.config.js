import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

function intelligenceDevApiPlugin() {
  const brainsMap = {
    orchestrator: 'crew/scripts/lib/orchestrator.rb',
    decision_engine: 'crew/scripts/lib/decision_engine.rb',
    execution_engine: 'crew/scripts/lib/execution_engine.rb',
    evaluator: 'crew/scripts/lib/evaluator.rb',
    memory_manager: 'crew/scripts/lib/memory_manager.rb',
    governance: 'crew/scripts/lib/governance.rb',
    llm_client: 'crew/scripts/lib/llm_client.rb',
    runtime_docs: 'crew/docs/runtime_architecture.md',
  }

  const toIso = (value) => {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? null : date.toISOString()
  }

  const buildPayload = () => {
    const workspaceRoot = path.resolve(process.cwd(), '..', '..')
    const runDir = path.join(workspaceRoot, 'crew', 'reports', 'runs')
    const agentsDir = path.join(workspaceRoot, 'crew', 'agents')
    const now = new Date()
    const since24h = now.getTime() - 24 * 60 * 60 * 1000

    const payload = {
      status: 'ok',
      generated_at: now.toISOString(),
      summary: {
        total_runs: 0,
        success_rate: 0,
        failed_runs: 0,
        last_24h_runs: 0,
        last_24h_success_rate: 0,
        latest_run_at: null,
      },
      decision_quality: {
        ambiguity_rate: 0,
        avg_retries_per_run: 0,
        top_intents: [],
        top_playbooks: [],
      },
      execution_quality: {
        avg_step_latency_ms: 0,
        avg_run_duration_ms: 0,
        failure_run_rate: 0,
      },
      learning_memory: {
        avg_lessons_used_per_run: 0,
        agents_with_profiles: 0,
      },
      governance_safety: {
        governance_blocked_events: 0,
      },
      cost_performance: {
        total_tokens: 0,
        avg_tokens_per_run: 0,
        llm_usage_rate: 0,
      },
      brains_map: brainsMap,
      agents: [],
      top_failure_types: [],
      top_intents: [],
      recent_runs: [],
    }

    const countBy = new Map()
    const countIntent = new Map()
    const countPlaybook = new Map()
    const recentRuns = []
    const durations = []

    let success = 0
    let failed = 0
    let runs24 = 0
    let success24 = 0
    let retries = 0
    let lessons = 0
    let tokens = 0
    let llmUsed = 0
    let steps = 0
    let stepLatency = 0
    let ambiguous = 0
    let failureRuns = 0
    let governanceBlocked = 0

    if (fs.existsSync(agentsDir)) {
      payload.agents = fs.readdirSync(agentsDir).filter((file) => file.endsWith('.profile.yml')).sort()
      payload.learning_memory.agents_with_profiles = payload.agents.length
    }

    if (!fs.existsSync(runDir)) return payload

    const files = fs.readdirSync(runDir)
      .filter((file) => file.startsWith('run-') && file.endsWith('.jsonl'))
      .map((file) => path.join(runDir, file))
      .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)
      .slice(0, 250)

    for (const runFile of files) {
      const text = fs.readFileSync(runFile, 'utf8')
      const lines = text.split('\n').filter(Boolean)
      let summary = null
      let startedAt = null
      let completedAt = null
      let runAmbiguous = false

      for (const line of lines) {
        try {
          const event = JSON.parse(line)
          if (event.type === 'run_started') startedAt = toIso(event.ts)
          if (event.type === 'intent_classified' && event.ambiguous) runAmbiguous = true
          if (event.type === 'run_completed') {
            summary = event.summary || null
            completedAt = toIso(event.ts)
            break
          }
        } catch {
          // ignore malformed line
        }
      }

      if (!summary) continue

      payload.summary.total_runs += 1
      if (summary.status === 'success') success += 1
      else failed += 1

      retries += Number(summary.retry_count || 0)
      lessons += Number(summary.lessons_used || 0)
      if (runAmbiguous) ambiguous += 1

      if (summary.intent) {
        countIntent.set(summary.intent, (countIntent.get(summary.intent) || 0) + 1)
      }
      if (summary.playbook) {
        countPlaybook.set(summary.playbook, (countPlaybook.get(summary.playbook) || 0) + 1)
      }

      const metrics = summary.metrics || {}
      const llmUsage = metrics.llm_usage || {}
      steps += Number(metrics.step_count || 0)
      stepLatency += Number(metrics.total_step_latency_ms || 0)
      tokens += Number(llmUsage.total_tokens || 0)
      if (summary.llm?.used) llmUsed += 1

      const failures = Array.isArray(summary.failures) ? summary.failures : []
      if (failures.length > 0) failureRuns += 1
      for (const failure of failures) {
        const key = failure?.type || 'unknown'
        countBy.set(key, (countBy.get(key) || 0) + 1)
        if (key === 'governance_blocked') governanceBlocked += 1
      }

      if (completedAt) {
        const completedMs = new Date(completedAt).getTime()
        if (!payload.summary.latest_run_at || completedMs > new Date(payload.summary.latest_run_at).getTime()) {
          payload.summary.latest_run_at = completedAt
        }
        if (completedMs >= since24h) {
          runs24 += 1
          if (summary.status === 'success') success24 += 1
        }

        let durationMs = null
        if (startedAt) {
          durationMs = Math.max(0, Math.round((new Date(completedAt).getTime() - new Date(startedAt).getTime())))
          durations.push(durationMs)
        }
        recentRuns.push({
          run_id: summary.run_id || path.basename(runFile, '.jsonl'),
          intent: summary.intent || null,
          playbook: summary.playbook || null,
          status: summary.status || null,
          retry_count: Number(summary.retry_count || 0),
          failures: failures.map((f) => f?.type || 'unknown'),
          total_score: summary.evaluation?.total_score ?? null,
          duration_ms: durationMs,
          completed_at: completedAt,
        })
      }
    }

    const totalRuns = payload.summary.total_runs
    payload.summary.failed_runs = failed
    payload.summary.success_rate = totalRuns ? success / totalRuns : 0
    payload.summary.last_24h_runs = runs24
    payload.summary.last_24h_success_rate = runs24 ? success24 / runs24 : 0

    payload.decision_quality.ambiguity_rate = totalRuns ? ambiguous / totalRuns : 0
    payload.decision_quality.avg_retries_per_run = totalRuns ? retries / totalRuns : 0
    payload.execution_quality.avg_step_latency_ms = steps ? Math.round(stepLatency / steps) : 0
    payload.execution_quality.avg_run_duration_ms = durations.length ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) : 0
    payload.execution_quality.failure_run_rate = totalRuns ? failureRuns / totalRuns : 0
    payload.learning_memory.avg_lessons_used_per_run = totalRuns ? lessons / totalRuns : 0
    payload.governance_safety.governance_blocked_events = governanceBlocked
    payload.cost_performance.total_tokens = tokens
    payload.cost_performance.avg_tokens_per_run = totalRuns ? tokens / totalRuns : 0
    payload.cost_performance.llm_usage_rate = totalRuns ? llmUsed / totalRuns : 0

    const mapTop = (map, keyName) => (
      [...map.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([key, count]) => ({ [keyName]: key, count }))
    )

    payload.top_failure_types = mapTop(countBy, 'type')
    payload.top_intents = mapTop(countIntent, 'intent')
    payload.decision_quality.top_intents = mapTop(countIntent, 'intent')
    payload.decision_quality.top_playbooks = mapTop(countPlaybook, 'playbook')
    payload.recent_runs = recentRuns
      .sort((a, b) => new Date(b.completed_at || 0).getTime() - new Date(a.completed_at || 0).getTime())
      .slice(0, 10)

    return payload
  }

  return {
    name: 'intelligence-dev-api',
    configureServer(server) {
      server.middlewares.use('/api/health', (_req, res) => {
        res.setHeader('Content-Type', 'application/json')
        res.end(JSON.stringify({ status: 'ok', db_connected: false, source: 'vite-dev-middleware' }))
      })

      server.middlewares.use('/api/intelligence/overview', (_req, res) => {
        res.setHeader('Content-Type', 'application/json')
        res.end(JSON.stringify(buildPayload()))
      })
    },
  }
}


export default defineConfig({
  plugins: [react(), intelligenceDevApiPlugin()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist', // expliciet relatieve output dir voor Vercel
  },
})
