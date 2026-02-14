import React, { useEffect, useMemo, useState } from 'react';
import Sidebar from './Sidebar';

const sections = [
  { id: 'overview', label: 'Overview' },
  { id: 'brains', label: 'Brains Map' },
  { id: 'failures', label: 'Failure Types' },
  { id: 'agents', label: 'Agents' }
];

export default function StatusIntelligence() {
  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
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
        setError(err.message || 'Failed to load intelligence status');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [apiBase]);

  const summary = useMemo(() => data?.summary || {}, [data]);

  return (
    <div className="dashboard-container">
      <Sidebar />
      <main className="content-area">
        <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
          <div className="panel-card">
            <h1 className="page-title">Status / Intelligence</h1>
            <p className="page-subtitle">Hier zie je waar de brains zitten en hoe de runtime presteert.</p>
            <div className="flex flex-wrap gap-2 mt-4">
              {sections.map(section => (
                <a
                  key={section.id}
                  href={`#${section.id}`}
                  className="px-3 py-1.5 rounded-full text-sm bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
                >
                  {section.label}
                </a>
              ))}
            </div>
          </div>

          {loading && <div className="panel-card">Intelligence status laden...</div>}
          {!loading && error && <div className="panel-card text-red-600">Kon status niet laden: {error}</div>}

          {!loading && !error && data && (
            <>
              <section id="overview" className="panel-card space-y-3">
                <h2 className="text-xl font-semibold">Overview</h2>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  <Metric label="Total Runs" value={summary.total_runs} />
                  <Metric label="Success Rate" value={pct(summary.success_rate)} />
                  <Metric label="Runs (24h)" value={summary.last_24h_runs} />
                  <Metric label="Success (24h)" value={pct(summary.last_24h_success_rate)} />
                </div>
                <p className="text-sm text-slate-500">Laatste run: {summary.latest_run_at || 'n/a'}</p>
              </section>

              <section id="brains" className="panel-card space-y-3">
                <h2 className="text-xl font-semibold">Brains Map</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {Object.entries(data.brains_map || {}).map(([key, path]) => (
                    <div key={key} className="border rounded-lg p-3 bg-slate-50">
                      <div className="font-semibold text-slate-800">{key}</div>
                      <code className="text-xs text-slate-600">{path}</code>
                    </div>
                  ))}
                </div>
              </section>

              <section id="failures" className="panel-card space-y-3">
                <h2 className="text-xl font-semibold">Failure Types</h2>
                {Array.isArray(data.top_failure_types) && data.top_failure_types.length > 0 ? (
                  <ul className="space-y-2">
                    {data.top_failure_types.map(item => (
                      <li key={item.type} className="flex items-center justify-between border rounded-lg px-3 py-2">
                        <span className="font-medium">{item.type}</span>
                        <span className="text-slate-600">{item.count}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-slate-500">Geen failure types gevonden.</p>
                )}
              </section>

              <section id="agents" className="panel-card space-y-3">
                <h2 className="text-xl font-semibold">Agents</h2>
                <div className="flex flex-wrap gap-2">
                  {(data.agents || []).map(agent => (
                    <span key={agent} className="px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-sm">
                      {agent}
                    </span>
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="border rounded-lg p-3 bg-white">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-xl font-bold text-slate-900 mt-1">{value ?? 0}</div>
    </div>
  );
}

function pct(value) {
  if (typeof value !== 'number') return '0%';
  return `${Math.round(value * 100)}%`;
}
