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
from app.services.cfo_service import anthropic_usage_record, log_token_usage_records
from app.services.token_guard import TokenGuard
from app.orchestration.intake_engine import IntakeEngine, detect_language, normalize_language_label
from app.orchestration.ceo_intent import check_resources, detect_job_type
from app.services.skill_matcher import (
    UNKNOWN_PRESET_AND_SKILL_MESSAGE,
    match_skill,
    persist_matched_skill,
)
from app.services.job_title_generator import format_job_title, generate_job_subject
from app.orchestration.nexus_pipeline import _missing_roles_for_payload
from app.utils.job_file_generator import generate_job_artifact, parse_output_to_sections
from app.orchestration.strategy_room import StrategyRoom
from models.unified import JobStatus, ExecutionPlan

logger = logging.getLogger(__name__)
# Temporary debug logger for client knowledge context injection (remove or set to DEBUG after validation)
knowledge_debug_logger = logging.getLogger("knowledge_debug")

# Model for pipeline agent calls (copywriter, reviewer)
CLAUDE_MODEL = DEFAULT_MODEL

TOOL_FIRST_RULE = """
TOOL-FIRST PRINCIPE (VERPLICHT):
- Je mag GEEN feiten, cijfers, prestaties of klantdata claimen zonder eerst een tool te hebben aangeroepen.
- Als je geen tool hebt om de data op te halen: zeg expliciet "Ik heb geen toegang tot deze data" — geen schatting, geen aanname.
- Geen retrieval = geen claim. Dit is een harde regel zonder uitzonderingen.
- Bij twijfel over een feit: label het als [AANNAME] en vraag om verificatie.
"""

# Per-step timeouts (seconds)
TIMEOUT_CONTENT_STEP = 120
TIMEOUT_GTM_STEP = 180
TIMEOUT_REVIEW_STEP = 60

# Thread pool for running sync _run_step_agent with timeout
_step_executor: Optional[ThreadPoolExecutor] = None


async def _maybe_set_structured_job_title(conn, job_id: str, job_post: str, preset_id: Optional[str] = None) -> None:
    """Set jobs.title in format: #NNNN — Client — Subject (best effort)."""
    try:
        logger.info("[job_title] START job_id=%s preset_id=%s", job_id, preset_id)
        row = await conn.fetchrow(
            """
            SELECT j.job_number_int, j.context, j.payload, c.client_name
            FROM jobs j
            LEFT JOIN clients c ON c.client_id::text = j.client_id::text
            WHERE j.id = $1
            """,
            job_id,
        )
        if not row:
            logger.info("[job_title] SKIP no row job_id=%s", job_id)
            return

        job_number_int = row.get("job_number_int")
        if job_number_int is None:
            logger.info("[job_title] SKIP missing job_number_int job_id=%s", job_id)
            return

        merged = _coerce_context(row.get("payload") or row.get("context"))
        client_name = (row.get("client_name") or "").strip() or (merged.get("client_name") or "").strip() or None
        subject = await generate_job_subject(job_post or "", preset_id=preset_id)
        title = format_job_title(int(job_number_int), client_name, subject)
        logger.info(
            "[job_title] UPDATE job_id=%s job_number_int=%s client_name=%s subject=%s title=%s",
            job_id,
            job_number_int,
            client_name or "",
            subject,
            title,
        )

        await conn.execute(
            "UPDATE jobs SET title = $1, updated_at = now() WHERE id = $2",
            title,
            job_id,
        )
    except Exception as e:
        logger.error("[job_title] FAILED job_id=%s error=%s", job_id, e, exc_info=True)


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


def format_data_output(raw_output: str | dict) -> str:
    """
    Formatteert ruwe data-output naar leesbare Nederlandse tekst (data_query / DataAgent).
    GSC-achtige payloads worden een Markdown-tabel; overige dicts een bullet-lijst.
    """
    if isinstance(raw_output, str):
        try:
            data = json.loads(raw_output)
        except (json.JSONDecodeError, ValueError):
            return raw_output
    else:
        data = raw_output

    if not isinstance(data, dict):
        return str(raw_output)

    resultaat = data.get("resultaat")
    gevonden = data.get("gevonden")

    def _row_is_gsc(row: Any) -> bool:
        return isinstance(row, dict) and "page" in row and any(
            k in row for k in ("clicks", "impressions", "ctr", "position")
        )

    def _format_ctr_pct(val: Any) -> str:
        try:
            x = float(val if val is not None else 0)
        except (TypeError, ValueError):
            return "—"
        if 0 <= x <= 1.0:
            return f"{x * 100:.1f}%"
        return f"{x:.1f}%"

    # GSC-achtige rijen (tops pagina's + metrics)
    if "resultaat" in data and "gevonden" in data and isinstance(resultaat, list):
        section_title = gevonden if isinstance(gevonden, str) else "Gevonden data"
        if not resultaat or _row_is_gsc(resultaat[0]):
            lines: list[str] = []
            lines.append(f"## {section_title}")
            lines.append("")
            if resultaat:
                lines.append("| Pagina | Clicks | Impressies | CTR | Positie |")
                lines.append("|--------|--------|------------|-----|---------|")
                for row in resultaat[:10]:
                    if not isinstance(row, dict):
                        continue
                    page = str(row.get("page", "")).replace("https://", "").replace("http://", "")[:80]
                    clicks = row.get("clicks", 0)
                    impressions = row.get("impressions", 0)
                    ctr = _format_ctr_pct(row.get("ctr", 0))
                    try:
                        pos = float(row.get("position", 0) or 0)
                        position = f"{pos:.1f}"
                    except (TypeError, ValueError):
                        position = "—"
                    lines.append(f"| {page} | {clicks} | {impressions} | {ctr} | {position} |")
            volledigheid = data.get("volledigheid")
            if volledigheid:
                lines.append("")
                lines.append(f"*{volledigheid}*")
            volgende = data.get("volgende_actie")
            if volgende:
                lines.append("")
                lines.append(f"**Volgende stap:** {volgende}")
            return "\n".join(lines)

        # client_knowledge-achtige rijen
        lines_k: list[str] = []
        lines_k.append(f"## {section_title}")
        lines_k.append("")
        for row in resultaat[:10]:
            if not isinstance(row, dict):
                lines_k.append(f"- {row}")
                continue
            src = row.get("source_url") or ""
            title_row = row.get("page_title") or ""
            chunk = (row.get("chunk_text") or "")[:200].replace("\n", " ")
            if title_row or src:
                lines_k.append(f"- **{title_row or src}**" + (f" — {src}" if title_row and src else ""))
            else:
                lines_k.append("- Item")
            if chunk:
                lines_k.append(f"  - {chunk}{'…' if len(str(row.get('chunk_text') or '')) > 200 else ''}")
        if data.get("volledigheid"):
            lines_k.append("")
            lines_k.append(f"*{data['volledigheid']}*")
        if data.get("volgende_actie"):
            lines_k.append("")
            lines_k.append(f"**Volgende stap:** {data['volgende_actie']}")
        return "\n".join(lines_k)

    # Generieke dict
    lines_g: list[str] = []
    for key, value in data.items():
        if isinstance(value, list):
            lines_g.append(f"**{key}:**")
            for item in value[:5]:
                if isinstance(item, dict):
                    lines_g.append(f"  - {json.dumps(item, ensure_ascii=False)[:120]}")
                else:
                    lines_g.append(f"  - {item}")
        else:
            lines_g.append(f"**{key}:** {value}")
    return "\n".join(lines_g)


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


