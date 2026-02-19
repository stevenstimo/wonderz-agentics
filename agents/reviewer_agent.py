"""Reviewer Agent — proofreader that checks text quality using OpenAI."""
import json
import logging
import os
import httpx
from typing import Any, Dict

logger = logging.getLogger(__name__)

KEYS_FILE = "/home/exedev/.config/wonderz-keys.json"
OPENAI_MODEL = "gpt-4o-mini"


def _get_openai_key() -> str:
    try:
        keys = json.load(open(KEYS_FILE))
        for k in keys:
            if k["name"] == "OPENAI_API_KEY" and k.get("value"):
                return k["value"]
    except Exception:
        pass
    return os.getenv("OPENAI_API_KEY", "")


async def _review_with_openai(copy_text: str, job_post: str, objective: str, target_audience: str) -> Dict[str, str]:
    api_key = _get_openai_key()
    if not api_key:
        raise RuntimeError("OpenAI API key not found")

    # Extract expected word count
    import re
    m = re.search(r'(\d+)\s*woord', job_post, re.IGNORECASE)
    expected_words = int(m.group(1)) if m else 400
    actual_words = len(copy_text.split())

    system_prompt = (
        "Je bent een strenge Nederlandse proofreader/redacteur. "
        "Beoordeel de aangeleverde tekst op de volgende criteria:\n"
        "1. RELEVANTIE (BELANGRIJKST): Gaat de tekst écht over het gevraagde onderwerp? "
        "Als de tekst generiek is of NIET specifiek over het onderwerp gaat, is het ALTIJD NEEDS_CHANGES met score 1. "
        "Een tekst over 'schrijven' of 'communicatie' terwijl het onderwerp 'korfbal' is = NEEDS_CHANGES.\n"
        "2. WOORDENAANTAL: Bevat de tekst ongeveer het gevraagde aantal woorden (±15%)?\n"
        "3. TAALGEBRUIK: Correct Nederlands, geen spelfouten, vloeiende zinnen.\n"
        "4. STRUCTUUR: Goede alinea-indeling, logische opbouw.\n"
        "5. INHOUD: Feitelijk correct, informatief, specifiek (niet vaag of generiek).\n\n"
        "Antwoord ALLEEN met valid JSON:\n"
        '{"status": "APPROVED" of "NEEDS_CHANGES", "feedback": "uitgebreide feedback", "score": 1-10}\n\n'
        "Keur ALLEEN goed (APPROVED) als de tekst aan ALLE criteria voldoet. "
        "Wees streng maar eerlijk."
    )

    user_prompt = (
        f"OPDRACHT: {job_post}\n"
        f"Doel: {objective}\n"
        f"Doelgroep: {target_audience}\n"
        f"Verwacht aantal woorden: {expected_words}\n"
        f"Werkelijk aantal woorden: {actual_words}\n\n"
        f"TE BEOORDELEN TEKST:\n---\n{copy_text}\n---\n"
    )

    from app.utils.retry import async_retry

    @async_retry(max_attempts=3, backoff_seconds=2.0, exceptions=(httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout))
    async def _call_openai(msgs):
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": OPENAI_MODEL,
                    "messages": msgs,
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            return resp.json()

    data = await _call_openai([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])

    total_tokens = data.get("usage", {}).get("total_tokens", 0)
    raw = data["choices"][0]["message"]["content"].strip()

    # Parse JSON from response
    parsed = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end > start:
            try:
                parsed = json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass

    if not isinstance(parsed, dict):
        return {'status': 'NEEDS_CHANGES', 'feedback': f'Reviewer kon respons niet parsen: {raw[:200]}'}

    status = str(parsed.get('status', 'NEEDS_CHANGES')).upper()
    if status not in ('APPROVED', 'NEEDS_CHANGES'):
        status = 'NEEDS_CHANGES'
    feedback = str(parsed.get('feedback', 'Geen specifieke feedback.'))
    score = parsed.get('score', 0)
    try:
        score = int(score)
    except (ValueError, TypeError):
        score = 5

    # Auto-approve if score >= 7 (good enough quality)
    if score >= 7:
        status = 'APPROVED'

    return {'status': status, 'feedback': feedback, 'score': score, 'total_tokens': total_tokens}


async def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = payload.get('context') or {}
    job_id = payload.get('job_id', '')
    copy_out = context.get('copy_agent') or {}

    copy_text = (
        (copy_out.get('data') or {}).get('draft_text')
        or copy_out.get('content')
        or ''
    ).strip()

    if not copy_text:
        return {
            'status': 'NEEDS_CHANGES',
            'feedback': 'Geen draft gevonden vanuit copy_agent output.',
            'summary': 'Draft ontbreekt',
        }

    # --- Token guard: check budget ---
    try:
        if job_id:
            from app.services.token_guard import TokenGuard
            guard = TokenGuard()
            check = await guard.check_before_call(job_id, estimated_tokens=800)
            if not check.get('allowed'):
                logger.warning('Token budget exceeded for reviewer on job %s', job_id)
                return {
                    'error': True,
                    'error_type': 'token_budget_exceeded',
                    'summary': f"Token budget exceeded: {check.get('reason')}",
                    'status': 'NEEDS_CHANGES',
                    'feedback': 'Token budget exceeded — cannot review.',
                }
    except Exception as e:
        logger.debug('TokenGuard check skipped in reviewer: %s', e)

    job_post = (
        context.get('job_post')
        or (context.get('payload') or {}).get('job_post')
        or 'Onbekende opdracht'
    )
    brief_context = ((context.get('brief') or {}).get('context')) or {}
    objective = str(brief_context.get('objective') or context.get('objective') or '')
    target_audience = str(brief_context.get('target_audience') or context.get('target_audience') or 'algemeen publiek')

    try:
        verdict = await _review_with_openai(copy_text, job_post, objective, target_audience)
    except Exception as e:
        logger.error('reviewer_agent LLM call failed for job %s: %s', job_id, e)
        return {
            'error': True,
            'error_type': 'api_error',
            'summary': f'Reviewer LLM call failed: {str(e)[:200]}',
            'status': 'NEEDS_CHANGES',
            'feedback': f'Reviewer kon niet draaien: {str(e)[:100]}',
        }

    total_tokens = verdict.get('total_tokens', 0)

    # --- Token guard: register usage ---
    try:
        if job_id and total_tokens > 0:
            from app.services.token_guard import TokenGuard
            guard = TokenGuard()
            await guard.register_usage(job_id, total_tokens)
    except Exception as e:
        logger.debug('TokenGuard register skipped in reviewer: %s', e)

    return {
        'status': verdict['status'],
        'feedback': verdict['feedback'],
        'score': verdict.get('score', 0),
        'summary': f"Reviewer: {verdict['status']} (score: {verdict.get('score', '?')})",
        'tokens_used': total_tokens,
        'data': {
            'objective': objective,
            'target_audience': target_audience,
            'model': OPENAI_MODEL,
            'tokens_used': total_tokens,
        },
    }
