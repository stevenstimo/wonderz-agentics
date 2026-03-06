import React, { useState } from 'react';

/**
 * PlanProposalView: Displays the CEO's proposed execution plan.
 * Shows agents to be hired and the sequence of steps.
 */
export function PlanProposalView({ jobId, plan, onApprove, onRequestChanges }) {
  const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
  const [isApproving, setIsApproving] = useState(false);
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [feedback, setFeedback] = useState('');

  const handleApprove = async () => {
    setIsApproving(true);
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 180000);
      const response = await fetch(`${apiBase}/api/jobs/${jobId}/approve-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error('Failed to approve plan');
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
      alert('Please provide feedback before requesting changes');
      return;
    }

    try {
      const response = await fetch(`${apiBase}/api/jobs/${jobId}/request-changes`, {
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

  if (!plan) {
    return <div className="p-6 text-gray-500">No plan generated yet</div>;
  }

  const { steps = [], hired_agents = [], estimated_duration_seconds = 0 } = plan;

  return (
    <div className="flex flex-col gap-6 p-6 bg-white rounded-lg border border-gray-200">
      <div>
        <h2 className="text-2xl font-bold mb-2">Your Execution Plan</h2>
        <p className="text-gray-600">
          Here's how I plan to achieve your goal. Please review and approve to get started.
        </p>
      </div>

      {/* Plan Summary */}
      <div className="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded">
        <div>
          <p className="text-sm text-gray-600">Estimated Duration</p>
          <p className="text-xl font-semibold">
            {Math.round(estimated_duration_seconds / 60)} minutes
          </p>
        </div>
        <div>
          <p className="text-sm text-gray-600">Agents Required</p>
          <p className="text-xl font-semibold">{hired_agents.length}</p>
        </div>
      </div>

      {/* Hired Agents */}
      {hired_agents.length > 0 && (
        <div>
          <h3 className="font-semibold text-gray-800 mb-3">Agents for This Job</h3>
          <div className="flex flex-wrap gap-2">
            {hired_agents.map((agent, idx) => (
              <span
                key={idx}
                className="px-4 py-2 bg-blue-100 text-blue-800 rounded-full text-sm font-medium"
              >
                {agent} ✓
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Step-by-Step Plan */}
      <div>
        <h3 className="font-semibold text-gray-800 mb-3">Step-by-Step Plan</h3>
        <div className="flex flex-col gap-3">
          {steps.map((step, idx) => (
            <div
              key={idx}
              className="flex items-start gap-4 p-4 border border-gray-200 rounded hover:bg-gray-50 transition"
            >
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-500 text-white flex items-center justify-center font-semibold text-sm">
                {step.step_index}
              </div>
              <div className="flex-grow">
                <p className="font-semibold text-gray-800">{step.agent_role}</p>
                <p className="text-sm text-gray-600 mt-1">{step.description}</p>
                <p className="text-xs text-gray-500 mt-2">
                  Tool: <code>{step.unified_tool}</code>
                </p>
                {step.requires_approval && (
                  <span className="inline-block mt-2 px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded font-medium">
                    Requires Approval
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Mr. Klein Commentary */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded">
        <p className="text-sm text-gray-700">
          <strong>Mr. Klein Notes:</strong> This plan has been carefully designed to achieve your objectives efficiently.
          Each step has been prioritized based on impact and dependencies.
        </p>
      </div>

      {/* Action Buttons */}
      {!showFeedbackForm ? (
        <div className="flex gap-3 mt-4">
          <button
            onClick={handleApprove}
            disabled={isApproving}
            className="flex-1 px-6 py-3 bg-green-600 text-white rounded font-semibold hover:bg-green-700 disabled:bg-gray-400 transition"
          >
            {isApproving ? 'Approving...' : '✓ Approve & Start'}
          </button>
          <button
            onClick={() => setShowFeedbackForm(true)}
            className="flex-1 px-6 py-3 bg-gray-200 text-gray-800 rounded font-semibold hover:bg-gray-300 transition"
          >
            Request Changes
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-3 mt-4">
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="What would you like me to change? Be specific..."
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

export default PlanProposalView;
