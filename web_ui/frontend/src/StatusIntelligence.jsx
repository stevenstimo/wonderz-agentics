import React, { useEffect, useMemo, useState } from 'react';
import Sidebar from './Sidebar';
import { Activity, Brain, Shield, Cpu, AlertTriangle, Coins, BookOpenText, RefreshCw } from 'lucide-react';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview' },
  { id: 'brains-map', label: 'Brains Map' },
  { id: 'decision-quality', label: 'Decision' },
  { id: 'execution-quality', label: 'Execution' },
  { id: 'learning-memory', label: 'Learning' },
  { id: 'failure-intel', label: 'Failures' },
  { id: 'governance-safety', label: 'Governance' },
  { id: 'cost-performance', label: 'Cost' },
  { id: 'recent-runs', label: 'Recent Runs' }
];

const STATIC_BRAINS_MAP = {
  orchestrator: 'crew/scripts/lib/orchestrator.rb',
  decision_engine: 'crew/scripts/lib/decision_engine.rb',
  execution_engine: 'crew/scripts/lib/execution_engine.rb',
  evaluator: 'crew/scripts/lib/evaluator.rb',
  memory_manager: 'crew/scripts/lib/memory_manager.rb',
  governance: 'crew/scripts/lib/governance.rb',
  llm_client: 'crew/scripts/lib/llm_client.rb',
  runtime_docs: 'crew/docs/runtime_architecture.md'
};

