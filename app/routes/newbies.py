"""Newbie pool API routes.

CRUD for newbies table. Crew Intelligent Spec v1.0.
Training: URL → score per category. readiness_score = avg(4 scores). status=ready when ≥70.
"""

import json
import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from app.core.config import DEFAULT_MODEL
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/newbies", tags=["newbies"])

# Category mapping: newbie_trainings.category → newbies.score_* column
TRAINING_CATEGORIES = ("management", "creative", "development", "operations")
CATEGORY_TO_COLUMN = {
    "management": "score_management",
    "creative": "score_creative",
    "development": "score_development",
    "operations": "score_operations",
}


def _slug(name: str) -> str:
    """Generate URL-safe slug from name."""
    s = (name or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s[:30].rstrip("-") or "newbie"


def _generate_newbie_id(name: str) -> str:
    """Generate newbie_id: newbie:{slug}-{short-uuid}."""
    slug = _slug(name)
    short = uuid.uuid4().hex[:8]
    return f"newbie:{slug}-{short}"


def _json_safe(val):
    """Convert DB value to JSON-serializable form."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):  # datetime, date, time
        return val.isoformat()
    if hasattr(val, "hex"):  # UUID
        return str(val)
    if hasattr(val, "__float__") and not isinstance(val, (int, float, bool)):  # Decimal
        return float(val)
    return val


def _row_to_dict(row) -> dict:
    """Convert newbie DB row to JSON-safe dict."""
    d = dict(row)
    return {k: _json_safe(v) for k, v in d.items()}


# --- Pydantic models ---


class CreateNewbieRequest(BaseModel):
    newbie_name: str = Field(..., min_length=1, max_length=100)
    persona: str = Field(..., min_length=1)
    qualities: str = Field(..., max_length=500)
    development: str = Field(..., max_length=500)
    suggested_role: Optional[str] = None


class UpdateNewbieRequest(BaseModel):
    newbie_name: Optional[str] = Field(None, min_length=1, max_length=100)
    persona: Optional[str] = None
    qualities: Optional[str] = Field(None, max_length=500)
    development: Optional[str] = Field(None, max_length=500)
    suggested_role: Optional[str] = None
    status: Optional[str] = None


# --- Endpoints ---


@router.get("")
async def list_newbies():
    """List all newbies, sorted by updated_at."""
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM newbies ORDER BY updated_at DESC NULLS LAST, created_at DESC"
        )
    return [_row_to_dict(r) for r in rows]


@router.get("/ready")
async def list_ready_newbies():
    """List newbies with readiness >= 70 and status = 'ready' (Hiring Hall candidates)."""
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM newbies
            WHERE readiness_score >= 70 AND status = 'ready'
            ORDER BY readiness_score DESC, updated_at DESC
            """
        )
    return [_row_to_dict(r) for r in rows]


@router.get("/{newbie_id}")
async def get_newbie(newbie_id: str):
    """Get a single newbie."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM newbies WHERE newbie_id = $1", newbie_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Newbie not found")
    return _row_to_dict(row)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_newbie(req: CreateNewbieRequest):
    """Create a new newbie (persona upload). readiness=0, status=in_training."""
    pool = await get_db()
    newbie_id = _generate_newbie_id(req.newbie_name)
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO newbies (
                newbie_id, newbie_name, persona, qualities, development,
                readiness_score, score_management, score_creative,
                score_development, score_operations,
                status, suggested_role, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, 0, 0, 0, 0, 0, 'in_training', $6, $7, $7)
            """,
            newbie_id,
            req.newbie_name.strip(),
            req.persona.strip(),
            req.qualities.strip(),
            req.development.strip(),
            req.suggested_role,
            now,
        )
        row = await conn.fetchrow(
            "SELECT * FROM newbies WHERE newbie_id = $1", newbie_id
        )

    logger.info("Created newbie %s: %s", newbie_id, req.newbie_name)
    return _row_to_dict(row)


