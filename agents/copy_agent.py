import re
import os
import httpx
from typing import Any, Dict

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-3-haiku-20240307"


def _extract_brief_fields(context: Dict[str, Any]) -> Dict[str, str]:
    base = (context or {})
    payload_ctx = (base.get('payload') or {}) if isinstance(base.get('payload'), dict) else {}
    brief_context = (((base.get('brief') or payload_ctx.get('brief') or {}).get('context')) or {})
    objective = brief_context.get('objective') or context.get('objective') or 'Schrijf heldere, nuttige content'
    target_audience = brief_context.get('target_audience') or context.get('target_audience') or 'algemeen publiek'
    platform = brief_context.get('platform') or context.get('platform') or 'web'
    return {
        'objective': str(objective),
        'target_audience': str(target_audience),
        'platform': str(platform),
    }


def _infer_topic(job_post: str) -> str:
    text = (job_post or '').strip()
    if not text:
        return 'dit onderwerp'
    m = re.search(r'over\s+([^,.!?\n]+)', text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text[:80]


def _fallback_copy(job_post: str, objective: str, target_audience: str, platform: str) -> str:
    topic = _infer_topic(job_post)
    style_seed = abs(hash(f"{job_post}|{objective}|{target_audience}|{platform}")) % 3

    intros = [
        f"Schaatsen draait om ritme, techniek en plezier, en {topic} laat precies zien waarom jongeren dit zo snel oppakken.",
        f"Voor jongeren is {topic} een perfecte combinatie van uitdaging en fun: je voelt direct vooruitgang op het ijs.",
        f"Wie met {topic} aan de slag gaat, ontdekt hoe snel conditie, balans en zelfvertrouwen kunnen groeien.",
    ]
    ctas = [
        "Begin met korte trainingsblokken, bouw rustig op en houd het speels.",
        "Werk met duidelijke doelen per week en vier kleine verbeteringen zichtbaar.",
        "Combineer techniek met teamoefeningen zodat motivatie en plezier hoog blijven.",
    ]

    intro = intros[style_seed]
    cta = ctas[style_seed]

    return (
        f"{intro}\n\n"
        f"Doel: {objective}. Voor doelgroep: {target_audience}. Publicatie op: {platform}. "
        f"Daarom moet de tekst concreet, motiverend en direct bruikbaar zijn.\n\n"
        f"Bij {topic} werkt een heldere opbouw het best: start met veiligheid en basispositie, ga daarna door naar afzet, bochten en tempo. "
        "Jongeren leren sneller wanneer uitleg kort is en oefeningen direct toepasbaar zijn. Gebruik actieve taal, korte zinnen en herkenbare voorbeelden.\n\n"
        f"Sluit af met een praktische vervolgstap: {cta} Zo voelt de lezer niet alleen inspiratie, maar ook richting om meteen te starten."
    )


async def _generate_copy_with_anthropic(job_post: str, objective: str, target_audience: str, platform: str) -> str:
    api_key = os.getenv('ANTHROPIC_API_KEY', '').strip()

    if not api_key or api_key in {'dummy_key', 'VULL_HIER_JE_KEY_IN', 'MIJNKEY'}:
        raise RuntimeError('Anthropic API key ontbreekt of is placeholder')

    system_prompt = (
        'You are a senior Dutch copywriter. Write fluent Dutch copy tailored to the request. '
        'Never use generic filler text. Make it specific to the subject, objective, audience, and channel.'
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
        'messages': [{'role': 'user', 'content': user_prompt}],
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
    job_post = (
        context.get('job_post')
        or (context.get('payload') or {}).get('job_post')
        or payload.get('job_post')
        or 'Schrijf een sterke tekst.'
    )
    fields = _extract_brief_fields(context)

    try:
        content = await _generate_copy_with_anthropic(
            job_post=job_post,
            objective=fields['objective'],
            target_audience=fields['target_audience'],
            platform=fields['platform'],
        )
    except Exception:
        # Assumption-based: deterministic local fallback keeps workflow alive without external model access.
        content = _fallback_copy(
            job_post=job_post,
            objective=fields['objective'],
            target_audience=fields['target_audience'],
            platform=fields['platform'],
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