export default function StatusIntelligence() {
  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${apiBase}/api/intelligence/overview`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const payload = await res.json();
      setData(payload);
    } catch (err) {
      setError(err.message || 'Could not load intelligence API');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [apiBase]);

  const summary = useMemo(() => data?.summary || {}, [data]);
  const decision = useMemo(() => data?.decision_quality || {}, [data]);
  const execution = useMemo(() => data?.execution_quality || {}, [data]);
  const learning = useMemo(() => data?.learning_memory || {}, [data]);
  const governance = useMemo(() => data?.governance_safety || {}, [data]);
  const cost = useMemo(() => data?.cost_performance || {}, [data]);
  const recentRuns = useMemo(() => data?.recent_runs || [], [data]);
  const brainsMap = useMemo(() => data?.brains_map || STATIC_BRAINS_MAP, [data]);
  const topFailures = useMemo(() => data?.top_failure_types || [], [data]);

  const healthLabel = statusLabel(summary.success_rate ?? 0);

  return (
    <div className="dashboard-container">
      <Sidebar />
      <main className="content-area">
        <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
          <section className="panel-card">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                  <Brain className="w-6 h-6 text-indigo-600" />
                  The Brains
                </h1>
                <p className="text-slate-600 mt-1">
                  Centrale inzichten over besluitvorming, uitvoering, geheugen en veiligheid.
                </p>
              </div>
              <button onClick={load} className="btn-manage gap-2" disabled={loading}>
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
            <div className="flex flex-wrap gap-2 mt-4">
              {NAV_ITEMS.map(item => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  className="px-3 py-1.5 rounded-full text-sm bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
                >
                  {item.label}
                </a>
              ))}
            </div>
          </section>

          {loading && (
            <section className="panel-card">
              <p className="text-slate-600">Intelligence data wordt geladen...</p>
            </section>
          )}

          {error && !loading && (
            <section className="panel-card border border-amber-300 bg-amber-50/60">
              <h2 className="text-lg font-semibold text-amber-900 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5" />
                Live data tijdelijk niet beschikbaar
              </h2>
              <p className="text-amber-900 text-sm mt-2">
                API error: <code>{error}</code> op <code>{apiBase}/api/intelligence/overview</code>.
              </p>
              <p className="text-amber-900 text-sm mt-1">
                Deze pagina toont wel de vaste architecture map, maar niet de live metrics.
              </p>
            </section>
          )}

          <section id="overview" className="panel-card space-y-3">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Activity className="w-5 h-5 text-indigo-600" />
              Overview
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              <Metric label="Health" value={healthLabel} />
              <Metric label="Total Runs" value={safe(summary.total_runs)} />
              <Metric label="Success Rate" value={pct(summary.success_rate)} />
              <Metric label="Runs 24h" value={safe(summary.last_24h_runs)} />
              <Metric label="Success 24h" value={pct(summary.last_24h_success_rate)} />
            </div>
            <p className="text-sm text-slate-500">Laatste run: {summary.latest_run_at || 'n/a'}</p>
          </section>

          <section id="brains-map" className="panel-card space-y-3">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Cpu className="w-5 h-5 text-indigo-600" />
              Brains Map
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {Object.entries(brainsMap).map(([key, path]) => (
                <div key={key} className="border rounded-lg p-3 bg-slate-50">
                  <div className="font-semibold text-slate-800">{key}</div>
                  <code className="text-xs text-slate-600">{path}</code>
                </div>
              ))}
            </div>
          </section>

          <section id="decision-quality" className="panel-card space-y-3">
            <h2 className="text-xl font-semibold">Decision Quality</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Metric label="Ambiguity Rate" value={pct(decision.ambiguity_rate)} />
              <Metric label="Avg Retries/Run" value={num(decision.avg_retries_per_run, 2)} />
              <Metric label="Top Intent" value={(decision.top_intents || [])[0]?.intent || 'n/a'} />
            </div>
          </section>

          <section id="execution-quality" className="panel-card space-y-3">
            <h2 className="text-xl font-semibold">Execution Quality</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Metric label="Avg Step Latency" value={`${safe(execution.avg_step_latency_ms)} ms`} />
              <Metric label="Avg Run Duration" value={`${safe(execution.avg_run_duration_ms)} ms`} />
              <Metric label="Failure Run Rate" value={pct(execution.failure_run_rate)} />
            </div>
          </section>

          <section id="learning-memory" className="panel-card space-y-3">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <BookOpenText className="w-5 h-5 text-indigo-600" />
              Learning & Memory
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Metric label="Avg Lessons/Run" value={num(learning.avg_lessons_used_per_run, 2)} />
              <Metric label="Agent Profiles" value={safe(learning.agents_with_profiles)} />
              <Metric label="Agents Listed" value={safe((data?.agents || []).length)} />
            </div>
          </section>

          <section id="failure-intel" className="panel-card space-y-3">
            <h2 className="text-xl font-semibold">Failure Intelligence</h2>
            {(topFailures || []).length > 0 ? (
              <ul className="space-y-2">
                {topFailures.map(item => (
                  <li key={item.type} className="flex items-center justify-between border rounded-lg px-3 py-2">
                    <span className="font-medium">{item.type}</span>
                    <span className="text-slate-600">{item.count}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500">Geen failure events beschikbaar.</p>
            )}
          </section>

          <section id="governance-safety" className="panel-card space-y-3">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Shield className="w-5 h-5 text-indigo-600" />
              Governance & Safety
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Metric label="Governance Blocks" value={safe(governance.governance_blocked_events)} />
              <Metric label="Top Failure Type" value={topFailures[0]?.type || 'n/a'} />
            </div>
          </section>

          <section id="cost-performance" className="panel-card space-y-3">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Coins className="w-5 h-5 text-indigo-600" />
              Cost & Performance
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Metric label="Total Tokens" value={safe(cost.total_tokens)} />
              <Metric label="Avg Tokens/Run" value={num(cost.avg_tokens_per_run, 1)} />
              <Metric label="LLM Usage Rate" value={pct(cost.llm_usage_rate)} />
            </div>
          </section>

          <section id="recent-runs" className="panel-card space-y-3">
            <h2 className="text-xl font-semibold">Recent Runs</h2>
            {(recentRuns || []).length === 0 ? (
              <p className="text-slate-500">Nog geen recente runs gevonden.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-2 pr-2">Run</th>
                      <th className="py-2 pr-2">Intent</th>
                      <th className="py-2 pr-2">Playbook</th>
                      <th className="py-2 pr-2">Status</th>
                      <th className="py-2 pr-2">Failures</th>
                      <th className="py-2 pr-2">Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentRuns.map(run => (
                      <tr key={`${run.run_id}-${run.completed_at}`} className="border-b">
                        <td className="py-2 pr-2 font-mono text-xs">{run.run_id || 'n/a'}</td>
                        <td className="py-2 pr-2">{run.intent || 'n/a'}</td>
                        <td className="py-2 pr-2">{run.playbook || 'n/a'}</td>
                        <td className="py-2 pr-2">{run.status || 'n/a'}</td>
                        <td className="py-2 pr-2">{(run.failures || []).join(', ') || '-'}</td>
                        <td className="py-2 pr-2">{run.duration_ms ? `${run.duration_ms} ms` : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="border rounded-lg p-3 bg-white">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-xl font-bold text-slate-900 mt-1">{value}</div>
    </div>
  );
}

function pct(value) {
  if (typeof value !== 'number') return '0%';
  return `${Math.round(value * 100)}%`;
}

function safe(value) {
  if (value === null || value === undefined) return 0;
  return value;
}

function num(value, precision = 1) {
  if (typeof value !== 'number') return '0';
  return value.toFixed(precision);
}

function statusLabel(successRate) {
  if (successRate >= 0.9) return 'Healthy';
  if (successRate >= 0.7) return 'Warning';
  return 'Critical';
}
