"""
Platform Spec sectie 3 — Source Registry.
Retrievalvolgorde en agent-specifieke overrides.
"""

# Platform spec sectie 3 — retrievalvolgorde
RETRIEVAL_ORDER = [
    "lessons-store",
    "repo-code",
    "internal-docs",
    "tickets-incidents",
    "adr-rfc",
    "telemetry-logs",
    "external-references",
]

# Agent-specifieke overrides (platform spec sectie 3.3)
AGENT_SOURCE_OVERRIDES = {
    "frontend-engineer": [
        {"source_id": "react-docs", "priority": "high"},
        {"source_id": "typescript-style", "priority": "medium"},
        {"source_id": "wcag", "priority": "high", "type": "compliance"},
    ],
    "backend-engineer": [
        {"source_id": "api-design", "priority": "high"},
        {"source_id": "owasp", "priority": "high", "type": "compliance"},
    ],
    "qa-engineer": [
        {"source_id": "testing-pyramid", "priority": "medium"},
    ],
}

# Externe bronnen (altijd require_retrieval)
EXTERNAL_SOURCE_IDS = {"external-references"}


class SourceRegistry:
    """
    Bepaalt geordende bronnenlijst per agent en policy (internal / require_retrieval).
    """

    def __init__(self):
        self._base_order = RETRIEVAL_ORDER
        self._overrides = AGENT_SOURCE_OVERRIDES
        self._external = EXTERNAL_SOURCE_IDS

    def get_sources_for_agent(self, agent_type: str) -> list[dict]:
        """
        Retourneert geordende bronnenlijst: base RETRIEVAL_ORDER
        + agent-specifieke overrides. Compliance-bronnen na interne bronnen,
        vóór external-references.
        """
        agent_key = (agent_type or "").strip().lower().replace(" ", "-")
        internal_order = [s for s in self._base_order if s != "external-references"]
        result = []
        for i, source_id in enumerate(internal_order, start=1):
            result.append({"source_id": source_id, "priority": i})

        overrides = self._overrides.get(agent_key, [])
        if not overrides:
            for k, v in self._overrides.items():
                if k in agent_key or agent_key in k:
                    overrides = v
                    break

        other = [o for o in overrides if o.get("type") != "compliance"]
        compliance = [o for o in overrides if o.get("type") == "compliance"]

        for o in other:
            sid = o.get("source_id")
            if not sid or any(r["source_id"] == sid for r in result):
                continue
            prio = "high" if o.get("priority") == "high" else "medium"
            result.append({"source_id": sid, "priority": prio})

        for o in compliance:
            sid = o.get("source_id")
            if not sid or any(r["source_id"] == sid for r in result):
                continue
            result.append({"source_id": sid, "priority": "high", "type": "compliance"})

        result.append({"source_id": "external-references", "priority": len(self._base_order)})
        return result

    def is_internal(self, source_id: str) -> bool:
        """
        True als bron interne bron is (alles behalve external-references
        en agent-specifieke externe bronnen zoals wcag/owasp die type=compliance hebben).
        """
        if not source_id:
            return False
        if source_id in self._external:
            return False
        for overrides in self._overrides.values():
            for o in overrides:
                if o.get("source_id") == source_id and o.get("type") == "compliance":
                    return False
        return True

    def requires_retrieval(self, source_id: str) -> bool:
        """
        True als bron alleen geldig is na daadwerkelijke retrieval.
        Externe bronnen: altijd True. Interne: False.
        """
        if not source_id:
            return False
        if source_id in self._external:
            return True
        for overrides in self._overrides.values():
            for o in overrides:
                if o.get("source_id") == source_id and o.get("type") == "compliance":
                    return True
        return False