class TrainNewbieRequest(BaseModel):
    newbie_id: Optional[str] = Field(None, min_length=1)  # voor POST /train (body) i.p.v. path
    source_url: Optional[str] = Field(None, min_length=10)
    url: Optional[str] = Field(None, min_length=10)
    urls: Optional[List[str]] = Field(None, min_length=1)  # bulk: meerdere URLs,zelfde categorie
    category: str = Field(..., pattern=r"^(management|creative|development|operations)$")

    @model_validator(mode="after")
    def require_url(self):
        has_single = bool((self.source_url or self.url or "").strip())
        has_bulk = bool(self.urls and len([u for u in self.urls if (u or "").strip()]) > 0)
        if not has_single and not has_bulk:
            raise ValueError("Either source_url, url, or urls array is required")
        if has_single and has_bulk:
            raise ValueError("Use either single URL or urls array, not both")
        return self

    def get_url(self) -> str:
        return (self.source_url or self.url or "").strip()

    def get_urls(self) -> List[str]:
        """Normalized list of URLs (bulk mode). Filters empty, strips whitespace."""
        if not self.urls:
            return []
        return [u.strip() for u in self.urls if (u or "").strip()]


def _compute_readiness(score_m: int, score_c: int, score_d: int, score_o: int) -> int:
    """Readiness = rounded average of 4 category scores (0-100)."""
    return min(100, round((score_m + score_c + score_d + score_o) / 4))


async def _update_readiness_and_status(conn, newbie_id: str) -> None:
    """Recalc readiness_score from 4 scores; auto-update status=ready when ≥70 and in_training."""
    row = await conn.fetchrow(
        "SELECT score_management, score_creative, score_development, score_operations, status FROM newbies WHERE newbie_id = $1",
        newbie_id,
    )
    if not row:
        return
    m = row.get("score_management") or 0
    c = row.get("score_creative") or 0
    d = row.get("score_development") or 0
    o = row.get("score_operations") or 0
    readiness = _compute_readiness(m, c, d, o)
    current_status = row.get("status") or "in_training"
    # Only auto-promote to ready when in_training and readiness >= 70
    new_status = "ready" if (readiness >= 70 and current_status == "in_training") else current_status
    await conn.execute(
        "UPDATE newbies SET readiness_score = $1, status = $2, updated_at = now() WHERE newbie_id = $3",
        readiness,
        new_status,
        newbie_id,
    )


MAX_SCORE_PER_CATEGORY = 80  # Laatste 20 punten komen via hire-beoordeling
SCORE_PER_TRAINING = 10  # MVP: vaste +10 per training


async def _do_train_newbie(conn, newbie_id: str, req: TrainNewbieRequest):
    """Shared logic for train endpoints. newbie_id from path or body. Raises on error."""
    from app.services.training import scrape_url, extract_text, TrainingError

    row = await conn.fetchrow("SELECT * FROM newbies WHERE newbie_id = $1", newbie_id)
    if not row:
        raise HTTPException(status_code=404, detail="Newbie not found")
    if row.get("status") == "hired":
        raise HTTPException(status_code=400, detail="Cannot train a hired newbie")

    url = req.get_url()
    existing = await conn.fetchrow(
        "SELECT 1 FROM newbie_trainings WHERE newbie_id = $1 AND source_url = $2 AND category = $3",
        newbie_id,
        url,
        req.category,
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Deze URL is al gebruikt voor deze categorie. Kies een andere URL.",
        )

    try:
        html = await scrape_url(url)
    except TrainingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    text = extract_text(html)
    stripped = (text or "").strip()
    if len(stripped) < 50:
        raise HTTPException(status_code=400, detail="Extracted text is too short (min 50 chars)")

    extracted_summary = (
        "Pagina vereist JavaScript — inhoud niet extraheerbaar via scraper"
        if len(stripped) < 200
        else stripped[:300]
    )

    score_gained = SCORE_PER_TRAINING
    col = CATEGORY_TO_COLUMN.get(req.category)
    if not col:
        raise HTTPException(status_code=400, detail="Invalid category")

    await conn.execute(
        """
        INSERT INTO newbie_trainings (newbie_id, source_url, category, score_gained, status, completed_at, extracted_summary)
        VALUES ($1, $2, $3, $4, 'completed', now(), $5)
        """,
        newbie_id,
        url,
        req.category,
        score_gained,
        extracted_summary,
    )
    await conn.execute(
        f"UPDATE newbies SET {col} = LEAST($1, COALESCE({col}, 0) + $2), updated_at = now() WHERE newbie_id = $3",
        MAX_SCORE_PER_CATEGORY,
        score_gained,
        newbie_id,
    )
    await _update_readiness_and_status(conn, newbie_id)
    return await conn.fetchrow("SELECT * FROM newbies WHERE newbie_id = $1", newbie_id)


