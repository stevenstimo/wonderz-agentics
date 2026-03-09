#!/usr/bin/env python3
"""
One-off cleanup: deactivate old The Dude test agent + log system_prompt of The Dude #1.
Run: python scripts/cleanup_hired_agents.py
"""
import asyncio
import os
import sys

# Load .env for DATABASE_URL
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

async def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("❌ DATABASE_URL not set")
        sys.exit(1)

    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg not found. pip install asyncpg")
        sys.exit(1)

    conn = await asyncpg.connect(url)

    # TAAK 1: Deactiveer oude "The Dude" agent
    result = await conn.execute(
        "UPDATE hired_agents SET is_active = false WHERE name = 'The Dude' AND role = 'New'"
    )
    print(f"TAAK 1: {result}")

    # TAAK 2: Log system_prompt van The Dude #1
    row = await conn.fetchrow(
        "SELECT name, system_prompt FROM hired_agents WHERE name = 'The Dude #1'"
    )
    if row:
        print("\nTAAK 2 — The Dude #1 system_prompt (voor kwaliteitsbeoordeling):")
        print("-" * 60)
        print(row["system_prompt"] or "(leeg)")
        print("-" * 60)
    else:
        print("\nTAAK 2: Geen agent gevonden met name = 'The Dude #1'")

    await conn.close()
    print("\n✅ Cleanup voltooid")


if __name__ == "__main__":
    asyncio.run(main())
