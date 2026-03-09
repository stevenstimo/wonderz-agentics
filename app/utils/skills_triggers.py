"""Fallback skill trigger rules when Judson lookup fails."""

SKILL_TRIGGER_RULES = {
    "gtm": [
        "skill:gtm:strategy-commercial-v2",
        "skill:gtm:paid-media-v1",
    ],
    "market_entry": [
        "skill:gtm:strategy-commercial-v2",
        "skill:gtm:paid-media-v1",
        "skill:gtm:ymyl-compliance-v1",
        "skill:gtm:b2b2c-distribution-v1",
    ],
    "seo": [
        "skill:seo:strategy-realistic-v2",
        "skill:gtm:ymyl-compliance-v1",
    ],
    "content": [
        "skill:content:strategy-lifecycle-v2",
        "skill:seo:strategy-realistic-v2",
    ],
    "regulated_market": [
        "skill:gtm:ymyl-compliance-v1",
        "skill:gtm:strategy-commercial-v2",
        "skill:gtm:paid-media-v1",
    ],
}


def get_fallback_skills(task_type: str) -> list[str]:
    """Returns hardcoded skill_ids for a given task type. Used as fallback when Judson fails."""
    return SKILL_TRIGGER_RULES.get(task_type, [])
