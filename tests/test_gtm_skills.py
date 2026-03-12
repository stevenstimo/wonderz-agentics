"""Unit tests for GTM Specialist skills and platform config."""

import pytest


def test_gtm_skills_completeness():
    """Alle 7 Phase 1 skills zijn gedefinieerd."""
    from app.agents.gtm_specialist import GTM_SKILLS_PHASE_1

    assert len(GTM_SKILLS_PHASE_1) == 7
    skill_ids = [s["skill_id"] for s in GTM_SKILLS_PHASE_1]
    assert "gtm:content-brief" in skill_ids
    assert "gtm:icp-definition" in skill_ids


def test_gtm_dependency_pipeline():
    """Content Brief vereist channel-strategy en messaging als dependencies."""
    from app.agents.gtm_specialist import GTM_SKILLS_PHASE_1

    cb = next(s for s in GTM_SKILLS_PHASE_1 if s["skill_id"] == "gtm:content-brief")
    assert "gtm:channel-strategy" in cb.get("dependencies", [])
    assert "gtm:messaging" in cb.get("dependencies", [])


def test_gtm_platform_config():
    """Alle drie platforms zijn geconfigureerd."""
    from app.agents.gtm_specialist import GTM_PLATFORMS

    assert "wonderz" in GTM_PLATFORMS
    assert "clawagency" in GTM_PLATFORMS
    assert "blogable" in GTM_PLATFORMS
