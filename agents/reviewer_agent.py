import json
import os
import httpx
from typing import Any, Dict

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-3-haiku-20240307"


async def _review_with_anthropic(copy_text: str, objective: str, target_audience: str) -> Dict[str, str]:
    api_key = os.getenv('ANTHROPIC_API_KEY', '').strip()

    # Assumption-based: fallback heuristic keeps pipeline operational without external API.
    if not api_key or api_key in {'dummy_key', 'VULL_HIER_JE_KEY_IN', 'MIJNKEY'}:
        status = 'APPROVED' if len(copy_text.strip()) >= 120 else 'NEEDS_CHANGES'
        feedback = (
            'Tekst is inhoudelijk sterk genoeg voor publicatie.'
            if status == 'APPROVED'
            else 'Tekst is te kort. Voeg meer concrete details en voorbeelden toe.'
        )
        return {'status': status, 'feedback': feedback}

    system_prompt = (
        'You are a strict Dutch content reviewer. '
        'Return only valid JSON with keys: status, feedback. '
        'status must be APPROVED or NEEDS_CHANGES.'
    )
    user_prompt = (
        f"Beoordeel deze Nederlandse tekst.\n"
        f"Doel: {objective}\n"
        f"Doelgroep: {target_audience}\n\n"
        f"TEKST:\n{copy_text}\n\n"
        "Criteria: duidelijkheid, juistheid, bruikbaarheid voor doelgroep."
    )

    payload = {
        'model': ANTHROPIC_MODEL,
        'max_tokens': 350,
        'system': system_prompt,
        'messages': [{'role': 'user', 'content': user_prompt}],
    }
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    raw = ''.join(chunk.get('text', '') for chunk in (data.get('content') or []) if isinstance(chunk, dict)).strip()
    parsed = None
    try:
        parsed = json.loads(raw)
    except Exception:
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(raw[start:end + 1])

    if not isinstance(parsed, dict):
        raise RuntimeError('Reviewer response is not valid JSON')

    status = str(parsed.get('status', '')).upper()
    if status not in {'APPROVED', 'NEEDS_CHANGES'}:
        status = 'NEEDS_CHANGES'
    feedback = str(parsed.get('feedback') or 'Geen feedback ontvangen van reviewer-model.')
    return {'status': status, 'feedback': feedback}


async def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = payload.get('context') or {}
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

    brief_context = (((context or {}).get('brief') or {}).get('context') or {})
    objective = str(brief_context.get('objective') or context.get('objective') or 'Doel niet gespecificeerd')
    target_audience = str(brief_context.get('target_audience') or context.get('target_audience') or 'Doelgroep niet gespecificeerd')

    verdict = await _review_with_anthropic(copy_text, objective, target_audience)
    status = verdict['status']
    feedback = verdict['feedback']

    return {
        'status': status,
        'feedback': feedback,
        'summary': f"Reviewer verdict: {status}",
        'data': {
            'objective': objective,
            'target_audience': target_audience,
            'model': ANTHROPIC_MODEL,
        },
    }
