"""
Alert management and delivery.
"""
from __future__ import annotations

from typing import Dict
from enum import Enum
from datetime import datetime
import logging
import httpx
import os

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"


class AlertManager:
    """
    Manages alert detection and delivery.
    """

    def __init__(self, pool):
        self.pool = pool
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        raw_emails = os.getenv("ALERT_EMAIL_RECIPIENTS", "")
        self.email_recipients = [email.strip() for email in raw_emails.split(",") if email.strip()]

        # Alert thresholds
        self.thresholds = {
            "error_rate": 0.15,    # 15% error rate = warning
            "success_rate": 0.80,  # <80% success = warning
            "budget_usage": 0.80,  # 80% budget = warning
            "health_score": 50,    # <50 health = critical
        }

    async def check_and_alert(self):
        """
        Check all alert conditions and send notifications.

        Called by background task every 5 minutes.
        """
        from app.services.metrics_collector import MetricsCollector

        collector = MetricsCollector(self.pool)
        health = await collector.get_system_health()

        alerts = []

        # Check health score
        if health["health_score"] < self.thresholds["health_score"]:
            alerts.append({
                "level": AlertLevel.CRITICAL,
                "title": "System Health Critical",
                "message": f"Health score: {health['health_score']}/100",
                "data": health,
            })

        # Check error rate
        error_rate = health["performance"]["error_rate"]
        if error_rate > self.thresholds["error_rate"]:
            alerts.append({
                "level": AlertLevel.WARNING,
                "title": "High Error Rate",
                "message": f"Error rate: {error_rate:.1%} (threshold: {self.thresholds['error_rate']:.1%})",
                "data": {"error_rate": error_rate},
            })

        # Check success rate
        success_rate = health["jobs"]["success_rate"]
        if success_rate < self.thresholds["success_rate"]:
            alerts.append({
                "level": AlertLevel.WARNING,
                "title": "Low Success Rate",
                "message": f"Success rate: {success_rate:.1%} (threshold: {self.thresholds['success_rate']:.1%})",
                "data": {"success_rate": success_rate},
            })

        # Check for suspended agents
        if health["agents"]["suspended"] > 0:
            alerts.append({
                "level": AlertLevel.WARNING,
                "title": "Agents Suspended",
                "message": f"{health['agents']['suspended']} agent(s) suspended due to quality issues",
                "data": {"suspended_count": health["agents"]["suspended"]},
            })

        # Send alerts
        for alert in alerts:
            await self.send_alert(alert)

        return alerts

    async def send_alert(self, alert: Dict):
        """Send alert via configured channels."""
        logger.warning("ALERT [%s]: %s - %s", alert["level"], alert["title"], alert["message"])

        # Slack
        if self.slack_webhook:
            await self._send_slack(alert)

        # Email (if critical)
        if alert["level"] == AlertLevel.CRITICAL and self.email_recipients:
            await self._send_email(alert)

    async def _send_slack(self, alert: Dict):
        """Send alert to Slack."""
        color = {
            AlertLevel.INFO: "#36a64f",
            AlertLevel.WARNING: "#ff9900",
            AlertLevel.CRITICAL: "#ff0000",
        }[alert["level"]]

        payload = {
            "attachments": [{
                "color": color,
                "title": alert["title"],
                "text": alert["message"],
                "footer": "Wonderz Agentic Platform",
                "ts": int(datetime.utcnow().timestamp()),
            }]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.slack_webhook,
                    json=payload,
                    timeout=5.0,
                )
                response.raise_for_status()
                logger.info("Slack alert sent successfully")
        except Exception as exc:
            logger.error("Failed to send Slack alert: %s", exc)

    async def _send_email(self, alert: Dict):
        """Send email alert (placeholder - integrate with your email service)."""
        logger.info("Would send email to %s: %s", self.email_recipients, alert["title"])
        # TODO: Integrate with SendGrid/AWS SES/etc
