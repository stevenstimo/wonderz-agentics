"""
Role templates — framework sectie 5 (docs/260317_crew_intelligent_agent_framework.md).
Default tool_whitelist, output_format, guardrails, model_config per role.
"""

ROLE_TEMPLATES = {
    "copywriter": {
        "role": "copywriter",
        "type": "worker",
        "tool_whitelist": [
            "read_brief", "read_product", "write_copy",
            "knowledge_retrieval", "submit_artifact",
        ],
        "skills": [
            "write_landing_page", "write_email_sequence",
            "rewrite_copy", "summarize_brief", "generate_headline_variants",
        ],
        "output_format": {"type": "markdown", "schema": "freeform"},
        "guardrails": {
            "scope_limitation": "Alleen marketing- en communicatiecontent. Nooit juridisch, financieel of medisch advies.",
            "quality_thresholds": ["Volledige uitvoering briefing", "Heldere structuur", "Geen niet-onderbouwde claims"],
            "escalation_rule": "Escaleer bij ontbrekende briefing, tegenstrijdige doelen of impact buiten marketingdomein.",
        },
        "model_config": {"model": "claude-sonnet", "temperature": 0.8, "top_p": 0.95},
    },
    "seo-specialist": {
        "role": "seo-specialist",
        "type": "worker",
        "tool_whitelist": [
            "web_search", "read_analytics", "read_url",
            "write_research", "score_keywords", "knowledge_retrieval", "submit_artifact",
        ],
        "skills": [
            "keyword_research", "competitor_analysis", "content_gap_analysis",
            "serp_analysis", "seo_brief_writing",
        ],
        "output_format": {"type": "json", "schema": "structured"},
        "guardrails": {
            "scope_limitation": "Alleen SEO- en contentstrategieadvies. Geen technische site-aanpassingen uitvoeren.",
            "quality_thresholds": ["Elke keyword-claim onderbouwd met data", "Bronnen geciteerd", "Prioriteitenlijst aanwezig"],
            "escalation_rule": "Escaleer bij conflicterende data, toegangsproblemen of strategische beslissingen buiten SEO-domein.",
        },
        "model_config": {"model": "claude-sonnet", "temperature": 0.6, "top_p": 0.9},
    },
    "support-specialist": {
        "role": "support-specialist",
        "type": "worker",
        "tool_whitelist": [
            "read_tickets", "read_product", "write_response",
            "flag_pattern", "create_summary", "knowledge_retrieval", "submit_artifact",
        ],
        "skills": [
            "answer_support_ticket", "escalate_complaint", "detect_recurring_issue",
            "write_faq_entry", "summarize_ticket_batch",
        ],
        "output_format": {"type": "markdown", "schema": "freeform"},
        "guardrails": {
            "scope_limitation": "Alleen klantvragen binnen productdomein. Geen prijsafspraken, juridische toezeggingen of technische deployments.",
            "quality_thresholds": ["Empathische toon", "Concreet antwoord of duidelijke doorverwijzing", "Geen valse beloften"],
            "escalation_rule": "Escaleer bij juridische claims, data-incidenten of herhaalde klachten over hetzelfde issue (3x+).",
        },
        "model_config": {"model": "claude-sonnet", "temperature": 0.7, "top_p": 0.95},
    },
    "incident-response": {
        "role": "incident-response",
        "type": "worker",
        "tool_whitelist": [
            "read_logs", "execute_fallback", "write_incident_report",
            "flag_escalation", "read_metrics",
        ],
        "skills": [
            "triage_incident", "identify_root_cause", "execute_rollback",
            "write_postmortem", "notify_stakeholders",
        ],
        "output_format": {"type": "json", "schema": "{ severity, root_cause, action_taken, next_steps }"},
        "guardrails": {
            "scope_limitation": "Alleen incident-response binnen gedefinieerde systemen. Geen productiewijzigingen zonder CEO-goedkeuring.",
            "quality_thresholds": ["Root cause geïdentificeerd of als unknown gelabeld", "Acties gedocumenteerd", "Next steps benoemd"],
            "escalation_rule": "Escaleer bij: impact op meer dan één systeem, onbekende root cause na twee iteraties, of data-verlies.",
        },
        "model_config": {"model": "claude-sonnet", "temperature": 0.2, "top_p": 0.9},
    },
    "senior-engineer": {
        "role": "senior-engineer",
        "type": "worker",
        "tool_whitelist": [
            "read_codebase", "write_code", "run_tests",
            "knowledge_retrieval", "submit_artifact", "flag_escalation",
        ],
        "skills": [
            "implement_feature", "write_unit_tests", "code_review",
            "refactor_code", "write_technical_spec",
        ],
        "output_format": {"type": "code", "schema": "freeform"},
        "guardrails": {
            "scope_limitation": "Alleen code binnen gedefinieerde scope. Geen productie-deployments, database-migrations of infrastructuurwijzigingen zonder aparte goedkeuring.",
            "quality_thresholds": ["Tests aanwezig", "Geen hardcoded secrets", "Geen breaking changes zonder vermelding"],
            "escalation_rule": "Escaleer bij architectuurkeuzes, breaking changes of ontbrekende requirements.",
        },
        "model_config": {"model": "claude-sonnet", "temperature": 0.3, "top_p": 0.9},
    },
    "qa-reviewer": {
        "role": "qa-reviewer",
        "type": "talent",
        "tool_whitelist": [
            "validate_output", "check_evidence", "score_confidence",
            "approve_artifact", "write_feedback", "create_development_point",
        ],
        "skills": [
            "validate_response_contract", "check_evidence_quality",
            "score_output_confidence", "flag_assumption_based_claims",
            "write_structured_feedback",
        ],
        "output_format": {
            "type": "json",
            "schema": "{ approved: bool, confidence_score: float, feedback: string, development_point: string|null }",
        },
        "guardrails": {
            "scope_limitation": "Beoordeel alleen Worker-output. Produceer zelf geen primaire content of oplossingen.",
            "quality_thresholds": ["Alle vier response-contract secties aanwezig", "Elke claim evidence-herleidbaar of assumption-based gelabeld"],
            "escalation_rule": "Escaleer bij 3x afwijzing van dezelfde Worker of twijfel over scope van originele opdracht.",
        },
        "model_config": {"model": "claude-sonnet", "temperature": 0.2, "top_p": 0.85},
    },
    "logic-validator": {
        "role": "logic-validator",
        "type": "talent",
        "tool_whitelist": [
            "validate_output", "check_evidence", "score_confidence",
            "approve_artifact", "write_feedback",
        ],
        "skills": [
            "validate_logical_consistency", "check_architectural_conformance",
            "detect_circular_reasoning", "verify_evidence_chain",
        ],
        "output_format": {
            "type": "json",
            "schema": "{ valid: bool, issues: string[], confidence_score: float }",
        },
        "guardrails": {
            "scope_limitation": "Logische en architecturele validatie alleen. Geen inhoudelijk oordeel over creatieve keuzes.",
            "quality_thresholds": ["Alle logische stappen gecontroleerd", "Afwijkingen benoemd met referentie"],
            "escalation_rule": "Escaleer bij fundamentele architectuurconflicten die buiten reviewbevoegdheid vallen.",
        },
        "model_config": {"model": "claude-sonnet", "temperature": 0.1, "top_p": 0.85},
    },
    "orchestrator": {
        "role": "orchestrator",
        "type": "orchestrator",
        "tool_whitelist": [
            "analyze_job", "build_execution_plan", "hire_agent",
            "delegate_task", "monitor_progress", "approve_output",
            "flag_escalation", "generate_intake_questions",
        ],
        "skills": [
            "analyze_job_post", "build_strategic_brief", "select_worker",
            "select_talent", "monitor_job_flow", "handle_approval_gate",
        ],
        "output_format": {
            "type": "json",
            "schema": "ExecutionPlan: { steps: [], assigned_agents: {}, approval_gates: [] }",
        },
        "guardrails": {
            "scope_limitation": "Orkestreer alleen. Produceer zelf geen inhoudelijke content. Delegeer altijd naar gespecialiseerde Workers.",
            "quality_thresholds": ["Elke job heeft een ExecutionPlan voor uitvoering", "Elke Worker-output passeert een Talent voor opslag"],
            "escalation_rule": "Escaleer naar gebruiker bij: budget_exceeded, systemisch falen, of strategische beslissing buiten platformscope.",
        },
        "model_config": {"model": "claude-sonnet", "temperature": 0.4, "top_p": 0.9},
    },
}


def get_role_template(role: str) -> dict | None:
    """Return role template by role key (e.g. copywriter, qa-reviewer, orchestrator)."""
    return ROLE_TEMPLATES.get(role)


def list_role_templates() -> list:
    """Return all role templates for API."""
    return list(ROLE_TEMPLATES.values())