async def _try_train_one_url(conn, newbie_id: str, url: str, category: str) -> tuple[bool, Optional[str]]:
    """Try to train one URL. Returns (success, error_message). Does not raise."""
    from app.services.training import scrape_url, extract_text, TrainingError

    row = await conn.fetchrow("SELECT * FROM newbies WHERE newbie_id = $1", newbie_id)
    if not row:
        return False, "Newbie not found"
    if row.get("status") == "hired":
        return False, "Cannot train a hired newbie"

    existing = await conn.fetchrow(
        "SELECT 1 FROM newbie_trainings WHERE newbie_id = $1 AND source_url = $2 AND category = $3",
        newbie_id,
        url,
        category,
    )
    if existing:
        return False, "URL al gebruikt voor deze categorie"

    try:
        html = await scrape_url(url)
    except TrainingError as e:
        return False, str(e)

    text = extract_text(html)
    stripped = (text or "").strip()
    if len(stripped) < 50:
        return False, "Extracted text is too short"

    extracted_summary = (
        "Pagina vereist JavaScript — inhoud niet extraheerbaar via scraper"
        if len(stripped) < 200
        else stripped[:300]
    )

    col = CATEGORY_TO_COLUMN.get(category)
    if not col:
        return False, "Invalid category"

    await conn.execute(
        """
        INSERT INTO newbie_trainings (newbie_id, source_url, category, score_gained, status, completed_at, extracted_summary)
        VALUES ($1, $2, $3, $4, 'completed', now(), $5)
        """,
        newbie_id,
        url,
        category,
        SCORE_PER_TRAINING,
        extracted_summary,
    )
    await conn.execute(
        f"UPDATE newbies SET {col} = LEAST($1, COALESCE({col}, 0) + $2), updated_at = now() WHERE newbie_id = $3",
        MAX_SCORE_PER_CATEGORY,
        SCORE_PER_TRAINING,
        newbie_id,
    )
    await _update_readiness_and_status(conn, newbie_id)
    return True, None


@router.post("/train", status_code=status.HTTP_201_CREATED)
async def train_newbie_body(req: TrainNewbieRequest):
    """Train a newbie with newbie_id in body. Single URL (source_url) or bulk (urls array)."""
    if not req.newbie_id:
        raise HTTPException(status_code=400, detail="newbie_id is required in request body")
    newbie_id = req.newbie_id.strip()

    urls = req.get_urls()
    if urls:
        # Bulk: process URLs sequentially
        pool = await get_db()
        processed = 0
        skipped = 0
        score_gained = 0
        row = None
        async with pool.acquire() as conn:
            for url in urls:
                ok, _err = await _try_train_one_url(conn, newbie_id, url, req.category)
                if ok:
                    processed += 1
                    score_gained += SCORE_PER_TRAINING
                    row = await conn.fetchrow("SELECT * FROM newbies WHERE newbie_id = $1", newbie_id)
                else:
                    skipped += 1
        logger.info("Bulk train newbie %s: processed=%s skipped=%s score_gained=%s", newbie_id, processed, skipped, score_gained)
        return {
            "processed": processed,
            "skipped": skipped,
            "score_gained": score_gained,
            "newbie": _row_to_dict(row) if row else None,
        }

    # Single URL
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await _do_train_newbie(conn, newbie_id, req)
    logger.info("Trained newbie %s: +%s in %s", newbie_id, SCORE_PER_TRAINING, req.category)
    return _row_to_dict(row)


