"""Skills API endpoints — manage the skills library."""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel

import app.db as _db
from app.services.skill_validator import SkillValidator

router = APIRouter(prefix="/api/skills", tags=["skills"])


class CreateSkillRequest(BaseModel):
    skill_id: str
    name: str
    domain: str
    skill_type: str
    applicable_to: List[str] = []
    content: str


class AssignSkillRequest(BaseModel):
    agent_id: str
    proficiency: str = "competent"


@router.get("")
async def list_skills(domain: Optional[str] = None):
    """Lijst van alle skills."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        if domain:
            skills = await conn.fetch("""
                SELECT * FROM agent_skills
                WHERE domain = $1
                ORDER BY success_rate DESC, name
            """, domain)
        else:
            skills = await conn.fetch("""
                SELECT * FROM agent_skills
                ORDER BY domain, name
            """)

    result = []
    for s in skills:
        d = dict(s)
        # Convert Decimal to float for JSON serialization
        if 'success_rate' in d and d['success_rate'] is not None:
            d['success_rate'] = float(d['success_rate'])
        # Convert datetime to isoformat
        for k in ('created_at', 'updated_at'):
            if k in d and d[k] is not None:
                d[k] = d[k].isoformat()
        result.append(d)

    return {"skills": result, "total": len(result)}


@router.get("/effectiveness")
async def get_skill_effectiveness(days: Optional[int] = 30):
    """Get A/B validation metrics for all skills."""
    if days is not None and days <= 0:
        raise HTTPException(status_code=400, detail="days must be positive")

    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    validator = SkillValidator(pool)
    results = await validator.get_all_skill_effectiveness(days or 30)

    return {
        "period_days": days or 30,
        "skills": results,
        "summary": {
            "total_skills": len(results),
            "effective_skills": len([s for s in results if s.get("effective")]),
            "top_performer": results[0] if results else None,
        },
    }


@router.get("/effectiveness/{skill_id:path}")
async def get_skill_effectiveness_detail(skill_id: str, days: Optional[int] = 30):
    """Get detailed effectiveness metrics for a single skill."""
    if days is not None and days <= 0:
        raise HTTPException(status_code=400, detail="days must be positive")

    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    validator = SkillValidator(pool)
    result = await validator.calculate_skill_effectiveness(skill_id, days or 30)
    return result


@router.get("/{skill_id:path}/agents")
async def get_skill_agents(skill_id: str):
    """Haal agents met deze skill op."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        agents = await conn.fetch("""
            SELECT
                a.agent_id,
                a.name,
                a.role,
                ass.proficiency,
                ass.assigned_at
            FROM agent_skill_assignments ass
            JOIN hired_agents a ON ass.agent_id = a.agent_id
            WHERE ass.skill_id = $1
            ORDER BY a.name
        """, skill_id)

    result = []
    for a in agents:
        d = dict(a)
        if 'assigned_at' in d and d['assigned_at'] is not None:
            d['assigned_at'] = d['assigned_at'].isoformat()
        result.append(d)

    return {"agents": result, "total": len(result)}


@router.get("/{skill_id:path}")
async def get_skill(skill_id: str):
    """Haal één skill op."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        skill = await conn.fetchrow("""
            SELECT * FROM agent_skills WHERE skill_id = $1
        """, skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    d = dict(skill)
    if 'success_rate' in d and d['success_rate'] is not None:
        d['success_rate'] = float(d['success_rate'])
    for k in ('created_at', 'updated_at'):
        if k in d and d[k] is not None:
            d[k] = d[k].isoformat()
    return d


@router.post("")
async def create_skill(req: CreateSkillRequest):
    """Maak een nieuwe skill aan."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT 1 FROM agent_skills WHERE skill_id = $1", req.skill_id
        )
        if existing:
            raise HTTPException(status_code=400, detail="Skill already exists")

        await conn.execute("""
            INSERT INTO agent_skills (skill_id, name, domain, skill_type, applicable_to, content)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, req.skill_id, req.name, req.domain, req.skill_type, req.applicable_to, req.content)

    return {"skill_id": req.skill_id, "status": "created"}


@router.post("/{skill_id:path}/assign")
async def assign_skill_to_agent(skill_id: str, req: AssignSkillRequest):
    """Wijs skill toe aan agent."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        exists = await conn.fetchrow("""
            SELECT 1 FROM agent_skill_assignments
            WHERE agent_id = $1 AND skill_id = $2
        """, req.agent_id, skill_id)

        if exists:
            raise HTTPException(status_code=400, detail="Agent already has this skill")

        await conn.execute("""
            INSERT INTO agent_skill_assignments (agent_id, skill_id, proficiency)
            VALUES ($1, $2, $3)
        """, req.agent_id, skill_id, req.proficiency)

    return {"agent_id": req.agent_id, "skill_id": skill_id, "status": "assigned"}


@router.delete("/{skill_id:path}/agents/{agent_id:path}")
async def remove_skill_from_agent(skill_id: str, agent_id: str):
    """Verwijder skill van agent."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM agent_skill_assignments
            WHERE agent_id = $1 AND skill_id = $2
        """, agent_id, skill_id)

    return {"agent_id": agent_id, "skill_id": skill_id, "status": "removed"}


@router.get("-usage/log")
async def get_skill_usage_log(limit: int = 50):
    """Haal recente skill usage logs op."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        logs = await conn.fetch("""
            SELECT
                l.log_id,
                l.job_id,
                l.agent_id,
                l.skill_id,
                s.name as skill_name,
                l.was_successful,
                l.feedback,
                l.logged_at
            FROM skill_usage_log l
            LEFT JOIN agent_skills s ON l.skill_id = s.skill_id
            ORDER BY l.logged_at DESC
            LIMIT $1
        """, limit)

    result = []
    for row in logs:
        d = dict(row)
        if 'logged_at' in d and d['logged_at'] is not None:
            d['logged_at'] = d['logged_at'].isoformat()
        result.append(d)

    return {"logs": result, "total": len(result)}
