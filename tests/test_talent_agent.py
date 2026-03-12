"""
Platform Spec V2 — TalentAgent unit tests.
Test A: valide output → niet rejected vanwege contract.
Test B: ontbrekende sectie → direct rejected, geen LLM, blocking_issues.
Test C: confidence score overschrijving door Python.
"""
import importlib.util
import json
import math
import os
import sys
from unittest.mock import MagicMock

import pytest

# Fake anthropic so we can run tests without the package; talent_agent imports it inside validate()
if "anthropic" not in sys.modules:
    _fake_anthropic = type(sys)("anthropic")
    _fake_anthropic.Anthropic = MagicMock()  # one mock instance used as the "class"
    sys.modules["anthropic"] = _fake_anthropic

# Load talent_agent without pulling agents.__init__ (and real anthropic)
_test_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_test_dir, "..")
_spec = importlib.util.spec_from_file_location(
    "talent_agent",
    os.path.join(_root, "agents", "talent_agent.py"),
)
_talent_agent_mod = importlib.util.module_from_spec(_spec)
if "agents" not in sys.modules:
    sys.modules["agents"] = type(sys)("agents")
sys.modules["agents.talent_agent"] = _talent_agent_mod
_spec.loader.exec_module(_talent_agent_mod)
TalentAgent = _talent_agent_mod.TalentAgent


def _valid_worker_output():
    """Worker output met alle 4 secties + evidence (contract compliant)."""
    return {
        "gevonden": "Bug in login flow",
        "oorzaak": "Missing null check",
        "fix_voorstel": "Add guard before dereference",
        "volgende_actie": "Deploy and monitor",
        "evidence": [{"source_id": "src1", "artifact_type": "file", "file_path": "auth.py"}],
        "assumption_based": [],
    }


@pytest.mark.asyncio
async def test_talent_direct_reject_missing_section():
    """Test B: output met ontbrekende sectie → direct rejected, geen LLM call, blocking_issues bevat sectie."""
    talent = TalentAgent()
    worker_output = {
        "gevonden": "Iets",
        "oorzaak": "Oorzaak",
        # fix_voorstel ontbreekt
        "volgende_actie": "Actie",
        "evidence": [{"source_id": "s", "artifact_type": "file"}],
        "assumption_based": [],
    }
    MockAnthropic = sys.modules["anthropic"].Anthropic
    result = await talent.validate(
        worker_output=worker_output,
        task_id="task-1",
        pool=None,
    )
    assert result["status"] == "rejected"
    assert "Ontbrekende sectie: fix_voorstel" in result["blocking_issues"]
    assert result["confidence_score"] == 0.0
    # Geen LLM call gedaan (validate() returns early bij missing_sections)
    MockAnthropic.assert_not_called()


@pytest.mark.asyncio
async def test_talent_valid_output_not_rejected_by_contract():
    """Test A: valide output (alle 4 secties + evidence) → status niet 'rejected' vanwege contract."""
    talent = TalentAgent()
    worker_output = _valid_worker_output()
    # Mock LLM om approved terug te geven
    llm_json = {
        "status": "approved",
        "checks": {c: "pass" for c in [
            "contract_compliance", "evidence_quality", "technical_correctness",
            "architecture_conformity", "risk_assessment", "test_verification", "lesson_quality",
        ]},
        "confidence_score": 0.85,
        "confidence_breakdown": {"evidence": 1.0, "fix_oorzaak": 0.9, "herbruikbaarheid": 0.7, "verificatie": 0.8},
        "delta": None,
        "blocking_issues": [],
        "lesson_action": "lesson_approved",
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(llm_json))]
    sys.modules["anthropic"].Anthropic.return_value.messages.create.return_value = mock_response
    result = await talent.validate(
        worker_output=worker_output,
        task_id="task-1",
        pool=None,
    )
    # Contract check passed; LLM said approved; Python may overwrite confidence but status stays approved
    assert result["status"] != "rejected"
    assert result["status"] in ("approved", "approved_with_changes")


@pytest.mark.asyncio
async def test_talent_confidence_score_overwritten_by_python():
    """Test C: LLM response met confidence_score=0.95 → Python berekening overschrijft; result == math.floor."""
    talent = TalentAgent()
    # Breakdown die in Python 0.69 geeft (floor), niet 0.95
    # 0.7*0.3 + 0.7*0.3 + 0.7*0.2 + 0.68*0.2 = 0.21+0.21+0.14+0.136 = 0.696 → floor 0.69
    worker_output = _valid_worker_output()
    llm_json = {
        "status": "approved",
        "checks": {c: "pass" for c in [
            "contract_compliance", "evidence_quality", "technical_correctness",
            "architecture_conformity", "risk_assessment", "test_verification", "lesson_quality",
        ]},
        "confidence_score": 0.95,
        "confidence_breakdown": {"evidence": 0.7, "fix_oorzaak": 0.7, "herbruikbaarheid": 0.7, "verificatie": 0.68},
        "delta": None,
        "blocking_issues": [],
        "lesson_action": "lesson_approved",
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(llm_json))]
    sys.modules["anthropic"].Anthropic.return_value.messages.create.return_value = mock_response
    result = await talent.validate(
        worker_output=worker_output,
        task_id="task-1",
        pool=None,
    )
    expected_score = math.floor((0.7 * 0.30 + 0.7 * 0.30 + 0.7 * 0.20 + 0.68 * 0.20) * 100) / 100.0
    assert result["confidence_score"] == expected_score
    assert result["confidence_score"] == 0.69
    assert result["confidence_score"] != 0.95
