-- Analytics comparison preset + integration activity metadata

ALTER TABLE client_integrations
  ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS last_verified TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_client_integrations_active_lookup
  ON client_integrations(user_id, client_slug, integration_type, is_active)
  WHERE is_active = true;

DO $$
BEGIN
  IF to_regclass('public.job_type_presets') IS NOT NULL THEN
    INSERT INTO job_type_presets (
      preset_id,
      job_type,
      description,
      trigger_hint,
      agent_slots,
      kpi_targets
    ) VALUES (
      'analytics-comparison',
      'Analytics Vergelijking',
      'Vergelijkt organisch versus paid performance met expliciete labeling van ontbrekende databronnen.',
      'indruk, vergelijking, analyse, organisch vs paid, paid vs organisch, traffic mix, kanaalanalyse, hoe staat',
      '[
        {"slot":"ceo","role":"CEO Orchestrator","agent_type":"ceo","persona":"Donna Paulsen","required":true},
        {"slot":"coo","role":"COO Coordinator","agent_type":"coo","persona":"Mr. Klein","required":true},
        {"slot":"data","role":"Data Agent","agent_type":"worker","persona":"Mike Ross","required":true},
        {"slot":"analyst","role":"Analysis Agent","agent_type":"worker","persona":"Harvey Specter","required":true},
        {"slot":"reviewer","role":"QA Reviewer","agent_type":"talent","persona":"Alan Turing","required":false}
      ]'::jsonb,
      '{"kpis":["Benodigde bronnen aanwezig of expliciet als ontbrekend gelabeld","Eindoutput bevat kwalitatieve vergelijking en conclusie"],"outputs":["Analyse per kanaal","Vergelijking met conclusie en vervolgstap"]}'::jsonb
    )
    ON CONFLICT (preset_id) DO NOTHING;
  END IF;
END $$;
