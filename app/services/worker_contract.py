"""
Platform Spec V1 — Response Contract (sectie 2).
Worker output: 4 secties + evidence / assumption_based.
"""

import re
from typing import Any

REQUIRED_SECTIONS = [
    "gevonden",
    "oorzaak",
    "fix_voorstel",
    "volgende_actie",
]

# Evidence item: source_id, artifact_type, file_path?, line_start?, line_end?, git_commit?, excerpt_summary?


class WorkerOutputValidator:
    """
    Valideert en parst Worker output conform platform spec sectie 2.
    """

    def validate(self, output: dict) -> dict:
        """
        Controleert of output voldoet aan het response contract.
        Returns: valid, missing_sections, empty_sections, has_evidence,
                 assumption_based_sections, warnings.
        """
        missing_sections = []
        empty_sections = []
        assumption_based_sections = []
        warnings = []

        for sec in REQUIRED_SECTIONS:
            val = output.get(sec)
            if val is None:
                missing_sections.append(sec)
            elif isinstance(val, str) and not val.strip():
                empty_sections.append(sec)
            elif not isinstance(val, str):
                try:
                    if not str(val).strip():
                        empty_sections.append(sec)
                except Exception:
                    empty_sections.append(sec)

        evidence = output.get("evidence")
        if not isinstance(evidence, list):
            evidence = []
        assumption_based = output.get("assumption_based")
        if not isinstance(assumption_based, list):
            assumption_based = []

        has_evidence = len(evidence) > 0
        for item in evidence:
            if not isinstance(item, dict):
                continue
            if not item.get("source_id") or not item.get("artifact_type"):
                warnings.append("Evidence item mist source_id of artifact_type")
            if not item.get("file_path") and not item.get("excerpt_summary"):
                warnings.append("Evidence zonder file_path of excerpt_summary")

        # assumption_based from parsed output (sectienaam per item)
        assumption_based_sections = list(assumption_based) if isinstance(assumption_based, list) else []

        valid = True
        if missing_sections:
            valid = False
        if empty_sections:
            valid = False
        if not has_evidence and not assumption_based_sections:
            valid = False
            warnings.append("Geen evidence en geen assumption-based label; agent moet kiezen.")

        return {
            "valid": valid,
            "missing_sections": missing_sections,
            "empty_sections": empty_sections,
            "has_evidence": has_evidence,
            "assumption_based_sections": assumption_based_sections,
            "warnings": warnings,
        }

    def parse_from_llm_response(self, raw_text: str) -> dict:
        """
        Parst ruwe LLM output naar WorkerOutput-structuur.
        Secties: Gevonden:, Oorzaak:, Fix voorstel:, Volgende actie:
        Evidence: [source_id] | [artifact_type] | [path]
        """
        if not raw_text or not isinstance(raw_text, str):
            return {
                "gevonden": None,
                "oorzaak": None,
                "fix_voorstel": None,
                "volgende_actie": None,
                "evidence": [],
                "assumption_based": [],
            }

        text = raw_text.strip()
        assumption_based = []
        if re.search(r"\bassumption-based\b", text, re.IGNORECASE):
            for sec in REQUIRED_SECTIONS:
                if sec == "gevonden" and re.search(r"gevonden[\s:].*?assumption-based", text, re.IGNORECASE | re.DOTALL):
                    assumption_based.append("gevonden")
                if sec == "oorzaak" and re.search(r"oorzaak[\s:].*?assumption-based", text, re.IGNORECASE | re.DOTALL):
                    assumption_based.append("oorzaak")
                if sec == "fix_voorstel" and re.search(r"fix\s*voorstel[\s:].*?assumption-based", text, re.IGNORECASE | re.DOTALL):
                    assumption_based.append("fix_voorstel")
                if sec == "volgende_actie" and re.search(r"volgende\s*actie[\s:].*?assumption-based", text, re.IGNORECASE | re.DOTALL):
                    assumption_based.append("volgende_actie")

        sections = {}
        pattern = re.compile(
            r"(?:^|\n)\s*(?:##\s*)?(gevonden|oorzaak|fix\s*voorstel|volgende\s*actie)\s*:?\s*\n(.*?)(?=(?:^|\n)\s*(?:##\s*)?(?:gevonden|oorzaak|fix\s*voorstel|volgende\s*actie)\s*:?|\Z)",
            re.IGNORECASE | re.DOTALL,
        )
        for m in pattern.finditer(text):
            name = m.group(1).strip().lower().replace(" ", "_")
            if name == "fix_voorstel":
                name = "fix_voorstel"
            body = (m.group(2) or "").strip()
            if name not in sections:
                sections[name] = body

        # Map to required keys
        gevonden = sections.get("gevonden")
        oorzaak = sections.get("oorzaak")
        fix_voorstel = sections.get("fix_voorstel")
        volgende_actie = sections.get("volgende_actie")

        # Fallback: try splitting by headers only
        if gevonden is None and "gevonden" not in sections:
            for sep in ["Gevonden:", "GEVONDEN:", "Gevonden"]:
                if sep.lower() in text.lower():
                    parts = re.split(re.escape(sep), text, maxsplit=1, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        rest = parts[1]
                        for next_sep in ["Oorzaak:", "Fix voorstel:", "Volgende actie:"]:
                            if next_sep.lower() in rest.lower():
                                rest = re.split(re.escape(next_sep), rest, maxsplit=1, flags=re.IGNORECASE)[0]
                        gevonden = rest.strip()
                    break

        evidence = []
        evidence_pattern = re.compile(
            r"Evidence\s*:\s*([^|\n]+)\s*\|\s*([^|\n]+)\s*(?:\|\s*([^\n]+))?",
            re.IGNORECASE,
        )
        for m in evidence_pattern.finditer(text):
            source_id = (m.group(1) or "").strip()
            artifact_type = (m.group(2) or "").strip()
            path_part = (m.group(3) or "").strip()
            evidence.append({
                "source_id": source_id or "unknown",
                "artifact_type": artifact_type or "unknown",
                "file_path": path_part if path_part else None,
                "excerpt_summary": path_part[:200] if path_part else None,
            })

        return {
            "gevonden": gevonden or "",
            "oorzaak": oorzaak or "",
            "fix_voorstel": fix_voorstel or "",
            "volgende_actie": volgende_actie or "",
            "evidence": evidence,
            "assumption_based": assumption_based,
        }

    def format_for_prompt(self) -> str:
        """Instructie voor Worker agents om correct te formatteren."""
        return """
Je output MOET exact de volgende vier secties bevatten:

Gevonden:
- [wat je hebt aangetroffen]
Evidence: [source_id] | [artifact_type] | [bestandspad:regels]

Oorzaak:
- [root cause]
Evidence: [source_id] | [artifact_type] | [bestandspad:regels]

Fix voorstel:
- [concrete wijziging]
Bestanden: [betrokken bestanden]
Tests: [testbestanden]

Volgende actie:
- [validatiestappen]

Als je geen interne evidence hebt: schrijf
"assumption-based" en voeg een verificatiestap toe.
Ontbreekt een sectie → output is ongeldig.
"""
