import asyncio
import json
import logging
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import DEFAULT_MODEL
from app.db import init_db_pool
from app.database import get_db
from app.services.token_guard import TokenGuard
from app.orchestration.intake_engine import IntakeEngine
from app.utils.job_file_generator import generate_job_artifact, parse_output_to_sections
from app.orchestration.strategy_room import StrategyRoom
from models.unified import JobStatus, ExecutionPlan

logger = logging.getLogger(__name__)
# Temporary debug logger for client knowledge context injection (remove or set to DEBUG after validation)
knowledge_debug_logger = logging.getLogger("knowledge_debug")

# Model for pipeline agent calls (copywriter, reviewer)
CLAUDE_MODEL = DEFAULT_MODEL

# Per-step timeouts (seconds)
TIMEOUT_CONTENT_STEP = 120
TIMEOUT_GTM_STEP = 180
TIMEOUT_REVIEW_STEP = 60

# Thread pool for running sync _run_step_agent with timeout
_step_executor: Optional[ThreadPoolExecutor] = None


def _get_step_executor() -> ThreadPoolExecutor:
    global _step_executor
    if _step_executor is None:
        _step_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="job_step")
    return _step_executor


def _json_default(obj: Any) -> Any:
    """For json.dumps: handle non-JSON-serializable values (e.g. datetime)."""
    from datetime import date, datetime
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


async def _maybe_generate_job_artifact(
    conn,
    job_id: str,
    context: Dict[str, Any],
    completed_steps: list,
    last_content: Optional[str],
    job_post: str,
) -> None:
    """Generate Word docx from job output when content is available. Non-blocking on error."""
    try:
        sections: List[Dict[str, str]] = []
        step_outputs = []
        for s in completed_steps:
            out = s.get("output") if isinstance(s, dict) else None
            if isinstance(out, str):
                try:
                    out = json.loads(out)
                except json.JSONDecodeError:
                    out = {}
            if isinstance(out, dict) and (out.get("content") or out.get("review")):
                step_outputs.append({
                    "step_name": (s.get("step_name") or s.get("agent_role") or "Output") if isinstance(s, dict) else "Output",
                    "content": out.get("content") or out.get("review", ""),
                })

        if len(step_outputs) > 1:
            sections = [{"heading": so["step_name"], "body": so["content"]} for so in step_outputs]
        elif last_content:
            sections = parse_output_to_sections(last_content)

        if not sections:
            return

        brief = context.get("brief") or {}
        if isinstance(brief, dict):
            brand = brief.get("brand") or brief.get("company") or ""
        else:
            brand = ""
        if not brand:
            brand = (job_post or "")[:50] or "Wonderz"
        job_title = "GTM_Strategie" if len(step_outputs) > 1 else "Content"
        content = {
            "title": (job_post or "Rapport")[:80],
            "brand": brand,
            "date": __import__("datetime").datetime.now().strftime("%d %B %Y"),
            "sections": sections,
        }
        await generate_job_artifact(
            conn=conn,
            job_id=job_id,
            content=content,
            file_type="docx",
            brand_name=brand,
            job_title=job_title,
        )
    except Exception as e:
        logger.warning("Job artifact generation skipped for %s: %s", job_id, e)


async def _get_pool():
    pool = await init_db_pool()
    if not pool:
        logger.warning("DB pool not initialised - job pipeline skipped")
        return None
    return pool


def _coerce_context(raw: Any) -> Dict[str, Any]:
    """Coerce context from DB to a plain dict. Handles None, dict, str,
    and double/triple-encoded JSON strings (JSONB string wrapping JSON)."""
    val = raw
    for _ in range(3):
        if not val:
            return {}
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, ValueError):
                return {}
        else:
            return {}
    return val if isinstance(val, dict) else {}


async def _load_job(conn, job_id: str):
    job = await conn.fetchrow(
        "SELECT id, user_id, job_post, context, payload, status, tokens_used FROM jobs WHERE id=$1",
        job_id,
    )
    if not job:
        raise ValueError(f"Job not found: {job_id}")
    return job


# Client knowledge (client_knowledge table) — inject @client context for CEO
CLIENT_CONTEXT_TEMPLATE = """
## [CONTEXT] Client: {client_name}

De volgende informatie is afkomstig van de kennisbronnen van {client_name}.
Gebruik deze informatie als primaire bron. Verzin geen feiten die hier niet instaan.
Als de context onvoldoende is, geef dit aan in je plan.

{chunks}

---
## [TAAK]
"""


async def _build_client_knowledge_block(
    pool,
    user_id: str,
    client_slug: str,
    query: str,
    match_count: int = 5,
    similarity_threshold: float = 0.4,
) -> str:
    """
    Retrieve client_knowledge chunks for the given client and query.
    Returns formatted block for CEO prompt, or a note if no chunks above threshold.
    """
    knowledge_debug_logger.info(
        "[KNOWLEDGE] Aangeroepen voor client_slug=%r, query=%s",
        client_slug,
        (query or "")[:100],
    )
    if not user_id or not client_slug:
        return ""
    query_clean = (query or "").strip()[:8000]
    if not query_clean:
        query_clean = "algemene context"

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT client_id, client_name FROM clients
                WHERE user_id = $1 AND LOWER(slug) = $2
                LIMIT 1
                """,
                user_id,
                client_slug.lower(),
            )
            if not row:
                return ""
            client_id = row["client_id"]
            client_name = row["client_name"] or client_slug

        from app.services.training import generate_embedding
        query_embedding = await generate_embedding(query_clean)
        import json
        emb_json = json.dumps(query_embedding)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ck.chunk_text, ck.source_url, ck.page_title,
                       1 - (ck.embedding <=> $1::vector) AS similarity
                FROM client_knowledge ck
                WHERE ck.client_id = $2
                  AND ck.is_active = true
                  AND 1 - (ck.embedding <=> $1::vector) > $3
                ORDER BY ck.embedding <=> $1::vector
                LIMIT $4
                """,
                emb_json,
                client_id,
                similarity_threshold,
                match_count,
            )
        if not rows:
            knowledge_debug_logger.warning(
                "[KNOWLEDGE] GEEN chunks gevonden voor %r — context leeg",
                client_slug,
            )
            return (
                f"\n## [CONTEXT] Client: {client_name}\n\n"
                "Er is geen relevante kennis beschikbaar voor deze client (geen chunks boven drempel).\n\n---\n\n"
            )
        knowledge_debug_logger.info(
            "[KNOWLEDGE] %s chunks gevonden boven threshold",
            len(rows),
        )
        for i, r in enumerate(rows):
            sim = r.get("similarity")
            src = (r.get("source_url") or r.get("page_title") or "—")[:60]
            txt = (r.get("chunk_text") or "")[:100]
            knowledge_debug_logger.info(
                "[KNOWLEDGE] Chunk %s: similarity=%.3f, source=%s, tekst=%s...",
                i + 1,
                float(sim) if sim is not None else 0,
                src,
                txt,
            )
        chunks_formatted = []
        for r in rows:
            src = r["source_url"] or r["page_title"] or "—"
            chunks_formatted.append(f'Bron ({src}): "{r["chunk_text"][:500]}{"..." if len(r["chunk_text"] or "") > 500 else ""}"')
        chunks_block = "\n\n".join(chunks_formatted)
        return CLIENT_CONTEXT_TEMPLATE.format(
            client_name=client_name,
            chunks=chunks_block,
        ).replace("\n## [TAAK]\n", "\n")
    except Exception as e:
        logger.warning("Client knowledge retrieval failed for slug=%s: %s", client_slug, e)
        return ""


