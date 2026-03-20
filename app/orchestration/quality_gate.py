"""QualityGate — evaluates step output before proceeding."""

import json

from app.orchestration.handoff_context import HandoffContext

QUALITY_THRESHOLDS = {
    "copy_agent": 0.70,
    "reviewer_agent": 0.75,
    "default": 0.65,
}


class QualityGate:
    """
    Beoordeelt of een step-output voldoende kwaliteit heeft om door te gaan.
    Score wordt berekend op basis van de reviewer-output of een heuristische check.
    """

    def evaluate(self, step_name: str, output: str, feedback: str = "") -> float:
        """
        Retourneert een score tussen 0.0 en 1.0.
        Heuristiek: gebruik APPROVED/NEEDS_CHANGES als basis indien aanwezig.
        Anders: lengte + structuur als proxy (assumption-based).
        """
        if "APPROVED" in output.upper():
            return 1.0
        if "NEEDS_CHANGES" in output.upper():
            return 0.40
        # SEO step returns compact JSON — avoid penalizing short keyword plans
        if "focus_keyword" in output and "{" in (output or "")[:400]:
            try:
                start = output.find("{")
                end = output.rfind("}") + 1
                if start >= 0 and end > start:
                    obj = json.loads(output[start:end])
                    if isinstance(obj, dict) and (
                        obj.get("focus_keyword") or obj.get("seo_keywords") or obj.get("keywords")
                    ):
                        return 0.95
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        # assumption-based: lengte als proxy voor kwaliteit
        word_count = len(output.split())
        if word_count >= 200:
            return 0.75
        if word_count >= 100:
            return 0.60
        return 0.40

    def passes(self, step_name: str, score: float) -> bool:
        threshold = QUALITY_THRESHOLDS.get(step_name, QUALITY_THRESHOLDS["default"])
        return score >= threshold

    def check(
        self, ctx: HandoffContext, step_name: str, output: str, feedback: str = ""
    ) -> bool:
        score = self.evaluate(step_name, output, feedback)
        ctx.quality_scores[step_name] = score
        return self.passes(step_name, score)
