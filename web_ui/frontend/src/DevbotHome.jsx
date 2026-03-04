import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import PageLayout from './PageLayout';
import DaveDevConsole from './DaveDevConsole';

const agents = [
  { id: 'dave', name: 'Dave Dev', description: 'Technical Consultant & Chief Architect' },
  // Meer agents kunnen hier toegevoegd worden
];

export default function DevbotHome() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedAgent = searchParams.get('agent');

  const handleSelectAgent = (agentId) => {
    setSearchParams({ agent: agentId });
  };

  const agent = agents.find(a => a.id === selectedAgent);

  return (
    <PageLayout size="medium" padded className="space-y-6">
          {!selectedAgent ? (
            // Agent selection screen
            <div className="space-y-6">
              <div className="panel-card">
                <h1 className="page-title">Devbot Agents</h1>
                <p className="page-subtitle">Selecteer een agent om te starten:</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {agents.map(a => (
                  <button
                    key={a.id}
                    onClick={() => handleSelectAgent(a.id)}
                    className="panel-card hover:shadow-lg transition-all text-left cursor-pointer"
                  >
                    <h2 className="page-title mb-2">{a.name}</h2>
                    <p className="text-sm text-slate-600">{a.description}</p>
                  </button>
                ))}
              </div>
            </div>
          ) : agent ? (
            // Agent console
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
            </div>
          ) : (
            <div className="panel-card">
              <p className="text-slate-600">Agent not found</p>
            </div>
          )}
      </PageLayout>
  );
}
