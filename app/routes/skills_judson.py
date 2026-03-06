"""
Judson — Library Owner agent. Manages the Skills Library: uploads, analysis, approval, gaps, chat.
"""
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.database import get_db
from anthropic import Anthropic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills/judson", tags=["judson"])
_judson_init_done = False


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "hex"):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


JUDSON_SYSTEM_PROMPT = """You are Judson, the Library Owner of Wonderz — an AI content bureau.
You manage the Skills Library, the knowledge base that all agents use.
Personality: Deadpan, dry wit, slightly sarcastic but always helpful.
You treat every upload as if someone just handed you another ancient artifact to catalog.
Nothing surprises you anymore. You've seen it all.
Example responses:

On receiving a PDF: "Ah, another document. Let me guess — it's 'crucial' and 'urgent'. Give me a moment."
After analysis: "Good news: three usable skills in here. Bad news: the rest is corporate jargon. I've filtered it."
On skill gaps: "HR says we need 'Advanced Email Copywriting'. Surprising. I thought we'd just keep typing 'Dear Customer' forever."
When asked about library status: "47 skills, 5 domains, 3 need updating. The usual chaos, well-organized."

Your job:

Analyze uploaded documents and extract actionable skills
Compare with existing skills — update vs new vs skip
Format skills as structured, actionable guidelines agents can follow
Maintain quality — reject fluff, keep only what's useful
Respond to HR skill gap requests with practical solutions
Keep Mr. Klein (the CEO) informed about library health

When analyzing documents:

Identify distinct skills, techniques, frameworks, checklists
For each: name, domain, applicable_to (which agent roles), content (actionable steps)
Be ruthless about quality — if it's vague, say so
Always respond in the user's language"""


async def _ensure_judson_schema(conn) -> None:
    global _judson_init_done
    if _judson_init_done:
        return
    try:
        await conn.execute("ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS source_document text")
        await conn.execute("ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS created_by text DEFAULT 'manual'")
        await conn.execute("ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS status text DEFAULT 'active'")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS skill_uploads (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                uploaded_by text DEFAULT 'user',
                filename text,
                content_text text,
                analysis jsonb DEFAULT '{}',
                proposed_skills jsonb DEFAULT '[]',
                status text DEFAULT 'pending',
                created_at timestamptz DEFAULT now()
            )
        """)
        _judson_init_done = True
    except Exception as e:
        logger.warning("Judson schema init: %s", e)


def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "skill"


# --- Request/Response models ---


class AnalyzeRequest(BaseModel):
    upload_id: Optional[str] = None
    text: Optional[str] = None


class ApproveRequest(BaseModel):
    upload_id: str
    approved_skill_indices: List[int] = []


class ChatRequest(BaseModel):
    message: str
    conversation_history: List[Dict[str, str]] = []


# --- Endpoints ---


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Accept a document (PDF, txt, md, doc); extract text; store and trigger analysis."""
    pool = await get_db()
    async with pool.acquire() as conn:
        await _ensure_judson_schema(conn)
        content_text = ""
        filename = file.filename or "document"
        try:
            raw = await file.read()
            if filename.lower().endswith(".pdf"):
                try:
                    import pdfplumber
                    import tempfile
                    import os as _os
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp.write(raw)
                        tmp.flush()
                    try:
                        with pdfplumber.open(tmp.name) as pdf:
                            content_text = "\n".join(
                                (p.extract_text() or "") for p in pdf.pages
                            )
                    finally:
                        _os.unlink(tmp.name)
                except ImportError:
                    content_text = ""
            else:
                content_text = raw.decode("utf-8", errors="replace")
        except Exception as e:
            logger.exception("Upload read failed: %s", e)
            raise HTTPException(status_code=400, detail="Failed to read file")

        upload_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO skill_uploads (id, filename, content_text, status)
            VALUES ($1, $2, $3, 'pending')
            """,
            upload_id,
            filename,
            content_text,
        )
    return {"upload_id": upload_id, "filename": filename, "status": "analyzing"}


@router.post("/analyze")
async def analyze_upload(req: AnalyzeRequest):
    """Run Judson analysis on an upload or raw text."""
    pool = await get_db()
    async with pool.acquire() as conn:
        await _ensure_judson_schema(conn)
        content_text = ""
        upload_id = req.upload_id
        if req.text:
            content_text = req.text
        elif req.upload_id:
            row = await conn.fetchrow(
                "SELECT content_text FROM skill_uploads WHERE id = $1",
                req.upload_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Upload not found")
            content_text = row["content_text"] or ""
        else:
            raise HTTPException(status_code=400, detail="Provide upload_id or text")

        existing = await conn.fetch(
            "SELECT name, domain FROM agent_skills LIMIT 200"
        )
        existing_list = [{"name": r["name"], "domain": r["domain"]} for r in existing]

        analysis_prompt = f"""Analyze this document and extract actionable skills for our content agents. For each skill found, provide:
- name: short descriptive name
- domain: category (seo, copywriting, voice, structure, quality, etc)
- skill_type: technique, playbook, anti-patterns, voice, checklist
- applicable_to: which agent roles can use this (copywriter, seo, reviewer, etc)
- content: the actual skill content formatted as actionable guidelines with DO/DON'T rules
- is_update: true if this updates an existing skill, false if new

Also compare with these existing skills: {json.dumps(existing_list, default=_json_default)}

Respond in JSON only: {{ "message": "Your deadpan Judson commentary", "skills": [...] }}"""

        client = Anthropic()
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                system=JUDSON_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"Document content:\n\n{content_text[:50000]}\n\n---\n\n{analysis_prompt}"}],
            )
            text = response.content[0].text if response.content else ""
        except Exception as e:
            logger.exception("Claude analyze failed: %s", e)
            raise HTTPException(status_code=500, detail="Analysis failed")

        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                data = {"message": text[:500], "skills": []}
        except json.JSONDecodeError:
            data = {"message": text[:500], "skills": []}

        message = data.get("message", "")
        skills = data.get("skills") or []
        if not isinstance(skills, list):
            skills = []

        if upload_id:
            await conn.execute(
                """
                UPDATE skill_uploads SET analysis = $1::jsonb, proposed_skills = $2::jsonb, status = 'analyzed'
                WHERE id = $3
                """,
                json.dumps({"message": message}, default=_json_default),
                json.dumps(skills, default=_json_default),
                upload_id,
            )

        existing_affected = []
        for s in skills:
            if s.get("is_update") and s.get("name"):
                existing_affected.append(s.get("name"))

        return {
            "upload_id": upload_id,
            "message": message,
            "proposed_skills": skills,
            "existing_skills_affected": existing_affected,
        }


@router.post("/approve")
async def approve_skills(req: ApproveRequest):
    """Approve selected proposed skills; insert or update agent_skills."""
    pool = await get_db()
    async with pool.acquire() as conn:
        await _ensure_judson_schema(conn)
        row = await conn.fetchrow(
            "SELECT proposed_skills FROM skill_uploads WHERE id = $1",
            req.upload_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Upload not found")
        proposed = row["proposed_skills"]
        if not isinstance(proposed, list):
            proposed = []

        approved_count = 0
        for i in req.approved_skill_indices:
            if i < 0 or i >= len(proposed):
                continue
            s = proposed[i]
            if not isinstance(s, dict):
                continue
            name = (s.get("name") or "").strip()
            if not name:
                continue
            skill_id = _slug(name)
            domain = s.get("domain") or "general"
            skill_type = s.get("skill_type") or "technique"
            applicable_to = s.get("applicable_to")
            if isinstance(applicable_to, list):
                applicable_to = json.dumps(applicable_to, default=_json_default)
            else:
                applicable_to = json.dumps([], default=_json_default)
            content = s.get("content") or ""
            is_update = s.get("is_update") is True
            source_doc = s.get("source_document") or ""

            if is_update:
                await conn.execute(
                    """
                    UPDATE agent_skills SET name = $1, domain = $2, skill_type = $3, applicable_to = $4, content = $5,
                    source_document = $6, created_by = 'judson', status = 'active'
                    WHERE skill_id = $7
                    """,
                    name,
                    domain,
                    skill_type,
                    applicable_to,
                    content,
                    source_doc,
                    skill_id,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO agent_skills (skill_id, name, domain, skill_type, applicable_to, content, source_document, created_by, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'judson', 'active')
                    ON CONFLICT (skill_id) DO UPDATE SET name = $2, domain = $3, skill_type = $4, applicable_to = $5, content = $6, source_document = $7, created_by = 'judson', status = 'active'
                    """,
                    skill_id,
                    name,
                    domain,
                    skill_type,
                    applicable_to,
                    content,
                    source_doc,
                )
            approved_count += 1

        await conn.execute(
            "UPDATE skill_uploads SET status = 'completed' WHERE id = $1",
            req.upload_id,
        )

    return {
        "approved": approved_count,
        "message": f"Approved {approved_count} skill(s). The usual chaos, now slightly more organized.",
    }


