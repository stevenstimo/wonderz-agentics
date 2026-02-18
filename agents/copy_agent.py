"""Copy Agent — writes text using OpenAI, incorporates reviewer feedback on retries."""
import re
import os
import json
import httpx
from typing import Any, Dict

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
                                 platform: str, reviewer_feedback: str = None) -> str:
    api_key = _get_openai_key()
    if not api_key:
        raise RuntimeError("OpenAI API key not found")

    # Extract word count from job_post if mentioned
    import re as _re
    m = _re.search(r'(\d+)\s*woord', job_post, _re.IGNORECASE)
    word_count = int(m.group(1)) if m else 400

    system_prompt = (
        "Je bent een ervaren Nederlandse copywriter. "
        "Schrijf vloeiend, informatief Nederlands. "
        "De tekst moet inhoudelijk correct, specifiek over het onderwerp, en goed gestructureerd zijn. "
        "Gebruik alinea's. Geen opsommingen tenzij gevraagd. "
        "Schrijf EXACT het gevraagde aantal woorden (±10%). "
        "Lever ALLEEN de tekst, zonder titel, zonder uitleg."
    )

    user_prompt = (
        f"Schrijf een Nederlandse tekst van {word_count} woorden.\n\n"
        f"Onderwerp/opdracht: {job_post}\n"
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

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": OPENAI_MODEL, "messages": messages, "max_tokens": 2000, "temperature": 0.7},
        )
        resp.raise_for_status()
        data = resp.json()

    text = data["choices"][0]["message"]["content"].strip()
    if not text:
        raise RuntimeError("OpenAI returned empty content")
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

    # Check if there's reviewer feedback from a previous round
    reviewer_out = context.get('reviewer_agent') or {}
    reviewer_feedback = None
    if isinstance(reviewer_out, dict):
        fb = reviewer_out.get('feedback', '')
        status = reviewer_out.get('status', '')
        if status == 'NEEDS_CHANGES' and fb:
            reviewer_feedback = fb

    content = await _generate_with_openai(
        job_post=job_post,
        objective=fields['objective'],
        target_audience=fields['target_audience'],
        platform=fields['platform'],
        reviewer_feedback=reviewer_feedback,
    )

    word_count = len(content.split())
    summary = content[:120]

    return {
        'status': 'DRAFT_READY',
        'content': content,
        'summary': summary,
        'word_count': word_count,
        'data': {
            'draft_text': content,
            'objective': fields['objective'],
            'target_audience': fields['target_audience'],
            'platform': fields['platform'],
            'model': OPENAI_MODEL,
            'had_reviewer_feedback': reviewer_feedback is not None,
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
