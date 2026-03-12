"""
Platform Spec V1 — WorkerOutputValidator unit tests.
"""
import pytest
from app.services.worker_contract import WorkerOutputValidator, REQUIRED_SECTIONS


def test_valid_output_with_evidence():
    """Test A: valide output met alle 4 secties + evidence → valid=True, missing_sections=[]"""
    validator = WorkerOutputValidator()
    output = {
        "gevonden": "Bug in checkout flow.",
        "oorzaak": "Missing null check.",
        "fix_voorstel": "Add guard clause.",
        "volgende_actie": "Deploy and monitor.",
        "evidence": [
            {"source_id": "repo-code", "artifact_type": "repo_file", "file_path": "apps/web/checkout/Page.tsx", "excerpt_summary": "checkout logic"},
        ],
        "assumption_based": [],
    }
    result = validator.validate(output)
    assert result["valid"] is True
    assert result["missing_sections"] == []
    assert result["empty_sections"] == []
    assert result["has_evidence"] is True


def test_missing_volgende_actie():
    """Test B: ontbrekende 'volgende_actie' sectie → valid=False, missing_sections=['volgende_actie']"""
    validator = WorkerOutputValidator()
    output = {
        "gevonden": "Issue found",
        "oorzaak": "Root cause",
        "fix_voorstel": "Fix proposal",
        "evidence": [{"source_id": "repo-code", "artifact_type": "repo_file", "file_path": "x.py"}],
        "assumption_based": [],
    }
    # geen key "volgende_actie"
    result = validator.validate(output)
    assert result["valid"] is False
    assert "volgende_actie" in result["missing_sections"]


def test_no_evidence_no_assumption_based():
    """Test C: alle secties aanwezig, geen evidence, geen assumption-based → valid=False, warnings bevat evidence melding"""
    validator = WorkerOutputValidator()
    output = {
        "gevonden": "Something",
        "oorzaak": "Cause",
        "fix_voorstel": "Fix",
        "volgende_actie": "Next",
        "evidence": [],
        "assumption_based": [],
    }
    result = validator.validate(output)
    assert result["valid"] is False
    assert any("evidence" in w.lower() or "assumption" in w.lower() for w in result["warnings"])


def test_assumption_based_oorzaak():
    """Test D: alle secties aanwezig, geen evidence, WEL assumption-based in oorzaak → valid=True, assumption_based_sections=['oorzaak']"""
    validator = WorkerOutputValidator()
    output = {
        "gevonden": "Something",
        "oorzaak": "Likely cause (assumption-based).",
        "fix_voorstel": "Proposed fix",
        "volgende_actie": "Verify in staging",
        "evidence": [],
        "assumption_based": ["oorzaak"],
    }
    result = validator.validate(output)
    assert result["valid"] is True
    assert "oorzaak" in result["assumption_based_sections"]


# --- SourceRegistry (Platform Spec V1) ---


def test_source_registry_order():
    """SourceRegistry: lessons-store first, wcag before external-references."""
    from app.services.source_registry import SourceRegistry
    registry = SourceRegistry()
    sources = registry.get_sources_for_agent("frontend-engineer")
    ids = [s["source_id"] for s in sources]
    assert ids[0] == "lessons-store"
    idx_wcag = next((i for i, s in enumerate(ids) if s == "wcag"), None)
    idx_ext = next((i for i, s in enumerate(ids) if s == "external-references"), None)
    assert idx_wcag is not None
    assert idx_ext is not None
    assert idx_wcag < idx_ext


def test_source_registry_internal_and_retrieval():
    """is_internal and requires_retrieval."""
    from app.services.source_registry import SourceRegistry
    registry = SourceRegistry()
    assert registry.is_internal("lessons-store") is True
    assert registry.is_internal("wcag") is False
    assert registry.requires_retrieval("external-references") is True