async def _save_checkpoint(conn, job_id: str, content: str, step_name: str) -> None:
    """Save intermediate content to job context so it survives crashes."""
    if not content or not isinstance(content, str):
        return
    try:
        await _update_job_context(conn, job_id, {"final_content": content, "checkpoint_step": step_name})
        logger.debug("Checkpoint saved for job %s after step %s", job_id, step_name)
    except Exception as e:
        logger.warning("Checkpoint save failed for job %s: %s", job_id, e)


def _get_step_timeout(agent_role: str, step_name: str) -> int:
    """Return timeout in seconds based on step type."""
    role_lower = (agent_role or "").lower()
    step_lower = (step_name or "").lower()
    if role_lower in ("reviewer", "review"):
        return TIMEOUT_REVIEW_STEP
    if any(kw in role_lower or kw in step_lower for kw in ("gtm", "campagne", "campaign", "launch", "go-to-market", "meta", "google", "email", "social", "seo")):
        return TIMEOUT_GTM_STEP
    return TIMEOUT_CONTENT_STEP


async def _run_step_agent_with_timeout(
    agent_role: str,
    step_name: str,
    context: Dict[str, Any],
    previous_content: Optional[str],
) -> Tuple[Dict[str, Any], int]:
    """Run agent step with per-step timeout. On timeout: mark step failed, pipeline continues."""
    timeout = _get_step_timeout(agent_role, step_name)
    loop = asyncio.get_event_loop()
    executor = _get_step_executor()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: _run_step_agent(agent_role, step_name, context, previous_content),
            ),
            timeout=timeout,
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("Step timeout after %ds: job step %s (%s)", timeout, step_name, agent_role)
        return (
            {
                "status": "failed",
                "content": None,
                "error": f"Step timeout after {timeout}s",
                "agent_role": agent_role,
                "step_name": step_name or agent_role,
            },
            0,
        )


