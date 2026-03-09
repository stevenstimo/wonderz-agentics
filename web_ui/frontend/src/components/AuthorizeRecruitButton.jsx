/**
 * AuthorizeRecruitButton — Submit button voor Hiring Hall
 * Toont loading state, error en success. Parent controleert form state en recruit flow.
 */

import React from 'react';
import { Sparkles } from 'lucide-react';

export default function AuthorizeRecruitButton({
  formData,
  onRecruit,
  isLoading,
  error,
  success,
  disabled,
}) {
  const handleClick = async (e) => {
    e.preventDefault();
    if (disabled || isLoading) return;
    await onRecruit(formData);
  };

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div
          className="rounded-xl bg-red-50 border border-red-200 px-5 py-4 text-red-700 font-medium"
          role="alert"
        >
          {error}
        </div>
      )}
      {success && (
        <div
          className="rounded-xl bg-green-50 border border-green-200 px-5 py-4 text-green-800 font-medium"
          role="status"
        >
          Agent aangemaakt: {success.agent_name || success.name} ({success.agent_id})
        </div>
      )}
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || isLoading}
        className="flex-1 bg-[#1d62e3] hover:bg-[#154dbb] disabled:opacity-70 disabled:cursor-not-allowed text-white font-black py-6 rounded-[32px] shadow-2xl shadow-[#1d62e3]/20 transition-all flex items-center justify-center gap-4 text-xl active:scale-[0.98]"
      >
        {isLoading ? (
          'Recruiting...'
        ) : (
          <>
            Authorize & Recruit Crew Member
            <Sparkles size={24} className="text-[#e0edff]" />
          </>
        )}
      </button>
    </div>
  );
}
