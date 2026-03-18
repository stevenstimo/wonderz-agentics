#!/usr/bin/env python3
"""
Seed 49 personas into hired_agents (Fase 4a) and development_points (Fase 4b).
Framework: docs/260317_crew_intelligent_agent_framework.md sectie 10 + 5.
Run: python scripts/seed_49_personas.py (requires DATABASE_URL).
Agents are created with is_active = false.
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.data.persona_roster import get_persona_roster
from app.data.role_templates import get_role_template


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "agent"


async def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    try:
        import asyncpg
    except ImportError:
        print("asyncpg required: pip install asyncpg", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(database_url)
    roster = get_persona_roster()
    now = datetime.now(timezone.utc)
    seen_slugs = {}
    inserted_agents = []
    agent_ids = []

    # Resolve columns
    cols = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'hired_agents' ORDER BY ordinal_position"
    )
    ha_cols = {r["column_name"] for r in cols}

    for name, badge, score, dev_priority, agent_type, role_key in roster:
        template = get_role_template(role_key)
        if not template:
            print(f"Skip {name}: no template for role_key={role_key}", file=sys.stderr)
            continue
        base_slug = slug(name)
        idx = seen_slugs.get(base_slug, 0)
        seen_slugs[base_slug] = idx + 1
        agent_id = f"agent:{agent_type}:{base_slug}-{idx:03d}" if idx else f"agent:{agent_type}:{base_slug}"
        existing = await conn.fetchrow("SELECT 1 FROM hired_agents WHERE agent_id = $1", agent_id)
        if existing:
            print(f"Skip {agent_id}: already exists")
            agent_ids.append(agent_id)
            continue

        goal = f"Persona {name} — {badge}. Ontwikkelpunt: {dev_priority}"
        system_prompt = f"Je bent {name}, een {badge} binnen Crew Intelligent. Je werkt conform je rol en de gedefinieerde guardrails."
        persona_source = f"{base_slug}-{idx:03d}" if idx else base_slug

        insert_cols = [
            "agent_id", "name", "type", "role", "goal", "system_prompt",
            "tool_whitelist", "knowledge_sources", "output_format", "guardrails", "model_config",
            "skills", "persona_source", "readiness_score", "is_active", "is_suspended",
            "created_at", "updated_at",
        ]
        insert_cols = [c for c in insert_cols if c in ha_cols]
        placeholders = ", ".join(f"${i+1}" for i in range(len(insert_cols)))
        names = ", ".join(insert_cols)
        values = [
            agent_id, name, agent_type, template["role"], goal, system_prompt,
            template.get("tool_whitelist") or [],
            [],
            json.dumps(template.get("output_format") or {}),
            json.dumps(template.get("guardrails") or {}),
            json.dumps(template.get("model_config") or {}),
            json.dumps(template.get("skills") or []),
            persona_source,
            score,
            False,
            False,
            now,
            now,
        ]
        value_map = dict(zip([
            "agent_id", "name", "type", "role", "goal", "system_prompt",
            "tool_whitelist", "knowledge_sources", "output_format", "guardrails", "model_config",
            "skills", "persona_source", "readiness_score", "is_active", "is_suspended",
            "created_at", "updated_at",
        ], values))
        values_ordered = [value_map[c] for c in insert_cols]
        await conn.execute(
            f"INSERT INTO hired_agents ({names}) VALUES ({placeholders})",
            *values_ordered,
        )
        inserted_agents.append((agent_id, name, dev_priority))
        agent_ids.append(agent_id)
        print(f"Inserted {agent_id} ({name})")

    # Fase 4b: development_points (3 per agent from development priority)
    dp_cols = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'development_points' ORDER BY ordinal_position"
    )
    dp_col_set = {r["column_name"] for r in dp_cols}
    for agent_id, name, dev_priority in inserted_agents:
        # Derive 3 patterns from development_priority (split by "&" or ", " or use same 3x with prefix)
        parts = re.split(r"\s+&\s+|\s*,\s*", dev_priority.strip())
        patterns = [p.strip() for p in parts if p.strip()]
        if len(patterns) < 3:
            patterns = [dev_priority] * 3
        else:
            patterns = patterns[:3]
        for i, pattern in enumerate(patterns):
            if not pattern:
                pattern = dev_priority
            safe_agent = agent_id.replace(":", "-")
            point_id = f"DP-2026-03-{safe_agent}-{i+1}"[:50]
            if "point_id" in dp_col_set and "agent_id" in dp_col_set and "issue_description" in dp_col_set:
                await conn.execute(
                    """
                    INSERT INTO development_points (point_id, agent_id, issue_description, impact, status, frequency)
                    VALUES ($1, $2, $3, 'low', 'OPEN', 1)
                    ON CONFLICT (point_id) DO NOTHING
                    """,
                    point_id,
                    agent_id,
                    pattern[:500],
                )
            elif "agent_id" in dp_col_set and "pattern" in dp_col_set:
                await conn.execute(
                    """
                    INSERT INTO development_points (agent_id, pattern, impact, status)
                    VALUES ($1, $2, 'low', 'open')
                    """,
                    agent_id,
                    pattern[:500],
                )
            else:
                print(f"development_points schema not matched; skip points for {agent_id}", file=sys.stderr)
                break
        print(f"Development points for {agent_id}")

    await conn.close()
    print(f"Done. Inserted {len(inserted_agents)} agents, {len(agent_ids)} total in roster.")


if __name__ == "__main__":
    asyncio.run(main())