async def _update_job_context(conn, job_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Read from payload or context (production may have payload only), merge updates, write to payload."""
    row = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_id)
    raw = (row.get("payload") or row.get("context")) if row else None
    current = _coerce_context(raw)
    current.update(updates)
    await conn.execute(
        "UPDATE jobs SET payload=COALESCE(payload, '{}'::jsonb)||$1::jsonb, updated_at=now() WHERE id=$2",
        json.dumps(updates, default=_json_default),
        job_id,
    )
    return current


async def _update_step_progress(conn, step_id, pct: int):
    """Update progress_pct for a job step (10% start, 70% after LLM, 100% done)."""
    await conn.execute(
        "UPDATE job_steps SET progress_pct = $1 WHERE id = $2",
        pct, step_id,
    )


async def _store_clarifications(conn, job_id: str, clarifications, round_number: int):
    for q in clarifications:
        await conn.execute(
            """
            INSERT INTO clarifications(job_id, question_id, question, asked_at, round_number)
            VALUES($1, $2, $3, now(), $4)
            ON CONFLICT (question_id)
            DO UPDATE SET question=$3, asked_at=now(), round_number=$4
            """,
            job_id,
            q.id,
            q.question,
            round_number,
        )


async def _next_clarification_round(conn, job_id: str) -> int:
    row = await conn.fetchrow(
        "SELECT COALESCE(MAX(round_number), 0) AS max_round FROM clarifications WHERE job_id=$1",
        job_id,
    )
    return (row.get("max_round") or 0) + 1


async def _fetch_available_agents(conn) -> List[str]:
    try:
        rows = await conn.fetch(
            "SELECT role FROM hired_agents WHERE status = 'active'"
        )
        return [r["role"] for r in rows if r.get("role")]
    except Exception as exc:
        logger.warning("Failed to load available agents: %s", exc)
        return []


def _brief_ctx(context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract objective, language, tone, focus, word_count from job context.brief."""
    brief = context.get("brief") if isinstance(context.get("brief"), dict) else {}
    ctx = brief.get("context") if isinstance(brief.get("context"), dict) else {}
    result = {
        "objective": ctx.get("objective") or brief.get("objective") or context.get("objective") or "",
        "language": ctx.get("language") or brief.get("language") or context.get("language") or "English",
        "tone": ctx.get("tone") or brief.get("tone") or context.get("tone") or "informative",
        "focus": ctx.get("focus") or brief.get("focus") or context.get("focus") or "general",
        "word_count": ctx.get("word_count") or brief.get("word_count") or context.get("word_count") or 400,
    }
    feedback_text = (context.get("user_feedback") or context.get("feedback")) or ""
    if isinstance(feedback_text, str) and feedback_text.strip():
        m = re.search(r"(\d+)\s*(?:woorden|words)", feedback_text.strip(), re.IGNORECASE)
        if m:
            result["word_count"] = int(m.group(1))
    return result


def _generate_image_gemini(prompt: str) -> dict:
    """Generate image using Gemini and save to disk, return URL path. Fallback to Pollinations if no key or error."""
    try:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            encoded = quote(prompt)
            return {"image_url": f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=768&nologo=true", "source": "pollinations"}

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(
            [f"Generate a professional editorial photograph: {prompt}"],
            generation_config={"response_mime_type": "image/jpeg"},
        )

        image_dir = "/home/exedev/wonderz-agentics/web_ui/frontend/dist/generated"
        os.makedirs(image_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex[:12]}.jpg"
        filepath = os.path.join(image_dir, filename)

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    image_bytes = part.inline_data.data
                    with open(filepath, "wb") as f:
                        f.write(image_bytes)
                    return {"image_url": f"/generated/{filename}", "source": "gemini"}

        encoded = quote(prompt)
        return {"image_url": f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=768&nologo=true", "source": "pollinations_fallback"}

    except Exception as e:
        logger.error("Gemini image generation failed: %s", e)
        encoded = quote(prompt)
        return {"image_url": f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=768&nologo=true", "source": "pollinations_fallback"}


def _build_image_prompt(context: Dict[str, Any]) -> str:
    """Build a descriptive English image prompt from job context for Pollinations.ai."""
    brief_ctx = _brief_ctx(context)
    objective = brief_ctx.get("objective") or context.get("objective", "") or "content"
    focus = brief_ctx.get("focus") or "general"
    topic = objective
    for prefix in [
        "Schrijf een tekst over ",
        "Write a text about ",
        "Write an article about ",
        "Maak een tekst over ",
        "schrijf een ",
        "write a ",
        "maak een ",
        "tekst over ",
        "artikel over ",
        "blog over ",
        "een tekst over ",
        "een artikel over ",
        "korte tekst over ",
        "short text about ",
    ]:
        if topic.lower().startswith(prefix.lower()):
            topic = topic[len(prefix) :].strip()
            break
    prompt = f"Beautiful professional photograph of {topic}"
    if focus and focus != "general":
        prompt += f", {focus} theme"
    prompt += ", high quality editorial photography, vibrant colors, no text overlay, magazine style"
    return prompt


def _run_step_agent(
    agent_role: str,
    step_name: str,
    context: Dict[str, Any],
    previous_content: Optional[str],
) -> Tuple[Dict[str, Any], int]:
    """
    Run one pipeline step: copywriter (Claude), reviewer (Claude), image_generator (Pollinations.ai), or generic Claude.
    Returns (output_dict, tokens_used).
    """
    role_lower = (agent_role or "").lower()
    step_desc = step_name or agent_role or "step"

    # Image generator: Gemini (with Pollinations fallback) — run BEFORE Anthropic check
    if role_lower in ("image_generator", "image generator", "imagegenerator", "image_generation"):
        image_prompt = _build_image_prompt(context)
        result = _generate_image_gemini(image_prompt)
        output = {
            "image_url": result["image_url"],
            "image_prompt": image_prompt,
            "image_status": "generated",
            "image_source": result.get("source", "unknown"),
            "agent_role": agent_role,
        }
        return (output, 0)

    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set; using placeholder for step %s", step_desc)
        return (
            {"status": "placeholder", "content": f"[Placeholder – {step_desc}. No API key.]", "agent_role": agent_role},
            0,
        )

    try:
        from anthropic import Anthropic
        client = Anthropic()
    except Exception as e:
        logger.warning("Anthropic client init failed: %s; using placeholder", e)
        return (
            {"status": "placeholder", "content": f"[Placeholder – {step_desc}. {e}]", "agent_role": agent_role},
            0,
        )

    brief_ctx = _brief_ctx(context)
    objective = brief_ctx.get("objective") or "content"
    language = str(brief_ctx.get("language") or "English")
    tone = str(brief_ctx.get("tone") or "informative")
    focus = str(brief_ctx.get("focus") or "general")
    word_count = brief_ctx.get("word_count")
    if word_count is None:
        word_count = 400
    try:
        word_count = int(word_count)
    except (TypeError, ValueError):
        word_count = 400

    # Copywriter: write main content (never pass previous/final_content — write fresh)
    if role_lower in ("copywriter", "copy writer"):
        system = (
            "You are a professional copywriter for a content bureau. Your ONLY job is to write the actual article text.\n\n"
            "CRITICAL RULES:\n"
            "- Write the COMPLETE, FINAL article text ready for publication\n"
            "- Do NOT write a plan, outline, structure overview, or project description\n"
            "- Do NOT include meta-commentary like \"Projectoverzicht\", \"Leveringscriteria\", \"Status: GOEDGEKEURD\"\n"
            "- Do NOT include checkmarks ✓, status labels, or section descriptions\n"
            "- Do NOT describe what you're going to write — just WRITE IT\n"
            "- Start directly with the article title as a # heading, then the content\n"
            "- When you receive CRITICAL USER FEEDBACK, write a completely new version from scratch. Do not request, expect, or paste any previous draft text.\n"
            f"- Use ## for section headings (not ###, not bold text like **Heading**)\n"
            f"- Write in {language}\n"
            f"- Tone: {tone}\n"
            f"- Write approximately {word_count} words\n\n"
            "EXAMPLE of what you should produce:\n"
            "# De Geschiedenis van Haarlem\n\n"
            "Haarlem is een van de oudste steden van Nederland...\n\n"
            "## De Middeleeuwen\n\n"
            "In de dertiende eeuw...\n\n"
            "EXAMPLE of what you should NEVER produce:\n"
            "# Goedgekeurd Plan: Tekst over Haarlem\n"
            "## Projectoverzicht\n"
            "**Taak:** Het schrijven van...\n"
            "**Lengte:** 400 woorden\n"
            "✓ Correcte spelling\n"
            "**Status:** GOEDGEKEURD"
        )
        knowledge_block = context.get("_knowledge_block") or ""
        if knowledge_block:
            system += "\n\n" + knowledge_block
        try:
            from app.services.worker_contract import WorkerOutputValidator
            system += "\n\n" + WorkerOutputValidator().format_for_prompt()
        except Exception:
            pass
        user = f"Write an article of approximately {word_count} words about: {objective}. Focus: {focus}."
        user_feedback = context.get("user_feedback") or context.get("feedback") or ""
        if user_feedback and isinstance(user_feedback, str):
            user += f"\n\nCRITICAL USER FEEDBACK (you MUST apply this — write a completely new version, do not reference any previous draft):\n{user_feedback}"
        plan_indicators = ["Projectoverzicht", "Leveringscriteria", "GOEDGEKEURD", "Uitvoeringsplan", "Volgende Stap", "Status:"]
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = (response.content[0].text if response.content else "").strip()
            tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            if any(indicator in text for indicator in plan_indicators):
                retry_system = system + "\n\nWARNING: Your previous attempt produced a plan/outline instead of an article. Write the ACTUAL ARTICLE TEXT. No plans, no outlines, no project descriptions."
                response = client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=4000,
                    system=retry_system,
                    messages=[{"role": "user", "content": user}],
                )
                text = (response.content[0].text if response.content else "").strip()
                tokens += (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            out = {"status": "completed", "content": text, "agent_role": agent_role, "step_name": step_desc}
            try:
                from app.services.worker_contract import WorkerOutputValidator
                validator = WorkerOutputValidator()
                parsed = validator.parse_from_llm_response(text)
                validation = validator.validate(parsed)
                out["worker_output"] = parsed
                out["validation_status"] = "valid" if validation.get("valid") else "invalid"
                out["validation_warnings"] = validation.get("warnings") or []
                if not validation.get("valid"):
                    logger.warning(
                        "Worker contract invalid: missing=%s empty=%s",
                        validation.get("missing_sections"),
                        validation.get("empty_sections"),
                    )
            except Exception as _vc:
                logger.debug("Worker contract parse/validate skipped: %s", _vc)
            return (out, tokens)
        except Exception as e:
            logger.exception("Copywriter step failed: %s", e)
            return ({"status": "failed", "content": "", "error": str(e), "agent_role": agent_role}, 0)

    # Reviewer: review previous content
    if role_lower in ("reviewer", "review"):
        if not previous_content:
            return ({"status": "skipped", "review": "No content to review.", "approved": True, "agent_role": agent_role}, 0)
        system = (
            "You are a content reviewer. Check quality, grammar, and tone consistency. Reply in the same language as the content. Keep the reply concise. End with APPROVED or CHANGES NEEDED. "
            "If the content looks like a plan or outline instead of actual article text, mark it as NOT APPROVED and explain that actual content is needed, not a plan."
        )
        knowledge_block = context.get("_knowledge_block") or ""
        if knowledge_block:
            system += "\n\n" + knowledge_block
        user = f"Review this content:\n\n{previous_content[:12000]}"
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            review_text = (response.content[0].text if response.content else "").strip()
            approved = "approved" in review_text.lower() or "changes needed" not in review_text.lower()
            tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            return (
                {"status": "completed", "review": review_text, "approved": approved, "agent_role": agent_role, "content": previous_content},
                tokens,
            )
        except Exception as e:
            logger.exception("Reviewer step failed: %s", e)
            return ({"status": "failed", "review": str(e), "approved": False, "agent_role": agent_role}, 0)

    # Generic: one Claude call
    system = f"You are a helpful assistant. Write in {language}. Tone: {tone}."
    knowledge_block = context.get("_knowledge_block") or ""
    if knowledge_block:
        system += "\n\n" + knowledge_block
    user = f"Task: {step_desc}. Context: {objective}. Produce the requested output (no meta-commentary)."
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = (response.content[0].text if response.content else "").strip()
        tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
        return ({"status": "completed", "content": text, "agent_role": agent_role, "step_name": step_desc}, tokens)
    except Exception as e:
        logger.exception("Generic step failed: %s", e)
        return ({"status": "failed", "content": f"[Error: {e}]", "agent_role": agent_role}, 0)


async def _insert_plan_steps(conn, job_id: str, plan: ExecutionPlan):
    for step in plan.steps:
        step_id = str(uuid.uuid4())
        step_name = step.description or f"step_{step.step_index}"
        input_payload = {"description": step.description} if step.description else {}
        await conn.execute(
            """
            INSERT INTO job_steps (
                step_index,
                job_id,
                id,
                step_name,
                agent_role,
                unified_tool,
                status,
                input_payload,
                requires_approval,
                created_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,now())
            """,
            step.step_index,
            job_id,
            step_id,
            step_name,
            step.agent_role,
            step.unified_tool,
            "pending",
            json.dumps(input_payload, default=_json_default),
            step.requires_approval,
        )


async def run_intake_inline(job_id: str, job_post: str):
    """
    1. Call IntakeEngine.analyze_job_post(job_post)
    2. If brief.is_complete is False:
       - Store clarification questions in the clarifications table
       - Keep job status as INTAKE_CLARIFICATION
    3. If brief.is_complete is True:
       - Call StrategyRoom.generate_execution_plan(brief, available_agents)
       - Store the plan steps in job_steps table using ACTUAL column names:
         (id, job_id, step_index, step_name, agent_role, unified_tool, status, input_payload, requires_approval)
       - Update job status to PLAN_PROPOSED
       - Store the plan in jobs.context jsonb
    """
    logger.info("Starting intake for job %s", job_id)
    pool = await _get_pool()
    if not pool:
        logger.warning("DB pool not available, skipping intake for job %s", job_id)
        return

    intake = IntakeEngine()
    strategy = StrategyRoom()
    client_slug = None
    client_context = None

    try:
        # Resolve client and GSC summary before intake so Mr. Klein can use Search Console data in his reply
        async with pool.acquire() as conn:
            job_row = await conn.fetchrow("SELECT user_id, context FROM jobs WHERE id = $1", job_id)
            existing_ctx = _coerce_context(job_row["context"] if job_row else None) if job_row else {}
            client_slug = existing_ctx.get("client_slug")
            if not client_slug and job_row and job_post:
                from app.services.client_mention import resolve_first_mention
                client_slug = await resolve_first_mention(pool, str(job_row["user_id"]), job_post)
            logger.info("intake client_slug after resolve: %s", client_slug)
            if client_slug and job_row:
                knowledge_debug_logger.info(
                    "[KNOWLEDGE] client_slug gedetecteerd: %r — knowledge block ophalen",
                    client_slug,
                )
                from app.services.dashboard import get_client_seo_summary_for_agent
                gsc_context = await get_client_seo_summary_for_agent(pool, str(job_row["user_id"]), client_slug)
                client_name = existing_ctx.get("client_name") or ""
                injected = (existing_ctx.get("injected_context") or "").strip()
                client_knowledge_block = await _build_client_knowledge_block(
                    pool, str(job_row["user_id"]), client_slug, job_post or "", match_count=5, similarity_threshold=0.4
                )
                if client_knowledge_block:
                    injected = (injected + "\n\n" + client_knowledge_block).strip() if injected else client_knowledge_block
                if injected or client_name:
                    client_info_block = (
                        "BESCHIKBARE CLIENT INFORMATIE:\n"
                        f"Klant: {client_name or '—'} (@{client_slug})\n\n"
                        f"{injected}\n\n---\n\n"
                    )
                    client_context = client_info_block + (gsc_context or "")
                else:
                    client_context = gsc_context
            else:
                client_context = None

        brief = intake.analyze_job_post(job_post, client_context=client_context)
        if client_slug:
            brief.context = dict(brief.context or {})
            brief.context["client_slug"] = client_slug

        chat_history = []
        ceo_content = brief.message or ""
        if not brief.is_complete and brief.clarifications:
            questions_text = "\n\n".join(
                f"{i + 1}. {q.question}" for i, q in enumerate(brief.clarifications)
            )
            if questions_text and questions_text not in ceo_content:
                ceo_content = (ceo_content.rstrip() + "\n\n" + questions_text).strip()
        chat_history.append({"role": "ceo", "content": ceo_content})
        async with pool.acquire() as conn:
            updates = {
                "brief": brief.model_dump(),
                "previous_answers": {},
                "chat_history": chat_history,
            }
            if client_slug:
                updates["client_slug"] = client_slug
            await _update_job_context(
                conn,
                job_id,
                updates,
            )

            if not brief.is_complete:
                await _store_clarifications(conn, job_id, brief.clarifications, round_number=1)
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.INTAKE_CLARIFICATION.value,
                    job_id,
                )
                return

            # Update status first so job is no longer INTAKE_CLARIFICATION even if plan generation fails
            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                JobStatus.PLAN_PROPOSED.value,
                job_id,
            )
            available_agents = await _fetch_available_agents(conn)
            plan = strategy.generate_execution_plan(brief, available_agents)
            await _insert_plan_steps(conn, job_id, plan)
            # V4: Event model — TASK_CREATED per step (fire-and-forget)
            try:
                from app.services.event_emitter import EventEmitter, EventType
                emitter = EventEmitter()
                job_title = (job_post or "")[:80] if job_post else ""
                for step in plan.steps:
                    step_name = step.description or f"step_{step.step_index}"
                    await emitter.emit(
                        pool,
                        EventType.TASK_CREATED,
                        agent_id=step.agent_role,
                        task_id=job_id,
                        job_id=job_id,
                        payload={"step_name": step_name, "title": job_title},
                    )
            except Exception as _ev:
                logger.warning("Event TASK_CREATED failed: %s", _ev)
            await _update_job_context(
                conn,
                job_id,
                {
                    "plan": plan.model_dump(),
                },
            )
    except Exception as exc:
        logger.error("Intake error for job %s: %s", job_id, exc, exc_info=True)


async def run_intake_answers_inline(job_id: str, answers: dict):
    """
    1. Load existing job context; pass chat_history into IntakeEngine.
    2. If not complete → store clarifications, stay INTAKE_CLARIFICATION.
    3. If complete and context has final_content (revision) → set RUNNING, run_job_inline (skip StrategyRoom).
    4. Else (first-time complete) → StrategyRoom → PLAN_PROPOSED.
    """
    pool = await _get_pool()
    if not pool:
        return

    intake = IntakeEngine()
    strategy = StrategyRoom()
    run_revision = False

    try:
        async with pool.acquire() as conn:
            job = await _load_job(conn, job_id)
            context = _coerce_context(job.get("payload") or job.get("context"))
            previous_answers = context.get("previous_answers") or {}
            merged_answers = {**previous_answers, **(answers or {})}
            job_post = job.get("job_post") or context.get("job_post") or ""
            chat_history = list(context.get("chat_history") or [])
            # Inject GSC/client data so Mr. Klein can answer questions about zoektermen, Search Console, etc.
            client_context = None
            user_id = str(job.get("user_id") or "")
            client_slug = context.get("client_slug")
            if not client_slug and job_post:
                from app.services.client_mention import resolve_first_mention
                client_slug = await resolve_first_mention(pool, user_id, job_post)
            if client_slug and user_id:
                from app.services.dashboard import get_client_seo_summary_for_agent
                gsc_context = await get_client_seo_summary_for_agent(pool, user_id, client_slug)
                client_name = context.get("client_name") or ""
                injected = (context.get("injected_context") or "").strip()
                if injected or client_name:
                    client_info_block = (
                        "BESCHIKBARE CLIENT INFORMATIE:\n"
                        f"Klant: {client_name or '—'} (@{client_slug})\n\n"
                        f"{injected}\n\n---\n\n"
                    )
                    client_context = client_info_block + (gsc_context or "")
                else:
                    client_context = gsc_context

            brief = intake.analyze_job_post(
                job_post,
                previous_answers=merged_answers,
                chat_history=chat_history if chat_history else None,
                client_context=client_context,
            )
            logger.info(
                "intake answers brief: is_complete=%s, clarifications=%d",
                brief.is_complete,
                len(brief.clarifications),
            )
            payload_complete = bool((context.get("brief") or {}).get("is_complete"))
            if not brief.is_complete and payload_complete:
                logger.info(
                    "force-completing intake: brief.is_complete=False but payload says complete"
                )
                brief.is_complete = True
            chat_history = list(chat_history)
            ceo_content = brief.message or ""
            if not brief.is_complete and brief.clarifications:
                questions_text = "\n\n".join(
                    f"{i + 1}. {q.question}" for i, q in enumerate(brief.clarifications)
                )
                if questions_text and questions_text not in ceo_content:
                    ceo_content = (ceo_content.rstrip() + "\n\n" + questions_text).strip()
            chat_history.append({"role": "ceo", "content": ceo_content})
            updates = {
                "brief": brief.model_dump(),
                "previous_answers": merged_answers,
                "chat_history": chat_history,
            }
            if client_slug:
                updates["client_slug"] = client_slug
            await _update_job_context(conn, job_id, updates)

            if not brief.is_complete:
                round_number = await _next_clarification_round(conn, job_id)
                await _store_clarifications(conn, job_id, brief.clarifications, round_number=round_number)
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.INTAKE_CLARIFICATION.value,
                    job_id,
                )
                return

            final_content = context.get("final_content") or ""
            if (
                final_content
                and final_content.strip()
                and final_content.strip().lower() != "no content produced"
            ):
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.RUNNING.value,
                    job_id,
                )
                run_revision = True
            else:
                # Update status first so job leaves INTAKE_CLARIFICATION even if plan generation fails
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.PLAN_PROPOSED.value,
                    job_id,
                )
                available_agents = await _fetch_available_agents(conn)
                plan = strategy.generate_execution_plan(brief, available_agents)
                await _insert_plan_steps(conn, job_id, plan)
                await _update_job_context(
                    conn,
                    job_id,
                    {
                        "plan": plan.model_dump(),
                    },
                )
        if run_revision:
            await run_job_inline(job_id, None)
    except Exception as exc:
        logger.error("run_intake_answers_inline failed for job %s: %s", job_id, exc, exc_info=True)


