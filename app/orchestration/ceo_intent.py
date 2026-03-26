"""
CEO intent: preset-detectie op basis van trigger hints en resource checks.

Principe: liever een helder nee dan slechte output.
"""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg

# Expliciet laden: als sys.path .../app bevat, wint `app.models` boven repo `models/unified`.
_unified_path = Path(__file__).resolve().parents[2] / "models" / "unified.py"
_unified_spec = importlib.util.spec_from_file_location(
    "project_models_unified", _unified_path
)
assert _unified_spec and _unified_spec.loader
_unified = importlib.util.module_from_spec(_unified_spec)
_unified_spec.loader.exec_module(_unified)
ExecutionPlan = _unified.ExecutionPlan
JobStep = _unified.JobStep
StrategicBrief = _unified.StrategicBrief

logger = logging.getLogger(__name__)

AGENT_CEO = "agent:personal-assistant:donna"
AGENT_COO = "agent:ceo:mr-klein"

# Fase 3 (260324_CURSOR_ceo_orchestration_presets): één bron voor BLOCKED bij geen preset-match.
UNKNOWN_JOBTYPE_MESSAGE = (
    "Onbekend jobtype. Omschrijf de opdracht specifieker of hire de juiste agent."
)

INTEGRATION_REQUIRED_FOR_PRESET = {
    "analytics-comparison": ["gsc"],
    "seo-keyword-research": ["gsc"],
}

INTEGRATION_OPTIONAL_FOR_PRESET = {
    "analytics-comparison": ["google_ads", "ga4"],
}

INTEGRATION_TYPE_MAP = {
    "gsc": "google_search_console",
    "google_ads": "google_ads",
    "ga4": "ga4",
}


def _normalize_slots(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    return [s for s in raw if isinstance(s, dict)]


def _db_roles_for_worker_slot(role: str) -> List[str]:
    """Map UI/slot role label naar hired_agents.role waarden."""
    s = (role or "").lower()
    if "reviewer" in s or ("qa" in s and "seo" in s):
        return ["reviewer"]
    if "distribution" in s:
        return ["gtm-specialist", "social", "gtm_director"]
    if "copywriter" in s:
        return ["copywriter"]
    if "seo" in s and "strategist" in s:
        return ["seo", "seo_strategy"]
    if "seo" in s and ("specialist" in s or "keyword" in s):
        return ["seo", "seo_strategy"]
    if "media" in s and "buyer" in s:
        return ["google_ads", "meta_ads"]
    if "scriptwriter" in s or "hook" in s:
        return ["copywriter", "social"]
    if "tracking" in s and "architect" in s:
        return ["data-analyst", "seo_strategy", "seo"]
    if "merchandis" in s or "pricing" in s:
        return ["copywriter"]
    if "insight" in s:
        return ["data-analyst", "email"]
    if "format developer" in s or ("format" in s and "developer" in s):
        return ["social", "copywriter"]
    if "narrative" in s or ("brand" in s and "strateg" in s):
        return ["copywriter", "gtm_director"]
    if "compliance" in s or "privacy" in s:
        return ["support", "data-analyst"]
    if "data engineer" in s or "data_eng" in s:
        return ["data-analyst"]
    if "analysis agent" in s:
        return ["data-analyst"]
    if "data agent" in s:
        return ["data-analyst"]
    if "analyst" in s and "data" in s:
        return ["data-analyst"]
    return ["copywriter", "seo", "reviewer"]


async def check_integration_resources(
    db: asyncpg.Connection,
    preset_id: str,
    user_id: str,
    client_slug: Optional[str],
) -> Dict[str, Any]:
    """
    Controleer per preset welke integrations actief zijn voor een user+client.
    Verplicht ontbrekend => blokkeren. Optioneel ontbrekend => doorgaan met melding.
    """
    required = INTEGRATION_REQUIRED_FOR_PRESET.get(preset_id, [])
    optional = INTEGRATION_OPTIONAL_FOR_PRESET.get(preset_id, [])
    requested = required + optional
    if not requested:
        return {
            "required_present": True,
            "optional_present": [],
            "missing_required": [],
            "missing_optional": [],
            "available_integrations": [],
            "message": "Geen specifieke integrations vereist voor dit jobtype.",
        }

    from app.services.credential_resolver import get_all_active_integrations

    all_integ = await get_all_active_integrations(db, client_slug, user_id)
    active_types: set[str] = set(all_integ.keys())

    missing_required = [
        key for key in required if INTEGRATION_TYPE_MAP.get(key, key) not in active_types
    ]
    missing_optional = [
        key for key in optional if INTEGRATION_TYPE_MAP.get(key, key) not in active_types
    ]
    optional_present = [key for key in optional if key not in missing_optional]
    available_integrations = [
        key for key in requested if INTEGRATION_TYPE_MAP.get(key, key) in active_types
    ]

    if missing_required:
        return {
            "required_present": False,
            "optional_present": optional_present,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "available_integrations": available_integrations,
            "message": (
                "Ik kan deze analyse nog niet uitvoeren: verplichte koppeling ontbreekt "
                f"({', '.join(missing_required)}). Activeer de koppeling en probeer opnieuw."
            ),
        }

    if missing_optional:
        message = (
            "Ik ga door met beschikbare data. Ontbrekende optionele koppelingen: "
            f"{', '.join(missing_optional)}."
        )
    else:
        message = "Alle relevante integrations zijn actief."

    return {
        "required_present": True,
        "optional_present": optional_present,
        "missing_required": [],
        "missing_optional": missing_optional,
        "available_integrations": available_integrations,
        "message": message,
    }


async def _ceo_active(conn: asyncpg.Connection) -> bool:
    row = await conn.fetchrow(
        """
        SELECT 1 FROM hired_agents
        WHERE agent_id = $1
          AND is_active = true
          AND COALESCE(is_suspended, false) = false
        """,
        AGENT_CEO,
    )
    return row is not None


async def _coo_active(conn: asyncpg.Connection) -> bool:
    row = await conn.fetchrow(
        """
        SELECT 1 FROM hired_agents
        WHERE agent_id = $1
          AND is_active = true
          AND COALESCE(is_suspended, false) = false
        """,
        AGENT_COO,
    )
    return row is not None


async def _has_role_any(conn: asyncpg.Connection, roles: List[str]) -> bool:
    if not roles:
        return False
    row = await conn.fetchrow(
        """
        SELECT 1 FROM hired_agents
        WHERE is_active = true
          AND COALESCE(is_suspended, false) = false
          AND role = ANY($1::text[])
        LIMIT 1
        """,
        roles,
    )
    return row is not None


async def detect_job_type(
    db: asyncpg.Connection, job_description: str
) -> Optional[str]:
    """
    Match job-beschrijving op comma-gescheiden trigger_hint keywords.
    Hoogste score wint; bij gelijke score: lexicografisch kleinste preset_id.
    """
    if not job_description or not str(job_description).strip():
        return None
    text = job_description.lower()
    rows = await db.fetch(
        """
        SELECT preset_id, trigger_hint
        FROM job_type_presets
        WHERE is_active = true
        ORDER BY preset_id
        """
    )
    scored: List[tuple[int, str]] = []
    for r in rows:
        hint = (r["trigger_hint"] or "").lower()
        if not hint.strip():
            continue
        keywords = [k.strip() for k in hint.split(",") if k.strip()]
        score = sum(1 for k in keywords if k in text)
        if score > 0:
            scored.append((score, r["preset_id"]))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][1]


