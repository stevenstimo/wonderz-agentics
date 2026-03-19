"""
StrategyRoom: Converts StrategicBrief to ExecutionPlan.

The CEO Agent uses this to determine which agents to hire and in what sequence.
GTM jobs get a multi-agent plan with GTM specialists (Marcus, Sophie, Tom, Anna, Daan, Eva).
"""

from typing import List, Dict, Optional
from models.unified import StrategicBrief, ExecutionPlan, JobStep
from datetime import datetime
import json
import logging
import time
from anthropic import Anthropic, APIError, APITimeoutError, RateLimitError

logger = logging.getLogger(__name__)

# Strategy room (plan) always uses Sonnet
CEO_MODEL = "claude-sonnet-4-6"


class HiredAgent:
    """Represents a hired agent for a job."""
    def __init__(self, role: str, agent_id: str):
        self.role = role
        self.agent_id = agent_id


GTM_KEYWORDS = [
    "gtm", "go-to-market", "campagne", "campaign", "launch",
    "lancering", "marktintroductie", "marketing strategie",
]


def is_gtm_job(job_post: str) -> bool:
    """Detect GTM/campaign/launch jobs that need multi-agent GTM plan."""
    if not job_post or not isinstance(job_post, str):
        return False
    return any(kw in job_post.lower() for kw in GTM_KEYWORDS)


REVIEWER_ROLES = {"reviewer", "ceo-reviewer"}
FINAL_ROLES = {"ceo"}


def _assign_dependencies(steps: List[JobStep]) -> List[JobStep]:
    """
    Fill depends_on for each step from agent_role defaults. Does not mutate input.
    Reviewer/ceo-reviewer: wait on all previous non-reviewer steps. CEO: wait on all previous. Others: [].
    """
    result: List[JobStep] = []
    for i, step in enumerate(steps):
        existing = getattr(step, "depends_on", []) or []
        if existing:
            result.append(step)
            continue
        role = (step.agent_role or "").strip().lower()
        if role in REVIEWER_ROLES:
            deps = [
                s.step_index for s in steps[:i]
                if (s.agent_role or "").strip().lower() not in REVIEWER_ROLES
            ]
        elif role in FINAL_ROLES:
            deps = [s.step_index for s in steps[:i]]
        else:
            deps = []
        d = step.model_dump()
        d["depends_on"] = deps
        result.append(JobStep(**d))
    return result


def build_gtm_plan(brief) -> "ExecutionPlan":
    """GTM jobs get a multi-agent plan with all GTM specialists."""
    steps = [
        JobStep(step_index=1, agent_role="agent:gtm:director", unified_tool="gtm_strategy", requires_approval=False, description="GTM strategie en marktanalyse"),
        JobStep(step_index=2, agent_role="agent:ads:meta", unified_tool="meta_ads", requires_approval=False, description="Meta/Instagram campagne plan"),
        JobStep(step_index=3, agent_role="agent:ads:google", unified_tool="google_ads", requires_approval=False, description="Google Ads strategie"),
        JobStep(step_index=4, agent_role="agent:email:specialist", unified_tool="email_marketing", requires_approval=False, description="Email sequence voor leads"),
        JobStep(step_index=5, agent_role="agent:social:specialist", unified_tool="social_content", requires_approval=False, description="Social media content plan"),
        JobStep(step_index=6, agent_role="agent:seo:strategist", unified_tool="seo_strategy", requires_approval=False, description="SEO en content strategie"),
        JobStep(step_index=7, agent_role="reviewer", unified_tool="review_content", requires_approval=False, description="Review alle campagne materialen"),
    ]
    steps = _assign_dependencies(steps)
    return ExecutionPlan(
        brief=brief,
        steps=steps,
        hired_agents=["agent:gtm:director", "agent:ads:meta", "agent:ads:google", "agent:email:specialist", "agent:social:specialist", "agent:seo:strategist", "reviewer"],
        estimated_duration_seconds=1200,
    )


