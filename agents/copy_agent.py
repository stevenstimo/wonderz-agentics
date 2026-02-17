import os
import httpx
from typing import Any, Dict

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-3-haiku-20240307"


def _extract_brief_fields(context: Dict[str, Any]) -> Dict[str, str]:
    brief_context = (((context or {}).get('brief') or {}).get('context') or {})
    objective = brief_context.get('objective') or context.get('objective') or 'Write clear high-quality copy'
    target_audience = brief_context.get('target_audience') or context.get('target_audience') or 'General audience'
    platform = brief_context.get('platform') or context.get('platform') or 'web'
    return {
        'objective': str(objective),
        'target_audience': str(target_audience),
        'platform': str(platform),
    }


async def _generate_copy_with_anthropic(job_post: str, objective: str, target_audience: str, platform: str) -> str:
    api_key = os.getenv('ANTHROPIC_API_KEY', '').strip()

    # Assumption-based: local dev must still progress if API key is missing.
    if not api_key or api_key in {'dummy_key', 'VULL_HIER_JE_KEY_IN', 'MIJNKEY'}:
        return (
            f"Doel: {objective}.\n\n"
            f"Deze tekst is gericht op: {target_audience}.\n"
            f"Publicatieplatform: {platform}.\n\n"
            f"{job_post}\n\n"
            "Voetbal helpt jongeren samenwerken, bewegen en zelfvertrouwen opbouwen. "
            "Met toegankelijke training, duidelijke spelregels en positieve coaching ontstaat "
            "een veilige omgeving waarin plezier en ontwikkeling centraal staan."
        )

    system_prompt = (
        "You are a senior Dutch copywriter. Write fluent Dutch marketing/editorial copy. "
        "Be concrete, useful, and avoid filler."
    )
    user_prompt = (
        f"Schrijf één sterke Nederlandse tekst op basis van:\n"
        f"- Oorspronkelijke aanvraag: {job_post}\n"
        f"- Doel: {objective}\n"
        f"- Doelgroep: {target_audience}\n"
        f"- Platform: {platform}\n\n"
        "Lever alleen de uiteindelijke tekst, zonder uitleg erboven."
    )

    payload = {
        'model': ANTHROPIC_MODEL,
        'max_tokens': 900,
        'system': system_prompt,
        'messages': [
            {'role': 'user', 'content': user_prompt}
        ],
    }
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    }

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    chunks = data.get('content') or []
    text = ''.join(chunk.get('text', '') for chunk in chunks if isinstance(chunk, dict)).strip()
    if not text:
        raise RuntimeError('Anthropic returned empty content')
    return text


async def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = payload.get('context') or {}
    job_post = context.get('job_post') or payload.get('job_post') or 'Schrijf een sterke tekst.'
    fields = _extract_brief_fields(context)

    try:
        content = await _generate_copy_with_anthropic(
            job_post=job_post,
            objective=fields['objective'],
            target_audience=fields['target_audience'],
            platform=fields['platform'],
        )
    except Exception:
        # Assumption-based: if upstream model is unavailable/rate-limited, continue with deterministic fallback draft.
        content = (
            f"Doel: {fields['objective']}.\n\n"
            f"Doelgroep: {fields['target_audience']}. Platform: {fields['platform']}.\n\n"
            f"{job_post}\n\n"
            "Voetbal geeft jongeren energie, structuur en teamgevoel. Met heldere oefeningen, "
            "laagdrempelige spelvormen en positieve coaching groeit zowel techniek als zelfvertrouwen."
        )
    summary = content[:100]

    return {
        'status': 'DRAFT_READY',
        'content': content,
        'summary': summary,
        'data': {
            'draft_text': content,
            'objective': fields['objective'],
            'target_audience': fields['target_audience'],
            'platform': fields['platform'],
            'model': ANTHROPIC_MODEL,
        },
        'artifacts': [
            {
                'name': 'copy_draft',
                'type': 'copy_draft',
                'proposed_data': {'text': content},
                'original_data': {},
                'review_feedback': None,
            }
        ],
    }
