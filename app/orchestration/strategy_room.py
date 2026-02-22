"""StrategyRoom: Converts StrategicBrief to ExecutionPlan.

The CEO Agent uses this to determine which agents to hire and in what sequence.
Now with dynamic agent selection from the hired_agents table.
"""

from typing import List, Dict, Optional
from models.unified import StrategicBrief, ExecutionPlan, JobStep
from datetime import datetime
import json
import logging
import time
import asyncpg
from anthropic import Anthropic, APIError, APITimeoutError, RateLimitError
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)


class StrategyRoom:
    """Creates ExecutionPlans from StrategicBriefs with dynamic agent selection."""

    # Role → tool mapping
    ROLE_TOOLS = {
        "copywriter": "write_copy",
        "seo": "optimize_seo",
        "reviewer": "review_content",
        "developer": "write_code",
        "paid_ads_manager": "manage_ads",
        "data_analyst": "analyze_data",
        "image-generator": "execute_task",
        "code-writer": "write_code",
        "data-analyst": "analyze_data",
        "video-editor": "execute_task",
        "audio-producer": "execute_task",
        "translator": "execute_task",
        "researcher": "execute_task",
    }

    # Role → description templates
    ROLE_DESCRIPTIONS = {
        "copywriter": "Write {word_count} words about {topic}",
        "seo": "Optimize content for SEO targeting {kpi}",
        "reviewer": "Review content for quality, clarity, and alignment",
        "developer": "Implement technical changes",
        "paid_ads_manager": "Create and optimize ad campaigns",
        "data_analyst": "Analyze data and generate insights",
        "image-generator": "Generate an image based on the brief",
        "code-writer": "Write code for the requested task",
        "data-analyst": "Analyze the provided data and summarize insights",
        "video-editor": "Edit or assemble a video based on the brief",
        "audio-producer": "Produce audio based on the brief",
        "translator": "Translate content based on the brief",
        "researcher": "Research the topic and summarize findings",
    }

    def __init__(self, model: str = "claude-sonnet-4-20250514", max_retries: int = 3):
        self.model = model
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.max_retries = max_retries

    async def get_available_agents(self, db_pool, role: str = None) -> List[dict]:
        """Fetch hired agents from database, optionally filtered by role."""
        if not db_pool:
            return []

        try:
            async with db_pool.acquire() as conn:
                if role:
                    agents = await conn.fetch(
                        "SELECT * FROM hired_agents WHERE role = $1 AND status = 'active'",
                        role
                    )
                else:
                    agents = await conn.fetch(
                        "SELECT * FROM hired_agents WHERE status = 'active'"
                    )
            return [dict(a) for a in agents]
        except Exception as e:
            logger.warning(f"Failed to fetch hired agents: {e}")
            return []

    def _determine_required_roles(self, brief: StrategicBrief) -> List[str]:
        """Determine which agent roles are needed based on the brief."""
        required_role = (brief.context or {}).get("required_role")
        if required_role:
            if required_role == "copywriter":
                return ["copywriter", "reviewer"]
            return [required_role]

        roles = []

        # Always need a writer
        roles.append("copywriter")

        # SEO if platform is website/blog
        platform = brief.context.get("platform", "").lower()
        if platform in ("website", "blog", "web"):
            roles.append("seo")

        # Always need a reviewer
        roles.append("reviewer")

        return roles

    def _get_step_description(self, role: str, brief: StrategicBrief) -> str:
        """Generate step description based on role and brief."""
        template = self.ROLE_DESCRIPTIONS.get(role, f"Execute {role} task")
        word_count = brief.context.get("word_count", "300")
        topic = brief.job_post[:80] if brief.job_post else "the topic"
        kpi = brief.context.get("kpi", "organic traffic")
        return template.format(word_count=word_count, topic=topic, kpi=kpi)

    def _get_tool_for_role(self, role: str) -> str:
        """Map role to unified tool."""
        return self.ROLE_TOOLS.get(role, "execute_task")

    async def generate_dynamic_plan(
        self,
        brief: StrategicBrief,
        db_pool=None
    ) -> ExecutionPlan:
        """Generate plan with dynamic agent selection from hired_agents table.

        This is the new async version that reads from the database.
        Falls back to role-based fallback IDs when no matching agent is found.
        """
        if not brief.is_complete:
            raise ValueError("StrategicBrief is not complete; cannot generate plan.")

        required_roles = self._determine_required_roles(brief)

        plan_steps = []
        missing_agents = []

        for idx, role in enumerate(required_roles):
            # Try to find a hired agent for this role
            agents = await self.get_available_agents(db_pool, role)

            if not agents:
                # No agent for this role — mark for hiring, use fallback ID
                missing_agents.append({
                    "role": role,
                    "reason": f"No active {role} agent found, needs hiring"
                })
                agent_id = f"agent:{role}"
            else:
                # Use highest-scoring available agent
                sorted_agents = sorted(
                    agents,
                    key=lambda a: (a.get("performance_score", 0), a.get("completed_tasks", 0)),
                    reverse=True
                )
                agent_id = sorted_agents[0]["agent_id"]

            plan_steps.append(JobStep(
                step_index=idx + 1,
                agent_role=role,
                agent_id=agent_id,
                unified_tool=self._get_tool_for_role(role),
                requires_approval=(role == "reviewer"),
                description=self._get_step_description(role, brief)
            ))

        # hired_agents list: role names of all agents involved
        hired_list = [s.agent_role for s in plan_steps]

        return ExecutionPlan(
            brief=brief,
            steps=plan_steps,
            hired_agents=hired_list,
            estimated_duration_seconds=len(plan_steps) * 120
        ), missing_agents

    def _get_fallback_plan(self, brief: StrategicBrief, reason: str = "") -> ExecutionPlan:
        """Generate a safe fallback plan when API call fails."""
        logger.warning(f"Using fallback plan. Reason: {reason}")

        steps = [
            JobStep(
                step_index=1,
                agent_role="copywriter",
                agent_id="agent:copywriter",
                unified_tool="write_copy",
                requires_approval=False,
                description="Create content based on the brief"
            ),
            JobStep(
                step_index=2,
                agent_role="reviewer",
                agent_id="agent:reviewer",
                unified_tool="review_content",
                requires_approval=True,
                description="Review copy for quality and alignment"
            )
        ]

        return ExecutionPlan(
            brief=brief,
            steps=steps,
            hired_agents=["copywriter", "reviewer"],
            estimated_duration_seconds=600
        )

    def generate_execution_plan(
        self,
        brief: StrategicBrief,
        available_agents: Optional[List[str]] = None
    ) -> ExecutionPlan:
        """Create an ExecutionPlan from a validated StrategicBrief.

        This is the synchronous version used by the existing intake flow.
        It still tries Claude for smart planning but falls back gracefully.
        Now includes agent_id in steps (using fallback IDs since no DB access here).
        """
        if not brief.is_complete:
            raise ValueError("StrategicBrief is not complete; cannot generate plan.")

        available_agents = available_agents or []

        system_prompt = """You are a project manager planning an AI bureau workflow.

Given a strategic brief, create a detailed step-by-step execution plan.

For the objective in the brief, determine:
1. What sequence of agents should work on it
2. What tools each agent will use
3. Whether each step requires approval

Available agent roles: copywriter, developer, seo, reviewer, paid_ads_manager, data_analyst

Respond with JSON:
{
    "steps": [
        {
            "step_index": 1,
            "agent_role": "copywriter",
            "unified_tool": "write_copy",
            "requires_approval": false,
            "description": "Write the requested content"
        }
    ],
    "required_hires": ["copywriter"],
    "estimated_duration_seconds": 300
}

The 'unified_tool' should be one of: write_copy, optimize_seo, review_content, write_code, manage_ads, analyze_data, execute_task.
"""

        user_message = f"""
Strategic Brief:
- Objective: {brief.context.get('objective', 'Unknown')}
- Platform: {brief.context.get('platform', 'Unknown')}
- Target Audience: {brief.context.get('target_audience', 'Not specified')}
- KPI: {brief.context.get('kpi', 'Not specified')}
- Job Post: {brief.job_post[:300]}

Available agents: {', '.join(available_agents) or 'None specified'}

Create a step-by-step plan to achieve the objective.
"""

        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"StrategyRoom API call attempt {attempt + 1}/{self.max_retries}")

                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}]
                )

                response_text = response.content[0].text

                try:
                    json_start = response_text.find("{")
                    json_end = response_text.rfind("}") + 1

                    if json_start == -1 or json_end <= json_start:
                        logger.error("No JSON found in strategy response")
                        return self._get_fallback_plan(brief, "Invalid response format")

                    json_str = response_text[json_start:json_end]
                    data = json.loads(json_str)

                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"JSON parsing error in strategy response: {e}")
                    return self._get_fallback_plan(brief, f"JSON parsing: {str(e)}")

                if not isinstance(data, dict) or "steps" not in data:
                    logger.error("Invalid strategy response structure")
                    return self._get_fallback_plan(brief, "Missing steps in response")

                try:
                    steps = []
                    for i, s in enumerate(data.get("steps", []), 1):
                        if not isinstance(s, dict):
                            continue

                        role = s.get("agent_role", "unknown")
                        step = JobStep(
                            step_index=s.get("step_index", i),
                            agent_role=role,
                            agent_id=f"agent:{role}",
                            unified_tool=s.get("unified_tool", self._get_tool_for_role(role)),
                            requires_approval=s.get("requires_approval", False),
                            description=s.get("description", "")
                        )
                        steps.append(step)

                    if not steps:
                        return self._get_fallback_plan(brief, "No valid steps in response")

                    plan = ExecutionPlan(
                        brief=brief,
                        steps=steps,
                        hired_agents=data.get("required_hires", []),
                        estimated_duration_seconds=data.get("estimated_duration_seconds", 600)
                    )

                    logger.info(f"Plan generated: {len(steps)} steps, {len(plan.hired_agents)} hires")
                    return plan

                except Exception as e:
                    logger.error(f"Error converting parsed data to ExecutionPlan: {e}")
                    return self._get_fallback_plan(brief, f"Conversion error: {str(e)}")

            except (APITimeoutError, TimeoutError) as e:
                last_error = e
                logger.warning(f"Timeout on attempt {attempt + 1}: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return self._get_fallback_plan(brief, f"API timeout: {str(e)}")

            except RateLimitError as e:
                last_error = e
                logger.warning(f"Rate limit on attempt {attempt + 1}: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
                return self._get_fallback_plan(brief, f"Rate limited: {str(e)}")

            except APIError as e:
                last_error = e
                logger.error(f"API error on attempt {attempt + 1}: {str(e)}")
                if "401" in str(e) or "403" in str(e):
                    return self._get_fallback_plan(brief, f"Auth error: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return self._get_fallback_plan(brief, f"API error: {str(e)}")

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error in strategy room: {e}", exc_info=True)
                return self._get_fallback_plan(brief, f"Unexpected error: {str(e)}")

        logger.error(f"Plan generation failed after all retries. Last error: {last_error}")
        return self._get_fallback_plan(brief, f"Failed after {self.max_retries} retries")
