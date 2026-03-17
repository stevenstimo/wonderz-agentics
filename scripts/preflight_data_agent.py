#!/usr/bin/env python3
"""
Pre-flight voor Data Agent Fase 1.
Voert de spec SQL-checks uit en rapporteert de exacte kolomnamen van hired_agents.
Draai vanuit repo root met DATABASE_URL gezet (bijv. uit ~/.bashrc).
"""
import asyncio
import os
import sys

# Repo root op path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from app.db import init_db_pool

    pool = await init_db_pool()
    if not pool:
        print("BLOCKER: Database pool niet geïnitialiseerd. Zet DATABASE_URL.")
        sys.exit(1)

    print("=== Pre-flight Data Agent Fase 1 ===\n")

    async with pool.acquire() as conn:
        # 1. hired_agents tabel (bestaat + sample)
        print("--- 1. hired_agents (agent_id, role, is_active) LIMIT 10 ---")
        try:
            rows = await conn.fetch("""
                SELECT agent_id, role, is_active
                FROM hired_agents
                ORDER BY updated_at DESC
                LIMIT 10
            """)
            for r in rows:
                print(dict(r))
            if not rows:
                print("(geen rijen)")
        except Exception as e:
            print(f"FOUT: {e}")

        # 2. Exacte kolomnamen hired_agents (voor INSERT)
        print("\n--- 2. KOLOMMEN hired_agents (information_schema) ---")
        try:
            cols = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'hired_agents'
                ORDER BY ordinal_position
            """)
            for c in cols:
                print(f"  {c['column_name']}: {c['data_type']} (nullable={c['is_nullable']})")
        except Exception as e:
            print(f"FOUT: {e}")

        # 3. jobs tabel kolommen
        print("\n--- 3. jobs tabel kolommen ---")
        try:
            cols = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'jobs'
                ORDER BY ordinal_position
            """)
            for c in cols:
                print(f"  {c['column_name']}: {c['data_type']}")
        except Exception as e:
            print(f"FOUT: {e}")

        # 4. Actieve agents (tool_whitelist kolomnaam kan tool_access_whitelist zijn)
        print("\n--- 4. Actieve agents (agent_id, role, tools) ---")
        try:
            # Probeer tool_whitelist, anders tool_access_whitelist
            try:
                rows = await conn.fetch("""
                    SELECT agent_id, role, tool_whitelist
                    FROM hired_agents WHERE is_active = true
                """)
                for r in rows:
                    print(f"  {r['agent_id']}: role={r['role']}, tool_whitelist={r['tool_whitelist']}")
            except Exception:
                rows = await conn.fetch("""
                    SELECT agent_id, role, tool_access_whitelist
                    FROM hired_agents WHERE is_active = true
                """)
                for r in rows:
                    print(f"  {r['agent_id']}: role={r['role']}, tool_access_whitelist={r['tool_access_whitelist']}")
            if not rows:
                print("  (geen actieve agents)")
        except Exception as e:
            print(f"FOUT: {e}")

        # 5. job_steps kolommen
        print("\n--- 5. job_steps kolommen ---")
        try:
            cols = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'job_steps'
                ORDER BY ordinal_position
            """)
            for c in cols:
                print(f"  {c['column_name']}: {c['data_type']}")
        except Exception as e:
            print(f"FOUT: {e}")

    print("\n=== Einde pre-flight ===")


if __name__ == "__main__":
    asyncio.run(main())
