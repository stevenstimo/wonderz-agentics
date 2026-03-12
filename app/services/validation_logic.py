"""
Platform Spec sectie 5 — confidence scoring rubric.
Truncation via math.floor, NOOIT round().
Sectie 18: unit tests.
"""
import math


def calculate_confidence_score(
    evidence: float,
    fix_oorzaak: float,
    herbruikbaarheid: float,
    verificatie: float,
) -> dict:
    """
    score = (evidence * 0.30) + (fix_oorzaak * 0.30) +
            (herbruikbaarheid * 0.20) + (verificatie * 0.20)
    Truncation via math.floor(score * 100) / 100.0, NOOIT round().
    """
    raw = (
        evidence * 0.30
        + fix_oorzaak * 0.30
        + herbruikbaarheid * 0.20
        + verificatie * 0.20
    )
    score = math.floor(raw * 100) / 100.0
    status = "approved" if score >= 0.70 else "rejected"
    return {
        "confidence_score": score,
        "is_retrievable": score >= 0.70,
        "status": status,
    }
