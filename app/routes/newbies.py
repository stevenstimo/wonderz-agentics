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
    source_url: Optional[str] = Field(None, min_length=10)
    url: Optional[str] = Field(None, min_length=10)
    category: str = Field(..., pattern=r"^(management|creative|development|operations)$")

    @model_validator(mode="after")
    def require_url(self):
        if not (self.source_url or self.url):
            raise ValueError("Either source_url or url is required")
        return self

    def get_url(self) -> str:
        return (self.source_url or self.url or "").strip()


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


@router.post("/{newbie_id}/train", status_code=status.HTTP_201_CREATED)
async def train_newbie(newbie_id: str, req: TrainNewbieRequest):
    """Train a newbie with a URL. Scrapes content, assigns +10 to category (max 80/category). Prevents duplicate URL spam."""
    from app.services.training import scrape_url, extract_text, TrainingError

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM newbies WHERE newbie_id = $1", newbie_id)
        if not row:
            raise HTTPException(status_code=404, detail="Newbie not found")
        if row.get("status") == "hired":
            raise HTTPException(status_code=400, detail="Cannot train a hired newbie")

        url = req.get_url()
        # Prevent duplicate URL spam: same URL + category already trained?
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
        if len(text or "").strip() < 50:
            raise HTTPException(status_code=400, detail="Extracted text is too short (min 50 chars)")

        score_gained = SCORE_PER_TRAINING

        col = CATEGORY_TO_COLUMN.get(req.category)
        if not col:
            raise HTTPException(status_code=400, detail="Invalid category")

        await conn.execute(
            """
            INSERT INTO newbie_trainings (newbie_id, source_url, category, score_gained, status, completed_at)
            VALUES ($1, $2, $3, $4, 'completed', now())
            """,
            newbie_id,
            url,
            req.category,
            score_gained,
        )

        # Add to newbie's category score; cap at MAX_SCORE_PER_CATEGORY (80)
        await conn.execute(
            f"UPDATE newbies SET {col} = LEAST($1, COALESCE({col}, 0) + $2), updated_at = now() WHERE newbie_id = $3",
            MAX_SCORE_PER_CATEGORY,
            score_gained,
            newbie_id,
        )

        await _update_readiness_and_status(conn, newbie_id)
        row = await conn.fetchrow("SELECT * FROM newbies WHERE newbie_id = $1", newbie_id)

    logger.info("Trained newbie %s: +%s in %s, readiness=%s", newbie_id, score_gained, req.category, row.get("readiness_score"))
    return _row_to_dict(row)


SYSTEM_PROMPT_MODEL = "claude-3-haiku-20240307"


async def _generate_system_prompt_via_claude(
    newbie_name: str,
    persona: str,
    qualities: str,
    development: str,
    role: str,
) -> str:
    """Generate system_prompt via Claude API. Uses claude-3-haiku for speed + cost.
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
        if req.status not in ("in_training", "ready", "hired", "inactive"):
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