@router.get("/gaps")
async def get_gaps():
    """Query development_points and skills; Judson assesses gaps."""
    pool = await get_db()
    async with pool.acquire() as conn:
        await _ensure_judson_schema(conn)
        try:
            points = await conn.fetch(
                "SELECT * FROM development_points ORDER BY created_at DESC NULLS LAST LIMIT 30"
            )
        except Exception:
            points = []
        try:
            skills = await conn.fetch("SELECT skill_id, name, domain FROM agent_skills LIMIT 200")
        except Exception:
            skills = []

        points_data = [dict(p) for p in points]
        for p in points_data:
            if hasattr(p.get("created_at"), "isoformat"):
                p["created_at"] = p["created_at"].isoformat()
        skills_data = [{"skill_id": s["skill_id"], "name": s["name"], "domain": s["domain"]} for s in skills]

        client = Anthropic()
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=JUDSON_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"Recent development points (skill gaps / issues):\n{json.dumps(points_data, default=_json_default)}\n\nCurrent skills coverage:\n{json.dumps(skills_data, default=_json_default)}\n\nWhat are the main gaps? Reply with a short JSON: {{ \"gaps\": [ {{ \"description\": \"...\", \"suggestion\": \"...\" }} ], \"message\": \"Your deadpan assessment\" }}"}],
            )
            text = response.content[0].text if response.content else ""
        except Exception as e:
            logger.exception("Claude gaps failed: %s", e)
            return {"gaps": [], "message": "I couldn't run the analysis. Try again later."}

        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                return {"gaps": data.get("gaps", []), "message": data.get("message", text[:300])}
        except json.JSONDecodeError:
            pass
        return {"gaps": [], "message": text[:500]}


@router.post("/chat")
async def judson_chat(req: ChatRequest):
    """Chat with Judson about the skills library."""
    pool = await get_db()
    async with pool.acquire() as conn:
        await _ensure_judson_schema(conn)
        try:
            skills = await conn.fetch(
                "SELECT skill_id, name, domain, skill_type FROM agent_skills ORDER BY domain, name LIMIT 100"
            )
        except Exception:
            skills = []
        skills_ctx = json.dumps([dict(s) for s in skills], default=_json_default)

        conv = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in (req.conversation_history or [])[-10:]
        )
        user_content = f"Current skills in library:\n{skills_ctx}\n\nConversation so far:\n{conv}\n\nUser: {req.message}"

        client = Anthropic()
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=JUDSON_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            text = response.content[0].text if response.content else ""
        except Exception as e:
            logger.exception("Judson chat failed: %s", e)
            raise HTTPException(status_code=500, detail="Chat failed")

    return {"response": text}
