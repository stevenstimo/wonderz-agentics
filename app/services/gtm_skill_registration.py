"""
GTM Skill Registration — registreert Phase 1 skills in agent_skills tabel.
# assumption-based: wordt alleen aangeroepen als agent_skills tabel bestaat en het schema compatibel is.
"""

import logging
from typing import Any

from app.agents.gtm_specialist import GTM_SKILLS_PHASE_1

logger = logging.getLogger(__name__)


async def register_gtm_skills(pool) -> int:
    """
    Registreer GTM_SKILLS_PHASE_1 in agent_skills indien de tabel bestaat.
    Retourneert aantal geregistreerde skills (0 als tabel niet bestaat of fout).
    """
    try:
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'agent_skills'
                """
            )
            if not exists:
                logger.info("agent_skills tabel niet gevonden — skip GTM skill registration")
                return 0
            cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='agent_skills'"
            )
            col_set = {r["column_name"] for r in cols}
            if not {"skill_id", "name", "domain", "skill_type", "content"}.issubset(col_set):
                logger.info("agent_skills schema niet compatibel — skip GTM skill registration")
                return 0
            count = 0
            for skill in GTM_SKILLS_PHASE_1:
                skill_id = skill.get("skill_id")
                if not skill_id:
                    continue
                name = skill.get("skill_name", skill_id)
                content = skill.get("description", "")
                applicable_to = [skill.get("agent_id", "agent:gtm-specialist")]
                await conn.execute(
                    """
                    INSERT INTO agent_skills (skill_id, name, domain, skill_type, content, applicable_to)
                    VALUES ($1, $2, 'gtm', 'technique', $3, $4)
                    ON CONFLICT (skill_id) DO UPDATE SET name = EXCLUDED.name, content = EXCLUDED.content
                    """,
                    skill_id,
                    name,
                    content,
                    applicable_to,
                )
                count += 1
            return count
    except Exception as e:
        logger.warning("GTM skill registration failed: %s", e)
        return 0
