"""Agents API endpoints."""

import json
import logging
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Body

from arq import ArqRedis

from app.middleware.auth import get_current_user, require_super_admin, TokenPayload
from app.dependencies import get_arq_pool
from pydantic import BaseModel, Field

import httpx

from app.database import get_db
from app.orchestration.direct_chat_engine import DirectChatEngine
from app.services.client_context import extract_client_context
from app.services.training import (
    generate_embedding,
    scrape_url,
    extract_text,
    chunk_text_by_chars,
    update_knowledge_sources,
    TrainingError,
)
from app.services.training_workflow import TrainingWorkflow
from app.data.agent_presets import AGENT_PRESETS
try:
    from app.data.role_templates import get_role_template, list_role_templates
except Exception:
    # Older deployments may not have role_templates module.
    def get_role_template(*args, **kwargs):
        return None

    def list_role_templates():
        return []

# Hiring Hall + framework sectie 5: geldige tools
VALID_TOOLS = [
    "read_product", "write_copy", "read_analytics", "write_social",
    "read_tickets", "write_tickets", "read_jobs", "send_report", "write_report",
    "web_search", "read_lessons", "write_email", "read_seo",
    "review_content", "optimize_seo", "keyword_research", "provide_feedback",
    "read_brief", "knowledge_retrieval", "submit_artifact", "read_url",
    "validate_output", "check_evidence", "score_confidence", "approve_artifact",
    "write_feedback", "create_development_point", "flag_escalation",
    "read_logs", "read_metrics", "write_research", "score_keywords",
    "write_response", "flag_pattern", "create_summary",
    "execute_fallback", "write_incident_report", "read_codebase", "write_code", "run_tests",
    "analyze_job", "build_execution_plan", "hire_agent", "delegate_task",
    "monitor_progress", "approve_output", "generate_intake_questions",
]
VALID_CATEGORIES = [
    "Management", "Content", "Marketing", "Operations",
    "Technical", "Support", "Analytics", "Custom",
]


def _json_default(obj: Any) -> Any:
    """For json.dumps: handle non-JSON-serializable values (e.g. datetime)."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _agent_improvement_to_legacy(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map agent_improvements row to legacy keys (point_id, issue_description, etc.) for API compatibility."""
    out = {
        "point_id": str(row.get("id", "")),
        "issue_description": row.get("title") or "",
        "root_cause": row.get("summary"),
        "evidence_example": row.get("details"),
        "frequency": 1,
        "impact": (row.get("severity") or "low").lower(),
        "status": (row.get("status") or "OPEN").upper(),
        "source_url": row.get("source_url") or row.get("source"),
        "agent_id": row.get("agent_id"),
    }
    for k in ("created_at", "updated_at"):
        if k in row and row.get(k) and hasattr(row[k], "isoformat"):
            out[k] = row[k].isoformat()
        elif k in row:
            out[k] = row.get(k)
    if "id" in row:
        out["id"] = str(row["id"])
    return out


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


