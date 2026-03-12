"""
DirectChatEngine: Lightweight 1:1 chat with hired agents.

Platform Spec v1.1 — Direct Chat Feature.
No job records, no approval gates, no lessons store.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from anthropic import Anthropic
from app.database import get_db
from app.services.job_pipeline import CLAUDE_MODEL
from app.services.training import generate_embedding

logger = logging.getLogger(__name__)

# Spec §5.1
SOFT_TOKEN_LIMIT = 10_000
HARD_BLOCK_LIMIT = 20_000
MAX_HISTORY = 20
TOP_K_KNOWLEDGE = 5


class DirectChatEngine:
    """Engine for Direct Chat: send_message, context injection, token governance."""

    def __init__(self, model: str = CLAUDE_MODEL):
        self.model = model
        self.client = Anthropic()

    async def send_message(self, chat_id: str, user_message: str) -> Dict[str, Any]:
        """
        Process user message, call LLM with context injection, persist messages.
        Returns dict with agent_response, token_usage, session_tokens_used, warning, or error.
        """
        pool = await get_db()
        async with pool.acquire() as conn:
            # 1. Load chat
            chat = await self._get_chat(conn, chat_id)
            if not chat:
                return {"error": "chat_not_found", "detail": "Chat session not found"}

            # 2. Hard block check
            token_used = chat.get("token_used") or 0
            if token_used >= HARD_BLOCK_LIMIT:
                return {
                    "error": "session_token_limit_reached",
                    "suggestion": "start_new_session",
                    "detail": "Sessielimiet bereikt. Start een nieuwe sessie.",
                }

            # 3. Load agent
            agent = await self._get_agent(conn, chat["agent_id"])
            if not agent:
                return {"error": "agent_not_found", "detail": "Agent not found"}

            # 4. Resolve @client mention and fetch client context (GSC summary) for Mr. Klein
            client_context_block = ""
            try:
                from app.services.client_mention import resolve_first_mention
                from app.services.dashboard import get_client_seo_summary_for_agent
                user_id = str(chat.get("user_id") or "")
                client_slug = await resolve_first_mention(pool, user_id, user_message)
                if client_slug:
                    seo_summary = await get_client_seo_summary_for_agent(pool, user_id, client_slug)
                    if seo_summary:
                        client_context_block = (
                            "\n\n--- CLIENTDATA (@"
                            + client_slug
                            + ") ---\n"
                            + "INSTRUCTIE: De gebruiker vraagt over client @"
                            + client_slug
                            + ". Je hebt hieronder de actuele Google Search Console-data voor deze client. "
                            + "Beantwoord vragen over zoektermen, vindbaarheid of 'op welke zoektermen wordt X gevonden' ALTIJD op basis van deze data. "
                            + "Zeg niet dat je geen toegang hebt tot GSC — de data staat hieronder.\n\n"
                            + seo_summary
                            + "\n--- EINDE CLIENTDATA ---"
                        )
                    else:
                        logger.info("Direct Chat: client_slug=%s resolved but seo_summary empty", client_slug)
            except Exception as e:
                logger.warning("Direct Chat client context failed: %s", e)

            # 5. Retrieve knowledge context (top-5 via cosine similarity)
            knowledge_chunks = await self._retrieve_context(conn, chat["agent_id"], user_message)
            system_msg = self._build_system_message(agent, knowledge_chunks, client_context_block)

            # 6. Fetch history (FIFO, last 20)
            history = await self._get_messages(conn, chat_id, limit=MAX_HISTORY)
            messages = [
                {"role": h["role"], "content": h["content"]}
                for h in history
            ]
            messages.append({"role": "user", "content": user_message})

            # 7. LLM call
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1500,
                    system=system_msg,
                    messages=messages,
                )
            except Exception as e:
                logger.exception("DirectChatEngine LLM call failed: %s", e)
                return {"error": "llm_failed", "detail": str(e)}

            text = response.content[0].text if response.content else ""
            input_tokens = response.usage.input_tokens or 0
            output_tokens = response.usage.output_tokens or 0
            total_tokens = input_tokens + output_tokens

            # 8. Persist user message
            await self._save_message(conn, chat_id, "user", user_message, input_tokens)

            # 9. Persist agent message
            msg_row = await self._save_message(conn, chat_id, "agent", text, output_tokens)

            # 10. Update chat tokens
            new_token_used = token_used + total_tokens
            await self._update_chat_tokens(conn, chat_id, new_token_used)

            # 11. Auto-title on first response
            if (chat.get("message_count") or 0) == 0:
                title = self._generate_title(user_message)
                await conn.execute(
                    "UPDATE direct_chats SET title = $1 WHERE chat_id = $2",
                    title,
                    chat_id,
                )

            # 12. Warning check
            warning = None
            if new_token_used >= SOFT_TOKEN_LIMIT * 0.8:
                pct = int(new_token_used / SOFT_TOKEN_LIMIT * 100)
                warning = f"Sessie op {pct}% van soft limit"

            return {
                "chat_id": chat_id,
                "message_id": msg_row["message_id"],
                "agent_response": text,
                "token_usage": total_tokens,
                "session_tokens_used": new_token_used,
                "soft_limit": SOFT_TOKEN_LIMIT,
                "warning": warning,
            }

    def _build_system_message(
        self,
        agent: Dict[str, Any],
        knowledge_chunks: List[str],
        client_context_block: str = "",
    ) -> str:
        """Build system message per spec §2.2 — agent identity from system_prompt + context."""
        system_prompt = agent.get("system_prompt") or agent.get("system_instructions") or ""
        name = agent.get("name") or agent.get("agent_name") or "Agent"
        role = agent.get("role") or ""
        goal = agent.get("goal") or ""
        tool_whitelist = agent.get("tool_access_whitelist") or agent.get("tool_whitelist") or []
        if isinstance(tool_whitelist, str):
            try:
                tool_whitelist = json.loads(tool_whitelist) if tool_whitelist else []
            except json.JSONDecodeError:
                tool_whitelist = []
        tools_str = ", ".join(str(t) for t in tool_whitelist) if tool_whitelist else "geen"

        knowledge_block = ""
        if knowledge_chunks:
            knowledge_block = "\n\nRelevante kenniscontext (gebruik indien van toepassing):\n" + "\n\n".join(
                f"- {chunk}" for chunk in knowledge_chunks
            )

        # Spec §2.1: system_prompt = volledige persoonlijkheid; role+goal = toegevoegde context
        base = system_prompt.strip() if system_prompt else f"Je bent {name} — {role}."
        return f"""{base}