@router.post("/{newbie_id}/train", status_code=status.HTTP_201_CREATED)
async def train_newbie_path(newbie_id: str, req: TrainNewbieRequest):
    """Train a newbie (newbie_id in path). Voor backwards compatibility."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await _do_train_newbie(conn, newbie_id, req)
    logger.info("Trained newbie %s: +%s in %s", newbie_id, SCORE_PER_TRAINING, req.category)
    return _row_to_dict(row)


@router.post("/backfill-summaries")
async def backfill_summaries():
    """
    Backfill extracted_summary for all newbie_trainings where it is NULL.
    Re-scrapes each URL and saves first 300 chars (or JS fallback if < 200 chars).
    """
    from app.services.training import scrape_url, extract_text, TrainingError

    pool = await get_db()
    updated = 0
    failed = 0
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT training_id, source_url FROM newbie_trainings WHERE extracted_summary IS NULL"
        )
        total = len(rows)
        for row in rows:
            training_id = row["training_id"]
            url = row["source_url"]
            try:
                html = await scrape_url(url)
                text = extract_text(html)
                stripped = (text or "").strip()
                extracted_summary = (
                    "Pagina vereist JavaScript — inhoud niet extraheerbaar via scraper"
                    if len(stripped) < 200
                    else stripped[:300]
                )
                await conn.execute(
                    "UPDATE newbie_trainings SET extracted_summary = $1 WHERE training_id = $2",
                    extracted_summary,
                    training_id,
                )
                updated += 1
            except (TrainingError, Exception) as e:
                logger.warning("Backfill failed for training_id=%s url=%s: %s", training_id, url, e)
                failed += 1
    return {"updated": updated, "failed": failed, "total": total}


SYSTEM_PROMPT_MODEL = DEFAULT_MODEL


async def _generate_system_prompt_via_claude(
    newbie_name: str,
    persona: str,
    qualities: str,
    development: str,
    role: str,
) -> str:
    """Generate system_prompt via Claude API. Uses DEFAULT_MODEL (config).
    No silent fallback: raises if API key missing or API call fails."""
    logger.info("Calling Claude API for system_prompt...")
    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set in hire context; cannot generate system_prompt")
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. System prompt generation requires the Anthropic API. "
            "Set the key in your environment or pass system_prompt explicitly in the hire request."
        )

    from anthropic import Anthropic

    system_instruction = (
        "Genereer een system_prompt voor een AI agent. "
        "Verwerk het karakter en de toon van de persona in de werkwijze. "
        "Max 400 woorden. Schrijf in de tweede persoon (Jij bent...)."
    )
    user_content = f"""Naam: {newbie_name}
Rol: {role}

Persona (wie is hij/zij?):
{persona or '(niet opgegeven)'}

Kwaliteiten (waar is hij/zij goed in?):
{qualities or '(niet opgegeven)'}

Ontwikkelpunten (wat moet nog groeien?):
{development or '(niet opgegeven)'}

Output alleen de system_prompt, geen uitleg of markdown."""

    try:
        client = Anthropic()
        response = client.messages.create(
            model=SYSTEM_PROMPT_MODEL,
            max_tokens=1024,
            system=system_instruction,
            messages=[{"role": "user", "content": user_content}],
        )
        text = (response.content[0].text if response.content else "").strip()
        if not text:
            logger.error("Claude API returned empty system_prompt for %s (role=%s)", newbie_name, role)
            raise ValueError("Claude API returned empty system_prompt")
        logger.info("Hire system_prompt generated for %s (role=%s):\n%s", newbie_name, role, text)
        return text
    except ValueError:
        raise
    except Exception as e:
        logger.exception("Claude API failed for system_prompt generation: %s", e)
        raise RuntimeError(
            f"System prompt generation failed: {e}. "
            "Pass system_prompt explicitly in the hire request to bypass Claude."
        ) from e


class HireNewbieRequest(BaseModel):
    role: Optional[str] = None  # defaults to suggested_role or "custom"
    system_prompt: Optional[str] = None  # defaults to persona + qualities + development
    goal: Optional[str] = None
    tool_whitelist: List[str] = Field(default_factory=list)
    knowledge_sources: List[dict] = Field(default_factory=list)


@router.post("/{newbie_id}/hire", status_code=status.HTTP_201_CREATED)
async def hire_newbie(newbie_id: str, req: HireNewbieRequest = HireNewbieRequest()):
    """Convert a ready newbie to a hired agent. Newbie status → hired, hired_as = agent_id."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM newbies WHERE newbie_id = $1", newbie_id)
        if not row:
            raise HTTPException(status_code=404, detail="Newbie not found")
        if row.get("status") == "hired":
            raise HTTPException(status_code=400, detail="Newbie already hired")
        if row.get("status") != "ready" and (row.get("readiness_score") or 0) < 70:
            raise HTTPException(
                status_code=400,
                detail="Newbie must be ready (readiness ≥ 70) to hire. Train first.",
            )

        name = row.get("newbie_name") or "Newbie"
        role = req.role or row.get("suggested_role") or "custom"
        system_prompt = req.system_prompt
        if not system_prompt:
            try:
                system_prompt = await _generate_system_prompt_via_claude(
                    newbie_name=name,
                    persona=row.get("persona") or "",
                    qualities=row.get("qualities") or "",
                    development=row.get("development") or "",
                    role=role,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except RuntimeError as e:
                raise HTTPException(status_code=503, detail=str(e))
            logger.info("Hire newbie %s: system_prompt (length=%d):\n%s", newbie_id, len(system_prompt), system_prompt)
        goal = req.goal or f"Execute tasks as {name}."
        tool_json = json.dumps(req.tool_whitelist or [])
        knowledge_json = json.dumps(req.knowledge_sources or [])

        agent_id = f"agent:{role.lower().replace(' ', '-')[:20]}-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        existing = await conn.fetchrow(
            "SELECT agent_id FROM hired_agents WHERE name = $1 AND is_active = true", name
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Agent met naam '{name}' bestaat al. Kies een andere naam of wijzig de newbie naam.",
            )

        await conn.execute(
            """
            INSERT INTO hired_agents (
                agent_id, name, role, goal, category,
                system_prompt, system_instructions,
                tool_access_whitelist, knowledge_base_sources,
                status, is_active, is_suspended,
                hired_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, 'Custom',
                $5, $5,
                $6::jsonb, $7::jsonb,
                'active', true, false,
                $8, $8
            )
            """,
            agent_id,
            name,
            role,
            goal,
            system_prompt,
            tool_json,
            knowledge_json,
            now,
        )

        await conn.execute(
            "UPDATE newbies SET status = 'hired', hired_as = $1, updated_at = now() WHERE newbie_id = $2",
            agent_id,
            newbie_id,
        )

        agent_row = await conn.fetchrow("SELECT * FROM hired_agents WHERE agent_id = $1", agent_id)

    logger.info("Hired newbie %s as agent %s", newbie_id, agent_id)
    return {
        "agent_id": agent_id,
        "name": name,
        "role": role,
        "status": "active",
        "hired_from_newbie": newbie_id,
        "agent": dict(agent_row) if agent_row else None,
    }