async def run_job_inline(job_id: str, context_extra: Optional[dict] = None):
    """
    1. Load job and job_steps; merge context from DB with context_extra (e.g. user feedback).
    2. For each step: run agent, store output, update tokens.
    3. After all steps complete: set status to JOB_READY.
    """
    pool = await _get_pool()
    if not pool:
        return

    steps_completed = False
    try:
        async with pool.acquire() as conn:
            job = await _load_job(conn, job_id)
            context = _coerce_context(job.get("payload") or job.get("context"))
            if context_extra:
                context = {**context, **context_extra}

            steps = await conn.fetch(
                """SELECT id, step_index, step_name, agent_role, unified_tool,
                          COALESCE(retry_count, 0) AS retry_count
                   FROM job_steps WHERE job_id=$1 ORDER BY step_index""",
                job_id,
            )
            num_steps = len(steps)

            # Revision: reset all steps so they run again with feedback
            is_revision = bool(context.get("user_feedback") or context.get("feedback") or context.get("final_content"))
            if is_revision and num_steps > 0:
                await conn.execute(
                    """
                    UPDATE job_steps SET status='pending', started_at=NULL, completed_at=NULL, output='{}'::jsonb, tokens_used=0, progress_pct=0
                    WHERE job_id=$1
                    """,
                    job_id,
                )
                logger.info("run_job_inline: job %s revision — reset %s steps", job_id, num_steps)

            logger.info("run_job_inline: job %s with %s steps", job_id, num_steps)

            # Fetch knowledge context for injection into agent prompts (defensive)
            knowledge_context = {"prompt_block": "", "sources_used": [], "total_chunks": 0, "total_lessons": 0}
            try:
                from app.services.knowledge_context import KnowledgeContextBuilder
                _kb = KnowledgeContextBuilder()
                _job_post = context.get("job_post") or job.get("job_post") or ""
                _brief = context.get("brief") or {}
                _domain = None
                if isinstance(_brief, dict):
                    _domain = _brief.get("domain") or _brief.get("focus")
                _client_slug = context.get("client_slug") or (isinstance(_brief, dict) and _brief.get("client_slug"))
                knowledge_context = await _kb.build(
                    pool=pool,
                    agent_id=f"pipeline:{job_id}",
                    query=_job_post,
                    domain=str(_domain) if _domain else None,
                    client_slug=str(_client_slug) if _client_slug else None,
                )
            except Exception as _kb_err:
                logger.warning("Knowledge retrieval failed for job %s: %s", job_id, _kb_err)

            if knowledge_context.get("prompt_block"):
                context["_knowledge_block"] = knowledge_context["prompt_block"]

            # Client knowledge: inject @client chunks when client_slug is set
            _client_slug = context.get("client_slug") or (isinstance(context.get("brief"), dict) and context.get("brief", {}).get("client_slug"))
            _user_id = str(job.get("user_id") or "")
            if _client_slug and _user_id:
                knowledge_debug_logger.info(
                    "[KNOWLEDGE] client_slug gedetecteerd: %r — knowledge block ophalen",
                    _client_slug,
                )
                _job_post = context.get("job_post") or job.get("job_post") or ""
                client_block = await _build_client_knowledge_block(
                    pool, _user_id, _client_slug, _job_post, match_count=5, similarity_threshold=0.4
                )
                if client_block:
                    context["_knowledge_block"] = (client_block + "\n\n" + (context.get("_knowledge_block") or "")).strip()

            # V6: TASK_EVIDENCE_COLLECTED — eenmalig na retrieval-cyclus (sectie 7)
            total_chunks = knowledge_context.get("total_chunks") or 0
            total_lessons = knowledge_context.get("total_lessons") or 0
            if total_chunks > 0 or total_lessons > 0:
                try:
                    from app.services.event_emitter import EventEmitter, EventType
                    emitter = EventEmitter()
                    sources = [
                        s.get("type", "unknown")
                        for s in knowledge_context.get("sources_used", [])
                    ]
                    await emitter.emit(
                        pool,
                        EventType.TASK_EVIDENCE_COLLECTED,
                        agent_id=f"pipeline:{job_id}",
                        task_id=job_id,
                        job_id=job_id,
                        payload={
                            "chunks_retrieved": total_chunks,
                            "lessons_retrieved": total_lessons,
                            "sources": sources,
                        },
                    )
                except Exception as _ev:
                    logger.warning("Event TASK_EVIDENCE_COLLECTED failed: %s", _ev)

            token_guard = TokenGuard(db_pool=pool)
            last_content: Optional[str] = None
            previous_content: Optional[str] = None
            for idx, step in enumerate(steps):
                # Token budget check before each step
                check = await token_guard.check_before_call(job_id, estimated_tokens=2000)
                if not check.get("allowed", True):
                    logger.warning(
                        "Job %s stopped: token budget exceeded (%s)",
                        job_id, check.get("reason", "unknown"),
                    )
                    try:
                        from app.services.system_events_service import get_system_events, SystemEventsService
                        svc = get_system_events()
                        if svc:
                            await svc.log_event(
                                event_type=SystemEventsService.TOKEN_BUDGET_EXCEEDED,
                                severity=SystemEventsService.CRITICAL,
                                job_id=job_id,
                                agent_id="agent:ceo",
                                message=f"Token budget overschreden voor job {job_id}: {check.get('used', 0)}/{check.get('budget', 0)}",
                                details={"token_count": check.get("used"), "budget": check.get("budget")},
                            )
                    except Exception as _log:
                        logger.debug("System event log (token budget) skipped: %s", _log)
                    await _update_job_context(conn, job_id, {
                        "token_budget_exceeded": True,
                        "tokens_used": check.get("used"),
                        "token_budget": check.get("budget"),
                    })
                    break
                if check.get("warning"):
                    logger.info(
                        "Token budget warning for job %s: %.1f%% used",
                        job_id, check.get("percentage", 0),
                    )
                    await _update_job_context(conn, job_id, {"token_budget_warning": check.get("percentage")})

                step_id = step["id"]
                step_name = step.get("step_name") or step.get("agent_role") or "step"
                agent_role = step.get("agent_role") or ""
                step_retries = int(step.get("retry_count") or 0)
                talent_result = None
                output = None
                tokens_used = 0

                while True:
                    await conn.execute(
                        "UPDATE job_steps SET status='running', started_at=now() WHERE id=$1",
                        step_id,
                    )
                    await _update_step_progress(conn, step_id, 10)

                    started = time.monotonic()
                    logger.info(
                        "Running job step %s for job %s (%s)",
                        step.get("step_name"),
                        job_id,
                        agent_role,
                    )

                    # Per-step agent knowledge from agent_knowledge (training workflow).
                    # assumption-based: first active agent with matching role is used when step has no agent_id.
                    step_agent_id = step.get("agent_id")
                    if not step_agent_id and agent_role:
                        row = await conn.fetchrow(
                            "SELECT agent_id FROM hired_agents WHERE role = $1 AND is_active = true LIMIT 1",
                            agent_role,
                        )
                        step_agent_id = row["agent_id"] if row else None
                    if step_agent_id:
                        try:
                            from app.services.training_workflow import retrieve_agent_context
                            job_post = context.get("job_post") or ""
                            query = f"{step_name or ''} {job_post}".strip() or (step.get("description") or "")
                            agent_context = await retrieve_agent_context(
                                agent_id=step_agent_id,
                                query=query[:8000] if query else "",
                                pool=pool,
                                top_k=5,
                            )
                            if agent_context:
                                context["_knowledge_block"] = agent_context
                        except Exception as _kw:
                            logger.warning("Per-step knowledge retrieval failed for %s: %s", step_agent_id, _kw)

                    output, tokens_used = await _run_step_agent_with_timeout(
                        agent_role=agent_role,
                        step_name=step_name,
                        context=context or {},
                        previous_content=previous_content,
                    )
                    await _update_step_progress(conn, step_id, 70)
                    output["step_name"] = step.get("step_name")
                    output["agent_role"] = step.get("agent_role")
                    output["unified_tool"] = step.get("unified_tool")

                    if output.get("content"):
                        last_content = output["content"]
                        previous_content = output["content"]
                    elif output.get("review") and previous_content:
                        last_content = previous_content

                    timing_ms = int((time.monotonic() - started) * 1000)

                    worker_output_json = None
                    validation_status_val = None
                    validation_warnings_val = None
                    if output.get("worker_output") is not None:
                        worker_output_json = json.dumps(output["worker_output"], default=_json_default)
                    if output.get("validation_status") is not None:
                        validation_status_val = output["validation_status"]
                    if output.get("validation_warnings") is not None:
                        validation_warnings_val = output["validation_warnings"]

                    await conn.execute(
                        """
                        UPDATE job_steps
                        SET status='completed', completed_at=now(), output=$1::jsonb, tokens_used=$2, timing_ms=$3, progress_pct=100,
                            worker_output=CASE WHEN $5::jsonb IS NOT NULL THEN $5::jsonb ELSE worker_output END,
                            validation_status=COALESCE($6, validation_status),
                            validation_warnings=COALESCE($7, validation_warnings)
                        WHERE id=$4
                        """,
                        json.dumps(output, default=_json_default),
                        tokens_used,
                        timing_ms,
                        step_id,
                        worker_output_json,
                        validation_status_val,
                        validation_warnings_val,
                    )
                    await _update_step_progress(conn, step_id, 100)

                    # V4: Event model — TASK_FIX_PROPOSED na worker output (fire-and-forget)
                    if output.get("worker_output"):
                        try:
                            from app.services.event_emitter import EventEmitter, EventType
                            emitter = EventEmitter()
                            await emitter.emit(
                                pool,
                                EventType.TASK_FIX_PROPOSED,
                                agent_id=agent_role,
                                task_id=job_id,
                                job_id=job_id,
                                payload={"validation_status": output.get("validation_status") or "pending"},
                            )
                        except Exception as _ev:
                            logger.warning("Event TASK_FIX_PROPOSED failed: %s", _ev)

                    # V6: Artifact tracking — evidence uit worker_output als citations + TASK_CITED edges
                    evidence = (output.get("worker_output") or {}).get("evidence") or []
                    if evidence:
                        try:
                            from app.services.artifact_tracker import ArtifactTracker
                            from app.services.knowledge_graph import KnowledgeGraph
                            tracker = ArtifactTracker()
                            citation_ids = await tracker.save_citations(
                                pool,
                                task_id=str(job_id),
                                job_id=str(job_id),
                                evidence_list=evidence,
                            )
                            artifact_ids = []
                            for e in evidence:
                                if not isinstance(e, dict):
                                    continue
                                locator = e.get("file_path") or e.get("source_id") or e.get("locator") or ""
                                if not locator:
                                    continue
                                at = e.get("artifact_type") or e.get("type") or "repo_file"
                                artifact_ids.append(tracker.build_artifact_id(at, locator))
                            if artifact_ids:
                                graph = KnowledgeGraph()
                                await tracker.add_task_cited_edges(
                                    pool, graph, str(job_id), artifact_ids
                                )
                        except Exception as _art_err:
                            logger.warning("Artifact tracking failed: %s", _art_err)

                    if knowledge_context.get("sources_used"):
                        try:
                            from app.services.knowledge_context import log_knowledge_usage
                            await log_knowledge_usage(
                                pool=pool,
                                job_id=str(job_id),
                                step_id=str(step_id),
                                agent_id=agent_role or f"pipeline:{job_id}",
                                sources=knowledge_context["sources_used"],
                            )
                        except Exception as _log_err:
                            logger.warning("Knowledge usage logging failed: %s", _log_err)

                    await token_guard.register_usage(job_id, tokens_used, step_id)

                    # V2: Talent validation when step has worker_output
                    talent_result = None
                    if output.get("worker_output"):
                        try:
                            from agents.talent_agent import TalentAgent
                            talent = TalentAgent()
                            talent_result = await talent.validate(
                                worker_output=output["worker_output"],
                                task_id=str(job_id),
                                pool=pool,
                            )
                            talent_status = talent_result.get("status") or "pending"
                            talent_output_json = json.dumps(talent_result, default=_json_default)
                            talent_delta = talent_result.get("delta")
                            talent_blocking = talent_result.get("blocking_issues") or []
                            await conn.execute(
                                """
                                UPDATE job_steps SET
                                    talent_status = $1,
                                    talent_output = $2::jsonb,
                                    talent_delta = $3,
                                    talent_blocking_issues = $4
                                WHERE id = $5
                                """,
                                talent_status,
                                talent_output_json,
                                talent_delta,
                                talent_blocking,
                                step_id,
                            )
                            checks = talent_result.get("checks") or {}
                            for check_name, result in checks.items():
                                if not check_name:
                                    continue
                                res_val = "pass" if result == "pass" else "fail"
                                await conn.execute(
                                    """
                                    INSERT INTO validation_decisions (task_id, step_id, check_name, result)
                                    VALUES ($1, $2, $3, $4)
                                    """,
                                    str(job_id),
                                    step_id,
                                    check_name,
                                    res_val,
                                )
                        except Exception as _talent_err:
                            logger.warning("Talent validation failed: %s", _talent_err)
                            talent_result = {"status": "rejected", "blocking_issues": [str(_talent_err)]}

                    # Retry logic: rejected -> max 2 retries; approved_with_changes -> 1 retry
                    if talent_result and talent_result.get("status") == "rejected":
                        if step_retries < 2:
                            step_retries += 1
                            await conn.execute(
                                "UPDATE job_steps SET retry_count = $1, retry_reason = $2 WHERE id = $3",
                                step_retries,
                                "talent_rejected",
                                step_id,
                            )
                            context["user_feedback"] = (
                                "Je vorige output werd afgekeurd door de Talent agent.\n\nBlokkerende issues:\n"
                                + "\n".join(talent_result.get("blocking_issues", []))
                                + ("\n\n" + (talent_result.get("delta") or "")) if talent_result.get("delta") else ""
                            )
                            continue
                        else:
                            # Na 3 pogingen: step status=failed, feedback voor CEO/HR (platform spec V2)
                            ceo_msg = "Talent agent heeft 3x afgekeurd: " + "; ".join(
                                talent_result.get("blocking_issues", [])
                            )
                            await conn.execute(
                                """UPDATE job_steps SET status = $1, feedback = $2 WHERE id = $3""",
                                "failed",
                                ceo_msg,
                                step_id,
                            )
                            try:
                                from app.services.system_events_service import get_system_events, SystemEventsService
                                svc = get_system_events()
                                if svc:
                                    await svc.log_event(
                                        event_type=SystemEventsService.VALIDATION_LOOP,
                                        severity=SystemEventsService.ERROR,
                                        job_id=job_id,
                                        agent_id=step_agent_id or agent_role or "agent:talent",
                                        message=f"Agent heeft 3x een rejected output geproduceerd voor job {job_id}",
                                        details={
                                            "retry_count": step_retries + 1,
                                            "last_feedback": talent_result.get("blocking_issues"),
                                            "step_id": str(step_id),
                                        },
                                    )
                            except Exception as _log:
                                logger.debug("System event log (validation loop) skipped: %s", _log)
                            # V4: Event model — TASK_REJECTED na 3 pogingen (fire-and-forget)
                            try:
                                from app.services.event_emitter import EventEmitter, EventType
                                emitter = EventEmitter()
                                await emitter.emit(
                                    pool,
                                    EventType.TASK_REJECTED,
                                    agent_id="agent:talent",
                                    task_id=job_id,
                                    job_id=job_id,
                                    payload={"blocking_issues": talent_result.get("blocking_issues") or []},
                                )
                            except Exception as _ev:
                                logger.warning("Event TASK_REJECTED failed: %s", _ev)
                            break
                    if talent_result and talent_result.get("status") == "approved_with_changes" and step_retries == 0:
                        step_retries += 1
                        await conn.execute(
                            "UPDATE job_steps SET retry_count = $1, retry_reason = $2 WHERE id = $3",
                            step_retries,
                            "talent_approved_with_changes",
                            step_id,
                        )
                        context["user_feedback"] = (
                            "De Talent agent keurt goed mits je de volgende aanpassingen doorvoert:\n\n"
                            + (talent_result.get("delta") or "")
                        )
                        continue
                    # V3: Lessons lifecycle when talent approved
                    if talent_result and talent_result.get("status") == "approved" and output.get("worker_output"):
                        try:
                            from app.services.lessons_lifecycle import LessonsLifecycle
                            lifecycle = LessonsLifecycle()
                            lesson_id = await lifecycle.propose(
                                pool, output["worker_output"], str(job_id), agent_role or f"pipeline:{job_id}"
                            )
                            await lifecycle.approve(
                                pool,
                                lesson_id,
                                float(talent_result.get("confidence_score") or 0),
                                "agent:talent",
                                talent_result.get("confidence_breakdown") or {},
                                task_id=str(job_id),
                                agent_id=agent_role or f"pipeline:{job_id}",
                                worker_output=output.get("worker_output"),
                            )
                            # V4: Event model — TASK_VALIDATED (fire-and-forget)
                            try:
                                from app.services.event_emitter import EventEmitter, EventType
                                emitter = EventEmitter()
                                await emitter.emit(
                                    pool,
                                    EventType.TASK_VALIDATED,
                                    agent_id="agent:talent",
                                    task_id=job_id,
                                    job_id=job_id,
                                    confidence_score=float(talent_result.get("confidence_score") or 0),
                                    payload={"talent_status": "approved"},
                                )
                            except Exception as _ev:
                                logger.warning("Event TASK_VALIDATED failed: %s", _ev)
                        except Exception as _lifecycle_err:
                            logger.warning("Lessons lifecycle failed: %s", _lifecycle_err)
                    break

                if output.get("image_url"):
                    await _update_job_context(conn, job_id, {"image_url": output["image_url"]})
                # Checkpoint: save content after each step that produces it (survives crash)
                if last_content and output.get("status") in ("completed", "success"):
                    await _save_checkpoint(conn, job_id, last_content, step_name or agent_role)
                logger.info("run_job_inline: job %s step %s of %s done", job_id, idx + 1, num_steps)

            # Ensure image_url is in job context for frontend (from any step that produced one)
            completed_steps = await conn.fetch(
                "SELECT output FROM job_steps WHERE job_id=$1 AND status='completed' ORDER BY step_index",
                job_id,
            )
            for step in completed_steps:
                step_output = step.get("output")
                if not step_output:
                    continue
                if isinstance(step_output, str):
                    try:
                        step_output = json.loads(step_output)
                    except json.JSONDecodeError:
                        continue
                if step_output.get("image_url"):
                    await _update_job_context(conn, job_id, {"image_url": step_output["image_url"]})
                    break

            # Extra safety: copy image_url from steps before JOB_READY (in case above missed it)
            job_id_str = str(job_id)
            pool_img = await get_db()
            async with pool_img.acquire() as conn_img:
                steps_rows = await conn_img.fetch("SELECT output FROM job_steps WHERE job_id=$1", job_id_str)
                for row in steps_rows:
                    step_output = row.get("output")
                    if isinstance(step_output, str):
                        try:
                            step_output = json.loads(step_output)
                        except Exception:
                            continue
                    if isinstance(step_output, dict) and step_output.get("image_url"):
                        await _update_job_context(conn_img, job_id_str, {"image_url": step_output["image_url"]})
                        break

            steps_completed = True
            logger.info("All steps done for job %s. Setting JOB_READY...", job_id_str)
            try:
                pool_ready = await get_db()
                async with pool_ready.acquire() as conn:
                    logger.info("Storing final_content for job %s", job_id_str)
                    await _update_job_context(conn, job_id_str, {"final_content": last_content or "No content produced"})
                    await _maybe_generate_job_artifact(conn, job_id_str, context or {}, completed_steps, last_content, job.get("job_post", ""))
                    logger.info("Updating status to JOB_READY for job %s", job_id_str)
                    result = await conn.execute(
                        "UPDATE jobs SET status='JOB_READY', updated_at=now() WHERE id=$1",
                        job_id_str,
                    )
                    logger.info("JOB_READY update result for job %s: %s", job_id_str, result)
            except Exception as e:
                logger.error("CRITICAL: Failed to set JOB_READY for job %s: %s", job_id_str, e, exc_info=True)
                raise
    except Exception as exc:
        logger.error(
            "run_job_inline failed for job %s: %s: %s",
            job_id,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        if steps_completed:
            try:
                async with pool.acquire() as conn_recovery:
                    await conn_recovery.execute(
                        "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                        JobStatus.JOB_READY.value,
                        job_id,
                    )
                logger.info("Job %s set to JOB_READY in recovery", job_id)
            except Exception as final_exc:
                logger.warning("Failed to set JOB_READY in recovery for job %s: %s", job_id, final_exc)
