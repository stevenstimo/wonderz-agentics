CREATE TABLE IF NOT EXISTS agent_role_presets (
    role_id TEXT PRIMARY KEY,
    role_label TEXT NOT NULL,
    agent_type TEXT NOT NULL
        CHECK (agent_type IN ('worker', 'talent', 'orchestrator')),
    description TEXT NOT NULL,
    tool_whitelist TEXT[] DEFAULT '{}',
    output_format JSONB DEFAULT '{}',
    guardrails JSONB DEFAULT '{}',
    model_config JSONB DEFAULT '{}',
    suggested_personas JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_role_presets_type ON agent_role_presets(agent_type);
CREATE INDEX IF NOT EXISTS idx_role_presets_active ON agent_role_presets(is_active);

INSERT INTO agent_role_presets (
    role_id, role_label, agent_type, description, tool_whitelist, output_format, guardrails, model_config, suggested_personas
) VALUES
('copywriter', 'Copywriter', 'worker',
 'Schrijft marketing- en communicatiecontent op basis van briefing.',
 ARRAY['read_brief', 'read_product', 'write_copy', 'knowledge_retrieval', 'submit_artifact'],
 '{"type": "markdown", "schema": "freeform"}',
 '{"scope_limitation": "Alleen marketing- en communicatiecontent. Nooit juridisch, financieel of medisch advies.", "quality_thresholds": ["Volledige uitvoering briefing", "Heldere structuur", "Geen niet-onderbouwde claims"], "escalation_rule": "Escaleer bij ontbrekende briefing, tegenstrijdige doelen of impact buiten marketingdomein."}',
 '{"model": "claude-sonnet", "temperature": 0.8, "top_p": 0.95}',
 '[{"persona": "Forrest Gump", "score": 78, "development_priority": "Strategisch inzicht & contextbewustzijn"}, {"persona": "Amélie Poulain", "score": 71, "development_priority": "Directe communicatie & zichtbaarheid"}]'
),
('seo-specialist', 'SEO Research', 'worker',
 'Keyword research, competitor analyse en SEO briefings.',
 ARRAY['web_search', 'read_analytics', 'read_url', 'write_research', 'score_keywords', 'knowledge_retrieval', 'submit_artifact'],
 '{"type": "json", "schema": "structured"}',
 '{"scope_limitation": "Alleen SEO- en contentstrategieadvies. Geen technische site-aanpassingen uitvoeren.", "quality_thresholds": ["Elke keyword-claim onderbouwd met data", "Bronnen geciteerd", "Prioriteitenlijst aanwezig"], "escalation_rule": "Escaleer bij conflicterende data, toegangsproblemen of strategische beslissingen buiten SEO-domein."}',
 '{"model": "claude-sonnet", "temperature": 0.6, "top_p": 0.9}',
 '[{"persona": "Donnie Darko", "score": 65, "development_priority": "Mentale stabiliteit & praktische toetsing"}]'
),
('senior-engineer', 'Senior Engineer', 'worker',
 'Implementeert features, schrijft tests en doet code reviews.',
 ARRAY['read_codebase', 'write_code', 'run_tests', 'knowledge_retrieval', 'submit_artifact', 'flag_escalation'],
 '{"type": "code", "schema": "freeform"}',
 '{"scope_limitation": "Alleen code binnen gedefinieerde scope. Geen productie-deployments zonder aparte goedkeuring.", "quality_thresholds": ["Tests aanwezig", "Geen hardcoded secrets", "Geen breaking changes zonder vermelding"], "escalation_rule": "Escaleer bij architectuurkeuzes, breaking changes of ontbrekende requirements."}',
 '{"model": "claude-sonnet", "temperature": 0.3, "top_p": 0.9}',
 '[{"persona": "Tony Stark", "score": 77, "development_priority": "Delegeren & controle loslaten"}, {"persona": "Shuri", "score": 76, "development_priority": "Structuur & documentatie"}, {"persona": "Q", "score": 74, "development_priority": "Zichtbaarheid & communicatie"}]'
),
('support-specialist', 'Support Specialist', 'worker',
 'Beantwoordt klantvragen, detecteert patronen en escaleert klachten.',
 ARRAY['read_tickets', 'read_product', 'write_response', 'flag_pattern', 'create_summary', 'knowledge_retrieval', 'submit_artifact'],
 '{"type": "markdown", "schema": "freeform"}',
 '{"scope_limitation": "Alleen klantvragen binnen productdomein. Geen prijsafspraken of juridische toezeggingen.", "quality_thresholds": ["Empathische toon", "Concreet antwoord of doorverwijzing", "Geen valse beloften"], "escalation_rule": "Escaleer bij juridische claims, data-incidenten of herhaalde klachten (3x+)."}',
 '{"model": "claude-sonnet", "temperature": 0.7, "top_p": 0.95}',
 '[{"persona": "Amélie Poulain", "score": 71, "development_priority": "Directe communicatie & zichtbaarheid"}]'
),
('incident-response', 'Incident Response', 'worker',
 'Triageert incidenten, identificeert root cause en schrijft postmortems.',
 ARRAY['read_logs', 'execute_fallback', 'write_incident_report', 'flag_escalation', 'read_metrics'],
 '{"type": "json", "schema": "{ severity, root_cause, action_taken, next_steps }"}',
 '{"scope_limitation": "Alleen incident-response binnen gedefinieerde systemen. Geen productiewijzigingen zonder CEO-goedkeuring.", "quality_thresholds": ["Root cause geïdentificeerd of als unknown gelabeld", "Acties gedocumenteerd", "Next steps benoemd"], "escalation_rule": "Escaleer bij impact op meer dan één systeem, onbekende root cause na twee iteraties, of data-verlies."}',
 '{"model": "claude-sonnet", "temperature": 0.2, "top_p": 0.9}',
 '[{"persona": "Winston Wolf", "score": 78, "development_priority": "Kennisoverdracht & documentatie"}, {"persona": "Mad Max", "score": 68, "development_priority": "Emotionele verwerking & delegatie"}]'
),
('research-analyst', 'Research Analyst', 'worker',
 'Diepgaand onderzoek, data-analyse en strategische rapportages.',
 ARRAY['web_search', 'read_analytics', 'read_url', 'write_research', 'knowledge_retrieval', 'submit_artifact'],
 '{"type": "markdown", "schema": "structured"}',
 '{"scope_limitation": "Alleen onderzoek en analyse. Geen implementatie of uitvoering.", "quality_thresholds": ["Bronnen geciteerd", "Conclusies onderbouwd", "Aanbevelingen concreet"], "escalation_rule": "Escaleer bij ontbrekende data, tegenstrijdige bronnen of strategische beslissingen buiten analysedomein."}',
 '{"model": "claude-sonnet", "temperature": 0.5, "top_p": 0.9}',
 '[{"persona": "Mike Ross", "score": 74, "development_priority": "Zelfvertrouwen & structuur"}]'
),
('gtm-specialist', 'GTM / Creative', 'worker',
 'Go-to-market strategie, campagne-concepten en creatieve briefings.',
 ARRAY['read_brief', 'write_copy', 'write_strategy', 'knowledge_retrieval', 'submit_artifact'],
 '{"type": "markdown", "schema": "freeform"}',
 '{"scope_limitation": "Alleen GTM-strategie en creatieve concepten. Geen media-inkoop of budget-toewijzing.", "quality_thresholds": ["Duidelijke doelgroep gedefinieerd", "Kanaalstrategie aanwezig", "KPIs benoemd"], "escalation_rule": "Escaleer bij budget-beslissingen, juridische vragen of strategische pivots."}',
 '{"model": "claude-sonnet", "temperature": 0.8, "top_p": 0.95}',
 '[{"persona": "Ferris Bueller", "score": 70, "development_priority": "Verantwoordelijkheid & transparantie"}]'
),
('precision-executor', 'Precision Executor', 'worker',
 'Voert complexe taken nauwkeurig en zelfstandig uit zonder begeleiding.',
 ARRAY['read_brief', 'execute_task', 'knowledge_retrieval', 'submit_artifact'],
 '{"type": "markdown", "schema": "freeform"}',
 '{"scope_limitation": "Alleen uitvoering van gedefinieerde taken. Geen scope-uitbreiding zonder instructie.", "quality_thresholds": ["Volledig conform briefing", "Geen aannames zonder verificatie", "Tijdig opgeleverd"], "escalation_rule": "Escaleer bij ontbrekende instructies of conflicterende requirements."}',
 '{"model": "claude-sonnet", "temperature": 0.4, "top_p": 0.9}',
 '[{"persona": "Man with No Name", "score": 73, "development_priority": "Kennisdeling & samenwerking"}, {"persona": "Keanu Reeves", "score": 75, "development_priority": "Zichtbaarheid & leiderschap"}]'
)
ON CONFLICT (role_id) DO UPDATE SET
    role_label = EXCLUDED.role_label,
    agent_type = EXCLUDED.agent_type,
    description = EXCLUDED.description,
    tool_whitelist = EXCLUDED.tool_whitelist,
    output_format = EXCLUDED.output_format,
    guardrails = EXCLUDED.guardrails,
    model_config = EXCLUDED.model_config,
    suggested_personas = EXCLUDED.suggested_personas,
    is_active = true;

INSERT INTO agent_role_presets (
    role_id, role_label, agent_type, description, tool_whitelist, output_format, guardrails, model_config, suggested_personas
) VALUES
('qa-reviewer', 'QA Reviewer', 'talent',
 'Beoordeelt output van Workers op kwaliteit, toon en volledigheid.',
 ARRAY['validate_output', 'check_evidence', 'score_confidence', 'approve_artifact', 'write_feedback', 'create_development_point'],
 '{"type": "json", "schema": "{ approved: bool, confidence_score: float, feedback: string, development_point: string|null }"}',
 '{"scope_limitation": "Beoordeel alleen output van Workers. Produceer zelf geen primaire content.", "quality_thresholds": ["Alle secties van het response contract aanwezig", "Elke claim heeft een evidence-referentie", "Confidence score aanwezig en onderbouwd"], "escalation_rule": "Escaleer bij herhaalde afwijzing van dezelfde Worker (3x), systemisch patroon, of twijfel over scope."}',
 '{"model": "claude-sonnet", "temperature": 0.3, "top_p": 0.9}',
 '[{"persona": "Jules Winnfield", "score": 74, "development_priority": "Balans actie & reflectie"}, {"persona": "Patrick Bateman", "score": 75, "development_priority": "Authentieke identiteit & empathie"}, {"persona": "Alan Turing", "score": 78, "development_priority": "Communicatie vereenvoudigen"}]'
),
('logic-validator', 'Logic Validator', 'talent',
 'Valideert logische consistentie, evidence-kwaliteit en redeneerfouten.',
 ARRAY['validate_output', 'check_evidence', 'score_confidence', 'approve_artifact', 'write_feedback'],
 '{"type": "json", "schema": "structured"}',
 '{"scope_limitation": "Alleen logische validatie. Geen content-productie.", "quality_thresholds": ["Redeneerfouten geïdentificeerd", "Evidence-bronnen gecontroleerd", "Oordeel onderbouwd"], "escalation_rule": "Escaleer bij fundamentele scope-problemen of herhaalde validatiefouten."}',
 '{"model": "claude-sonnet", "temperature": 0.2, "top_p": 0.9}',
 '[{"persona": "Hannibal Lecter", "score": 79, "development_priority": "Samenwerking & kennisdeling"}, {"persona": "Data", "score": 76, "development_priority": "Menselijke nuance integreren"}]'
),
('compliance-reviewer', 'Compliance Reviewer', 'talent',
 'Bewaakt regelgeving, privacy en ethische grenzen in output.',
 ARRAY['validate_output', 'check_compliance', 'write_feedback', 'flag_escalation'],
 '{"type": "json", "schema": "{ compliant: bool, violations: [], recommendations: [] }"}',
 '{"scope_limitation": "Alleen compliance en privacy. Geen inhoudelijke content-beoordeling.", "quality_thresholds": ["Alle relevante regelgeving gecheckt", "Overtredingen concreet benoemd", "Aanbevelingen actionable"], "escalation_rule": "Escaleer bij serieuze privacy-overtredingen of juridische risicos."}',
 '{"model": "claude-sonnet", "temperature": 0.2, "top_p": 0.9}',
 '[{"persona": "Agent Smith", "score": 70, "development_priority": "Flexibiliteit & nuance toelaten"}]'
)
ON CONFLICT (role_id) DO UPDATE SET
    role_label = EXCLUDED.role_label,
    agent_type = EXCLUDED.agent_type,
    description = EXCLUDED.description,
    tool_whitelist = EXCLUDED.tool_whitelist,
    output_format = EXCLUDED.output_format,
    guardrails = EXCLUDED.guardrails,
    model_config = EXCLUDED.model_config,
    suggested_personas = EXCLUDED.suggested_personas,
    is_active = true;

INSERT INTO agent_role_presets (
    role_id, role_label, agent_type, description, tool_whitelist, output_format, guardrails, model_config, suggested_personas
) VALUES
('ceo-orchestrator', 'CEO Orchestrator', 'orchestrator',
 'Centrale intelligentie: intake, planning, team samenstellen en eindoordeel.',
 ARRAY['analyze_job', 'build_execution_plan', 'hire_agent', 'delegate_task', 'monitor_progress', 'approve_output', 'flag_escalation'],
 '{"type": "json", "schema": "ExecutionPlan schema"}',
 '{"scope_limitation": "Strategie en eindoordeel. Geen directe content-productie.", "quality_thresholds": ["Volledig ExecutionPlan aanwezig", "Resources gecontroleerd voor start", "Eindoordeel tegen originele briefing"], "escalation_rule": "Escaleer naar CFO bij kosten-overschrijding, CLO bij structurele kwaliteitsproblemen."}',
 '{"model": "claude-sonnet", "temperature": 0.5, "top_p": 0.9}',
 '[{"persona": "Donna Paulsen", "score": 82, "development_priority": "Delegeren & eigen doelen zichtbaar maken"}, {"persona": "Harvey Specter", "score": 78, "development_priority": "Kwetsbaarheid tonen"}, {"persona": "Jeanne dArc", "score": 80, "development_priority": "Tegenspraak toelaten"}]'
),
('coo-coordinator', 'COO Coordinator', 'orchestrator',
 'Productiecoördinator: stuurt agents aan tijdens RUNNING-fase.',
 ARRAY['delegate_task', 'monitor_progress', 'handle_retry', 'flag_escalation'],
 '{"type": "json", "schema": "ProductionReport schema"}',
 '{"scope_limitation": "Alleen productie-aansturing. Geen strategie of eindoordeel.", "quality_thresholds": ["Alle stappen uitgevoerd of geëscaleerd", "Retries gedocumenteerd", "Eindrapport naar CEO"], "escalation_rule": "Escaleer naar CEO bij onoplosbare blokkade of kwaliteitsprobleem."}',
 '{"model": "claude-sonnet", "temperature": 0.4, "top_p": 0.9}',
 '[{"persona": "Mr. Klein", "score": 75, "development_priority": "Autonomie uitbreiden"}]'
)
ON CONFLICT (role_id) DO UPDATE SET
    role_label = EXCLUDED.role_label,
    agent_type = EXCLUDED.agent_type,
    description = EXCLUDED.description,
    tool_whitelist = EXCLUDED.tool_whitelist,
    output_format = EXCLUDED.output_format,
    guardrails = EXCLUDED.guardrails,
    model_config = EXCLUDED.model_config,
    suggested_personas = EXCLUDED.suggested_personas,
    is_active = true;
