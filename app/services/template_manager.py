"""Job template management."""
from typing import List, Dict, Optional, Any
import logging
import re

logger = logging.getLogger(__name__)


class TemplateManager:
    """Manages job templates and instantiation."""

    def __init__(self, pool):
        self.pool = pool

    async def get_all_templates(
        self,
        category: Optional[str] = None,
        platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all available templates, optionally filtered."""
        async with self.pool.acquire() as conn:
            if category and platform:
                templates = await conn.fetch(
                    """
                    SELECT * FROM job_templates
                    WHERE category = $1 AND platform = $2
                    ORDER BY usage_count DESC
                    """,
                    category,
                    platform,
                )
            elif category:
                templates = await conn.fetch(
                    """
                    SELECT * FROM job_templates
                    WHERE category = $1
                    ORDER BY usage_count DESC
                    """,
                    category,
                )
            elif platform:
                templates = await conn.fetch(
                    """
                    SELECT * FROM job_templates
                    WHERE platform = $1
                    ORDER BY usage_count DESC
                    """,
                    platform,
                )
            else:
                templates = await conn.fetch(
                    """
                    SELECT * FROM job_templates
                    ORDER BY category, usage_count DESC
                    """
                )

        return [dict(t) for t in templates]

    async def instantiate_template(
        self,
        template_id: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create job post from template by filling in variables.

        Example:
        Template: "Write about [PRODUCT_NAME] for [AUDIENCE]"
        Variables: {"PRODUCT_NAME": "iPhone 15", "AUDIENCE": "tech enthusiasts"}
        Result: "Write about iPhone 15 for tech enthusiasts"
        """
        async with self.pool.acquire() as conn:
            template = await conn.fetchrow(
                """
                SELECT job_post_template, required_agents, suggested_skills
                FROM job_templates
                WHERE template_id = $1
                """,
                template_id,
            )

        if not template:
            raise ValueError(f"Template {template_id} not found")

        job_post = template["job_post_template"]
        for key, value in variables.items():
            placeholder = f"[{key}]"
            job_post = job_post.replace(placeholder, str(value))

        remaining = re.findall(r"\[([A-Z_]+)\]", job_post)
        if remaining:
            logger.warning("Unfilled placeholders: %s", remaining)

        return {
            "job_post": job_post,
            "required_agents": template["required_agents"],
            "suggested_skills": template["suggested_skills"],
        }

    async def record_template_usage(
        self,
        template_id: str,
        success: Optional[bool] = None
    ) -> None:
        """Track template usage and success rate."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE job_templates
                SET usage_count = usage_count + 1,
                    updated_at = NOW()
                WHERE template_id = $1
                """,
                template_id,
            )

            if success is not None:
                current = await conn.fetchrow(
                    """
                    SELECT usage_count, success_rate
                    FROM job_templates
                    WHERE template_id = $1
                    """,
                    template_id,
                )

                if current:
                    old_rate = current["success_rate"] or 0.5
                    count = current["usage_count"]
                    new_rate = (old_rate * (count - 1) + (1 if success else 0)) / count

                    await conn.execute(
                        """
                        UPDATE job_templates
                        SET success_rate = $1
                        WHERE template_id = $2
                        """,
                        new_rate,
                        template_id,
                    )
