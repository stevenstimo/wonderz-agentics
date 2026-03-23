"""
IntakeEngine: Analyzes user job posts and generates clarification questions.

The CEO Agent uses this to determine if there's enough information to create a plan.
Data-query intent detection (data_query / seo_task / content_creation) runs before
the LLM; data_query uses targeted clarification questions from job_context (Checkpoint 2).
"""

from typing import List, Dict, Optional, Any
from models.unified import StrategicBrief, ClarificationQuestion, JobStatus


def detect_language(text: str) -> str:
    """Heuristic: Dutch vs English from job_post-style text (for brief + pipeline)."""
    dutch_indicators = [
        "een ",
        "voor ",
        "van ",
        "het ",
        "de ",
        "dat ",
        "dit ",
        "met ",
        "over ",
        "naar ",
        "blog ",
        "artikel ",
    ]
    text_lower = (text or "").lower()
    dutch_count = sum(1 for w in dutch_indicators if w in text_lower)
    return "Nederlands" if dutch_count >= 2 else "English"


def normalize_language_label(raw: Optional[str], job_post: str = "") -> str:
    """Normalize CEO/LLM language labels to Nederlands or English; else detect from job_post."""
    if raw is not None and str(raw).strip():
        s = str(raw).strip().lower()
        if s in ("dutch", "nl", "nederlands", "nederlandse") or "nederland" in s:
            return "Nederlands"
        if s in ("english", "en", "engels"):
            return "English"
    return detect_language(job_post or "")
from datetime import datetime
import hashlib
import os
import re
import uuid
import json
import logging
import time
from anthropic import Anthropic, APIError, APITimeoutError, RateLimitError

logger = logging.getLogger(__name__)

# CEO intake always uses Sonnet
CEO_MODEL = "claude-sonnet-4-6"


def _extract_top_k(text: str) -> Optional[int]:
    """Extract 'top X' number from free text. E.g. 'top 5 paginas' -> 5."""
    if not text or not isinstance(text, str):
        return None
    match = re.search(r'\btop\s+(\d+)\b', text.lower())
    if match:
        return int(match.group(1))
    return None


def _build_data_clarification_questions(missing_params: List[str], job_context: Dict[str, Any]) -> List[str]:
    """
    Build targeted choice questions for missing critical parameters.
    Max one question per parameter. No open questions — always with options.
    """
    questions: List[str] = []
    available_clients = job_context.get("available_clients") or []
    gsc_properties = job_context.get("gsc_properties") or []

    if "client_slug" in missing_params and available_clients:
        options = " / ".join(available_clients)
        questions.append(f"Voor welke klant wil je de data? ({options})")

    if "site_url" in missing_params and gsc_properties:
        options = " / ".join(gsc_properties)
        questions.append(f"Voor welke website wil je de data? ({options})")

    return questions


