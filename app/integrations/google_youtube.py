"""
YouTube Data API v3 + YouTube Analytics API adapter.
Channeldata, videometrics en kijkgedrag per klant via OAuth.
Activeren: klant koppelt via Integrations UI (OAuth).
"""
import logging

import httpx

logger = logging.getLogger(__name__)

DATA_BASE = "https://www.googleapis.com/youtube/v3"
ANALYTICS_BASE = "https://youtubeanalytics.googleapis.com/v2"


async def get_channel_summary(access_token: str) -> dict:
    """Haalt channeldata op: naam, subscribers, views, videocount."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{DATA_BASE}/channels",
                params={"part": "snippet,statistics", "mine": "true"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])

        if not items:
            return {"enabled": True, "data": None, "error": "no_channel"}

        ch = items[0]
        stats = ch.get("statistics", {})
        return {
            "enabled": True,
            "data": {
                "channel_id": ch.get("id"),
                "title": ch.get("snippet", {}).get("title"),
                "subscriber_count": stats.get("subscriberCount"),
                "view_count": stats.get("viewCount"),
                "video_count": stats.get("videoCount"),
            },
        }
    except Exception as e:
        logger.error("YouTube channel fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}


async def get_top_videos(access_token: str, max_results: int = 10) -> dict:
    """Haalt top videos op gesorteerd op views."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{DATA_BASE}/search",
                params={
                    "part": "snippet",
                    "forMine": "true",
                    "type": "video",
                    "order": "viewCount",
                    "maxResults": max_results,
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])

        return {
            "enabled": True,
            "data": {
                "videos": [
                    {
                        "video_id": v.get("id", {}).get("videoId"),
                        "title": v.get("snippet", {}).get("title"),
                        "published_at": v.get("snippet", {}).get("publishedAt"),
                        "thumbnail": v.get("snippet", {})
                        .get("thumbnails", {})
                        .get("medium", {})
                        .get("url"),
                    }
                    for v in items
                ]
            },
        }
    except Exception as e:
        logger.error("YouTube top videos fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}


async def get_analytics(access_token: str, channel_id: str, start_date: str, end_date: str) -> dict:
    """Haalt YouTube Analytics op: views, watchTime, subscribers."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{ANALYTICS_BASE}/reports",
                params={
                    "ids": f"channel=={channel_id}",
                    "startDate": start_date,
                    "endDate": end_date,
                    "metrics": "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost",
                    "dimensions": "day",
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()

        return {
            "enabled": True,
            "data": {
                "headers": [h.get("name") for h in raw.get("columnHeaders", [])],
                "rows": raw.get("rows", []),
            },
        }
    except Exception as e:
        logger.error("YouTube analytics fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}
