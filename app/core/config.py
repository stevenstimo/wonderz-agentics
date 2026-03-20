"""Central config — env vars loaded at import. Use for vars that must be available to systemd."""

import os

# Default Claude model for agents and pipelines (single place for upgrades)
DEFAULT_MODEL = os.getenv("CLAUDE_DEFAULT_MODEL", "claude-sonnet-4-20250514")

# Google OAuth & APIs — ensure these are in systemd Environment or .env
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")
GOOGLE_ADS_DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
# MCC (Manager) customer ID: verplicht als je client-accounts onder een Manager gebruikt. Zet op het 10-cijferige MCC-ID (bijv. 1234567890).
GOOGLE_ADS_LOGIN_CUSTOMER_ID = (os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "") or "").replace("-", "").strip()
# Google PageSpeed Insights API key (voor Lighthouse dashboard block)
PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "")
