"""
IntakeEngine: Analyzes user job posts and generates clarification questions.

The CEO Agent uses this to determine if there's enough information to create a plan.
"""

from typing import List, Dict, Optional
from models.unified import StrategicBrief, ClarificationQuestion, JobStatus
from datetime import datetime
import uuid
import json
import logging
import time
from anthropic import Anthropic, APIError, APITimeoutError, RateLimitError
from app.services.agent_instruction_builder import instruction_builder, OutputFormat
from app.services.task_type_detector import task_type_detector
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)


class IntakeEngine:
    """Analyzes job posts and generates strategic briefs with clarification questions."""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022", max_retries: int = 3):
        self.model = model
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.max_retries = max_retries

    def _get_fallback_brief(self, job_post: str, reason: str = "", previous_answers: Optional[Dict[str, str]] = None) -> StrategicBrief:
        """Generate a fallback brief when API call fails."""
        logger.warning(f"Using fallback brief for intake. Reason: {reason}")

        output_format = self._detect_output_format(job_post, previous_answers)
        task_type, required_role = task_type_detector.detect_with_role(job_post)
        
        # If user already answered questions, treat brief as complete
        if previous_answers and len(previous_answers) > 0:
            answers_text = "; ".join(f"{v}" for v in previous_answers.values())
            return StrategicBrief(
                job_post=job_post,
                is_complete=True,
                clarifications=[],
                context={
                    "objective": next((v for k, v in previous_answers.items() if "achiev" in k.lower() or "doel" in k.lower()), answers_text),
                    "target_audience": next((v for k, v in previous_answers.items() if "audience" in k.lower() or "doelgroep" in k.lower()), "algemeen publiek"),
                    "platform": next((v for k, v in previous_answers.items() if "platform" in k.lower()), "web"),
                    **({"output_format": output_format} if output_format else {}),
                    "task_type": task_type.value,
                    "required_role": required_role.value if required_role else None,
                }
            )

        return StrategicBrief(
            job_post=job_post,
            is_complete=False,
            clarifications=[
                ClarificationQuestion(
                    id=str(uuid.uuid4()),
                    question="What platform are you using? (e.g., Shopify, WordPress, custom site)",
                    created_at=datetime.utcnow()
                ),
                ClarificationQuestion(
                    id=str(uuid.uuid4()),
                    question="Who is your target audience?",
                    created_at=datetime.utcnow()
                ),
                ClarificationQuestion(
                    id=str(uuid.uuid4()),
                    question="What are you hoping to achieve with this request?",
                    created_at=datetime.utcnow()
                )
            ],
            context={
                **({"error": reason} if reason else {}),
                **({"output_format": output_format} if output_format else {}),
                "task_type": task_type.value,
                "required_role": required_role.value if required_role else None,
            }
        )

    def analyze_job_post(self, job_post: str, previous_answers: Optional[Dict[str, str]] = None) -> StrategicBrief:
        """
        Analyze a job post and return a StrategicBrief.
        
        If previous_answers is provided, we incorporate the user's feedback into the analysis.
        
        Returns:
            StrategicBrief with is_complete=True if all info is gathered,
            or is_complete=False with clarifications if more info is needed.
            
        Handles:
        - API timeouts with retry logic
        - Rate limiting with exponential backoff
        - JSON parsing failures with fallback questions
        - Invalid responses with sensible defaults
        """
        
        system_prompt = """You are the CEO Agent of an AI bureau. Your job is to analyze job posts from users and determine:
1. Whether you have enough information to create a detailed execution plan
2. If not, what clarifying questions you need to ask

Analyze the job post for:
- **Context**: Which platform/store is this for? (Shopify, WordPress, etc.)
- **Objective**: What is the goal? (e.g., increase conversions, improve SEO, refresh copy)
- **Target Audience**: Who are the customers?
- **Assets/Credentials**: Do we have access to the platform?
- **Timeline**: How urgent is this?
- **KPI**: What metric will we measure success by?

Respond with a JSON object with this structure:
{
    "is_complete": boolean,
    "context": {
        "platform": "string or 'MISSING'",
        "objective": "string",
        "target_audience": "string or 'NOT_SPECIFIED'",
        "has_credentials": "true or false",
        "timeline": "string",
        "kpi": "string or 'NOT_SPECIFIED'"
    },
    "clarifications": [
        {
            "id": "uuid",
            "question": "Your question here?"
        }
    ],
    "summary": "One-line summary of what the user wants"
}

Only set is_complete=true if you have: platform, objective, target_audience, AND credentials access.
"""

        user_message = f"Job Post:\n{job_post}"
        if previous_answers:
            user_message += f"\n\nPrevious Q&A:\n{json.dumps(previous_answers, indent=2)}"

        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"IntakeEngine API call attempt {attempt + 1}/{self.max_retries}")
                
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1500,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}]
                )

                response_text = response.content[0].text
                
                # Parse the JSON response
                try:
                    # Try to extract JSON from the response
                    json_start = response_text.find("{")
                    json_end = response_text.rfind("}") + 1
                    
                    if json_start == -1 or json_end <= json_start:
                        logger.error("No JSON found in Claude response")
                        return self._get_fallback_brief(job_post, "Invalid Claude response format", previous_answers=previous_answers)
                    
                    json_str = response_text[json_start:json_end]
                    data = json.loads(json_str)
                    
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"JSON parsing error in intake response: {e}")
                    return self._get_fallback_brief(job_post, f"JSON parsing error: {str(e)}", previous_answers=previous_answers)

                # Validate parsed data structure
                if not isinstance(data, dict):
                    logger.error("Claude response is not a dict")
                    return self._get_fallback_brief(job_post, "Invalid response structure", previous_answers=previous_answers)
                
                # Convert parsed data to StrategicBrief
                try:
                    output_format = self._detect_output_format(job_post, previous_answers)
                    task_type, required_role = task_type_detector.detect_with_role(job_post)
                    clarifications = [
                        ClarificationQuestion(
                            id=q.get("id", str(uuid.uuid4())),
                            question=q.get("question", "Can you provide more details?"),
                            created_at=datetime.utcnow()
                        )
                        for q in data.get("clarifications", [])
                        if isinstance(q, dict) and "question" in q
                    ]

                    brief = StrategicBrief(
                        job_post=job_post,
                        is_complete=data.get("is_complete", False),
                        clarifications=clarifications,
                        context=self._normalize_context({
                            **data.get("context", {}),
                            **({"output_format": output_format} if output_format else {}),
                            "task_type": task_type.value,
                            "required_role": required_role.value if required_role else None,
                        })
                    )

                    logger.info(f"Intake analysis complete: is_complete={brief.is_complete}, questions={len(brief.clarifications)}")
                    return brief
                    
                except Exception as e:
                    logger.error(f"Error converting parsed data to StrategicBrief: {e}")
                    return self._get_fallback_brief(job_post, f"Conversion error: {str(e)}", previous_answers=previous_answers)

            except (APITimeoutError, TimeoutError) as e:
                last_error = e
                logger.warning(f"Timeout on attempt {attempt + 1}: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Max retries exceeded for timeout: {e}")
                    return self._get_fallback_brief(job_post, f"API timeout: {str(e)}", previous_answers=previous_answers)

            except RateLimitError as e:
                last_error = e
                logger.warning(f"Rate limit error on attempt {attempt + 1}: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    # Longer backoff for rate limits: 2s, 4s, 8s
                    wait_time = 2 ** (attempt + 1)
                    logger.info(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Max retries exceeded for rate limit: {e}")
                    return self._get_fallback_brief(job_post, f"Rate limited: {str(e)}", previous_answers=previous_answers)

            except APIError as e:
                last_error = e
                logger.error(f"API error on attempt {attempt + 1}: {str(e)}")
                
                # Don't retry on auth or validation errors
                if "401" in str(e) or "403" in str(e):
                    logger.error("Authentication error - not retrying")
                    return self._get_fallback_brief(job_post, f"Auth error: {str(e)}", previous_answers=previous_answers)
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Max retries exceeded: {e}")
                    return self._get_fallback_brief(job_post, f"API error: {str(e)}", previous_answers=previous_answers)

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error in intake: {e}", exc_info=True)
                return self._get_fallback_brief(job_post, f"Unexpected error: {str(e)}", previous_answers=previous_answers)

        # Should not reach here, but fallback just in case
        logger.error(f"Intake failed after all retries. Last error: {last_error}")
        return self._get_fallback_brief(job_post, f"Failed after {self.max_retries} retries", previous_answers=previous_answers)

    def _normalize_context(self, context: Dict) -> Dict[str, str]:
        """Convert context dict values to strings for consistency."""
        result = {}
        for key, value in context.items():
            if isinstance(value, str):
                result[key] = value
            elif value is None:
                continue
            else:
                result[key] = str(value)
        return result

    def _detect_output_format(self, job_post: str, previous_answers: Optional[Dict[str, str]] = None) -> Optional[str]:
        """Heuristic detection of requested output format from user intent."""
        haystack = job_post or ""
        if previous_answers:
            haystack += " " + " ".join(str(v) for v in previous_answers.values())

        detected: OutputFormat = instruction_builder.detect_output_format(haystack)
        return detected.value if detected else None
