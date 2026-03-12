"""
Email Intake Channel §4.2: Extract subject, body and metadata from raw email.
Strips HTML, signatures and quoted reply lines for CEO analysis.
"""

import email
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from typing import Optional

from bs4 import BeautifulSoup


@dataclass
class ParsedEmail:
    """Result of EmailParser.parse()."""

    message_id: str       # stable id for dedupe (hash of Message-ID or fallback)
    from_address: str
    from_name: str
    subject: str
    body_raw: str
    body_clean: str
    received_at: datetime


class EmailParser:
    """Parse raw email into ParsedEmail. Strips HTML, quoted replies, signatures."""

    SIGNATURE_PATTERNS = [
        r"met vriendelijke groe.*",
        r"kind regards.*",
        r"--\s*$",
        r"sent from my.*",
        r"best regards.*",
        r"groeten,.*",
    ]

    @classmethod
    def parse(cls, msg: email.message.Message) -> ParsedEmail:
        """Parse email message into ParsedEmail. Handles missing Date/Message-ID."""
        body_raw = cls._extract_body(msg)
        body_clean = cls._clean_body(body_raw)
        from_header = msg.get("From") or ""
        from_address = cls._extract_address(from_header)
        from_name = cls._extract_name(from_header)
        subject = cls._decode_header(msg.get("Subject") or "")
        received_at = cls._parse_date(msg.get("Date"))
        message_id = cls._hash_message_id(msg, from_address=from_address, subject=subject, received_at=received_at)
        return ParsedEmail(
            message_id=message_id,
            from_address=from_address,
            from_name=from_name,
            subject=subject,
            body_raw=body_raw,
            body_clean=body_clean,
            received_at=received_at,
        )

    @classmethod
    def _extract_body(cls, msg: email.message.Message) -> str:
        """Get plain text body; prefer text/plain, else text/html decoded to text."""
        if msg.is_multipart():
            text_plain = None
            text_html = None
            for part in msg.walk():
                ct = (part.get_content_type() or "").lower()
                if ct == "text/plain":
                    text_plain = cls._decode_payload(part)
                    if text_plain:
                        return text_plain
                if ct == "text/html":
                    text_html = cls._decode_payload(part)
            if text_html:
                return text_html
            return ""
        return cls._decode_payload(msg)

    @staticmethod
    def _decode_payload(part: email.message.Message) -> str:
        """Decode part payload to str. Handles base64/quoted-printable."""
        payload = part.get_payload(decode=True)
        if payload is None:
            return part.get_payload() or ""
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except Exception:
            return payload.decode("utf-8", errors="replace")

    @classmethod
    def _clean_body(cls, raw: str) -> str:
        """Strip HTML, quoted reply lines, and signature blocks."""
        if not raw:
            return ""
        # 1. Strip HTML
        text = BeautifulSoup(raw, "html.parser").get_text(separator="\n")
        # 2. Remove quoted reply lines ("> ")
        lines = [line for line in text.splitlines() if not line.strip().startswith(">")]
        text = "\n".join(lines)
        # 3. Remove signature (split on first pattern match, take head)
        for pattern in cls.SIGNATURE_PATTERNS:
            parts = re.split(pattern, text, maxsplit=1, flags=re.IGNORECASE | re.DOTALL)
            text = (parts[0] if parts else "").strip()
        return text.strip()

    @classmethod
    def _hash_message_id(cls, msg: email.message.Message, from_address: str = "", subject: str = "", received_at: Optional[datetime] = None) -> str:
        """Stable id for dedupe: hash of Message-ID header, or fallback from from+subject+date."""
        mid = msg.get("Message-ID")
        if mid:
            mid = mid.strip().strip("<>")
            return hashlib.sha256(mid.encode("utf-8", errors="replace")).hexdigest()[:32]
        # Fallback when Message-ID is missing (e.g. some clients)
        fallback = f"{from_address}|{subject}|{received_at or datetime.now(timezone.utc)}"
        return hashlib.sha256(fallback.encode("utf-8", errors="replace")).hexdigest()[:32]

    @staticmethod
    def _extract_address(from_header: str) -> str:
        """Extract email address from From header (e.g. 'Name <a@b.com>' -> 'a@b.com')."""
        if not from_header:
            return ""
        parsed = email.utils.getaddresses([from_header])
        if parsed:
            return (parsed[0][1] or "").strip()
        return from_header.strip()

    @staticmethod
    def _extract_name(from_header: str) -> str:
        """Extract display name from From header."""
        if not from_header:
            return ""
        parsed = email.utils.getaddresses([from_header])
        if parsed:
            return (parsed[0][0] or "").strip()
        return ""

    @staticmethod
    def _decode_header(header_value: str) -> str:
        """Decode MIME-encoded header (e.g. =?UTF-8?B?...?=) to str."""
        if not header_value:
            return ""
        decoded_parts = []
        for part, charset in email.header.decode_header(header_value):
            if isinstance(part, bytes):
                try:
                    decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
                except Exception:
                    decoded_parts.append(part.decode("utf-8", errors="replace"))
            else:
                decoded_parts.append(part or "")
        return "".join(decoded_parts).strip()

    @classmethod
    def _parse_date(cls, date_str: Optional[str]) -> datetime:
        """Parse Date header to datetime. Fallback to now() if missing or invalid."""
        if not date_str or not date_str.strip():
            return datetime.now(timezone.utc)
        try:
            dt = email.utils.parsedate_to_datetime(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError):
            return datetime.now(timezone.utc)
