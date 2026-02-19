"""Copy Agent — writes text using OpenAI, incorporates reviewer feedback on retries."""
import re
import os
import json
import logging
import httpx
from typing import Any, Dict

logger = logging.getLogger(__name__)

KEYS_FILE = "/home/exedev/.config/wonderz-keys.json"
OPENAI_MODEL = "gpt-4o-mini"


def _get_openai_key() -> str:
    """Read key from wonderz-keys.json or env."""
    try:
        keys = json.load(open(KEYS_FILE))
        for k in keys:
            if k["name"] == "OPENAI_API_KEY" and k.get("value"):
                return k["value"]
    except Exception:
        pass
    return os.getenv("OPENAI_API_KEY", "")


def _extract_brief_fields(context: Dict[str, Any]) -> Dict[str, str]:
    base = context or {}
    payload_ctx = (base.get('payload') or {}) if isinstance(base.get('payload'), dict) else {}
    brief_context = ((base.get('brief') or payload_ctx.get('brief') or {}).get('context')) or {}
    return {
        'objective': str(brief_context.get('objective') or context.get('objective') or ''),
        'target_audience': str(brief_context.get('target_audience') or context.get('target_audience') or 'algemeen publiek'),
        'platform': str(brief_context.get('platform') or context.get('platform') or 'web'),
    }


async def _generate_with_openai(job_post: str, objective: str, target_audience: str,
                                 platform: str, reviewer_feedback: str = None,
                                 skill_context: str = "",
                                 base_system_prompt: str | None = None) -> dict:
    api_key = _get_openai_key()
    if not api_key:
        raise RuntimeError("OpenAI API key not found")

    # Extract word count and topic from job_post
    import re as _re
    m = _re.search(r'(\d+)\s*woord', job_post, _re.IGNORECASE)
    word_count = int(m.group(1)) if m else 400

    # Extract the actual topic — remove word count instructions
    topic = _re.sub(r'schrijf\s+(een\s+)?(tekst|artikel|blog|stuk)\s+(van\s+)?', '', job_post, flags=_re.IGNORECASE).strip()
    topic = _re.sub(r'\d+\s*woorden?\s*(over)?', '', topic, flags=_re.IGNORECASE).strip()
    topic = topic.strip(' .,;:-') or job_post  # fallback to full job_post

    if not base_system_prompt:
        base_system_prompt = (
            "Je bent een ervaren Nederlandse copywriter. "
            "Schrijf vloeiend, informatief Nederlands. "
            "De tekst moet VOLLEDIG en UITSLUITEND gaan over het opgegeven onderwerp. "
            "Schrijf GEEN generieke tekst over schrijven, marketing of communicatie. "
            "Schrijf specifieke, feitelijke informatie over het onderwerp. "
            "Gebruik alinea's. Geen opsommingen tenzij gevraagd. "
            "Schrijf EXACT het gevraagde aantal woorden (±10%). "
            "Lever ALLEEN de tekst, zonder titel, zonder uitleg."
        )

    # Enhance with loaded skills
    if skill_context:
        system_prompt = (
            f"{base_system_prompt}\n\n"
            f"# RELEVANT SKILLS FOR THIS TASK\n\n"
            f"{skill_context}\n\n"
            f"---\n\n"
            f"IMPORTANT: Follow the best practices, patterns, and anti-patterns outlined in the skills above. "
            f"Your output MUST align with these guidelines."
        )
    else:
        system_prompt = base_system_prompt

    user_prompt = (
        f"ONDERWERP: {topic}\n\n"
        f"Schrijf een informatieve Nederlandse tekst van {word_count} woorden over {topic}.\n"
        f"De HELE tekst moet gaan over {topic}. Geen enkele alinea mag off-topic zijn.\n"
    )
    if objective:
        user_prompt += f"Doel: {objective}\n"
    user_prompt += f"Doelgroep: {target_audience}\nPlatform: {platform}\n"

    if reviewer_feedback:
        user_prompt += (
            f"\n--- FEEDBACK VAN PROOFREADER ---\n"
            f"{reviewer_feedback}\n"
            f"--- EINDE FEEDBACK ---\n\n"
            f"Herschrijf de tekst volledig op basis van bovenstaande feedback. "
            f"Zorg dat ALLE genoemde problemen zijn opgelost.\n"
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    from app.utils.retry import async_retry

    @async_retry(max_attempts=3, backoff_seconds=2.0, exceptions=(httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout))
    async def _call_openai(msgs):
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": OPENAI_MODEL, "messages": msgs, "max_tokens": 2000, "temperature": 0.7},
            )
            resp.raise_for_status()
            return resp.json()

    data = await _call_openai(messages)

    text = data["choices"][0]["message"]["content"].strip()
    if not text:
        raise RuntimeError("OpenAI returned empty content")

    # Return text + usage for token tracking
    usage = data.get("usage", {})
    return {"text": text, "total_tokens": usage.get("total_tokens", 0)}