class GSCServiceForClient:
    """
    Thin GSC adapter for DataAgent. Uses existing OAuth flow:
    get_valid_access_token(conn, user_id, client_slug, "google_search_console") + fetch_gsc_top_pages.
    """

    def __init__(self, pool: Any, user_id: str, client_slug: str):
        self.pool = pool
        self.user_id = user_id
        self.client_slug = client_slug

    async def get_top_pages(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: Optional[List[str]] = None,
        metrics: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        from app.services.dashboard import get_valid_access_token, fetch_gsc_top_pages
        async with self.pool.acquire() as conn:
            token = await get_valid_access_token(
                conn, self.user_id, self.client_slug, "google_search_console"
            )
        if not token:
            raise RuntimeError("GSC token not available for this client")
        return await fetch_gsc_top_pages(token, site_url, start_date, end_date, limit)


async def get_gsc_service(
    pool: Any, user_id: str, client_slug: str
) -> Optional[GSCServiceForClient]:
    """
    Return a GSC service adapter for the client (same OAuth as dashboard/SEO).
    Returns None if no valid token so DataAgent can return _unavailable_result.
    """
    from app.services.dashboard import get_valid_access_token
    async with pool.acquire() as conn:
        token = await get_valid_access_token(
            conn, str(user_id), client_slug or "", "google_search_console"
        )
    return GSCServiceForClient(pool, str(user_id), client_slug or "") if token else None


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


async def _block_job(conn, job_id: str, reason: str, missing_roles: list) -> None:
    """Zet job op BLOCKED en merge preset-blockvelden in payload (jsonb)."""
    block_data = {
        "block_reason": reason,
        "ceo_preset_blocked": True,
        "missing_roles": missing_roles,
    }
    await conn.execute(
        """
        UPDATE jobs
        SET status = $1,
            payload = COALESCE(payload, '{}'::jsonb) || $2::jsonb,
            updated_at = now()
        WHERE id = $3
        """,
        JobStatus.BLOCKED.value,
        json.dumps(block_data),
        job_id,
    )

    # Fire-and-forget via best-effort: create HR improvements record for dashboard.
    try:
        from app.services.hr_blocked_job_notifier import notify_blocked_job_improvements

        await notify_blocked_job_improvements(
            conn=conn,
            job_id=job_id,
            block_reason=reason,
            missing_roles=missing_roles,
        )
    except Exception:
        logger.exception("[job_pipeline] HR blocked job notifier failed job=%s", job_id)


async def _load_job(conn, job_id: str):
    job = await conn.fetchrow(
        "SELECT id, user_id, job_post, context, payload, status, tokens_used FROM jobs WHERE id=$1",
        job_id,
    )
    if not job:
        raise ValueError(f"Job not found: {job_id}")
    return job


async def _get_available_clients_for_user(conn, user_id: str) -> List[str]:
    """
    Return list of client slugs for this user (for intake completeness / clarification).
    Table: clients, column: slug. Checkpoint 2: real DB query, no stub.
    """
    if not user_id:
        return []
    rows = await conn.fetch(
        """
        SELECT slug FROM clients
        WHERE user_id = $1 AND (is_active IS NULL OR is_active = true)
        ORDER BY slug
        """,
        user_id,
    )
    return [r["slug"] for r in rows if r.get("slug")]


def _parse_extra_config_gsc_sites(extra_config: Any) -> List[str]:
    """Extract list of GSC site URLs from client_integrations.extra_config (gsc_sites or site_url)."""
    if not extra_config:
        return []
    if isinstance(extra_config, str):
        try:
            extra_config = json.loads(extra_config)
        except (TypeError, ValueError):
            return []
    if not isinstance(extra_config, dict):
        return []
    single = extra_config.get("site_url")
    if isinstance(single, str) and single.strip():
        # Preferred: when a direct site is selected for this client, keep scope to that one site.
        return [single.strip()]

    sites = extra_config.get("gsc_sites")
    if isinstance(sites, list) and sites:
        return [s for s in sites if isinstance(s, str) and s.strip()]
    return []


async def _get_gsc_properties_for_client(conn, user_id: str, client_slug: str) -> List[str]:
    """
    Return list of GSC site URLs for this client (from OAuth config).
    Table: client_integrations (integration_type = 'google_search_console'), extra_config.
    Checkpoint 2: real DB lookup, no stub.
    """
    if not user_id or not client_slug:
        return []
    row = await conn.fetchrow(
        """
        SELECT extra_config FROM client_integrations
        WHERE user_id = $1 AND client_slug = $2 AND integration_type = 'google_search_console'
        """,
        user_id,
        client_slug,
    )
    if not row:
        return []
    return _parse_extra_config_gsc_sites(row.get("extra_config"))


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
    *,
    job_id: Optional[str] = None,
    job_step_id: Optional[str] = None,
    agent_id: Optional[str] = None,
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
        output_dict, tokens_used, usage_records = result
        if job_id and usage_records:
            pool = await _get_pool()
            if pool:
                try:
                    async with pool.acquire() as conn:
                        await log_token_usage_records(
                            conn,
                            job_id,
                            step_name or agent_role or "step",
                            usage_records,
                            agent_id=agent_id,
                            job_step_id=job_step_id,
                        )
                except Exception as _cfo_err:
                    logger.debug("CFO log_token_usage_records skipped: %s", _cfo_err)
        return (output_dict, tokens_used)
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


def count_words(text: str) -> int:
    return len((text or "").split())


def _reviewer_minimum_word_target(context: Dict[str, Any]) -> Optional[int]:
    """
    Minimum word count only when job/brief text explicitly specifies a number (Dutch/English).
    Does not use the default ~400 copywriter target — avoids false positives.
    """
    bc = _brief_ctx(context)
    parts: List[str] = [
        str(bc.get("objective") or ""),
        str(context.get("job_post") or ""),
    ]
    brief = context.get("brief") if isinstance(context.get("brief"), dict) else {}
    try:
        parts.append(json.dumps(brief, ensure_ascii=False))
    except (TypeError, ValueError):
        parts.append(str(brief))
    blob = "\n".join(parts).lower()
    candidates: List[int] = []
    for pattern in (
        r"min(?:imaal)?\s*(\d{2,5})\s*woorden?",
        r"minimum\s+of\s*(\d{2,5})\s*words?",
        r"at\s+least\s*(\d{2,5})\s*words?",
        r"(?:^|[\s\n])(\d{2,5})\s*woorden\b",
        r"(?:^|[\s\n])(\d{2,5})\s*words\b",
    ):
        for m in re.finditer(pattern, blob, re.IGNORECASE):
            try:
                n = int(m.group(1))
                if 50 <= n <= 100_000:
                    candidates.append(n)
            except (TypeError, ValueError):
                continue
    return max(candidates) if candidates else None


def _brief_ctx(context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract objective, language, tone, focus, word_count from job context.brief."""
    brief = context.get("brief") if isinstance(context.get("brief"), dict) else {}
    ctx = brief.get("context") if isinstance(brief.get("context"), dict) else {}
    jp = str(context.get("job_post") or "")
    lang_raw = ctx.get("language") or brief.get("language") or context.get("language")
    if lang_raw is not None and str(lang_raw).strip():
        language = normalize_language_label(str(lang_raw), jp)
    else:
        language = detect_language(jp) if jp.strip() else "English"
    result = {
        "objective": ctx.get("objective") or brief.get("objective") or context.get("objective") or "",
        "language": language,
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


def _extract_text_from_anthropic_content(content: Any) -> str:
    """Extract concatenated text from all text blocks in Anthropic message content (content[0] may be non-text)."""
    if not content:
        return ""
    parts = []
    for block in content:
        if hasattr(block, "text") and block.text is not None:
            parts.append(str(block.text))
    return "".join(parts).strip()


def _parse_seo_handoff_from_llm_text(text: str) -> dict:
    """
    Parse SEO step JSON output into handoff fields for the copywriter.
    Tolerant of markdown fences and alternate keys.
    """
    if not text or not isinstance(text, str):
        return {}
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    kws = data.get("seo_keywords") or data.get("keywords") or []
    if isinstance(kws, str):
        kws = [k.strip() for k in kws.split(",") if k.strip()]
    if not isinstance(kws, list):
        kws = []
    kws = [str(x).strip() for x in kws if str(x).strip()]
    focus = str(data.get("focus_keyword") or data.get("focus") or "").strip()
    intent = str(data.get("keyword_intent") or data.get("intent") or "informatief").strip()
    return {"seo_keywords": kws, "focus_keyword": focus, "keyword_intent": intent}


def parse_keyword_output(text: str, focus_keyword: str = "") -> dict:
    """
    Parse legacy keyword-research text into structured keyword table data.
    Recognizes blocks like:
    - **Keyword**\\nZoekvolume: 1.200 | KD: 25 <description>
    """
    if not text or not isinstance(text, str):
        return {
            "output_type": "keyword_table",
            "focus_keyword": str(focus_keyword or "").strip(),
            "keywords": [],
        }

    keywords: list[dict[str, Any]] = []
    sections = re.split(r"\*\*(.+?)\*\*", text)
    i = 1
    while i < len(sections) - 1:
        keyword_name = str(sections[i] or "").strip()
        content = str(sections[i + 1] or "").strip()

        volume_match = re.search(r"Zoekvolume[:\s]+([0-9.,]+)", content, re.IGNORECASE)
        kd_match = re.search(r"KD[:\s]+(\d+)", content, re.IGNORECASE)

        search_volume = 0
        if volume_match:
            try:
                search_volume = int(volume_match.group(1).replace(".", "").replace(",", ""))
            except ValueError:
                search_volume = 0

        kd = 0
        if kd_match:
            try:
                kd = int(kd_match.group(1))
            except ValueError:
                kd = 0

        description = re.sub(
            r"Zoekvolume[:\s]+[0-9.,]+\s*\|?\s*KD[:\s]+\d+\s*",
            "",
            content,
            flags=re.IGNORECASE,
        ).strip()

        if keyword_name and (search_volume > 0 or kd > 0):
            keywords.append(
                {
                    "keyword": keyword_name,
                    "search_volume": search_volume,
                    "kd": kd,
                    "description": description,
                }
            )
        i += 2

    return {
        "output_type": "keyword_table",
        "focus_keyword": str(focus_keyword or "").strip(),
        "keywords": keywords,
    }


def _normalize_keyword_table_output(raw: Any, focus_keyword: str = "") -> dict:
    """
    Normalize keyword output to canonical frontend shape:
    { output_type: 'keyword_table', focus_keyword, keywords: [...] }
    """
    if isinstance(raw, str):
        parsed = parse_keyword_output(raw, focus_keyword=focus_keyword)
        return parsed

    if not isinstance(raw, dict):
        return {
            "output_type": "keyword_table",
            "focus_keyword": str(focus_keyword or "").strip(),
            "keywords": [],
        }

    kws = raw.get("keywords") or raw.get("seo_keywords") or []
    if isinstance(kws, str):
        kws = [k.strip() for k in kws.split(",") if k.strip()]

    normalized_keywords: list[dict[str, Any]] = []
    if isinstance(kws, list):
        for item in kws:
            if isinstance(item, dict):
                keyword = str(item.get("keyword") or item.get("title") or "").strip()
                if not keyword:
                    continue
                sv = item.get("search_volume") if item.get("search_volume") is not None else item.get("volume")
                try:
                    search_volume = int(str(sv).replace(".", "").replace(",", "")) if sv not in (None, "") else 0
                except ValueError:
                    search_volume = 0
                try:
                    kd = int(item.get("kd") or 0)
                except (TypeError, ValueError):
                    kd = 0
                normalized_keywords.append(
                    {
                        "keyword": keyword,
                        "search_volume": search_volume,
                        "kd": kd,
                        "description": str(item.get("description") or item.get("omschrijving") or "").strip(),
                    }
                )
            else:
                k = str(item or "").strip()
                if k:
                    normalized_keywords.append(
                        {"keyword": k, "search_volume": 0, "kd": 0, "description": ""}
                    )

    if not normalized_keywords and isinstance(raw.get("content"), str):
        return parse_keyword_output(raw.get("content", ""), focus_keyword=focus_keyword)

    return {
        "output_type": "keyword_table",
        "focus_keyword": str(raw.get("focus_keyword") or raw.get("focus") or focus_keyword or "").strip(),
        "keywords": normalized_keywords,
    }


def _run_step_agent(
    agent_role: str,
    step_name: str,
    context: Dict[str, Any],
    previous_content: Optional[str],
) -> Tuple[Dict[str, Any], int, List[Dict[str, Any]]]:
    """
    Run one pipeline step: copywriter (Claude), reviewer (Claude), image_generator (Pollinations.ai), or generic Claude.
    Returns (output_dict, tokens_used, anthropic_usage_records_for_cfo).
    """
    role_lower = (agent_role or "").lower()
    step_desc = step_name or agent_role or "step"

    # Content agents produce free-form text; skip WorkerOutputValidator (dev-style sections).
    CONTENT_AGENT_ROLES = frozenset({
        "copywriter", "copy writer", "reviewer", "review",
        "seo", "image_generator", "image generator", "imagegenerator", "image_generation",
    })
    is_content_role = role_lower in CONTENT_AGENT_ROLES

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
        return (output, 0, [])

    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set; using placeholder for step %s", step_desc)
        return (
            {"status": "placeholder", "content": f"[Placeholder – {step_desc}. No API key.]", "agent_role": agent_role},
            0,
            [],
        )

    try:
        from anthropic import Anthropic
        client = Anthropic()
    except Exception as e:
        logger.warning("Anthropic client init failed: %s; using placeholder", e)
        return (
            {"status": "placeholder", "content": f"[Placeholder – {step_desc}. {e}]", "agent_role": agent_role},
            0,
            [],
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
            + TOOL_FIRST_RULE
            + "\n"
            f"Communiceer altijd in de volgende taal: {language}. Dit geldt voor je analyse, feedback en alle output.\n"
            f"BELANGRIJK: Schrijf de volledige content in {language}. "
            "Dit is verplicht en heeft prioriteit boven alles. "
            f"Gebruik de keywords als SEO-richtlijn maar schrijf altijd in {language}.\n"
            "- Write the COMPLETE, FINAL article text ready for publication\n"
            "- Do NOT write a plan, outline, structure overview, or project description\n"
            "- Do NOT include meta-commentary like \"Projectoverzicht\", \"Leveringscriteria\", \"Status: GOEDGEKEURD\"\n"
            "- Do NOT include checkmarks ✓, status labels, or section descriptions\n"
            "- Do NOT describe what you're going to write — just WRITE IT\n"
            "- Start directly with the article title as a # heading, then the content\n"
            "- When you receive CRITICAL USER FEEDBACK, write a completely new version from scratch. Do not request, expect, or paste any previous draft text.\n"
            f"- Use ## for section headings (not ###, not bold text like **Heading**)\n"
            f"- Write in {language}\n"
            f"- Schrijf alle door jou geproduceerde content in deze taal: {language}. "
            f"(Write all output in this language.)\n"
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
        seo_kws = context.get("seo_keywords") or []
        focus_kw = (context.get("focus_keyword") or "").strip()
        if seo_kws or focus_kw:
            if not isinstance(seo_kws, list):
                seo_kws = [str(seo_kws)] if seo_kws else []
            extra = ", ".join(str(k) for k in seo_kws if k)
            system += f"""

## SEO Instructies
Verwerk de volgende keywords natuurlijk in de tekst:
- Focus keyword: {focus_kw or "(zie aanvullende keywords)"}
- Aanvullende keywords: {extra or "(geen)"}
- Zoekintentie: {context.get("keyword_intent") or "informatief"}

Het focus keyword moet voorkomen in de eerste alinea en minimaal 2x in de volledige tekst (natuurlijk verweven, geen keyword stuffing).
"""
        if not is_content_role:
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
        usage_records: List[Dict[str, Any]] = []
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            rec = anthropic_usage_record(CLAUDE_MODEL, response)
            if rec:
                usage_records.append(rec)
            logger.info("Copywriter raw response type: %s", type(response.content))
            logger.info("Copywriter content blocks: %s", len(response.content or []))
            for i, block in enumerate(response.content or []):
                logger.info("Block %s: type=%s, has_text=%s", i, getattr(block, "type", type(block).__name__), hasattr(block, "text"))
            text = _extract_text_from_anthropic_content(response.content)
            tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            if any(indicator in text for indicator in plan_indicators):
                retry_system = system + "\n\nWARNING: Your previous attempt produced a plan/outline instead of an article. Write the ACTUAL ARTICLE TEXT. No plans, no outlines, no project descriptions."
                response = client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=4000,
                    system=retry_system,
                    messages=[{"role": "user", "content": user}],
                )
                rec2 = anthropic_usage_record(CLAUDE_MODEL, response)
                if rec2:
                    usage_records.append(rec2)
                text = _extract_text_from_anthropic_content(response.content)
                tokens += (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            if not text:
                logger.warning("Copywriter step returned empty content (response had %s blocks)", len(response.content or []))
                return (
                    {"status": "failed", "content": "", "error": "Copywriter produced empty content", "agent_role": agent_role},
                    tokens,
                    usage_records,
                )
            out = {"status": "completed", "content": text, "agent_role": agent_role, "step_name": step_desc}
            if not is_content_role:
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
            return (out, tokens, usage_records)
        except Exception as e:
            logger.exception("Copywriter step failed: %s", e)
            return ({"status": "failed", "content": "", "error": str(e), "agent_role": agent_role}, 0, [])

    # Reviewer: review previous content
    if role_lower in ("reviewer", "review"):
        if not previous_content:
            return ({"status": "skipped", "review": "No content to review.", "approved": True, "agent_role": agent_role}, 0, [])
        system = (
            "CRITICAL RULES:\n"
            + TOOL_FIRST_RULE
            + "\n\n"
            "You are a content reviewer. Check quality, grammar, and tone consistency. Reply in the same language as the content. Keep the reply concise. End with APPROVED or CHANGES NEEDED. "
            "If the content looks like a plan or outline instead of actual article text, mark it as NOT APPROVED and explain that actual content is needed, not a plan.\n"
            f"Communiceer altijd in de volgende taal: {language}. Dit geldt voor je analyse, feedback en alle output.\n\n"
            "KWALITEITSCHECK WOORDENAANTAL:\n"
            "- Als de brief of opdracht een minimum woordenaantal specificeert (bijv. \"2000 woorden\", \"minimaal 1500 woorden\", \"at least 2000 words\"):\n"
            "  - Tel het aantal woorden in de aangeleverde content.\n"
            "  - Als de content meer dan 20% onder dat minimum zit (dus strikt minder dan 80% van het gevraagde minimum): geef CHANGES NEEDED.\n"
            "  - Vermeld in je feedback expliciet: \"Content bevat X woorden maar brief vraagt minimaal Y woorden\" (met echte X en Y).\n"
            "- Als de brief geen expliciet woordenaantal noemt: geen woordenaantal-check toepassen op basis van dit blok.\n"
        )
        knowledge_block = context.get("_knowledge_block") or ""
        if knowledge_block:
            system += "\n\n" + knowledge_block
        min_w = _reviewer_minimum_word_target(context)
        wc = count_words(previous_content)
        user = f"Review this content:\n\n{previous_content[:12000]}"
        if min_w is not None:
            threshold = int(min_w * 0.8)
            user += (
                f"\n\n[Opdracht-context] Er is een expliciet minimum van ongeveer {min_w} woorden geïdentificeerd in de opdracht. "
                f"De content telt ongeveer {wc} woorden. "
                f"Als {wc} < {threshold}, moet je CHANGES NEEDED geven en het werkelijke woordenaantal noemen."
            )
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            rev_usage: List[Dict[str, Any]] = []
            rec = anthropic_usage_record(CLAUDE_MODEL, response)
            if rec:
                rev_usage.append(rec)
            review_text = (response.content[0].text if response.content else "").strip()
            approved = "approved" in review_text.lower() or "changes needed" not in review_text.lower()
            tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            return (
                {"status": "completed", "review": review_text, "approved": approved, "agent_role": agent_role, "content": previous_content},
                tokens,
                rev_usage,
            )
        except Exception as e:
            logger.exception("Reviewer step failed: %s", e)
            return ({"status": "failed", "review": str(e), "approved": False, "agent_role": agent_role}, 0, [])

    # SEO: keyword plan as JSON for handoff to copywriter (no GSC — LLM-only)
    if role_lower == "seo":
        system = (
            "CRITICAL RULES:\n"
            + TOOL_FIRST_RULE
            + "\n\n"
            "You are an SEO specialist. Produce a concise keyword plan as a single JSON object only "
            "(no markdown fences, no commentary before or after the JSON).\n\n"
            "Required shape:\n"
            '{"focus_keyword": "string", "seo_keywords": ["kw1", "kw2", ...], "keyword_intent": "informatief"}\n'
            "- focus_keyword: one primary query for the page\n"
            "- seo_keywords: 4-7 strings total, must include focus_keyword once; add sensible variants\n"
            '- keyword_intent: one of: informatief, transactioneel, commercieel, navigational\n'
            f"Communiceer altijd in de volgende taal: {language}. Dit geldt voor je analyse, feedback en alle output.\n"
            f"\nGenereer alle keywords in de volgende taal: {language}. "
            f"Gebruik geen Engelse keywords als de taal Nederlands is.\n"
        )
        knowledge_block = context.get("_knowledge_block") or ""
        if knowledge_block:
            system += "\n\n" + knowledge_block
        user = (
            f"Topic / objective:\n{objective}\n"
            f"Focus area: {focus}\nLanguage: {language}\n"
            "Return JSON only."
        )
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1500,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            seo_usage: List[Dict[str, Any]] = []
            rec = anthropic_usage_record(CLAUDE_MODEL, response)
            if rec:
                seo_usage.append(rec)
            text = _extract_text_from_anthropic_content(response.content)
            tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            if not text:
                return (
                    {
                        "status": "failed",
                        "content": "",
                        "error": "SEO step produced empty content",
                        "agent_role": agent_role,
                    },
                    tokens,
                    seo_usage,
                )
            return (
                {
                    "status": "completed",
                    "content": text,
                    "agent_role": agent_role,
                    "step_name": step_desc,
                },
                tokens,
                seo_usage,
            )
        except Exception as e:
            logger.exception("SEO keyword step failed: %s", e)
            return ({"status": "failed", "content": "", "error": str(e), "agent_role": agent_role}, 0, [])

    # Generic: one Claude call
    system = (
        "CRITICAL RULES:\n"
        + TOOL_FIRST_RULE
        + "\n\n"
        f"You are a helpful assistant. Write in {language}. Tone: {tone}. "
        f"Communiceer altijd in de volgende taal: {language}. Dit geldt voor je analyse, feedback en alle output."
    )
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
        gen_usage: List[Dict[str, Any]] = []
        rec = anthropic_usage_record(CLAUDE_MODEL, response)
        if rec:
            gen_usage.append(rec)
        text = (response.content[0].text if response.content else "").strip()
        tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
        return ({"status": "completed", "content": text, "agent_role": agent_role, "step_name": step_desc}, tokens, gen_usage)
    except Exception as e:
        logger.exception("Generic step failed: %s", e)
        return ({"status": "failed", "content": f"[Error: {e}]", "agent_role": agent_role}, 0, [])


async def _insert_plan_steps(conn, job_id: str, plan: ExecutionPlan):
    # Guard: voorkom dubbele insert voor dezelfde job
    existing = await conn.fetchval(
        "SELECT COUNT(*) FROM job_steps WHERE job_id = $1",
        job_id,
    )
    if existing > 0:
        logger.info(
            "Skipping _insert_plan_steps for job %s: %d steps already exist",
            job_id,
            existing,
        )
        return

    # Replace any existing steps so we never duplicate when plan is generated/saved twice.
    await conn.execute("DELETE FROM job_steps WHERE job_id = $1", job_id)
    # Columns from information_schema; id omitted (default). Include agent if present (NOT NULL in some envs).
    for step in plan.steps:
        step_name = step.description or f"step_{step.step_index}"
        input_payload = {"description": step.description} if step.description else {}
        input_payload_json = json.dumps(input_payload, default=_json_default)
        agent_value = step.agent_role or step.unified_tool or step_name or "unknown"
        agent_id_value = f"agent:{step.agent_role}" if step.agent_role else agent_value
        await conn.execute(
            """
            INSERT INTO job_steps (
                job_id,
                step_index,
                step_name,
                agent_role,
                agent_id,
                agent,
                unified_tool,
                status,
                input_payload,
                requires_approval,
                created_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,now())
            """,
            job_id,
            step.step_index,
            step_name,
            step.agent_role,
            agent_id_value,
            agent_value,
            step.unified_tool,
            "pending",
            input_payload_json,
            step.requires_approval,
        )


async def run_data_pipeline(job_id: str) -> None:
    """
    Data-query pipeline: load context, run DataAgent (GSC/client_knowledge), set proposed_data and JOB_READY.
    GSC service is initialised via existing OAuth (get_gsc_service).
    """
    from app.agents.data_agent import DataAgent

    pool = await _get_pool()
    if not pool:
        logger.warning("DB pool not available, skipping run_data_pipeline for job %s", job_id)
        return
    try:
        async with pool.acquire() as conn:
            job = await _load_job(conn, job_id)
            context = _coerce_context(job.get("payload") or job.get("context"))
            query_params = dict(context.get("query_params") or {})
            query_params["raw_query"] = context.get("original_query") or job.get("job_post") or ""
            query_params.setdefault("client_slug", context.get("client_slug"))
            if not query_params.get("site_url") and context.get("gsc_properties"):
                first_site = (context["gsc_properties"] or [{}])[0]
                if isinstance(first_site, dict):
                    query_params["site_url"] = first_site.get("site_url") or first_site.get("gsc_site_url")
            if not query_params.get("site_url"):
                query_params["site_url"] = context.get("site_url") or context.get("gsc_site_url")
            preset_id = str(context.get("preset_id") or "").strip()
            if not preset_id:
                detected_preset = await detect_job_type(conn, str(job.get("job_post") or query_params.get("raw_query") or ""))
                if detected_preset:
                    preset_id = str(detected_preset)
                    await _update_job_context(conn, job_id, {"preset_id": preset_id})

        user_id = str(job.get("user_id") or "")
        client_slug = context.get("client_slug") or query_params.get("client_slug")
        gsc_service = await get_gsc_service(pool, user_id, client_slug)
        agent = DataAgent(db=pool, gsc_service=gsc_service, analytics_service=None)
        result = await agent.execute(job_id, query_params)

        proposed_data = {
            "gevonden": result.get("gevonden"),
            "resultaat": result.get("resultaat", []),
            "volledigheid": result.get("volledigheid"),
            "volgende_actie": result.get("volgende_actie"),
        }
        raw_query = str(query_params.get("raw_query") or "").lower()
        is_comparison_query = (
            ("organisch" in raw_query and "paid" in raw_query)
            or "vs" in raw_query
            or "vergelijk" in raw_query
        )
        should_run_analysis = preset_id == "analytics-comparison" or (not preset_id and is_comparison_query)

        final_content = format_data_output(proposed_data)
        analysis_payload: dict[str, Any] | None = None
        fetched_data: dict[str, Any] | None = None
        if should_run_analysis:
            from app.agents.analysis_agent import run_analysis
            from app.services.credential_resolver import get_all_active_integrations

            available_integrations: list[str] = []
            missing_integrations: list[str] = []
            integration_map = {"google_search_console": "gsc", "google_ads": "google_ads", "ga4": "ga4"}
            async with pool.acquire() as conn:
                all_integ = await get_all_active_integrations(
                    conn, client_slug or "", user_id
                )
            active_types = set(all_integ.keys())
            for integ_type, canonical in integration_map.items():
                if integ_type in active_types:
                    available_integrations.append(canonical)
                else:
                    missing_integrations.append(canonical)

            fetched_data = {"gsc": proposed_data}
            if "google_ads" in available_integrations:
                from app.services.ads_fetcher import fetch_ads_data_for_client

                async with pool.acquire() as ads_conn:
                    ads_result = await fetch_ads_data_for_client(
                        db=ads_conn,
                        client_slug=client_slug or "",
                        user_id=user_id,
                        date_range_days=28,
                    )
                if ads_result["available"]:
                    fetched_data["google_ads"] = ads_result["data"]
                    logger.info(
                        "run_data_pipeline: Google Ads data toegevoegd aan fetched_data job=%s",
                        job_id,
                    )
                else:
                    fetched_data["google_ads"] = {
                        "available": False,
                        "reason": ads_result["reason"],
                    }
                    logger.info(
                        "run_data_pipeline: Google Ads niet beschikbaar job=%s reden=%s",
                        job_id,
                        ads_result["reason"],
                    )

            analysis_payload = await run_analysis(
                job_id=job_id,
                client_name=str(client_slug or "onbekende klant"),
                raw_data=fetched_data,
                available_integrations=available_integrations,
                missing_integrations=missing_integrations,
                original_question=str(query_params.get("raw_query") or ""),
            )
            final_content = str(analysis_payload.get("analysis") or final_content)

        async with pool.acquire() as conn:
            await _update_job_context(conn, job_id, {
                "proposed_data": proposed_data,
                "pipeline_type": "direct_response",
                "final_content": final_content,
                "analysis_payload": analysis_payload,
                "fetched_data": fetched_data,
                "preset_id": preset_id or None,
            })
            await conn.execute(
                "UPDATE jobs SET status = $1, updated_at = now() WHERE id = $2",
                JobStatus.JOB_READY.value,
                job_id,
            )
        logger.info("run_data_pipeline: job %s set to JOB_READY (DataAgent)", job_id)
    except Exception as e:
        logger.exception("run_data_pipeline failed for job %s: %s", job_id, e)


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
        # Resolve client and build job_context for type detection (Checkpoint 2: real DB queries)
        async with pool.acquire() as conn:
            job_row = await conn.fetchrow("SELECT user_id, context FROM jobs WHERE id = $1", job_id)
            existing_ctx = _coerce_context(job_row["context"] if job_row else None) if job_row else {}
            user_id_str = str(job_row["user_id"]) if job_row else ""
            client_slug = existing_ctx.get("client_slug")
            if not client_slug and job_row and job_post:
                from app.services.client_mention import resolve_first_mention
                client_slug = await resolve_first_mention(pool, user_id_str, job_post)
            logger.info("intake client_slug after resolve: %s", client_slug)

            available_clients = await _get_available_clients_for_user(conn, user_id_str)
            # GSC properties: intentionally fetched for all jobs with client_slug (before task_type is known).
            # Query filters correctly on user_id + client_slug; timing/scope causes no issues.
            gsc_properties = await _get_gsc_properties_for_client(conn, user_id_str, client_slug) if client_slug else []
            job_context = {
                **existing_ctx,
                "client_slug": client_slug,
                "available_clients": available_clients,
                "gsc_properties": gsc_properties,
                "site_url": existing_ctx.get("site_url") or existing_ctx.get("gsc_site_url"),
            }

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

        brief = intake.analyze_job_post(job_post, client_context=client_context, job_context=job_context)
        if client_slug:
            brief.context = dict(brief.context or {})
            brief.context["client_slug"] = client_slug

        chat_history = []
        is_data_query_incomplete = (
            isinstance(brief.context, dict)
            and brief.context.get("detected_task_type") == "data_query"
            and not brief.is_complete
            and brief.clarifications
        )
        if is_data_query_incomplete:
            # data_query: max one question, show it once without numbering
            ceo_content = brief.clarifications[0].question
        else:
            ceo_content = brief.message or ""
            # If message already contains questions (?), it is leading — do not append clarifications.
            if (
                not brief.is_complete
                and brief.clarifications
                and "?" not in (ceo_content or "")
            ):
                questions_text = "\n\n".join(
                    f"{i + 1}. {q.question}" for i, q in enumerate(brief.clarifications)
                )
                if questions_text and questions_text not in ceo_content:
                    ceo_content = (ceo_content.rstrip() + "\n\n" + questions_text).strip()
        chat_history.append({"role": "ceo", "content": ceo_content})
        async with pool.acquire() as conn:
            intake_recs = getattr(intake, "_llm_usage_records", None) or []
            if intake_recs:
                await log_token_usage_records(conn, job_id, "intake", intake_recs, agent_id="intake")

            updates = {
                "brief": brief.model_dump(),
                "previous_answers": {},
                "chat_history": chat_history,
                "detected_task_type": brief.context.get("detected_task_type") if isinstance(brief.context, dict) else None,
                "query_params": brief.context.get("query_params") if isinstance(brief.context, dict) else None,
                "defaults_applied": brief.context.get("defaults_applied") if isinstance(brief.context, dict) else None,
                "original_query": job_post,
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

            preset_id = await detect_job_type(conn, job_post)
            updates["preset_id"] = preset_id
            await _update_job_context(conn, job_id, updates)

            # data_query complete: skip StrategyRoom and plan steps; run data pipeline (RUNNING -> JOB_READY)
            detected = (brief.context or {}) if isinstance(brief.context, dict) else {}
            if detected.get("detected_task_type") == "data_query":
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.RUNNING.value,
                    job_id,
                )
                asyncio.create_task(run_data_pipeline(job_id))
                return

            if preset_id:
                resource_report = await check_resources(conn, preset_id)
                if not resource_report["ready"]:
                    await _block_job(
                        conn,
                        job_id,
                        resource_report["message"],
                        _missing_roles_for_payload(resource_report.get("missing") or []),
                    )
                    return
            else:
                matched = await match_skill(conn, job_post)
                if matched:
                    await persist_matched_skill(conn, job_id, matched)
                else:
                    await _block_job(
                        conn,
                        job_id,
                        UNKNOWN_PRESET_AND_SKILL_MESSAGE,
                        [],
                    )
                    return

            # Content path: plan and steps
            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                JobStatus.PLAN_PROPOSED.value,
                job_id,
            )
            available_agents = await _fetch_available_agents(conn)
            plan = strategy.generate_execution_plan(brief, available_agents)
            strat_recs = getattr(strategy, "_llm_usage_records", None) or []
            if strat_recs:
                await log_token_usage_records(conn, job_id, "strategy_room", strat_recs, agent_id="strategy_room")
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
            await _maybe_set_structured_job_title(conn, job_id, job_post, preset_id=preset_id)
    except Exception as exc:
        logger.error("Intake error for job %s: %s", job_id, exc, exc_info=True)


async def run_intake_answers_inline(job_id: str, answers: dict):
    """
    1. Load existing job context; pass chat_history into IntakeEngine.
    2. If not complete → store clarifications, stay INTAKE_CLARIFICATION.
    3. If complete and context has final_content (revision) → set RUNNING, run_job_inline (skip StrategyRoom).
    4. Else (first-time complete) → StrategyRoom → PLAN_PROPOSED.
    """
    logger.info("run_intake_answers_inline started for job %s", job_id)
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

            # Job context for type detection (data_query completeness)
            available_clients = await _get_available_clients_for_user(conn, user_id)
            # If user just answered a data_query clarification (e.g. "Voor welke klant? (asured / merk-b)"):
            # match answer robustly (case-insensitive, strip). Only set client_slug on valid match;
            # invalid answer leaves client_slug unset so _detect_task_type returns is_complete=False
            # and the same clarification is shown again (no silent fallback).
            if not client_slug and context.get("detected_task_type") == "data_query" and answers:
                for _q_id, answer in (answers or {}).items():
                    if not answer or not isinstance(answer, str):
                        continue
                    ans = answer.strip().lower()
                    if not ans:
                        continue
                    for slug in available_clients:
                        if (slug or "").strip().lower() == ans:
                            client_slug = slug  # use canonical slug from DB
                            context["client_slug"] = slug
                            break
                    if client_slug:
                        break
            gsc_properties = await _get_gsc_properties_for_client(conn, user_id, client_slug) if client_slug else []
            job_context = {
                **context,
                "client_slug": client_slug,
                "available_clients": available_clients,
                "gsc_properties": gsc_properties,
                "site_url": context.get("site_url") or context.get("gsc_site_url"),
            }

            brief = intake.analyze_job_post(
                job_post,
                previous_answers=merged_answers,
                chat_history=chat_history if chat_history else None,
                client_context=client_context,
                job_context=job_context,
            )
            logger.info(
                "intake answers brief: is_complete=%s, clarifications=%d",
                brief.is_complete,
                len(brief.clarifications),
            )
            intake_recs_ans = getattr(intake, "_llm_usage_records", None) or []
            if intake_recs_ans:
                await log_token_usage_records(conn, job_id, "intake", intake_recs_ans, agent_id="intake")

            payload_complete = bool((context.get("brief") or {}).get("is_complete"))
            if not brief.is_complete and payload_complete:
                logger.info(
                    "force-completing intake: brief.is_complete=False but payload says complete"
                )
                brief.is_complete = True
            chat_history = list(chat_history)
            is_data_query_incomplete = (
                isinstance(brief.context, dict)
                and brief.context.get("detected_task_type") == "data_query"
                and not brief.is_complete
                and brief.clarifications
            )
            if is_data_query_incomplete:
                ceo_content = brief.clarifications[0].question
            else:
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
                logger.info(
                    "run_intake_answers_inline completed for job %s, new status=%s",
                    job_id,
                    JobStatus.INTAKE_CLARIFICATION.value,
                )
                return

            # data_query complete after clarification answer: run data pipeline
            detected = (brief.context or {}) if isinstance(brief.context, dict) else {}
            if detected.get("detected_task_type") == "data_query":
                await _update_job_context(conn, job_id, {
                    "detected_task_type": "data_query",
                    "query_params": detected.get("query_params") or {},
                    "defaults_applied": detected.get("defaults_applied") or {},
                    "original_query": job_post,
                })
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.RUNNING.value,
                    job_id,
                )
                asyncio.create_task(run_data_pipeline(job_id))
                logger.info("run_intake_answers_inline: data_query complete for job %s, run_data_pipeline queued", job_id)
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
                preset_id = await detect_job_type(conn, job_post)
                if preset_id:
                    resource_report = await check_resources(conn, preset_id)
                    if not resource_report["ready"]:
                        await _block_job(
                            conn,
                            job_id,
                            resource_report["message"],
                            _missing_roles_for_payload(resource_report.get("missing") or []),
                        )
                        return
                else:
                    matched = await match_skill(conn, job_post)
                    if matched:
                        await persist_matched_skill(conn, job_id, matched)
                    else:
                        await _block_job(
                            conn,
                            job_id,
                            UNKNOWN_PRESET_AND_SKILL_MESSAGE,
                            [],
                        )
                        return

                # Update status first so job leaves INTAKE_CLARIFICATION even if plan generation fails
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.PLAN_PROPOSED.value,
                    job_id,
                )
                available_agents = await _fetch_available_agents(conn)
                plan = strategy.generate_execution_plan(brief, available_agents)
                strat_recs_ans = getattr(strategy, "_llm_usage_records", None) or []
                if strat_recs_ans:
                    await log_token_usage_records(conn, job_id, "strategy_room", strat_recs_ans, agent_id="strategy_room")
                await _insert_plan_steps(conn, job_id, plan)
                await _update_job_context(
                    conn,
                    job_id,
                    {
                        "plan": plan.model_dump(),
                    },
                )
                await _maybe_set_structured_job_title(conn, job_id, job_post, preset_id=preset_id)
        if run_revision:
            logger.info(
                "run_intake_answers_inline completed for job %s, new status=%s",
                job_id,
                JobStatus.RUNNING.value,
            )
            await run_job_inline(job_id, None)
        else:
            logger.info(
                "run_intake_answers_inline completed for job %s, new status=%s",
                job_id,
                JobStatus.PLAN_PROPOSED.value,
            )
    except Exception as exc:
        logger.exception("run_intake_answers_inline failed for job %s: %s", job_id, exc)


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
            pipeline_stopped = False
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
                stop_pipeline = False

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
                        job_id=job_id,
                        job_step_id=str(step_id) if step_id is not None else None,
                        agent_id=str(step_agent_id) if step_agent_id else None,
                    )
                    await _update_step_progress(conn, step_id, 70)
                    output["step_name"] = step.get("step_name")
                    output["agent_role"] = step.get("agent_role")
                    output["unified_tool"] = step.get("unified_tool")

                    # Fail step and stop pipeline when copywriter returns failed or empty content (Reviewer must not get empty template)
                    role_lower = (agent_role or "").lower()
                    step_failed = output.get("status") == "failed"
                    if not step_failed and role_lower in ("copywriter", "copy writer"):
                        content_str = output.get("content")
                        if not content_str or not str(content_str).strip():
                            step_failed = True
                            output["status"] = "failed"
                            output["error"] = output.get("error") or "Copywriter produced empty content"
                            logger.warning("Copywriter step produced empty content for job %s; marking step failed and stopping pipeline", job_id)
                    if step_failed:
                        error_log = output.get("error") or "Step failed"
                        await conn.execute(
                            """
                            UPDATE job_steps
                            SET status='failed', completed_at=now(), output=$1::jsonb, tokens_used=$2, timing_ms=$3, progress_pct=100, error_log=$5
                            WHERE id=$4
                            """,
                            json.dumps(output, default=_json_default),
                            tokens_used,
                            int((time.monotonic() - started) * 1000),
                            step_id,
                            error_log,
                        )
                        stop_pipeline = True
                        pipeline_stopped = True
                        break

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

                    if role_lower == "seo" and output.get("content"):
                        handoff = _parse_seo_handoff_from_llm_text(str(output.get("content") or ""))
                        if handoff.get("seo_keywords") or handoff.get("focus_keyword"):
                            context["seo_keywords"] = handoff.get("seo_keywords") or []
                            context["focus_keyword"] = handoff.get("focus_keyword") or ""
                            context["keyword_intent"] = handoff.get("keyword_intent") or ""

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

                if stop_pipeline:
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

            if pipeline_stopped:
                logger.warning("Job %s pipeline stopped (step failed); not setting JOB_READY", job_id_str)
            else:
                steps_completed = True
                logger.info("All steps done for job %s. Setting JOB_READY...", job_id_str)
                try:
                    pool_ready = await get_db()
                    async with pool_ready.acquire() as conn:
                        logger.info("Storing final_content for job %s", job_id_str)
                        updates: Dict[str, Any] = {"final_content": last_content or "No content produced"}
                        preset_id = str(context.get("preset_id") or "").strip()
                        if preset_id == "seo-keyword-research":
                            keyword_payload = _normalize_keyword_table_output(
                                last_content or "",
                                focus_keyword=str(context.get("focus_keyword") or "").strip(),
                            )
                            if keyword_payload.get("keywords"):
                                updates["proposed_data"] = keyword_payload
                        await _update_job_context(conn, job_id_str, updates)
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
