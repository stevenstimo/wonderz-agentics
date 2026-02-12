import React from 'react';

export default function AgentList({ agents }) {
  if (!agents || agents.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {agents.map((name) => (
        <span key={name} className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded text-xs font-medium">
          {name}
        </span>
      ))}
    </div>
  );
}
