"""
IntakeEngine: Analyzes user job posts and generates clarification questions.

The CEO Agent uses this to determine if there's enough information to create a plan.
"""

from typing import List, Dict, Optional, Any
from models.unified import StrategicBrief, ClarificationQuestion, JobStatus
from datetime import datetime
import hashlib
import os
import uuid
import json
import logging
import time
from anthropic import Anthropic, APIError, APITimeoutError, RateLimitError

logger = logging.getLogger(__name__)


class IntakeEngine:
    """Analyzes job posts and generates strategic briefs with clarification questions."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250929", max_retries: int = 3):
        self.model = model
        # #region agent log
        try:
            from app.debug_log import log_anthropic_key
            log_anthropic_key("intake_engine.py:IntakeEngine.__init__", "env key before Anthropic()", "H5", "run1")
        except Exception:
            pass
        # #endregion
        self.client = Anthropic()
        self.max_retries = max_retries

    def _get_fallback_brief(self, job_post: str, reason: str = "", key_fingerprint: Optional[str] = None) -> StrategicBrief:
        """Generate a fallback brief when API call fails. key_fingerprint (first 8 of sha256) is included so the UI can verify which key was used."""
        logger.warning(f"Using fallback brief for intake. Reason: {reason}")
        ctx = {"error": reason} if reason else {}
        if key_fingerprint is not None:
            ctx["key_fingerprint"] = key_fingerprint
        return StrategicBrief(
            job_post=job_post,
            is_complete=False,
            clarifications=[
                ClarificationQuestion(
                    id=str(uuid.uuid4()),
                    question="What language should the content be in, and any particular angle?",
                    created_at=datetime.utcnow()
                )
            ],
            context=ctx,
            message="Something went wrong on my side. Could you tell me the language and angle you have in mind?",
        )

    def analyze_job_post(
        self,
        job_post: str,
        previous_answers: Optional[Dict[str, str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> StrategicBrief:
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
        key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        key_fp = hashlib.sha256(key.encode()).hexdigest()[:8] if key else ""

        system_prompt = """You are the CEO of an AI content bureau. You have a quick, friendly chat with the user to understand their request.

RULES:
- The user already told you what they want. Read it carefully.
- If the objective is clear (e.g. "write a 400 word article about X"), you probably have enough info.
- Ask a MAXIMUM of 2 short questions per round. Keep them conversational.
- ONLY ask about: language (Dutch/English), tone/angle, specific focus or preferences.
- NEVER ask about: platform, credentials, KPIs, SEO keywords, success metrics, deployment, login details.
- If you have enough info to start, set is_complete=true immediately.
- Reply in the same language as the user's job_post.
- Be brief and friendly, not corporate.

Respond with JSON:
{
    "is_complete": boolean,
    "message": "Your conversational reply to the user",
    "context": {
        "objective": "what the user wants",
        "language": "Dutch/English/detected from input",
        "tone": "informative/storytelling/etc or 'not specified'",
        "focus": "specific angle or 'general'",
        "word_count": number or null,
        "includes_image": true/false
    },
    "clarifications": [
        {"id": "uuid", "question": "Only if you REALLY need to ask something"}
    ]
}

EXAMPLES of good behavior:
- Input: "maak een tekst over Alkmaar, 400 woorden, met image"
  → is_complete: true, message: "Duidelijk! Ik maak een Nederlandse tekst van 400 woorden over Alkmaar met een passende afbeelding. Ik zet het team aan het werk."
  Reason: objective clear, language Dutch, word count and image specified.

- Input: "schrijf iets over honden"
  → is_complete: false, message: ask for length and angle (e.g. "Hoeveel woorden wil je ongeveer, en welke invalshoek? (verzorging, gedrag, rassen...)")
  Reason: too vague.

- Input: "I need a product description for my Shopify store"
  → is_complete: false, message: ask which product and length.
  Reason: no product specified.

- Input: "write content for my website"
  → is_complete: false, message: "Sure! What topic should the content cover, and roughly how many words are you looking for?"

- Input: "blog post about Amsterdam"
  → is_complete: false, message: "Nice topic! Two quick questions: should this be in Dutch or English, and any particular angle? (history, tourism, food, nightlife...)"

RULES:
- If user gives topic + word count → is_complete should be TRUE.
- Default language from input: Dutch text → Dutch, English text → English.
- Default tone: informative. Default focus: general overview.
"""

        user_message = f"Job Post:\n{job_post}"
        if chat_history:
            user_message += "\n\nConversation so far:\n"
            for entry in chat_history:
                role = entry.get("role", "")
                content = entry.get("content", "")
                label = "CEO" if role == "ceo" else "User"
                user_message += f"{label}: {content}\n"
        elif previous_answers:
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
                        return self._get_fallback_brief(job_post, "Invalid Claude response format", key_fingerprint=key_fp)
                    
                    json_str = response_text[json_start:json_end]
                    data = json.loads(json_str)
                    
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"JSON parsing error in intake response: {e}")
                    return self._get_fallback_brief(job_post, f"JSON parsing error: {str(e)}", key_fingerprint=key_fp)

                # Validate parsed data structure
                if not isinstance(data, dict):
                    logger.error("Claude response is not a dict")
                    return self._get_fallback_brief(job_post, "Invalid response structure", key_fingerprint=key_fp)
                
                # Convert parsed data to StrategicBrief
                try:
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
                        context=self._normalize_context(data.get("context", {})),
                        message=data.get("message") or "",
                    )

                    logger.info(f"Intake analysis complete: is_complete={brief.is_complete}, questions={len(brief.clarifications)}")
                    return brief
                    
                except Exception as e:
                    logger.error(f"Error converting parsed data to StrategicBrief: {e}")
                    return self._get_fallback_brief(job_post, f"Conversion error: {str(e)}", key_fingerprint=key_fp)

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
                    return self._get_fallback_brief(job_post, f"API timeout: {str(e)}", key_fingerprint=key_fp)

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
                    return self._get_fallback_brief(job_post, f"Rate limited: {str(e)}", key_fingerprint=key_fp)

            except APIError as e:
                last_error = e
                logger.error(f"API error on attempt {attempt + 1}: {str(e)}")
                
                # Don't retry on auth or validation errors
                if "401" in str(e) or "403" in str(e):
                    logger.error("Authentication error - not retrying")
                    return self._get_fallback_brief(job_post, f"Auth error: {str(e)}", key_fingerprint=key_fp)
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Max retries exceeded: {e}")
                    return self._get_fallback_brief(job_post, f"API error: {str(e)}", key_fingerprint=key_fp)

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error in intake: {e}", exc_info=True)
                return self._get_fallback_brief(job_post, f"Unexpected error: {str(e)}", key_fingerprint=key_fp)

        # Should not reach here, but fallback just in case
        logger.error(f"Intake failed after all retries. Last error: {last_error}")
        return self._get_fallback_brief(job_post, f"Failed after {self.max_retries} retries", key_fingerprint=key_fp)

    def _normalize_context(self, context: Dict) -> Dict[str, Any]:
        """Convert context dict; keep types that are JSON-serializable."""
        result = {}
        for key, value in context.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                result[key] = value
            else:
                result[key] = str(value)
        return result

