/**
 * useHiringHall — React hook voor de Hiring Hall
 * Koppelt de "Authorize & Recruit Crew Member" knop aan het backend endpoint.
 * Handelt loading state, validatie, errors en success af.
 *
 * Gebruik:
 *   const { recruit, isLoading, error, success, reset } = useHiringHall();
 *   <AuthorizeRecruitButton formData={formData} onRecruit={recruit} ... />
 *
 * Spec ref: Product Spec v1.1 sectie 2.3, 8
 */

import { useState, useCallback } from 'react';

const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8090').replace(/\/$/, '');

function validateForm(data) {
  if (!data.agent_name?.trim() || data.agent_name.trim().length < 2) {
    return 'Naam is verplicht (minimaal 2 tekens).';
  }
  if (!data.role?.trim()) {
    return 'Rol is verplicht.';
  }
  if (!data.goal?.trim() || data.goal.trim().length < 10) {
    return 'Doel is verplicht (minimaal 10 tekens).';
  }
  if (!data.system_prompt?.trim() || data.system_prompt.trim().length < 20) {
    return 'System Instructions zijn verplicht (minimaal 20 tekens).';
  }
  return null;
}

export function useHiringHall() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const reset = useCallback(() => {
    setError(null);
    setSuccess(null);
    setIsLoading(false);
  }, []);

  const recruit = useCallback(async (data) => {
    const validationError = validateForm(data);
    if (validationError) {
      setError(validationError);
      return null;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch(`${BASE_URL}/api/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_name: data.agent_name.trim(),
          role: data.role.trim(),
          category: data.category || 'Custom',
          goal: data.goal.trim(),
          system_prompt: data.system_prompt.trim(),
          tool_whitelist: data.tool_whitelist || [],
          knowledge_sources: data.knowledge_sources || [],
        }),
      });

      const json = await response.json();

      if (response.status === 201) {
        setSuccess(json);
        return json;
      }

      if (response.status === 409) {
        setError(json.detail || 'Een agent met deze naam bestaat al. Kies een andere naam.');
        return null;
      }

      if (response.status === 422) {
        const detail = json.detail;
        if (Array.isArray(detail) && detail.length > 0) {
          const firstError = detail[0];
          setError(`Validatiefout: ${firstError.msg} (veld: ${firstError.loc?.join('.')})`);
        } else {
          setError(detail || 'Validatiefout — controleer alle velden.');
        }
        return null;
      }

      setError(json.detail || `Onverwachte fout (HTTP ${response.status}).`);
      return null;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Netwerk fout. Is de backend actief?';
      setError(msg);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { recruit, isLoading, error, success, reset };
}
