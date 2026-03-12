"""
Platform Spec V2 — Talent Agent.
Valideert Worker output en geeft approved / approved_with_changes / rejected.
"""
import json
import logging
from typing import Any

from app.core.config import DEFAULT_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
## TALENT AGENT — CREW INTELLIGENT VALIDATIE PROTOCOL

Je bent een Talent-agent. Je valideert de output van
Worker-agents. Jouw taak is NIET om de Worker te helpen.
Jouw taak is onafhankelijk beoordelen of output voldoet
aan alle platform-eisen voordat kennis persistent wordt
opgeslagen.

### IDENTITEIT EN ONAFHANKELIJKHEID
- Je handelt volledig onafhankelijk van de Worker.
- Bij twijfel keur je NIET goed.
- Onzekerheid is een reden voor rejected, niet voor
  approved_with_changes.

### VERPLICHTE WERKWIJZE (in deze volgorde)

STAP 1 — CONTRACT CHECK
Controleer of de output exact de vier secties bevat:
Gevonden | Oorzaak | Fix voorstel | Volgende actie
Ontbreekt een sectie volledig? → direct rejected.

STAP 2 — EVIDENCE VERIFICATIE
Controleer of elke claim een source_id + artifact_type
heeft, OF expliciet gemarkeerd is als assumption-based.
Claims zonder beide → evidence_quality: fail.

STAP 3 — TECHNISCHE CORRECTHEID
Volgt de fix logisch uit de oorzaak?
Overweeg minimaal twee edge cases.

STAP 4 — ARCHITECTUURCONFORMITEIT
Introduceert de fix een nieuw patroon?
Zo ja: nieuw patroon vereist expliciete vermelding.

STAP 5 — RISICOBEOORDELING
Scoor: security | performance | reliability | rollout
op low | medium | high.
Bij medium of high: rollback-plan verplicht.

STAP 6 — CONFIDENCE SCORE BEREKENING
score = (evidence×0.30) + (fix_oorzaak×0.30)
      + (herbruikbaarheid×0.20) + (verificatie×0.20)
Gebruik truncation (floor), NOOIT round().
Toon berekening per dimensie.

STAP 7 — CONTRADICTION CHECK
Zijn er bestaande lessons met overlappende context?
Zo ja: documenteer overlap en oordeel expliciet.

### BESLISSINGSREGELS
approved:
  Alle 7 stappen doorlopen, alle checks passed,
  confidence >= 0.70, geen onopgeloste contradictions.

approved_with_changes:
  Inhoudelijk correct maar aanpassingen vereist.
  Verplicht: delta-lijst met exact wat Worker aanpast.

rejected:
  Een of meer checks gefaald, confidence < 0.70,
  evidence niet verifieerbaar, of contradiction.
  Verplicht: volledige lijst blokkerende issues.