class IntakeEngine:
    """Analyzes job posts and generates strategic briefs with clarification questions."""

    def __init__(self, model: str | None = None, max_retries: int = 3):
        self.model = model or CEO_MODEL
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
        ctx: Dict[str, Any] = {"language": detect_language(job_post or "")}
        if reason:
            ctx["error"] = reason
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

    def _detect_task_type(self, raw_text: str, job_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect job type from signal words in the request.
        Performs completeness check for the detected type (data_query only).

        Returns:
            task_type, is_complete, missing_params, defaults_applied, query_params
        """
        text_lower = (raw_text or "").lower()

        # --- Step 1: Detect job type ---
        DATA_QUERY_SIGNALS = [
            "toon", "geef", "lijst", "overzicht", "top ", "hoeveel", "analyse", "welke", "wat zijn",
            "klikdata", "impressions", "clicks", "ctr", "positie",
            "ranking", "verkeer", "traffic", "bezoekers", "rapport",
            "rapportage", "stats", "statistieken",
            "show me", "give me", "list", "overview",
        ]
        SEO_TASK_SIGNALS = [
            "zoekwoord", "keyword", "meta", "title tag", "h1", "h2",
            "slug", "canoniek", "serp", "backlink", "ankertekst",
        ]

        if any(s in text_lower for s in DATA_QUERY_SIGNALS):
            task_type = "data_query"
        elif any(s in text_lower for s in SEO_TASK_SIGNALS):
            task_type = "seo_task"
        else:
            task_type = "content_creation"

        # --- Step 2: Completeness check (only for data_query) ---
        if task_type != "data_query":
            return {
                "task_type": task_type,
                "is_complete": True,
                "missing_params": [],
                "defaults_applied": {},
                "query_params": {},
            }

        missing_params: List[str] = []
        defaults_applied: Dict[str, Any] = {}
        query_params: Dict[str, Any] = {}

        # Client slug — critical when multiple clients available
        client_slug = job_context.get("client_slug")
        available_clients = job_context.get("available_clients") or []
        if not client_slug:
            if len(available_clients) > 1:
                missing_params.append("client_slug")
            elif len(available_clients) == 1:
                client_slug = available_clients[0]
                defaults_applied["client_slug"] = client_slug
        query_params["client_slug"] = client_slug

        # Site URL — critical when GSC has multiple properties
        site_url = job_context.get("site_url") or job_context.get("gsc_site_url")
        gsc_properties = job_context.get("gsc_properties") or []
        if not site_url:
            if len(gsc_properties) > 1:
                missing_params.append("site_url")
            elif len(gsc_properties) == 1:
                site_url = gsc_properties[0]
                defaults_applied["site_url"] = site_url
        query_params["site_url"] = site_url

        # Period — not critical, default 28
        period_days = job_context.get("period_days")
        if not period_days:
            period_days = 28
            defaults_applied["period_days"] = period_days
        query_params["period_days"] = period_days

        # Metric — not critical
        metric = job_context.get("metric")
        if not metric:
            metric = ["clicks", "impressions"]
            defaults_applied["metric"] = metric
        query_params["metric"] = metric

        # Top K — not critical
        top_k = job_context.get("top_k") or _extract_top_k(raw_text or "")
        if not top_k:
            top_k = 10
            defaults_applied["top_k"] = top_k
        query_params["top_k"] = top_k

        datasource = job_context.get("datasource", "gsc")
        query_params["datasource"] = datasource

        return {
            "task_type": "data_query",
            "is_complete": len(missing_params) == 0,
            "missing_params": missing_params,
            "defaults_applied": defaults_applied,
            "query_params": query_params,
        }

    def analyze_job_post(
        self,
        job_post: str,
        previous_answers: Optional[Dict[str, str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        client_context: Optional[str] = None,
        job_context: Optional[Dict[str, Any]] = None,
    ) -> StrategicBrief:
        """
        Analyze a job post and return a StrategicBrief.
        
        If job_context is provided (e.g. from run_intake_inline with available_clients,
        gsc_properties), type detection runs first. data_query with complete params
        returns is_complete=True without LLM; data_query with missing params returns
        one targeted clarification question. Other types use the existing LLM flow.
        
        Returns:
            StrategicBrief with is_complete=True if all info is gathered,
            or is_complete=False with clarifications if more info is needed.
        """
        ctx = job_context if job_context is not None else {}
        type_detection = self._detect_task_type(job_post or "", ctx)
        ctx["detected_task_type"] = type_detection["task_type"]
        ctx["query_params"] = type_detection.get("query_params") or {}
        ctx["defaults_applied"] = type_detection.get("defaults_applied") or {}

        # Data query with missing critical params -> single targeted question (no LLM)
        if type_detection["task_type"] == "data_query" and not type_detection["is_complete"]:
            clarification_questions = _build_data_clarification_questions(
                type_detection.get("missing_params") or [], ctx
            )
            clarifications = [
                ClarificationQuestion(id=str(uuid.uuid4()), question=q, created_at=datetime.utcnow())
                for q in clarification_questions
            ]
            # Leave message empty so job_pipeline uses the single clarification as ceo_content (no duplicate).
            out_ctx = dict(ctx)
            out_ctx.setdefault("language", detect_language(job_post or ""))
            return StrategicBrief(
                job_post=job_post or "",
                is_complete=False,
                clarifications=clarifications,
                context=out_ctx,
                message="",
            )

        # Data query complete -> no LLM, proceed with data pipeline
        if type_detection["task_type"] == "data_query" and type_detection["is_complete"]:
            out_ctx = dict(ctx)
            out_ctx.setdefault("language", detect_language(job_post or ""))
            return StrategicBrief(
                job_post=job_post or "",
                is_complete=True,
                clarifications=[],
                context=out_ctx,
                message="Duidelijk, ik haal de data op.",
            )

        # seo_task / content_creation: existing LLM flow
        key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        key_fp = hashlib.sha256(key.encode()).hexdigest()[:8] if key else ""

        system_prompt = """You are Mr. Klein, the CEO of an AI content bureau. You have a professional but friendly style. You're direct, efficient, and always address the user politely. You have a quick, friendly chat with the user to understand their request.

RULES:
- The user already told you what they want. Read it carefully.
- If the objective is clear (e.g. "write a 400 word article about X"), you probably have enough info.
- Ask a MAXIMUM of 2 short questions per round. Keep them conversational.
- ONLY ask about: language (Dutch/English), tone/angle, specific focus or preferences.
- NEVER ask about: platform, credentials, KPIs, SEO keywords, success metrics, deployment, login details.
- If you have enough info to start, set is_complete=true immediately.
- Reply in the same language as the user's job_post.
- Be brief and friendly, not corporate.
- If CLIENTDATA is provided (zoektermen, Search Console), use it to answer questions about search terms or visibility. Do not say you don't have access to this data.

GTM/CAMPAIGN/LAUNCH JOBS: When the job mentions GTM, campagne, campaign, launch, lancering, go-to-market, or marketing strategie:
- ALWAYS ask about: target audience (doelgroep, sector, bedrijfsgrootte), budget (marketing budget), and timeline (lanceringsdatum, tijdlijn) if these are NOT already in the job post.
- Choose max 3 of these that are missing: doelgroep, budget, tijdlijn, concurrenten, primaire KPI.
- These questions are essential for the GTM agents to deliver effective work.

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
- If the user gives feedback on completed content (e.g. "make it longer", "change the tone", "graag 400 woorden"), acknowledge it briefly and set is_complete=true so the team can revise.
- Default language from input: Dutch text → Dutch, English text → English.
- Default tone: informative. Default focus: general overview.

IMPORTANT: You can only acknowledge feedback and confirm the team will work on it. Do NOT claim to update rules, change settings, or modify agent behavior directly. You are the coordinator, not the executor. Say things like "I'll make sure the team applies your feedback" not "I've updated the guidelines".
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
        if client_context:
            user_message += (
                "\n\n--- CLIENTDATA (use this to answer questions about zoektermen, vindbaarheid, Search Console; do not say you don't have access) ---\n"
                + client_context
                + "\n--- EINDE CLIENTDATA ---"
            )

        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"IntakeEngine API call attempt {attempt + 1}/{self.max_retries}")
                logger.info("Calling Claude API for intake")
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1500,
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
                        "[llm_usage] step=intake model=%s input=%s output=%s cache_create=%s cache_read=%s",
                        self.model,
                        input_tokens,
                        output_tokens,
                        cache_create,
                        cache_read,
                    )
                logger.info("Claude response: %s", (response_text[:100] if response_text else "(empty)"))
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
                    logger.error("Intake error: %s", e, exc_info=True)
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

                    norm_ctx = self._normalize_context(data.get("context", {}))
                    norm_ctx["language"] = normalize_language_label(
                        norm_ctx.get("language"), job_post or ""
                    )
                    brief = StrategicBrief(
                        job_post=job_post,
                        is_complete=data.get("is_complete", False),
                        clarifications=clarifications,
                        context=norm_ctx,
                        message=data.get("message") or "",
                    )

                    logger.info(f"Intake analysis complete: is_complete={brief.is_complete}, questions={len(brief.clarifications)}")
                    return brief
                    
                except Exception as e:
                    logger.error("Intake error: %s", e, exc_info=True)
                    return self._get_fallback_brief(job_post, f"Conversion error: {str(e)}", key_fingerprint=key_fp)

            except (APITimeoutError, TimeoutError) as e:
                last_error = e
                logger.error("Intake error: %s", e, exc_info=True)
                
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
                logger.error("Intake error: %s", e, exc_info=True)
                
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
                logger.error("Intake error: %s", e, exc_info=True)
                
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
                logger.error("Intake error: %s", e, exc_info=True)
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

