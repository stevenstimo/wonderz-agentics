"""WordPress adapter - basis structuur voor agent integratie."""

import httpx
import logging

logger = logging.getLogger(__name__)


class WordPressAdapter:
    """Minimale WordPress adapter. Vereist WP_URL, WP_USERNAME en WP_APP_PASSWORD in .env.vm"""

    def __init__(self, wp_url: str, username: str, app_password: str):
        self.wp_url = wp_url.rstrip("/")
        self.username = username
        self.app_password = app_password
        self.base_url = f"{self.wp_url}/wp-json/wp/v2"

    async def get_posts(self, limit: int = 10) -> list:
        """Haal posts op uit WordPress."""
        # TODO: implementeer na WP_APP_PASSWORD in .env.vm
        raise NotImplementedError("WordPress adapter nog niet geconfigureerd")

    async def create_post(self, title: str, content: str, status: str = "draft") -> dict:
        """Maak een nieuwe post aan in WordPress."""
        raise NotImplementedError("WordPress adapter nog niet geconfigureerd")