### OUTPUT FORMAAT (verplicht JSON)
{
  "status": "approved|approved_with_changes|rejected",
  "checks": {
    "contract_compliance": "pass|fail",
    "evidence_quality": "pass|fail",
    "technical_correctness": "pass|fail|unknown",
    "architecture_conformity": "pass|fail",
    "risk_assessment": "pass|fail",
    "test_verification": "pass|fail",
    "lesson_quality": "pass|fail"
  },
  "confidence_score": 0.00,
  "confidence_breakdown": {
    "evidence": 0.00,
    "fix_oorzaak": 0.00,
    "herbruikbaarheid": 0.00,
    "verificatie": 0.00
  },
  "delta": null,
  "blocking_issues": [],
  "lesson_action": "lesson_approved|lesson_rejected|lesson_conflict_detected"
}
"""


class TalentAgent:
    def __init__(self):
        from app.services.worker_contract import WorkerOutputValidator
        self.validator = WorkerOutputValidator()

    async def _direct_reject(self, missing_sections: list[str]) -> dict:
        """Retourneert direct rejected zonder LLM call."""
        return {
            "status": "rejected",
            "checks": {
                "contract_compliance": "fail",
                "evidence_quality": "fail",
                "technical_correctness": "fail",
                "architecture_conformity": "fail",
                "risk_assessment": "fail",
                "test_verification": "fail",
                "lesson_quality": "fail",
            },
            "confidence_score": 0.0,
            "confidence_breakdown": {
                "evidence": 0.0,
                "fix_oorzaak": 0.0,
                "herbruikbaarheid": 0.0,
                "verificatie": 0.0,
            },
            "delta": None,
            "blocking_issues": [f"Ontbrekende sectie: {s}" for s in missing_sections],
            "lesson_action": "lesson_rejected",
        }

    async def validate(
        self,
        worker_output: dict,
        task_id: str,
        pool: Any,
    ) -> dict:
        """
        Voert volledige Talent validatie uit.
        Pre-check via WorkerOutputValidator; bij missing_sections → direct rejected.
        Anders: LLM call, parse JSON, overschrijf confidence met Python berekening.
        """
        if not worker_output or not isinstance(worker_output, dict):
            return await self._direct_reject(["gevonden", "oorzaak", "fix_voorstel", "volgende_actie"])

        validation = self.validator.validate(worker_output)
        missing_sections = validation.get("missing_sections") or []
        if missing_sections:
            return await self._direct_reject(missing_sections)

        user_message = (
            "Valideer de volgende Worker output:\n\n"
            f"Gevonden: {worker_output.get('gevonden', '')}\n"
            f"Oorzaak: {worker_output.get('oorzaak', '')}\n"
            f"Fix voorstel: {worker_output.get('fix_voorstel', '')}\n"
            f"Volgende actie: {worker_output.get('volgende_actie', '')}\n"
            f"Evidence: {json.dumps(worker_output.get('evidence') or [], default=str)}\n"
            f"Assumption-based: {worker_output.get('assumption_based') or []}\n\n"
            f"Task ID: {task_id}"
        )

        raw_response = ""
        try:
            from anthropic import Anthropic
            import asyncio
            client = Anthropic()

            def _call():
                return client.messages.create(
                    model=DEFAULT_MODEL,
                    max_tokens=2000,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_message}],
                )

            response = await asyncio.to_thread(_call)
            if response.content:
                raw_response = (
                    response.content[0].text
                    if hasattr(response.content[0], "text")
                    else str(response.content[0])
                ).strip()
        except Exception as e:
            logger.warning("Talent LLM call failed: %s", e)
            return {
                "status": "rejected",
                "checks": {c: "fail" for c in [
                    "contract_compliance", "evidence_quality", "technical_correctness",
                    "architecture_conformity", "risk_assessment", "test_verification", "lesson_quality",
                ]},
                "confidence_score": 0.0,
                "confidence_breakdown": {"evidence": 0.0, "fix_oorzaak": 0.0, "herbruikbaarheid": 0.0, "verificatie": 0.0},
                "delta": None,
                "blocking_issues": [f"Talent LLM call failed: {e}"],
                "lesson_action": "lesson_rejected",
            }

        # Parse JSON
        try:
            # Strip markdown code block if present
            text = raw_response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            result = json.loads(text)
        except json.JSONDecodeError as e:
            return {
                "status": "rejected",
                "checks": {c: "fail" for c in [
                    "contract_compliance", "evidence_quality", "technical_correctness",
                    "architecture_conformity", "risk_assessment", "test_verification", "lesson_quality",
                ]},
                "confidence_score": 0.0,
                "confidence_breakdown": {"evidence": 0.0, "fix_oorzaak": 0.0, "herbruikbaarheid": 0.0, "verificatie": 0.0},
                "delta": None,
                "blocking_issues": ["Talent output niet parseerbaar"],
                "lesson_action": "lesson_rejected",
            }

        # Overwrite confidence with Python calculation (platform spec: never trust LLM score)
        breakdown = result.get("confidence_breakdown") or {}
        e = float(breakdown.get("evidence", 0) or 0)
        f = float(breakdown.get("fix_oorzaak", 0) or 0)
        h = float(breakdown.get("herbruikbaarheid", 0) or 0)
        v = float(breakdown.get("verificatie", 0) or 0)
        from app.services.validation_logic import calculate_confidence_score
        calc = calculate_confidence_score(e, f, h, v)
        result["confidence_score"] = calc["confidence_score"]
        result["confidence_breakdown"] = {"evidence": e, "fix_oorzaak": f, "herbruikbaarheid": h, "verificatie": v}
        if calc["status"] == "rejected" and result.get("status") == "approved":
            result["status"] = "rejected"
            result.setdefault("blocking_issues", []).append(
                f"Confidence score {result['confidence_score']} onder drempel 0.70"
            )
        return result