@router.post("/{newbie_id}/promote", status_code=status.HTTP_201_CREATED)
async def promote_newbie(newbie_id: str):
    """
    Promote a ready newbie to hired_agents (Fase A.4).
    Sets newbies.status = 'promoted', creates hired_agents with is_active = true,
    copies relevant fields. Newbie must have readiness >= 70 and status = 'ready'.
    """
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM newbies WHERE newbie_id = $1", newbie_id)
        if not row:
            raise HTTPException(status_code=404, detail="Newbie not found")
        if row.get("status") == "promoted":
            raise HTTPException(status_code=400, detail="Newbie already promoted")
        if row.get("status") == "hired":
            raise HTTPException(status_code=400, detail="Newbie already hired (use hire endpoint)")
        if (row.get("readiness_score") or 0) < 70:
            raise HTTPException(
                status_code=400,
                detail="Newbie must have readiness >= 70 to promote. Train first.",
            )
        if row.get("status") != "ready":
            raise HTTPException(
                status_code=400,
                detail="Newbie must be status 'ready' to promote. Update status or train first.",
            )

        name = row.get("newbie_name") or "Newbie"
        agent_type = row.get("type") or "worker"
        role = row.get("role") or row.get("suggested_role") or "custom"
        persona_source = row.get("persona_source") or ""
        goal = f"Persona {name}. Ontwikkelpunt: {row.get('development_priority') or row.get('development') or '—'}"
        system_prompt = (
            f"Je bent {name}, een {row.get('badge') or 'crew member'} binnen Crew Intelligent. "
            f"Persona: {row.get('persona') or ''}. Kwaliteiten: {row.get('qualities') or ''}. "
            f"Ontwikkeling: {row.get('development') or ''}."
        )
        # Migrated newbies have newbie_id = agent_id (agent:type:slug); reuse as agent_id when promoting
        if (row.get("newbie_id") or "").startswith("agent:"):
            agent_id = row["newbie_id"]
        else:
            agent_id = f"agent:{agent_type}:{_slug(name)}-{uuid.uuid4().hex[:8]}"

        now = datetime.now(timezone.utc)
        existing = await conn.fetchrow(
            "SELECT agent_id FROM hired_agents WHERE agent_id = $1", agent_id
        )
        if existing:
            agent_id = f"agent:{agent_type}:{_slug(name)}-{uuid.uuid4().hex[:8]}"

        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'hired_agents' ORDER BY ordinal_position"
        )
        col_set = {r["column_name"] for r in cols}
        insert_cols = [
            "agent_id", "name", "type", "role", "goal", "system_prompt",
            "tool_whitelist", "knowledge_sources", "output_format", "guardrails", "model_config",
            "skills", "persona_source", "readiness_score", "is_active", "is_suspended",
            "created_at", "updated_at",
        ]
        insert_cols = [c for c in insert_cols if c in col_set]
        if not insert_cols:
            insert_cols = [
                "agent_id", "name", "role", "goal", "category",
                "system_prompt", "system_instructions",
                "tool_access_whitelist", "knowledge_base_sources",
                "status", "is_active", "is_suspended", "hired_at", "updated_at",
            ]
            insert_cols = [c for c in insert_cols if c in col_set]
        placeholders = ", ".join(f"${i+1}" for i in range(len(insert_cols)))
        names = ", ".join(insert_cols)
        value_map = {}
        for c in insert_cols:
            if c == "agent_id":
                value_map[c] = agent_id
            elif c == "name":
                value_map[c] = name
            elif c == "type":
                value_map[c] = agent_type
            elif c == "role":
                value_map[c] = role
            elif c == "goal":
                value_map[c] = goal
            elif c == "system_prompt":
                value_map[c] = system_prompt
            elif c == "tool_whitelist":
                value_map[c] = []
            elif c == "tool_access_whitelist":
                value_map[c] = json.dumps([])
            elif c == "knowledge_sources":
                value_map[c] = json.dumps([])
            elif c == "knowledge_base_sources":
                value_map[c] = json.dumps([])
            elif c in ("output_format", "guardrails", "model_config", "skills"):
                value_map[c] = json.dumps({} if c != "skills" else [])
            elif c == "persona_source":
                value_map[c] = persona_source
            elif c == "readiness_score":
                value_map[c] = row.get("readiness_score") or 0
            elif c == "is_active":
                value_map[c] = True
            elif c == "is_suspended":
                value_map[c] = False
            elif c == "status":
                value_map[c] = "active"
            elif c == "category":
                value_map[c] = "Custom"
            elif c == "system_instructions":
                value_map[c] = system_prompt
            elif c in ("created_at", "updated_at", "hired_at"):
                value_map[c] = now
        values_ordered = [value_map[c] for c in insert_cols]
        await conn.execute(
            f"INSERT INTO hired_agents ({names}) VALUES ({placeholders})",
            *values_ordered,
        )
        await conn.execute(
            "UPDATE newbies SET status = 'promoted', hired_as = $1, updated_at = now() WHERE newbie_id = $2",
            agent_id,
            newbie_id,
        )
        agent_row = await conn.fetchrow("SELECT * FROM hired_agents WHERE agent_id = $1", agent_id)

    logger.info("Promoted newbie %s to agent %s", newbie_id, agent_id)
    return {
        "agent_id": agent_id,
        "name": name,
        "role": role,
        "status": "active",
        "promoted_from_newbie": newbie_id,
        "agent": _row_to_dict(agent_row) if agent_row else None,
    }