def _to_json_compat(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _to_json_str(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def _serialize_agent_row(row: Any) -> Dict[str, Any]:
    record = dict(row)
    record["permissions"] = _to_json_compat(record.get("permissions"))
    record["knowledge_base_sources"] = _to_json_compat(record.get("knowledge_base_sources"))
    record["tool_access_whitelist"] = _to_json_compat(record.get("tool_access_whitelist"))
    record["hiring_logic"] = _to_json_compat(record.get("hiring_logic"))
    # Framework columns (use when present)
    for key in ("tool_whitelist", "knowledge_sources", "output_format", "guardrails", "model_config", "skills"):
        if key in record and record[key] is not None:
            record[key] = _to_json_compat(record[key])
    # API contract: expose llm_config instead of model_config (Pydantic v2 reserved name).
    if "model_config" in record and "llm_config" not in record:
        record["llm_config"] = record.pop("model_config")
    # tool_whitelist can be TEXT[] from DB — ensure list for JSON
    if "tool_whitelist" in record and isinstance(record["tool_whitelist"], (list, tuple)):
        record["tool_whitelist"] = list(record["tool_whitelist"])
    # Spec compat: agent_name alias voor name
    if "name" in record and "agent_name" not in record:
        record["agent_name"] = record["name"]
    return record



def _generate_agent_id(role: str) -> str:
    """Legacy: agent:<role>-<short-uuid>."""
    short_uuid = str(uuid.uuid4())[:4]
    safe_role = role.lower().replace(" ", "-")[:30]
    return f"agent:{safe_role}-{short_uuid}"


def _generate_agent_id_slug(name: str, role: str) -> str:
    """Product Spec v1.1: agent:<role>:<slug> uit naam."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "agent"
    safe_role = role.lower().replace(" ", "-")[:30]
    return f"agent:{safe_role}:{slug}"


def _generate_agent_id_with_suffix(role: str) -> str:
    """agent:<role>-<uuid4[:8]> for collision avoidance."""
    safe_role = role.lower().replace(" ", "-")[:30]
    return f"agent:{safe_role}-{uuid.uuid4().hex[:8]}"


class KnowledgeSource(BaseModel):
    url: str
    added_at: Optional[str] = None
    status: str = "pending"
    approved_by: Optional[str] = None


class AgentCreateHiringHall(BaseModel):
    """Hiring Hall spec (Product Spec v1.1): agent_name, goal, system_prompt, etc."""
    agent_name: str = Field(..., min_length=2, max_length=100)
    role: str = Field(...)
    category: str = Field(default="Custom")
    goal: str = Field(..., min_length=10, max_length=500)
    system_prompt: str = Field(..., min_length=20)
    tool_whitelist: List[str] = Field(default_factory=list)
    knowledge_sources: List[Any] = Field(default_factory=list)


class AgentCreate(BaseModel):
    """Legacy: agent_id, name, role — backward compat voor talents promote etc."""
    agent_id: Any
    name: str
    role: str
    specialization: Optional[str] = None
    status: Optional[str] = None
    permissions: Optional[Any] = None
    system_instructions: Optional[str] = None
    knowledge_base_sources: Optional[Any] = None
    tool_access_whitelist: Optional[Any] = None
    hiring_logic: Optional[Any] = None
    performance_score: Optional[float] = None
    completed_tasks: Optional[int] = None
    hired_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_suspended: Optional[bool] = None
    system_prompt: Optional[str] = None


class AgentUpdate(BaseModel):
    agent_id: Optional[Any] = None
    name: Optional[str] = None
    role: Optional[str] = None
    specialization: Optional[str] = None
    status: Optional[str] = None
    permissions: Optional[Any] = None
    system_instructions: Optional[str] = None
    knowledge_base_sources: Optional[Any] = None
    tool_access_whitelist: Optional[Any] = None
    hiring_logic: Optional[Any] = None
    performance_score: Optional[float] = None
    completed_tasks: Optional[int] = None
    hired_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_suspended: Optional[bool] = None
    system_prompt: Optional[str] = None
    goal: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None
    llm_config: Optional[dict] = None


class AgentResponse(BaseModel):
    id: Any
    agent_id: Any
    name: str
    role: str
    specialization: Optional[str] = None
    status: Optional[str] = None
    permissions: Optional[Any] = None
    system_instructions: Optional[str] = None
    knowledge_base_sources: Optional[Any] = None
    tool_access_whitelist: Optional[Any] = None
    hiring_logic: Optional[Any] = None
    performance_score: Optional[float] = None
    completed_tasks: Optional[int] = None
    hired_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_suspended: Optional[bool] = None
    system_prompt: Optional[str] = None
    goal: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None
    llm_config: Optional[dict] = None


@router.get("")
async def list_agents(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    is_active: Optional[bool] = Query(None, description="Filter by is_active"),
    category: Optional[str] = Query(None, description="Filter by category"),
) -> Dict[str, Any]:
    """Returns {agents: [...], count: N, total: N}. Optional filters: is_active, category."""
    pool = await get_db()
    conditions: List[str] = []
    values: List[Any] = []
    idx = 1
    if is_active is not None:
        conditions.append(f"is_active = ${idx}")
        idx += 1
        values.append(is_active)
    if category is not None:
        conditions.append(f"category = ${idx}")
        idx += 1
        values.append(category)
    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM hired_agents
            """ + where_clause + """
            ORDER BY
                CASE WHEN LOWER(role) = 'ceo' THEN 0 ELSE 1 END,
                COALESCE(name, '') ASC
            """,
            *values,
        )

    result: List[Dict[str, Any]] = []
    for row in rows:
        rec = _serialize_agent_row(row)
        rec.pop("system_prompt", None)
        result.append(rec)
    n = len(result)
    return {"agents": result, "count": n, "total": n}


@router.get("/presets")
async def list_agent_presets(
    current_user: Annotated[TokenPayload, Depends(require_super_admin)],
) -> Dict[str, Any]:
    """Beschikbare agent presets voor het NewCrewMember formulier."""
    return {
        "presets": AGENT_PRESETS,
        "total": len(AGENT_PRESETS),
    }


@router.get("/role-templates")
async def get_role_templates_list(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Rol-templates (framework sectie 5) voor default tool_whitelist, output_format, guardrails, llm_config."""
    return {"role_templates": list_role_templates()}


@router.get("/{agent_id}/detail")
async def get_agent_detail(
    agent_id: str,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Get agent plus related data: recent work, development points, applicable skills."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM hired_agents WHERE agent_id = $1", agent_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")
        agent = _serialize_agent_row(row)
        role = agent.get("role") or ""
        specialization = agent.get("specialization") or ""

        steps = await conn.fetch(
            """SELECT js.*, j.job_post FROM job_steps js
               LEFT JOIN jobs j ON js.job_id = j.id
               WHERE js.agent_role = $1
               ORDER BY js.created_at DESC NULLS LAST
               LIMIT 20""",
            role,
        )
        dev_rows = await conn.fetch(
            """SELECT * FROM agent_improvements
               WHERE agent_id = $1
               ORDER BY created_at DESC NULLS LAST
               LIMIT 20""",
            agent_id,
        )
        dev_points = [_agent_improvement_to_legacy(dict(r)) for r in dev_rows]
        skills = await conn.fetch(
            """SELECT * FROM agent_skills
               WHERE $1 = ANY(applicable_to) OR $2 = ANY(applicable_to)""",
            role,
            specialization,
        )

    def row_to_dict(r) -> Dict[str, Any]:
        d = dict(r)
        for key in list(d.keys()):
            if hasattr(d[key], "isoformat"):
                d[key] = d[key].isoformat()
        return d

    return {
        "agent": agent,
        "recent_work": [row_to_dict(s) for s in steps],
        "development_points": [row_to_dict(d) for d in dev_points],
        "skills": [row_to_dict(s) for s in skills],
    }


# ─── Direct Chat (Platform Spec v1.1) ──────────────────────────────────────

@router.post("/{agent_id}/chats", status_code=status.HTTP_201_CREATED)
async def create_direct_chat(
    agent_id: str,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Create new Direct Chat session for agent. Chat ID format: DC-YYYY-MM-###."""
    pool = await get_db()
    async with pool.acquire() as conn:
        agent = await conn.fetchrow(
            "SELECT agent_id FROM hired_agents WHERE agent_id = $1", agent_id
        )
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        prefix = datetime.now(timezone.utc).strftime("DC-%Y-%m-")
        row = await conn.fetchrow(
            """
            SELECT COALESCE(MAX(
                CAST(SUBSTRING(chat_id FROM LENGTH($1) + 1) AS INTEGER)
            ), 0) + 1 AS next_num
            FROM direct_chats
            WHERE chat_id LIKE $1 || '%'
            """,
            prefix,
        )
        next_num = row["next_num"] if row else 1
        chat_id = f"{prefix}{next_num:03d}"

        await conn.execute(
            """
            INSERT INTO direct_chats (chat_id, agent_id, user_id, message_count, token_used)
            VALUES ($1, $2, $3, 0, 0)
            """,
            chat_id,
            agent_id,
            str(current_user.user_id),
        )

    return {"chat_id": chat_id, "agent_id": agent_id}


@router.get("/{agent_id}/chats")
async def list_direct_chats(
    agent_id: str,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> List[Dict[str, Any]]:
    """List Direct Chat sessions for this agent, sorted by last_message_at DESC."""
    pool = await get_db()
    async with pool.acquire() as conn:
        agent = await conn.fetchrow(
            "SELECT agent_id FROM hired_agents WHERE agent_id = $1", agent_id
        )
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        rows = await conn.fetch(
            """
            SELECT chat_id, agent_id, user_id, title, message_count, token_used,
                   created_at, last_message_at
            FROM direct_chats
            WHERE agent_id = $1 AND user_id = $2
            ORDER BY last_message_at DESC
            """,
            agent_id,
            str(current_user.user_id),
        )

    def _row_to_dict(r):
        d = dict(r)
        for k in list(d.keys()):
            if hasattr(d[k], "isoformat"):
                d[k] = d[k].isoformat()
        return d

    return [_row_to_dict(r) for r in rows]


@router.get("/{agent_id}/chats/{chat_id}")
async def get_direct_chat(
    agent_id: str,
    chat_id: str,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Get full Direct Chat session with all messages."""
    pool = await get_db()
    async with pool.acquire() as conn:
        chat = await conn.fetchrow(
            """
            SELECT chat_id, agent_id, user_id, title, message_count, token_used,
                   created_at, last_message_at
            FROM direct_chats
            WHERE chat_id = $1 AND agent_id = $2 AND user_id = $3
            """,
            chat_id,
            agent_id,
            str(current_user.user_id),
        )
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        messages = await conn.fetch(
            """
            SELECT message_id, chat_id, role, content, created_at
            FROM direct_chat_messages
            WHERE chat_id = $1
            ORDER BY message_id ASC
            """,
            chat_id,
        )

    def _row_to_dict(r):
        d = dict(r)
        for k in list(d.keys()):
            if hasattr(d[k], "isoformat"):
                d[k] = d[k].isoformat()
        return d

    return {
        "chat": _row_to_dict(chat),
        "messages": [_row_to_dict(m) for m in messages],
    }


class DirectChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)


@router.post("/{agent_id}/chats/{chat_id}/message")
async def send_direct_chat_message(
    agent_id: str,
    chat_id: str,
    body: DirectChatMessageRequest,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Send message to agent; returns agent response."""
    pool = await get_db()
    async with pool.acquire() as conn:
        chat = await conn.fetchrow(
            """
            SELECT chat_id, agent_id, user_id FROM direct_chats
            WHERE chat_id = $1 AND agent_id = $2 AND user_id = $3
            """,
            chat_id,
            agent_id,
            str(current_user.user_id),
        )
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

    user_message = body.message
    client_context = await extract_client_context(user_message, str(current_user.user_id))
    if client_context:
        enriched_message = f"{client_context}\n\nGebruikersvraag: {user_message}"
    else:
        enriched_message = user_message

    engine = DirectChatEngine()
    result = await engine.send_message(chat_id, enriched_message)

    if "error" in result:
        if result["error"] == "chat_not_found":
            raise HTTPException(status_code=404, detail=result.get("detail", "Chat not found"))
        if result["error"] == "agent_not_found":
            raise HTTPException(status_code=404, detail=result.get("detail", "Agent not found"))
        if result["error"] == "session_token_limit_reached":
            raise HTTPException(
                status_code=429,
                detail=result.get("detail", "Session token limit reached"),
            )
        raise HTTPException(
            status_code=500,
            detail=result.get("detail", "Failed to send message"),
        )

    return result


class TrainAgentBody(BaseModel):
    url: str = Field(...)
    approved_by: str = Field(default="ceo")


class KnowledgeSaveRequest(BaseModel):
    chat_id: str = Field(...)
    message_id: int = Field(...)
    label: Optional[str] = Field(None, max_length=200)


@router.post("/{agent_id}/knowledge/save", status_code=status.HTTP_201_CREATED)
async def save_to_memory(
    agent_id: str,
    body: KnowledgeSaveRequest,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Save agent message from Direct Chat as knowledge chunk. Spec §8.3."""
    pool = await get_db()
    async with pool.acquire() as conn:
        chat = await conn.fetchrow(
            """
            SELECT chat_id, agent_id, user_id FROM direct_chats
            WHERE chat_id = $1 AND agent_id = $2 AND user_id = $3
            """,
            body.chat_id,
            agent_id,
            str(current_user.user_id),
        )
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        msg = await conn.fetchrow(
            """
            SELECT content FROM direct_chat_messages
            WHERE chat_id = $1 AND message_id = $2 AND role = 'agent'
            """,
            body.chat_id,
            body.message_id,
        )
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")

    content = msg["content"]
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Message has no content")

    source_url = f"direct_chat:{body.chat_id}"
    if body.label:
        source_url = f"{source_url}#{body.label[:100]}"

    try:
        embedding = await generate_embedding(content)
    except Exception as e:
        logger.warning("Embedding failed for save-to-memory: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate embedding")

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_knowledge (agent_id, source_url, chunk_text, embedding, chunk_index, is_active)
            VALUES ($1, $2, $3, $4::vector, 0, true)
            """,
            agent_id,
            source_url,
            content,
            json.dumps(embedding),
        )

    return {"status": "saved", "source_url": source_url}


@router.delete("/{agent_id}/chats/{chat_id}")
async def delete_direct_chat(
    agent_id: str,
    chat_id: str,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Delete Direct Chat session (CASCADE removes messages)."""
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM direct_chats
            WHERE chat_id = $1 AND agent_id = $2 AND user_id = $3
            RETURNING chat_id
            """,
            chat_id,
            agent_id,
            str(current_user.user_id),
        )
    if "DELETE 0" in str(result) or not result:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"status": "deleted", "chat_id": chat_id}


# ─── End Direct Chat ───────────────────────────────────────────────────────


@router.patch("/{agent_id}/avatar")
async def update_agent_avatar(
    agent_id: str,
    current_user: Annotated[TokenPayload, Depends(require_super_admin)],
    req: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """Store avatar config in permissions.avatar."""
    pool = await get_db()
    merge = {"avatar": req}
    async with pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE hired_agents
               SET permissions = COALESCE(permissions, '{}'::jsonb) || $1::jsonb,
                   updated_at = now()
               WHERE agent_id = $2""",
            json.dumps(merge, default=_json_default),
            agent_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "updated"}


def _unwrap_sources(val: Any) -> list:
    if isinstance(val, str):
        try:
            return json.loads(val) if val else []
        except Exception:
            return []
    return list(val) if isinstance(val, (list, tuple)) else []


async def _set_knowledge_source_status(
    pool, agent_id: str, source_url: str, status: str, error_msg: Optional[str] = None
) -> None:
    """Update status of one entry in knowledge_sources (or knowledge_base_sources) by url."""
    async with pool.acquire() as conn:
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'hired_agents'",
        )
        col_set = {r["column_name"] for r in cols}
        source_col = "knowledge_sources" if "knowledge_sources" in col_set else "knowledge_base_sources"
        row = await conn.fetchrow(
            f"SELECT {source_col} FROM hired_agents WHERE agent_id = $1",
            agent_id,
        )
    if not row:
        return
    sources = _unwrap_sources(row.get(source_col))
    for s in sources:
        if isinstance(s, dict) and s.get("url") == source_url:
            s["status"] = status
            if error_msg is not None:
                s["error"] = error_msg[:500]
            break
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE hired_agents SET {source_col} = $1::jsonb, updated_at = now()
            WHERE agent_id = $2
            """,
            json.dumps(sources, default=_json_default),
            agent_id,
        )


async def _append_knowledge_processing(pool, agent_id: str, url: str, approved_by: str) -> None:
    """Append a knowledge_sources (or knowledge_base_sources) entry with status processing."""
    now_iso = datetime.now(timezone.utc).isoformat()
    async with pool.acquire() as conn:
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'hired_agents'",
        )
        col_set = {r["column_name"] for r in cols}
        source_col = "knowledge_sources" if "knowledge_sources" in col_set else "knowledge_base_sources"
        row = await conn.fetchrow(
            f"SELECT {source_col} FROM hired_agents WHERE agent_id = $1",
            agent_id,
        )
    sources = _unwrap_sources(row.get(source_col) if row else None)
    sources = [s for s in sources if isinstance(s, dict) and s.get("url") != url]
    sources.append({
        "url": url,
        "added_at": now_iso,
        "status": "processing",
        "approved_by": approved_by,
    })
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE hired_agents SET {source_col} = $1::jsonb, updated_at = now()
            WHERE agent_id = $2
            """,
            json.dumps(sources, default=_json_default),
            agent_id,
        )


async def _run_training_background(agent_id: str, url: str, approved_by: str) -> None:
    """Run training in background: scrape → chunk (char 2000/200) → embed → store. Updates knowledge_base_sources."""
    pool = await get_db()
    if not pool:
        logger.error("Training %s: no DB pool", agent_id)
        return
    try:
        html = await scrape_url(url)
        text = extract_text(html)
        if len(text) < 100:
            await _set_knowledge_source_status(
                pool, agent_id, url, "failed", "Pagina bevat te weinig tekst"
            )
            return
        chunks = chunk_text_by_chars(text, chunk_size=2000, overlap=200)
        if not chunks:
            await _set_knowledge_source_status(
                pool, agent_id, url, "failed", "Geen chunks gegenereerd"
            )
            return

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE agent_knowledge SET is_active = false
                WHERE agent_id = $1 AND source_url = $2
                """,
                agent_id,
                url,
            )

        for idx, chunk in enumerate(chunks):
            embedding = await generate_embedding((chunk or "")[:8000])
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO agent_knowledge (agent_id, source_url, chunk_text, embedding, chunk_index, is_active)
                    VALUES ($1, $2, $3, $4::vector, $5, true)
                    """,
                    agent_id,
                    url,
                    chunk,
                    json.dumps(embedding),
                    idx,
                )

        await update_knowledge_sources(pool, agent_id, url, len(chunks), approved_by=approved_by)
        await _set_knowledge_source_status(pool, agent_id, url, "active")
        logger.info("Training completed for %s %s: %s chunks", agent_id, url, len(chunks))
    except TrainingError as e:
        logger.warning("Training failed for %s %s: %s", agent_id, url, e)
        await _set_knowledge_source_status(pool, agent_id, url, "failed", str(e))
    except Exception as e:
        logger.exception("Training failed for %s %s", agent_id, url)
        await _set_knowledge_source_status(pool, agent_id, url, "failed", str(e)[:500])


@router.post("/{agent_id}/train", status_code=status.HTTP_202_ACCEPTED)
async def train_agent(
    agent_id: str,
    body: TrainAgentBody,
    arq_pool: ArqRedis = Depends(get_arq_pool),
    current_user: TokenPayload = Depends(require_super_admin),
) -> Dict[str, Any]:
    """Start training for an agent with a URL. Returns 202; training runs in background. No CEO approval gate."""
    url = (body.url or "").strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=422, detail="URL moet beginnen met http:// of https://")
    pool = await get_db()
    async with pool.acquire() as conn:
        agent = await conn.fetchrow(
            "SELECT agent_id FROM hired_agents WHERE agent_id = $1",
            agent_id,
        )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    _browser_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=5.0) as client:
            head = await client.head(url, headers=_browser_headers)
            head.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=422,
            detail=f"URL niet bereikbaar: {str(e)}",
        ) from e

    approved_by = (body.approved_by or "user").strip() or "user"
    await _append_knowledge_processing(pool, agent_id, url, approved_by)
    await arq_pool.enqueue_job("_run_training_background", agent_id, url, approved_by)

    return {
        "agent_id": agent_id,
        "url": url,
        "status": "started",
        "message": f"Training gestart voor agent:{agent_id}",
    }


@router.get("/{agent_id}/context")
async def get_agent_context(
    agent_id: str,
    current_user: Annotated[TokenPayload, Depends(require_super_admin)],
    query: str = Query(..., description="Query voor context retrieval"),
    top_k: int = Query(default=5, ge=1, le=20),
) -> Dict[str, Any]:
    """Test context retrieval voor een agent. Spec sectie 5, stap 5."""
    pool = await get_db()
    workflow = TrainingWorkflow(pool)
    chunks = await workflow.retrieve_context(agent_id=agent_id, query=query, top_k=top_k)
    return {"agent_id": agent_id, "query": query, "chunks": chunks, "count": len(chunks)}


@router.get("/{agent_id}/knowledge")
async def get_agent_knowledge(
    agent_id: str,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Overzicht van alle kennisbronnen van een agent (gegroepeerd per URL)."""
    pool = await get_db()
    async with pool.acquire() as conn:
        agent = await conn.fetchrow(
            "SELECT agent_id, name FROM hired_agents WHERE agent_id = $1",
            agent_id,
        )
        if not agent:
            raise HTTPException(status_code=404, detail="Agent niet gevonden")

        rows = await conn.fetch(
            """
            SELECT
                source_url,
                COUNT(*) AS chunk_count,
                MAX(created_at) AS last_added,
                bool_and(is_active) AS all_active
            FROM agent_knowledge
            WHERE agent_id = $1
            GROUP BY source_url
            ORDER BY MAX(created_at) DESC
            """,
            agent_id,
        )
    sources = []
    total_chunks = 0
    for r in rows:
        d = dict(r)
        total_chunks += int(d.get("chunk_count") or 0)
        if d.get("last_added") and hasattr(d["last_added"], "isoformat"):
            d["last_added"] = d["last_added"].isoformat()
        sources.append(d)
    return {
        "agent_id": agent_id,
        "agent_name": agent.get("name"),
        "sources": sources,
        "total_chunks": total_chunks,
    }


@router.delete("/{agent_id}/knowledge")
async def deactivate_knowledge_source(
    agent_id: str,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    source_url: str = Query(..., description="URL van de bron om te deactiveren"),
) -> Dict[str, Any]:
    """Deactiveer alle chunks van een specifieke source_url (is_active = false)."""
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE agent_knowledge
            SET is_active = false
            WHERE agent_id = $1 AND source_url = $2 AND is_active = true
            """,
            agent_id,
            source_url,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Bron niet gevonden of al inactief")
    return {"deactivated": True, "source_url": source_url}


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> Dict[str, Any]:
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                id,
                agent_id,
                name,
                role,
                specialization,
                status,
                permissions,
                system_instructions,
                knowledge_base_sources,
                tool_access_whitelist,
                hiring_logic,
                performance_score,
                completed_tasks,
                hired_at,
                updated_at,
                is_suspended,
                system_prompt
            FROM hired_agents
            WHERE agent_id = $1
            """,
            agent_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    return _serialize_agent_row(row)


def _is_hiring_hall_payload(body: Dict[str, Any]) -> bool:
    """Detecteert spec-style payload (agent_name, goal) vs legacy (agent_id, name)."""
    return "agent_name" in body or "goal" in body


def _is_framework_payload(body: Dict[str, Any]) -> bool:
    """True if request contains framework sectie 4 fields (type, output_format, guardrails, llm_config)."""
    return (
        body.get("type") is not None
        and body.get("output_format") is not None
        and body.get("guardrails") is not None
        and body.get("llm_config") is not None
    )


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    current_user: Annotated[TokenPayload, Depends(require_super_admin)],
    body: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """
    Maakt een nieuwe agent aan.
    Ondersteunt twee payload-vormen:
    - Hiring Hall spec: agent_name, role, category, goal, system_prompt, tool_whitelist, knowledge_sources
    - Legacy: agent_id, name, role, specialization, system_instructions, etc.
    """
    pool = await get_db()
    now = datetime.now(timezone.utc)

    if _is_framework_payload(body):
        # ─── Framework payload (Crew Intelligent sectie 4) ──────────────────
        name = (body.get("name") or body.get("agent_name") or "").strip()
        role = (body.get("role") or "").strip()
        agent_type = (body.get("type") or "").strip().lower()
        if agent_type not in ("worker", "talent", "orchestrator"):
            raise HTTPException(status_code=422, detail="type must be worker, talent, or orchestrator")
        goal = (body.get("goal") or "").strip()
        system_prompt = (body.get("system_prompt") or "").strip()
        tool_whitelist = body.get("tool_whitelist") or []
        if not isinstance(tool_whitelist, list):
            tool_whitelist = []
        if not tool_whitelist:
            raise HTTPException(status_code=422, detail="tool_whitelist must have at least one tool")
        output_format = body.get("output_format")
        guardrails = body.get("guardrails") or {}
        if not isinstance(guardrails, dict):
            guardrails = {}
        if not guardrails.get("scope_limitation") or not guardrails.get("escalation_rule"):
            raise HTTPException(status_code=422, detail="guardrails must include scope_limitation and escalation_rule")
        llm_config = body.get("llm_config") or {}
        if not isinstance(llm_config, dict):
            llm_config = {}
        temp = llm_config.get("temperature", 0.7)
        if not isinstance(temp, (int, float)) or temp < 0.1 or temp > 0.9:
            raise HTTPException(status_code=422, detail="llm_config.temperature must be between 0.1 and 0.9")
        knowledge_sources = body.get("knowledge_sources") or []
        if not isinstance(knowledge_sources, list):
            knowledge_sources = []
        skills = body.get("skills")
        if skills is None:
            skills = []
        if not isinstance(skills, list):
            skills = []
        persona_source = (body.get("persona_source") or "").strip() or None
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "agent"
        agent_id = f"agent:{agent_type}:{slug}"
        async with pool.acquire() as conn:
            n = 0
            while True:
                existing = await conn.fetchrow(
                    "SELECT agent_id FROM hired_agents WHERE agent_id = $1",
                    agent_id,
                )
                if not existing:
                    break
                n += 1
                agent_id = f"agent:{agent_type}:{slug}-{n}"
            cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'hired_agents' ORDER BY ordinal_position",
            )
            col_set = {r["column_name"] for r in cols}
            insert_cols = [
                "agent_id", "name", "type", "role", "goal", "system_prompt",
                "tool_whitelist", "knowledge_sources", "output_format", "guardrails", "model_config",
                "skills", "persona_source", "readiness_score", "is_active", "is_suspended",
                "created_at", "updated_at",
            ]
            insert_cols = [c for c in insert_cols if c in col_set]
            placeholders = ", ".join(f"${i+1}" for i in range(len(insert_cols)))
            names = ", ".join(insert_cols)
            values = [
                agent_id, name, agent_type, role, goal, system_prompt,
                tool_whitelist, json.dumps(knowledge_sources), json.dumps(output_format or {}), json.dumps(guardrails), json.dumps(llm_config),
                json.dumps(skills), persona_source, 0, False, False,
                now, now,
            ]
            value_map = dict(zip([
                "agent_id", "name", "type", "role", "goal", "system_prompt",
                "tool_whitelist", "knowledge_sources", "output_format", "guardrails", "model_config",
                "skills", "persona_source", "readiness_score", "is_active", "is_suspended",
                "created_at", "updated_at",
            ], values))
            values_ordered = [value_map[c] for c in insert_cols]
            row = await conn.fetchrow(
                f"""
                INSERT INTO hired_agents ({names})
                VALUES ({placeholders})
                RETURNING *
                """,
                *values_ordered,
            )
        logger.info("Agent aangemaakt (framework): %s (%s), is_active=false", agent_id, name)
        return _serialize_agent_row(row)

    if _is_hiring_hall_payload(body):
        # ─── Hiring Hall spec (Product Spec v1.1) ─────────────────────────
        try:
            payload = AgentCreateHiringHall(**body)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))

        # Valideer tool_whitelist
        for t in payload.tool_whitelist:
            if t not in VALID_TOOLS:
                raise HTTPException(
                    status_code=422,
                    detail=f"Onbekende tool: {t}. Geldige tools: {VALID_TOOLS}",
                )

        agent_id = _generate_agent_id_slug(payload.agent_name, payload.role)
        knowledge_json = json.dumps(payload.knowledge_sources) if payload.knowledge_sources else "[]"
        tool_json = json.dumps(payload.tool_whitelist)

        async with pool.acquire() as conn:
            while True:
                existing = await conn.fetchrow(
                    "SELECT agent_id FROM hired_agents WHERE agent_id = $1",
                    agent_id,
                )
                if not existing:
                    break
                agent_id = _generate_agent_id_with_suffix(payload.role)

            row = await conn.fetchrow(
                """
                INSERT INTO hired_agents (
                    agent_id, name, role, goal, category,
                    system_prompt, system_instructions,
                    tool_access_whitelist, knowledge_base_sources,
                    status, is_active, is_suspended,
                    hired_at, updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $6,
                    $7::jsonb, $8::jsonb,
                    'active', false, false,
                    $9, $9
                )
                RETURNING *
                """,
                agent_id,
                payload.agent_name,
                payload.role,
                payload.goal,
                payload.category,
                payload.system_prompt,
                tool_json,
                knowledge_json,
                now,
            )

        logger.info("Agent aangemaakt (Hiring Hall): %s (%s), is_active=false", agent_id, payload.agent_name)
        return _serialize_agent_row(row)

    # ─── Legacy payload (agent_id, name, role) ─────────────────────────────
    try:
        legacy = AgentCreate(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    hired_at = legacy.hired_at or now
    updated_at = legacy.updated_at or now

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO hired_agents (
                agent_id, name, role, specialization, status,
                permissions, system_instructions, knowledge_base_sources,
                tool_access_whitelist, hiring_logic,
                performance_score, completed_tasks, hired_at, updated_at,
                is_suspended, system_prompt
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16
            )
            RETURNING *
            """,
            legacy.agent_id,
            legacy.name,
            legacy.role,
            legacy.specialization,
            legacy.status or "active",
            _to_json_str(legacy.permissions),
            legacy.system_instructions,
            _to_json_str(legacy.knowledge_base_sources),
            _to_json_str(legacy.tool_access_whitelist),
            _to_json_str(legacy.hiring_logic),
            legacy.performance_score,
            legacy.completed_tasks,
            hired_at,
            updated_at,
            legacy.is_suspended,
            legacy.system_prompt,
        )

    return _serialize_agent_row(row)


@router.post("/{agent_id}/activate")
async def activate_agent(
    agent_id: str,
    current_user: Annotated[TokenPayload, Depends(require_super_admin)],
) -> Dict[str, Any]:
    """
    Zet is_active = true alleen als alle verplichte velden (framework sectie 4) aanwezig zijn.
    """
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM hired_agents WHERE agent_id = $1",
            agent_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")
        r = dict(row)
        # Check required fields
        if not (r.get("name") or r.get("agent_name")):
            raise HTTPException(status_code=400, detail="name is required to activate")
        if not r.get("role"):
            raise HTTPException(status_code=400, detail="role is required to activate")
        if not r.get("goal"):
            raise HTTPException(status_code=400, detail="goal is required to activate")
        if not r.get("system_prompt"):
            raise HTTPException(status_code=400, detail="system_prompt is required to activate")
        tool_whitelist = r.get("tool_whitelist")
        if tool_whitelist is None:
            tool_whitelist = r.get("tool_access_whitelist")
        if isinstance(tool_whitelist, str):
            try:
                tool_whitelist = json.loads(tool_whitelist) if tool_whitelist else []
            except Exception:
                tool_whitelist = []
        if not (isinstance(tool_whitelist, list) and len(tool_whitelist) > 0):
            raise HTTPException(status_code=400, detail="tool_whitelist must have at least one tool")
        required_column_by_api_key = {
            "output_format": "output_format",
            "guardrails": "guardrails",
            "llm_config": "model_config",
        }
        for api_key, db_col in required_column_by_api_key.items():
            val = r.get(db_col)
            if val is None or (isinstance(val, str) and (not val or val in ("{}", "null"))):
                raise HTTPException(status_code=400, detail=f"{api_key} is required to activate")
        agent_type = r.get("type")
        if not agent_type:
            raise HTTPException(status_code=400, detail="type is required to activate")
        await conn.execute(
            "UPDATE hired_agents SET is_active = true, updated_at = now() WHERE agent_id = $1",
            agent_id,
        )
    return {"status": "activated", "agent_id": agent_id}


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    body: AgentUpdate,
    current_user: Annotated[TokenPayload, Depends(require_super_admin)],
) -> Dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    # API alias -> DB column
    if "llm_config" in data:
        data["model_config"] = data.pop("llm_config")

    # Validate tool_access_whitelist against VALID_TOOLS
    if "tool_access_whitelist" in data:
        tools = data["tool_access_whitelist"]
        if isinstance(tools, str):
            try:
                tools = json.loads(tools) if tools else []
            except json.JSONDecodeError:
                tools = []
        if not isinstance(tools, list):
            tools = []
        for t in tools:
            if t not in VALID_TOOLS:
                raise HTTPException(
                    status_code=422,
                    detail=f"Onbekende tool: {t}. Geldige tools: {VALID_TOOLS}",
                )

    data["updated_at"] = datetime.now(timezone.utc)

    json_fields = {
        "permissions",
        "knowledge_base_sources",
        "tool_access_whitelist",
        "hiring_logic",
        "model_config",
    }
    for key in json_fields:
        if key in data:
            data[key] = _to_json_str(data[key])

    columns = list(data.keys())
    set_clause = ", ".join(f"{col} = ${idx}" for idx, col in enumerate(columns, start=1))
    values = [data[col] for col in columns]
    values.append(agent_id)

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE hired_agents
            SET {set_clause}
            WHERE agent_id = ${len(values)}
            RETURNING
                id,
                agent_id,
                name,
                role,
                specialization,
                status,
                permissions,
                system_instructions,
                knowledge_base_sources,
                tool_access_whitelist,
                hiring_logic,
                performance_score,
                completed_tasks,
                hired_at,
                updated_at,
                is_suspended,
                system_prompt,
                goal,
                category,
                is_active,
                model_config
            """,
            *values,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    return _serialize_agent_row(row)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    current_user: Annotated[TokenPayload, Depends(require_super_admin)],
) -> Dict[str, Any]:
    """Soft delete: zet is_active op false. Agent blijft zichtbaar maar grijs."""
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE hired_agents SET is_active = false WHERE agent_id = $1",
            agent_id,
        )

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"status": "deactivated", "agent_id": agent_id}