Rol: {role} | Doel binnen de crew: {goal}
{knowledge_block}{client_context_block}

Beschikbare tools: {tools_str}

Je beantwoordt vragen als een gesprekspartner, niet als een formele Worker.
Geen response contract vereist. Wees direct, behulpzaam en authentiek."""

    async def _retrieve_context(
        self, conn, agent_id: str, query: str, top_k: int = TOP_K_KNOWLEDGE
    ) -> List[str]:
        """Top-k knowledge chunks via cosine similarity on agent_knowledge."""
        try:
            embedding = await generate_embedding(query)
        except Exception as e:
            logger.warning("Embedding failed for Direct Chat context: %s", e)
            return []

        try:
            rows = await conn.fetch(
                """
                SELECT chunk_text FROM agent_knowledge
                WHERE agent_id = $1 AND is_active = true AND embedding IS NOT NULL
                ORDER BY embedding <=> $2::vector
                LIMIT $3
                """,
                agent_id,
                json.dumps(embedding),
                top_k,
            )
            return [r["chunk_text"] for r in rows]
        except Exception as e:
            logger.warning("Knowledge retrieval failed: %s", e)
            return []

    def _generate_title(self, first_message: str) -> str:
        """Auto-title from first user message — truncate to ~60 chars."""
        if not first_message or not isinstance(first_message, str):
            return "Direct Chat"
        cleaned = first_message.strip()[:60]
        return cleaned + "…" if len(first_message.strip()) > 60 else cleaned

    async def _get_chat(self, conn, chat_id: str) -> Optional[Dict[str, Any]]:
        row = await conn.fetchrow(
            "SELECT * FROM direct_chats WHERE chat_id = $1", chat_id
        )
        return dict(row) if row else None

    async def _get_agent(self, conn, agent_id: str) -> Optional[Dict[str, Any]]:
        row = await conn.fetchrow(
            """
            SELECT agent_id, name, role, goal, system_prompt, system_instructions,
                   tool_access_whitelist
            FROM hired_agents
            WHERE agent_id = $1
            """,
            agent_id,
        )
        return dict(row) if row else None

    async def _get_messages(
        self, conn, chat_id: str, limit: int = MAX_HISTORY
    ) -> List[Dict[str, Any]]:
        rows = await conn.fetch(
            """
            SELECT message_id, role, content, created_at
            FROM direct_chat_messages
            WHERE chat_id = $1
            ORDER BY message_id ASC
            """,
            chat_id,
        )
        # FIFO trim: take last N
        trimmed = list(rows)[-limit:] if len(rows) > limit else list(rows)
        return [dict(r) for r in trimmed]

    async def _save_message(
        self, conn, chat_id: str, role: str, content: str, token_usage: int = 0
    ) -> Dict[str, Any]:
        row = await conn.fetchrow(
            """
            INSERT INTO direct_chat_messages (chat_id, role, content, token_usage)
            VALUES ($1, $2, $3, $4)
            RETURNING message_id, role, content, created_at
            """,
            chat_id,
            role,
            content,
            token_usage,
        )
        await conn.execute(
            """
            UPDATE direct_chats
            SET last_message_at = now(), message_count = message_count + 1
            WHERE chat_id = $1
            """,
            chat_id,
        )
        return dict(row)

    async def _update_chat_tokens(self, conn, chat_id: str, token_used: int) -> None:
        await conn.execute(
            "UPDATE direct_chats SET token_used = $1, last_message_at = now() WHERE chat_id = $2",
            token_used,
            chat_id,
        )
