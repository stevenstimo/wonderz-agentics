"""
Email Intake Channel §5 & §6 — CEO email intake: 3 mandatory example emails (high/medium/low)
and parsing/truncation. All 3 show completeness_score and score_breakdown in output.
"""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_intake_processor import (
    BODY_TRUNCATE_CHARS,
    EmailIntakeProcessor,
    _parse_ceo_json,
    _truncate_body,
)
from app.services.email_parser import ParsedEmail


def _parsed(subject: str, body_clean: str) -> ParsedEmail:
    return ParsedEmail(
        message_id="test-id",
        from_address="test@example.com",
        from_name="Test",
        subject=subject,
        body_raw=body_clean,
        body_clean=body_clean,
        received_at=datetime.now(timezone.utc),
    )


# High score (≥ 0.70): fully described — platform, audience, length
HIGH_BODY = (
    "Graag een blogartikel van 600 woorden voor onze website (WordPress), "
    "gericht op ondernemers in de retail (MKB). Onderwerp: duurzaam ondernemen. "
    "Toon: professioneel maar toegankelijk. Klaar voor publicatie volgende week."
)
HIGH_JSON = {
    "completeness_score": 0.82,
    "score_breakdown": {"doel": 0.9, "context": 0.85, "scope": 0.8, "kpi": 0.75},
    "plan": {"steps": [{"agent_role": "copywriter", "description": "Blog 600 woorden", "assumptions": []}]},
    "review_note": "",
}

# Medium (0.40–0.69): goal clear, no audience/platform
MEDIUM_BODY = "Wil graag een artikel over thuiswerken. Nederlands, ongeveer 400 woorden."
MEDIUM_JSON = {
    "completeness_score": 0.55,
    "score_breakdown": {"doel": 0.8, "context": 0.4, "scope": 0.5, "kpi": 0.4},
    "plan": {"steps": [{"agent_role": "copywriter", "description": "Artikel thuiswerken", "assumptions": ["Doelgroep niet vermeld"]}]},
    "review_note": "Doelgroep of platform ontbreekt.",
}

# Low (< 0.40): one sentence, no context
LOW_BODY = "Maak iets over voetbal."
LOW_JSON = {
    "completeness_score": 0.25,
    "score_breakdown": {"doel": 0.4, "context": 0.1, "scope": 0.2, "kpi": 0.1},
    "plan": {"steps": [{"agent_role": "copywriter", "description": "Content over voetbal", "assumptions": ["Doelgroep, lengte, platform onbekend"]}]},
    "review_note": "Geef via de UI aan: doelgroep, gewenste lengte en waar het gebruikt wordt.",
}


def _mock_anthropic(response_json: dict):
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=json.dumps(response_json))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_resp
    return mock_client


@pytest.mark.asyncio
async def test_ceo_high_score():
    """Hoge score (≥ 0.70): volledig omschreven taak met platform, doelgroep en gewenste lengte."""
    parsed = _parsed("Blog duurzaam ondernemen", HIGH_BODY)
    with patch("app.services.email_intake_processor.Anthropic", return_value=_mock_anthropic(HIGH_JSON)):
        result = await EmailIntakeProcessor._run_ceo_intake(parsed)
    assert result["completeness_score"] >= 0.70
    assert "score_breakdown" in result
    for dim in ("doel", "context", "scope", "kpi"):
        assert dim in result["score_breakdown"]
    # Output: tonen completeness_score en score_breakdown
    print("\n[High score] completeness_score:", result["completeness_score"])
    print("[High score] score_breakdown:", result["score_breakdown"])


@pytest.mark.asyncio
async def test_ceo_medium_score():
    """Middel (0.40–0.69): doel duidelijk maar geen doelgroep of platform."""
    parsed = _parsed("Artikel thuiswerken", MEDIUM_BODY)
    with patch("app.services.email_intake_processor.Anthropic", return_value=_mock_anthropic(MEDIUM_JSON)):
        result = await EmailIntakeProcessor._run_ceo_intake(parsed)
    assert 0.40 <= result["completeness_score"] <= 0.69
    assert "score_breakdown" in result
    for dim in ("doel", "context", "scope", "kpi"):
        assert dim in result["score_breakdown"]
    print("\n[Medium score] completeness_score:", result["completeness_score"])
    print("[Medium score] score_breakdown:", result["score_breakdown"])


@pytest.mark.asyncio
async def test_ceo_low_score():
    """Lage score (< 0.40): één zin zonder context."""
    parsed = _parsed("Voetbal", LOW_BODY)
    with patch("app.services.email_intake_processor.Anthropic", return_value=_mock_anthropic(LOW_JSON)):
        result = await EmailIntakeProcessor._run_ceo_intake(parsed)
    assert result["completeness_score"] < 0.40
    assert "score_breakdown" in result
    for dim in ("doel", "context", "scope", "kpi"):
        assert dim in result["score_breakdown"]
    print("\n[Low score] completeness_score:", result["completeness_score"])
    print("[Low score] score_breakdown:", result["score_breakdown"])


def test_parse_ceo_json_fallback_markdown():
    """json.loads with explicit fallback: model returns markdown code block → no crash."""
    wrapped = '```json\n{"completeness_score": 0.5, "score_breakdown": {"doel": 0.5, "context": 0.5, "scope": 0.5, "kpi": 0.5}, "plan": {"steps": []}, "review_note": ""}\n```'
    result = _parse_ceo_json(wrapped)
    assert result["completeness_score"] == 0.5
    assert result["score_breakdown"]["doel"] == 0.5


def test_parse_ceo_json_fallback_invalid_returns_safe_default():
    """Invalid JSON / garbage → safe default, no crash."""
    result = _parse_ceo_json("Geen JSON hier, alleen tekst.")
    assert result["completeness_score"] == 0.0
    assert "score_breakdown" in result
    assert result["score_breakdown"]["doel"] == 0.0


def test_body_truncated_to_3000():
    """Body wordt afgekapt op 3000 tekens voor de LLM-call."""
    long_body = "x" * 5000
    truncated = _truncate_body(long_body)
    assert len(truncated) == BODY_TRUNCATE_CHARS
    assert truncated == "x" * 3000
