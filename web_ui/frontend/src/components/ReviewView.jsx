import React, { useState } from 'react';

/**
 * ReviewView: Shows the diff between original and proposed data.
 * Allows final approval or rejection with feedback.
 */
export function ReviewView({ jobId, artifacts, ceoSummary, onApprove, onRequestChanges }) {
  const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
  const [isApproving, setIsApproving] = useState(false);
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [selectedArtifact, setSelectedArtifact] = useState(0);

  const handleApprove = async () => {
    setIsApproving(true);
    try {
      const response = await fetch(`${apiBase}/api/jobs/${jobId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        throw new Error('Failed to approve job');
      }

      if (onApprove) {
        onApprove();
      }
    } catch (err) {
      alert('Error: ' + err.message);
    } finally {
      setIsApproving(false);
    }
  };

  const handleRequestChanges = async () => {
    if (!feedback.trim()) {
      alert('Please provide feedback');
      return;
    }

    try {
      const response = await fetch(`${apiBase}/api/jobs/${jobId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback })
      });

      if (!response.ok) {
        throw new Error('Failed to send feedback');
      }

      setFeedback('');
      setShowFeedbackForm(false);
      
      if (onRequestChanges) {
        onRequestChanges();
      }
    } catch (err) {
      alert('Error: ' + err.message);
    }
  };

  if (!artifacts || artifacts.length === 0) {
    return <div className="p-6 text-gray-500">No artifacts available for review</div>;
  }

  const artifact = artifacts[selectedArtifact];

  return (
    <div className="flex flex-col gap-6 p-6 bg-white rounded-lg border border-gray-200">
      <div>
        <h2 className="text-2xl font-bold mb-2">Review & Approval</h2>
        <p className="text-gray-600">
          Here's what we've prepared. Review the changes and approve to deploy.
        </p>
      </div>

      {/* CEO Commentary */}
      {ceoSummary && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded">
          <p className="text-sm font-semibold text-blue-900 mb-2">CEO Summary</p>
          <p className="text-sm text-gray-700">{ceoSummary}</p>
        </div>
      )}

      {/* Artifact Selector */}
      {artifacts.length > 1 && (
        <div>
          <p className="text-sm font-semibold text-gray-700 mb-2">Review Items</p>
          <div className="flex flex-wrap gap-2">
            {artifacts.map((art, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedArtifact(idx)}
                className={`px-4 py-2 rounded text-sm font-medium transition ${
                  selectedArtifact === idx
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-800 hover:bg-gray-300'
                }`}
              >
                {art.artifact_type} {idx + 1}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Diff Display */}
      <div>
        <h3 className="font-semibold text-gray-800 mb-3">
          {artifact.name || artifact.artifact_type}
        </h3>

        <div className="grid grid-cols-2 gap-4">
          {/* Original Data */}
          <div className="p-4 border-2 border-red-200 rounded bg-red-50">
            <p className="text-sm font-semibold text-red-900 mb-3">Original</p>
            <SimpleDiff data={artifact.original_data} />
          </div>

          {/* Proposed Data */}
          <div className="p-4 border-2 border-green-200 rounded bg-green-50">
            <p className="text-sm font-semibold text-green-900 mb-3">Proposed Changes</p>
            <SimpleDiff data={artifact.proposed_data} highlight={true} />
          </div>
        </div>

        {/* Review Feedback if exists */}
        {artifact.review_feedback && (
          <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded">
            <p className="text-sm font-semibold text-yellow-900 mb-2">Review Notes</p>
            <p className="text-sm text-gray-700">{artifact.review_feedback}</p>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      {!showFeedbackForm ? (
        <div className="flex gap-3 mt-6">
          <button
            onClick={handleApprove}
            disabled={isApproving}
            className="flex-1 px-6 py-3 bg-green-600 text-white rounded font-semibold hover:bg-green-700 disabled:bg-gray-400 transition"
          >
            {isApproving ? 'Deploying...' : '✓ Approve & Deploy'}
          </button>
          <button
            onClick={() => setShowFeedbackForm(true)}
            className="flex-1 px-6 py-3 bg-gray-200 text-gray-800 rounded font-semibold hover:bg-gray-300 transition"
          >
            Request Revisions
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-3 mt-6">
          <p className="text-sm font-semibold text-gray-700">What needs to be changed?</p>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Be specific about what you'd like us to revise..."
            className="p-3 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={4}
          />
          <div className="flex gap-3">
            <button
              onClick={handleRequestChanges}
              className="flex-1 px-6 py-3 bg-orange-600 text-white rounded font-semibold hover:bg-orange-700 transition"
            >
              Send Feedback
            </button>
            <button
              onClick={() => {
                setShowFeedbackForm(false);
                setFeedback('');
              }}
              className="flex-1 px-6 py-3 bg-gray-200 text-gray-800 rounded font-semibold hover:bg-gray-300 transition"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Simple diff display component for showing original vs proposed data
 */
function SimpleDiff({ data, highlight = false }) {
  if (typeof data === 'string') {
    return (
      <p className={`text-sm whitespace-pre-wrap ${highlight ? 'font-semibold' : ''}`}>
        {data}
      </p>
    );
  }

  if (typeof data === 'object' && data !== null) {
    return (
      <div className="space-y-2">
        {Object.entries(data).map(([key, value]) => (
          <div key={key}>
            <p className="text-xs font-semibold text-gray-600 uppercase">{key}</p>
            <p className={`text-sm mt-1 ${highlight ? 'font-semibold text-green-800' : 'text-gray-800'}`}>
              {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
            </p>
          </div>
        ))}
      </div>
    );
  }

  return <p className="text-sm text-gray-600">No data</p>;
}

export default ReviewView;