async def _load_skill_context(agent_id: str, context: Dict[str, Any]) -> tuple:
    """Load and select applicable skills for this task. Returns (skill_context_str, skill_ids)."""
    try:
        import app.db as _db
        pool = _db._pool
        if not pool or not agent_id:
            return "", []

        from app.services.skill_loader import SkillLoader
        loader = SkillLoader(pool)
        agent_skills = await loader.get_agent_skills(agent_id)
        if not agent_skills:
            return "", []

        # Determine applicable skills based on task context
        task_text = (context.get('job_post') or '').lower()
        platform = (context.get('platform') or '').lower()
        brief_ctx = ((context.get('brief') or {}).get('context')) or {}
        target_audience = str(brief_ctx.get('target_audience') or context.get('target_audience') or '').lower()

        applicable = []

        # SEO skill if website/blog
        if any(kw in platform for kw in ('website', 'blog', 'web')):
            seo = next((s for s in agent_skills if 'seo' in s['skill_id']), None)
            if seo:
                applicable.append(seo)

        # Voice skill based on audience
        if any(kw in target_audience for kw in ('b2b', 'professional', 'zakelijk')):
            voice = next((s for s in agent_skills if 'b2b-professional' in s['skill_id']), None)
            if voice:
                applicable.append(voice)
        elif any(kw in target_audience for kw in ('casual', 'consumer', 'jeugd', 'jong')):
            voice = next((s for s in agent_skills if 'casual' in s['skill_id']), None)
            if voice:
                applicable.append(voice)

        # Structure skill (always applicable)
        structure = next((s for s in agent_skills if 'structure' in s['skill_id']), None)
        if structure:
            applicable.append(structure)

        # Anti-patterns skill (always applicable)
        anti = next((s for s in agent_skills if 'anti-patterns' in s['skill_id']), None)
        if anti:
            applicable.append(anti)

        skill_context = loader.compose_skill_context(applicable)
        skill_ids = [s['skill_id'] for s in applicable]
        return skill_context, skill_ids

    except Exception as e:
        logger.debug('Skill loading skipped: %s', e)
        return "", []


async def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = payload.get('context') or {}
    job_id = payload.get('job_id', '')
    job_post = (
        context.get('job_post')
        or (context.get('payload') or {}).get('job_post')
        or payload.get('job_post')
        or 'Schrijf een sterke tekst.'
    )
    fields = _extract_brief_fields(context)

    # --- Load agent skills ---
    agent_config = payload.get('agent_config') or {}
    agent_id = agent_config.get('agent_id', '')
    skill_context, skill_ids_used = await _load_skill_context(agent_id, context)
    if skill_context:
        logger.info('copy_agent loaded %d skills for job %s', len(skill_ids_used), job_id)

    # --- Token guard: check budget before calling LLM ---
    try:
        if job_id:
            from app.services.token_guard import TokenGuard
            guard = TokenGuard()  # will use direct connection if no pool
            check = await guard.check_before_call(job_id, estimated_tokens=1500)
            if not check.get('allowed'):
                logger.warning('Token budget exceeded for job %s: %s', job_id, check)
                return {
                    'error': True,
                    'error_type': 'token_budget_exceeded',
                    'summary': f"Token budget exceeded: {check.get('reason')}",
                    'tokens_info': check,
                }
            if check.get('warning'):
                logger.info('Token budget warning for job %s: %.1f%%', job_id, check.get('percentage', 0))
    except Exception as e:
        logger.debug('TokenGuard check skipped: %s', e)

    # Check if there's reviewer feedback from a previous round
    reviewer_out = context.get('reviewer_agent') or {}
    reviewer_feedback = None
    if isinstance(reviewer_out, dict):
        fb = reviewer_out.get('feedback', '')
        status = reviewer_out.get('status', '')
        if status == 'NEEDS_CHANGES' and fb:
            reviewer_feedback = fb

    try:
        base_system_prompt = (
            agent_config.get('system_prompt')
            or agent_config.get('system_instructions')
        )
        result = await _generate_with_openai(
            job_post=job_post,
            objective=fields['objective'],
            target_audience=fields['target_audience'],
            platform=fields['platform'],
            reviewer_feedback=reviewer_feedback,
            skill_context=skill_context,
            base_system_prompt=base_system_prompt,
        )
    except Exception as e:
        logger.error('copy_agent LLM call failed for job %s: %s', job_id, e)
        return {
            'error': True,
            'error_type': 'api_error',
            'summary': f'LLM call failed: {str(e)[:200]}',
        }

    content = result['text']
    total_tokens = result.get('total_tokens', 0)

    # --- Token guard: register actual usage ---
    try:
        if job_id and total_tokens > 0:
            from app.services.token_guard import TokenGuard
            guard = TokenGuard()
            await guard.register_usage(job_id, total_tokens)
    except Exception as e:
        logger.debug('TokenGuard register skipped: %s', e)

    # --- Track skill usage ---
    if skill_ids_used and job_id:
        try:
            import app.db as _db
            pool = _db._pool
            if pool:
                from app.services.skill_loader import SkillLoader
                loader = SkillLoader(pool)
                await loader.record_skill_usage(job_id, agent_id, skill_ids_used)
                logger.info('Tracked %d skills for job %s', len(skill_ids_used), job_id)
        except Exception as e:
            logger.debug('Skill tracking skipped: %s', e)

    word_count = len(content.split())
    summary = content[:120]

    return {
        'status': 'DRAFT_READY',
        'content': content,
        'summary': summary,
        'word_count': word_count,
        'tokens_used': total_tokens,
        'data': {
            'draft_text': content,
            'objective': fields['objective'],
            'target_audience': fields['target_audience'],
            'platform': fields['platform'],
            'model': OPENAI_MODEL,
            'had_reviewer_feedback': reviewer_feedback is not None,
            'tokens_used': total_tokens,
            'skills_used': skill_ids_used,
        },
        'artifacts': [
            {
                'name': 'copy_draft',
                'type': 'text',
                'proposed_data': {'text': content},
                'original_data': {},
                'review_feedback': None,
            }
        ],
    }
