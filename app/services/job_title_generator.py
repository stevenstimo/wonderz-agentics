"""
Generate structured job titles.

Format:
- #0112 — De Visman — GSC Traffic Analyse
- #0005 — SEO Blog Schrijven
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def format_job_title(job_number: int, client_name: Optional[str], subject: str) -> str:
    nr = f"#{int(job_number):04d}"
    parts = [nr]
    if client_name and str(client_name).strip():
        parts.append(str(client_name).strip())
    parts.append((subject or "Opdracht").strip())
    return " — ".join(parts)


async def generate_job_subject(
    job_description: str,
    job_type: Optional[str] = None,
    preset_id: Optional[str] = None,
) -> str:
    """
    Deterministic 3-5 word subject generator.
    """
    preset_subjects = {
        "seo-keyword-research": "SEO Keyword Research",
        "seo-content-campaign": "SEO Content Campagne",
        "paid-ads-launch": "Paid Ads Launch",
        "ecommerce-launch": "Product Launch",
        "retention-lifecycle": "Lifecycle Campagne",
        "brand-narrative": "Brand Narratief",
        "data-infra-setup": "Data Infrastructuur",
        "data-query": "Data Analyse",
    }
    if preset_id and preset_id in preset_subjects:
        return preset_subjects[preset_id]
    if job_type and job_type in preset_subjects:
        return preset_subjects[job_type]

    desc = (job_description or "").lower()
    if any(k in desc for k in ("gsc", "search console", "traffic", "clicks")):
        return "GSC Traffic Analyse"
    if any(k in desc for k in ("keyword", "zoekwoord", "zoekvolume")):
        return "Keyword Research"
    if any(k in desc for k in ("blog", "artikel", "schrijf", "schrijven")):
        return "Blog Artikel"
    if any(k in desc for k in ("advertentie", "ads", "campagne")):
        return "Ads Campagne"
    if any(k in desc for k in ("rapport", "analyse", "data")):
        return "Data Analyse"
    if any(k in desc for k in ("product", "webshop", "shopify")):
        return "Product Launch"

    return "Opdracht"

