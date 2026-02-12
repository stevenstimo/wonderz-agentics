import React from 'react';

export default function ProgressBar({ stages, currentStage }) {
  const currentIndex = stages.findIndex(s => s.id === currentStage);
  const percent = ((currentIndex + 1) / stages.length) * 100;

  return (
    <div className="w-full mb-6">
      <div className="relative h-3 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="absolute left-0 top-0 h-full bg-indigo-500 transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
      <div className="flex justify-between mt-1 text-xs text-gray-500">
        {stages.map((stage, i) => (
          <span key={stage.id} className={
            i === currentIndex
              ? 'font-bold text-indigo-700'
              : i < currentIndex
                ? 'text-green-600'
                : ''
          }>
            {stage.name}
          </span>
        ))}
      </div>
    </div>
  );
}