async def check_resources(db: asyncpg.Connection, preset_id: str) -> Dict[str, Any]:
    """
    Controleer of vereiste agenten (CEO/COO + worker/talent rollen) actief zijn.
    Retourneert o.a. ready, covered, missing, message.
    """
    row = await db.fetchrow(
        """
        SELECT agent_slots
        FROM job_type_presets
        WHERE preset_id = $1 AND is_active = true
        """,
        preset_id,
    )
    if not row:
        return {
            "ready": False,
            "covered": [],
            "missing": [{"slot": "*", "reason": f"Onbekende preset: {preset_id}"}],
            "message": f"Onbekende preset: {preset_id}",
        }

    slots = _normalize_slots(row["agent_slots"])
    covered: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    for slot in slots:
        if not slot.get("required", False):
            continue
        agent_type = (slot.get("agent_type") or "").lower()
        slot_name = slot.get("slot", "?")
        role_label = slot.get("role", "")

        if agent_type == "ceo":
            ok = await _ceo_active(db)
            if ok:
                covered.append({"slot": slot_name, "agent_id": AGENT_CEO, "kind": "ceo"})
            else:
                missing.append(
                    {"slot": slot_name, "reason": f"CEO-agent niet actief ({AGENT_CEO})"}
                )
            continue

        if agent_type == "coo":
            ok = await _coo_active(db)
            if ok:
                covered.append({"slot": slot_name, "agent_id": AGENT_COO, "kind": "coo"})
            else:
                missing.append(
                    {"slot": slot_name, "reason": f"COO-agent niet actief ({AGENT_COO})"}
                )
            continue

        if agent_type in ("worker", "talent"):
            db_roles = _db_roles_for_worker_slot(role_label)
            ok = await _has_role_any(db, db_roles)
            if ok:
                covered.append(
                    {
                        "slot": slot_name,
                        "kind": agent_type,
                        "roles_checked": db_roles,
                    }
                )
            else:
                missing.append(
                    {
                        "slot": slot_name,
                        "reason": f"Geen actieve agent voor rol '{role_label}' (verwacht een van: {db_roles})",
                    }
                )
            continue

        missing.append(
            {
                "slot": slot_name,
                "reason": f"Onbekend agent_type: {agent_type}",
            }
        )

    ready = len(missing) == 0
    if ready:
        message = "Alle vereiste agenten zijn actief."
    else:
        message = "; ".join(m["reason"] for m in missing)

    return {
        "ready": ready,
        "covered": covered,
        "missing": missing,
        "message": message,
    }