@router.get("/{newbie_id}/trainings")
async def list_newbie_trainings(newbie_id: str):
    """List training history for a newbie."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT newbie_id FROM newbies WHERE newbie_id = $1", newbie_id)
        if not row:
            raise HTTPException(status_code=404, detail="Newbie not found")
        rows = await conn.fetch(
            "SELECT * FROM newbie_trainings WHERE newbie_id = $1 ORDER BY created_at DESC",
            newbie_id,
        )
    return [dict(r) for r in rows]


@router.patch("/{newbie_id}")
async def update_newbie(newbie_id: str, req: UpdateNewbieRequest):
    """Update a newbie's fields."""
    pool = await get_db()
    updates = []
    params = []
    idx = 1

    if req.newbie_name is not None:
        updates.append(f"newbie_name = ${idx}")
        params.append(req.newbie_name.strip())
        idx += 1
    if req.persona is not None:
        updates.append(f"persona = ${idx}")
        params.append(req.persona.strip())
        idx += 1
    if req.qualities is not None:
        updates.append(f"qualities = ${idx}")
        params.append(req.qualities.strip())
        idx += 1
    if req.development is not None:
        updates.append(f"development = ${idx}")
        params.append(req.development.strip())
        idx += 1
    if req.suggested_role is not None:
        updates.append(f"suggested_role = ${idx}")
        params.append(req.suggested_role)
        idx += 1
    if req.status is not None:
        if req.status not in ("in_training", "ready", "hired", "inactive", "promoted"):
            raise HTTPException(status_code=400, detail="Invalid status")
        updates.append(f"status = ${idx}")
        params.append(req.status)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append(f"updated_at = ${idx}")
    params.append(datetime.now(timezone.utc))
    idx += 1
    params.append(newbie_id)

    async with pool.acquire() as conn:
        result = await conn.execute(
            f"UPDATE newbies SET {', '.join(updates)} WHERE newbie_id = ${idx}",
            *params,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Newbie not found")
        row = await conn.fetchrow(
            "SELECT * FROM newbies WHERE newbie_id = $1", newbie_id
        )

    return _row_to_dict(row)
