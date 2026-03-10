import React, { useState } from 'react';
import { apiUrl, apiFetch } from './apiClient';

/**
 * IntakeChatView: Legacy/fallback form for intake Q&A (PATCH /answer).
 * JobDetail now uses the chat UI with POST /api/jobs/{id}/chat and chat_history.
 * Kept for potential rollback or other references.
 */
export function IntakeChatView({ jobId, clarifications, onAnswersSubmitted }) {
  const [answers, setAnswers] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleAnswerChange = (questionId, value) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await apiFetch(`/api/jobs/${jobId}/answer`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers })
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to submit answers');
      }

      setAnswers({});
      if (onAnswersSubmitted) {
        onAnswersSubmitted();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6 bg-white rounded-lg border border-gray-200">
      <div>
        <h2 className="text-2xl font-bold mb-2">Let's Clarify Your Request</h2>
        <p className="text-gray-600">
          Please answer the following questions so I can create the perfect plan for you.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded text-red-800">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        {clarifications.map((q, idx) => (
          <div key={q.question_id} className="flex flex-col gap-2">
            <label className="font-semibold text-gray-800">
              {idx + 1}. {q.question}
            </label>
            <textarea
              value={answers[q.question_id] || "Not specified" || ''}
              onChange={(e) => handleAnswerChange(q.question_id, e.target.value)}
              placeholder="Your answer..."
              className="p-3 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={3}
              required
            />
          </div>
        ))}

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-4 px-6 py-3 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700 disabled:bg-gray-400 transition"
        >
          {isSubmitting ? 'Submitting...' : 'Submit Answers'}
        </button>
      </form>

      <div className="text-sm text-gray-500">
        Don't worry, I'll use this information to create a tailored plan for your project.
      </div>
    </div>
  );
}

export default IntakeChatView;