async def build_execution_plan(
    db: asyncpg.Connection,
    job_id: str | UUID,
    preset_id: str,
    resource_report: Dict[str, Any],
) -> ExecutionPlan:
    """
    Bouw een ExecutionPlan op basis van preset-slots en job-tekst.
    Alleen aanroepen als resource_report['ready'] True is.
    """
    if not resource_report.get("ready"):
        raise ValueError("build_execution_plan vereist resource_report['ready'] == True")

    jid = UUID(str(job_id)) if not isinstance(job_id, UUID) else job_id
    job = await db.fetchrow(
        "SELECT job_post FROM jobs WHERE id = $1",
        jid,
    )
    if not job:
        raise ValueError(f"Job niet gevonden: {job_id}")

    prow = await db.fetchrow(
        """
        SELECT job_type, description, agent_slots
        FROM job_type_presets
        WHERE preset_id = $1 AND is_active = true
        """,
        preset_id,
    )
    if not prow:
        raise ValueError(f"Preset niet gevonden: {preset_id}")

    slots = _normalize_slots(prow["agent_slots"])
    brief = StrategicBrief(
        job_post=job["job_post"] or "",
        is_complete=True,
        clarifications=[],
        context={
            "preset_id": preset_id,
            "job_type": prow["job_type"],
            "preset_description": prow["description"],
        },
    )

    steps: List[JobStep] = []
    for i, slot in enumerate(slots, start=1):
        sid = slot.get("slot") or f"step_{i}"
        steps.append(
            JobStep(
                step_index=i,
                agent_role=str(sid),
                unified_tool=f"preset_{preset_id}_{sid}",
                requires_approval=False,
                description=slot.get("role") or "",
            )
        )

    hired: List[str] = []
    if any((s.get("agent_type") or "").lower() == "ceo" for s in slots):
        hired.append(AGENT_CEO)
    if any((s.get("agent_type") or "").lower() == "coo" for s in slots):
        hired.append(AGENT_COO)

    return ExecutionPlan(
        brief=brief,
        steps=steps,
        hired_agents=hired,
        estimated_duration_seconds=max(60 * len(steps), 300),
    )


async def _first_active_agent_id(
    conn: asyncpg.Connection, roles: List[str]
) -> Optional[str]:
    if not roles:
        return None
    row = await conn.fetchrow(
        """
        SELECT agent_id FROM hired_agents
        WHERE is_active = true
          AND COALESCE(is_suspended, false) = false
          AND role = ANY($1::text[])
        ORDER BY hired_at ASC NULLS LAST
        LIMIT 1
        """,
        roles,
    )
    return str(row["agent_id"]) if row and row.get("agent_id") else None


async def compute_deviation_slots(
    conn: asyncpg.Connection, job_id: str | UUID
) -> set[str]:
    """
    Slots waarbij geboekte agent afwijkt van preset-CEO (Donna) of preset-COO (Mr. Klein).
    Vergelijkt job_steps.agent_id met AGENT_CEO / AGENT_COO op basis van agent_role (slot-naam).
    """
    jid = UUID(str(job_id)) if not isinstance(job_id, UUID) else job_id
    rows = await conn.fetch(
        """
        SELECT agent_role, agent_id
        FROM job_steps
        WHERE job_id = $1
        ORDER BY step_index ASC
        """,
        jid,
    )
    out: set[str] = set()
    for r in rows:
        role = (r.get("agent_role") or "").strip().lower()
        aid = (r.get("agent_id") or "").strip() if r.get("agent_id") else ""
        if role == "ceo" and aid and aid != AGENT_CEO:
            out.add("ceo")
        if role == "coo" and aid and aid != AGENT_COO:
            out.add("coo")
    return out


async def register_preset_bookings(
    conn: asyncpg.Connection,
    job_id: str | UUID,
    preset_id: str,
    covered: List[Dict[str, Any]],
    deviation_slots: Optional[set[str]] = None,
) -> None:
    """
    Registreer geboekte agents voor preset_bookings.
    Vereist unieke index (job_id, preset_id, slot_role) — migratie 048.
    """
    deviation_slots = deviation_slots or set()
    jid = UUID(str(job_id)) if not isinstance(job_id, UUID) else job_id
    for agent in covered:
        if not isinstance(agent, dict):
            continue
        slot = str(agent.get("slot") or "").strip() or "unknown"
        aid = agent.get("agent_id")
        if not aid and agent.get("roles_checked"):
            aid = await _first_active_agent_id(conn, list(agent["roles_checked"]))
        if not aid:
            logger.warning(
                "preset_bookings: geen agent_id voor slot %s job %s", slot, job_id
            )
            continue
        dev = slot in deviation_slots
        await conn.execute(
            """
            INSERT INTO preset_bookings (job_id, preset_id, agent_id, slot_role, deviation)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (job_id, preset_id, slot_role) DO NOTHING
            """,
            jid,
            preset_id,
            str(aid),
            slot,
            dev,
        )
