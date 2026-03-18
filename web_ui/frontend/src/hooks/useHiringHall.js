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
  if (!data.agent_name?.trim() && !data.name?.trim()) {
    return 'Naam is verplicht (minimaal 2 tekens).';
  }
  const name = (data.agent_name || data.name || '').trim();
  if (name.length < 2) return 'Naam is verplicht (minimaal 2 tekens).';
  if (!data.role?.trim()) return 'Rol is verplicht.';
  if (!data.goal?.trim() || data.goal.trim().length < 10) return 'Doel is verplicht (minimaal 10 tekens).';
  if (!data.system_prompt?.trim() || data.system_prompt.trim().length < 20) {
    return 'System Instructions zijn verplicht (minimaal 20 tekens).';
  }
  const toolList = data.tool_whitelist || [];
  if (!Array.isArray(toolList) || toolList.length < 1) {
    return 'Minimaal één tool is verplicht (tool_whitelist).';
  }
  if (data.type && !['worker', 'talent', 'orchestrator'].includes(data.type)) {
    return 'Type moet worker, talent of orchestrator zijn.';
  }
  if (data.guardrails) {
    if (!data.guardrails.scope_limitation?.trim()) return 'Guardrails: scope_limitation is verplicht.';
    if (!data.guardrails.escalation_rule?.trim()) return 'Guardrails: escalation_rule is verplicht.';
  }
  if (data.model_config != null && typeof data.model_config.temperature === 'number') {
    if (data.model_config.temperature < 0.1 || data.model_config.temperature > 0.9) {
      return 'Temperature moet tussen 0.1 en 0.9 liggen.';
    }
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
      const name = (data.agent_name || data.name || '').trim();
      const isFramework = data.type && data.output_format && data.guardrails && data.model_config;
      const payload = isFramework
        ? {
            name,
            agent_name: name,
            role: (data.role || '').trim(),
            type: (data.type || 'worker').toLowerCase(),
            goal: (data.goal || '').trim(),
            system_prompt: (data.system_prompt || '').trim(),
            tool_whitelist: Array.isArray(data.tool_whitelist) ? data.tool_whitelist : [],
            knowledge_sources: Array.isArray(data.knowledge_sources) ? data.knowledge_sources : [],
            output_format: data.output_format || { type: 'markdown', schema: 'freeform' },
            guardrails: data.guardrails || { scope_limitation: '', quality_thresholds: [], escalation_rule: '' },
            model_config: data.model_config || { model: 'claude-sonnet', temperature: 0.7, top_p: 0.9 },
          }
        : {
            agent_name: name,
            role: (data.role || '').trim(),
            category: data.category || 'Custom',
            goal: (data.goal || '').trim(),
            system_prompt: (data.system_prompt || '').trim(),
            tool_whitelist: Array.isArray(data.tool_whitelist) ? data.tool_whitelist : [],
            knowledge_sources: Array.isArray(data.knowledge_sources) ? data.knowledge_sources : [],
          };
      const response = await fetch(`${BASE_URL}/api/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
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