class StrategyRoom:
    """Creates ExecutionPlans from StrategicBriefs."""

    def __init__(self, model: str | None = None, max_retries: int = 3):
        self.model = model or CEO_MODEL
        self.client = Anthropic()
        self.max_retries = max_retries

    def _get_fallback_plan(self, brief: StrategicBrief, reason: str = "") -> ExecutionPlan:
        """Generate a safe fallback plan: copywriter → reviewer, optionally seo and image."""
        logger.warning(f"Using fallback plan. Reason: {reason}")
        ctx = getattr(brief, "context", {}) or {}
        if not isinstance(ctx, dict):
            ctx = {}
        includes_image = ctx.get("includes_image") is True
        job_lower = (brief.job_post or "").lower()
        obj_lower = (ctx.get("objective") or "").lower()
        include_seo = "seo" in job_lower or "search" in job_lower or "seo" in obj_lower or "search" in obj_lower
        steps = [
            JobStep(
                step_index=1,
                agent_role="copywriter",
                unified_tool="write_content",
                requires_approval=False,
                description="Write the main content based on the brief",
            ),
            JobStep(
                step_index=2,
                agent_role="reviewer",
                unified_tool="review_content",
                requires_approval=False,
                description="Review the content for quality and tone",
            ),
        ]
        idx = 3
        if include_seo:
            steps.append(
                JobStep(
                    step_index=idx,
                    agent_role="seo",
                    unified_tool="optimize_seo",
                    requires_approval=False,
                    description="Optimize content for search",
                )
            )
            idx += 1
        if includes_image:
            steps.append(
                JobStep(
                    step_index=idx,
                    agent_role="image_generator",
                    unified_tool="generate_image",
                    requires_approval=False,
                    description="Generate image placeholder",
                )
            )
        hires = ["copywriter", "reviewer"] + (["seo"] if include_seo else []) + (["image_generator"] if includes_image else [])
        steps = _assign_dependencies(steps)
        return ExecutionPlan(
            brief=brief,
            steps=steps,
            hired_agents=hires,
            estimated_duration_seconds=600,
        )

    def generate_execution_plan(
        self, 
        brief: StrategicBrief,
        available_agents: Optional[List[str]] = None
    ) -> ExecutionPlan:
        """
        Create an ExecutionPlan from a validated StrategicBrief.
        
        Args:
            brief: The validated StrategicBrief from IntakeEngine
            available_agents: List of agent roles we currently have access to
        
        Returns:
            ExecutionPlan with step-by-step instructions and required hires
            
        Handles:
        - API timeouts with retry logic and exponential backoff
        - Rate limiting with longer backoff
        - JSON parsing failures with sensible fallback plan
        - Invalid responses with default sequencing
        """
        
        if not brief.is_complete:
            raise ValueError("StrategicBrief is not complete; cannot generate plan.")

        # GTM jobs: use multi-agent GTM plan instead of copywriter flow
        job_post = getattr(brief, "job_post", "") or ""
        if is_gtm_job(job_post):
            logger.info("GTM job detected — using GTM multi-agent plan")
            return build_gtm_plan(brief)

        available_agents = available_agents or []
        
        system_prompt = """You are a project manager for a content bureau. Create a simple, practical execution plan.

For typical content jobs, the plan must be:
- Step 1: copywriter — write the content (unified_tool: write_content, description: "Write the main content based on the brief")
- Step 2: reviewer — review the content (unified_tool: review_content, description: "Review the content for quality and tone")
- Step 3: seo — only include if the brief or objective mentions SEO, search, or keywords (unified_tool: optimize_seo, description: "Optimize content for search"). If no SEO mentioned, do NOT include this step.
- Step 4: image_generator — only include if the brief says image, afbeelding, or includes_image is true (unified_tool: generate_image, description: "Generate image placeholder"). Otherwise omit.

Use only these agent_role values: copywriter, reviewer, seo, image_generator. Keep 2-4 steps. No approval required.

Respond with JSON only:
{
    "steps": [
        {"step_index": 1, "agent_role": "copywriter", "unified_tool": "write_content", "requires_approval": false, "description": "Write the main content based on the brief"},
        {"step_index": 2, "agent_role": "reviewer", "unified_tool": "review_content", "requires_approval": false, "description": "Review the content for quality and tone"}
    ],
    "required_hires": ["copywriter", "reviewer"],
    "estimated_duration_seconds": 300
}
"""

        ctx = brief.context if isinstance(brief.context, dict) else {}
        if ctx.get("detected_task_type") == "data_query":
            logger.info("Data-query detected — using single-step data_agent plan")
            steps = [
                JobStep(
                    step_index=1,
                    agent_role="data_agent",
                    unified_tool="fetch_data",
                    requires_approval=False,
                    description="Fetch data using DataAgent",
                )
            ]
            return ExecutionPlan(
                brief=brief,
                steps=steps,
                hired_agents=["data_agent"],
                estimated_duration_seconds=120,
            )
        job_lower = (brief.job_post or "").lower()
        user_message = f"""Strategic Brief:
- Objective: {ctx.get('objective', 'Unknown')}
- Language: {ctx.get('language', 'English')}
- Tone: {ctx.get('tone', 'informative')}
- Focus: {ctx.get('focus', 'general')}
- Word count: {ctx.get('word_count', 'not specified')}
- Includes image: {ctx.get('includes_image', False)}
- Job post (excerpt): {(brief.job_post or '')[:300]}

Create a simple plan: copywriter then reviewer. Add seo step only if SEO/search is mentioned. Add image_generator step only if image/afbeelding is requested.
"""

        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"StrategyRoom API call attempt {attempt + 1}/{self.max_retries}")
                
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    cache_control={"type": "ephemeral"},
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )

                response_text = response.content[0].text
                usage = getattr(response, "usage", None)
                if usage is not None:
                    cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
                    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
                    input_tokens = getattr(usage, "input_tokens", 0) or 0
                    output_tokens = getattr(usage, "output_tokens", 0) or 0
                    logger.info(
                        "[llm_usage] step=strategy_room model=%s input=%s output=%s cache_create=%s cache_read=%s",
                        self.model,
                        input_tokens,
                        output_tokens,
                        cache_create,
                        cache_read,
                    )

                # Parse JSON response
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

                # Validate response structure
                if not isinstance(data, dict) or "steps" not in data:
                    logger.error("Invalid strategy response structure")
                    return self._get_fallback_plan(brief, "Missing steps in response")

                # Convert to JobStep objects with validation; deduplicate by agent_role (LLM sometimes returns each step twice).
                try:
                    seen_roles: set = set()
                    steps = []
                    for i, s in enumerate(data.get("steps", []), 1):
                        if not isinstance(s, dict):
                            logger.warning(f"Step {i} is not a dict, skipping")
                            continue
                        role = (s.get("agent_role") or "unknown").strip().lower()
                        if role in seen_roles:
                            logger.debug("Skipping duplicate step role: %s", role)
                            continue
                        seen_roles.add(role)
                        step = JobStep(
                            step_index=len(steps) + 1,
                            agent_role=s.get("agent_role", "unknown"),
                            unified_tool=s.get("unified_tool", "read_product"),
                            requires_approval=s.get("requires_approval", False),
                            description=s.get("description", "")
                        )
                        steps.append(step)
                    
                    if not steps:
                        logger.error("No valid steps parsed from response")
                        return self._get_fallback_plan(brief, "No valid steps in response")

                    ctx = brief.context if isinstance(brief.context, dict) else {}
                    if ctx.get("includes_image") and not any(
                        (s.agent_role or "").lower() in ("image", "image_generator") for s in steps
                    ):
                        steps.append(
                            JobStep(
                                step_index=len(steps) + 1,
                                agent_role="image_generator",
                                unified_tool="generate_image",
                                requires_approval=False,
                                description="Generate image placeholder",
                            )
                        )

                    steps = _assign_dependencies(steps)
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
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Max retries exceeded for timeout")
                    return self._get_fallback_plan(brief, f"API timeout: {str(e)}")

            except RateLimitError as e:
                last_error = e
                logger.warning(f"Rate limit error on attempt {attempt + 1}: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** (attempt + 1)  # 2s, 4s, 8s
                    logger.info(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("Max retries exceeded for rate limit")
                    return self._get_fallback_plan(brief, f"Rate limited: {str(e)}")

            except APIError as e:
                last_error = e
                logger.error(f"API error on attempt {attempt + 1}: {str(e)}")
                
                # Don't retry auth/validation errors
                if "401" in str(e) or "403" in str(e):
                    logger.error("Authentication error - not retrying")
                    return self._get_fallback_plan(brief, f"Auth error: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("Max retries exceeded")
                    return self._get_fallback_plan(brief, f"API error: {str(e)}")

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error in strategy room: {e}", exc_info=True)
                return self._get_fallback_plan(brief, f"Unexpected error: {str(e)}")

        # Should not reach here
        logger.error(f"Plan generation failed after all retries. Last error: {last_error}")
        return self._get_fallback_plan(brief, f"Failed after {self.max_retries} retries")

