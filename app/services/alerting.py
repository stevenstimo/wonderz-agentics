"""Basic alerting — log-based with optional email.

Alerts are always written to the structured log.  When SMTP credentials are
configured they are also sent by email.
"""
import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)

# SMTP config from environment
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
ALERT_FROM = os.getenv("ALERT_FROM", "alerts@wonderz-agentic.exe.xyz")
ALERT_TO = os.getenv("ALERT_TO", "")


class AlertManager:
    """Send alerts via structured log + optional email."""

    _instance: Optional["AlertManager"] = None

    def __init__(self):
        self.smtp_configured = bool(SMTP_HOST and SMTP_USER and SMTP_PASS and ALERT_TO)

    @classmethod
    def get(cls) -> "AlertManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def send_alert(
        self,
        subject: str,
        body: str,
        priority: str = "medium",
        extra: Optional[dict] = None,
    ):
        """Fire an alert.  Always logs; emails if SMTP is configured."""
        alert_data = {
            "alert": True,
            "priority": priority,
            "subject": subject,
            "body": body,
            "timestamp": datetime.now().isoformat(),
            **(extra or {}),
        }

        # Always log
        log_fn = {
            "critical": logger.critical,
            "high": logger.error,
            "medium": logger.warning,
            "low": logger.info,
        }.get(priority, logger.warning)

        log_fn("ALERT [%s] %s: %s", priority.upper(), subject, body)

        # Email if configured
        if self.smtp_configured:
            self._send_email(subject, body, priority)

    def _send_email(self, subject: str, body: str, priority: str):
        try:
            msg = MIMEMultipart()
            msg["From"] = ALERT_FROM
            msg["To"] = ALERT_TO
            msg["Subject"] = f"[WONDERZ {priority.upper()}] {subject}"
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)

            logger.info("Alert email sent: %s", subject)
        except Exception as e:
            logger.error("Failed to send alert email: %s", e)
