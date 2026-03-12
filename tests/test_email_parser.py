"""
Email Intake Channel §4.2 — EmailParser unit tests (5 required).
"""
import email
from email import policy
from datetime import datetime, timezone

import pytest

from app.services.email_parser import EmailParser, ParsedEmail


def _message_from_string(s: str) -> email.message.EmailMessage:
    """Build EmailMessage from header + body string."""
    return email.message_from_string(s, policy=policy.default)


def test_plain_body():
    """Plain text body is extracted as-is; body_clean equals body_raw when no HTML/quotes/sig."""
    raw = (
        "From: jan@example.com\n"
        "Subject: Een verzoek\n"
        "Date: Mon, 15 Jan 2024 10:00:00 +0000\n"
        "Message-ID: <abc123@mail.gmail.com>\n"
        "\n"
        "Hallo, ik wil graag een artikel van 400 woorden over Alkmaar."
    )
    msg = _message_from_string(raw)
    parsed = EmailParser.parse(msg)
    assert parsed.from_address == "jan@example.com"
    assert parsed.subject == "Een verzoek"
    assert "400 woorden" in parsed.body_raw
    assert "400 woorden" in parsed.body_clean
    assert parsed.body_raw.strip() == parsed.body_clean.strip()


def test_html_body():
    """HTML body is stripped to plain text; tags and entities gone."""
    raw = (
        "From: test@example.com\n"
        "Subject: HTML mail\n"
        "Date: Tue, 16 Jan 2024 12:00:00 +0000\n"
        "Message-ID: <html1@test>\n"
        "Content-Type: text/html; charset=utf-8\n"
        "\n"
        "<p>Dit is <b>vet</b> en <a href=\"#\">een link</a>.</p>\n"
        "<p>Tweede alinea.</p>"
    )
    msg = _message_from_string(raw)
    parsed = EmailParser.parse(msg)
    assert "vet" in parsed.body_clean
    assert "een link" in parsed.body_clean
    assert "<p>" not in parsed.body_clean
    assert "<b>" not in parsed.body_clean
    assert "Tweede alinea" in parsed.body_clean


def test_signature_strip():
    """Signature block (e.g. 'met vriendelijke groet') is removed from body_clean."""
    raw = (
        "From: marie@example.com\n"
        "Subject: Opdracht\n"
        "Date: Wed, 17 Jan 2024 09:00:00 +0000\n"
        "Message-ID: <sig1@test>\n"
        "\n"
        "Graag een blogpost over duurzaamheid.\n"
        "\n"
        "Met vriendelijke groet,\n"
        "Marie\n"
        "Sent from my iPhone"
    )
    msg = _message_from_string(raw)
    parsed = EmailParser.parse(msg)
    assert "blogpost" in parsed.body_clean
    assert "duurzaamheid" in parsed.body_clean
    assert "Met vriendelijke groet" not in parsed.body_clean
    assert "Marie" not in parsed.body_clean
    assert "Sent from my iPhone" not in parsed.body_clean


def test_quoted_reply_strip():
    """Quoted reply lines (lines starting with '>') are removed from body_clean."""
    raw = (
        "From: reply@example.com\n"
        "Subject: Re: Project\n"
        "Date: Thu, 18 Jan 2024 14:00:00 +0000\n"
        "Message-ID: <quote1@test>\n"
        "\n"
        "Ik wil hierop verder gaan.\n"
        "\n"
        "> Op 17 jan 2024 schreef iemand:\n"
        "> Dit was de eerdere tekst.\n"
        "> Nog meer quoted tekst."
    )
    msg = _message_from_string(raw)
    parsed = EmailParser.parse(msg)
    assert "Ik wil hierop verder gaan" in parsed.body_clean
    assert "Op 17 jan 2024" not in parsed.body_clean
    assert "Dit was de eerdere" not in parsed.body_clean
    assert "Nog meer quoted" not in parsed.body_clean


def test_missing_date_fallback():
    """When Date header is missing or invalid, received_at falls back to sensible default."""
    raw = (
        "From: nodate@example.com\n"
        "Subject: Geen datum\n"
        "Message-ID: <nodate1@test>\n"
        "\n"
        "Body zonder datum header."
    )
    msg = _message_from_string(raw)
    parsed = EmailParser.parse(msg)
    assert parsed.from_address == "nodate@example.com"
    assert "Body zonder datum" in parsed.body_clean
    assert parsed.received_at is not None
    # Should be timezone-aware and roughly "now" (within last minute)
    now = datetime.now(timezone.utc)
    delta = abs((now - parsed.received_at).total_seconds())
    assert delta < 60, "received_at should be near now when Date is missing"
