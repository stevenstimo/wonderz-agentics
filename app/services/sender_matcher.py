"""
Email Intake Channel §4.3: Match from_address to user_id.
Exact match, case-insensitive. No fuzzy matching.
Uses existing DB pool: get_db() + pool.acquire() (assumption-based: spec said "db.fetchrow";
we use the codebase pattern of get_db + conn from app.database).
"""

from app.database import get_db


class SenderMatcher:
    """Maps sender email to user id from users table."""

    @staticmethod
    async def match(from_address: str) -> str | None:
        """Return user_id (str) if sender is known, None if unknown."""
        if not (from_address or from_address.strip()):
            return None
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM users WHERE LOWER(email) = LOWER($1)",
                from_address.strip(),
            )
        return str(row["id"]) if row else None
