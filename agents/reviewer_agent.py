import asyncio
from typing import Any, Dict


async def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Review the draft copy and return a verdict: APPROVED, NEEDS_CHANGES, or REJECTED.

    Simple heuristic: if the draft contains the word 'bad' -> REJECTED, if short -> NEEDS_CHANGES, else APPROVED.
    """
    await asyncio.sleep(0.2)
    context = payload.get("context", {})
    draft = None
    copy_out = context.get("copy_agent")
    if copy_out and isinstance(copy_out, dict):
        # prefer content_text from artifact
        data = copy_out.get("data") or {}
        draft = data.get("draft_text") or copy_out.get("content_text")

    if not draft:
        return {"summary": "no draft found", "status": "REJECTED", "data": {}}

    text = draft.lower()
    if "bad" in text:
        return {"summary": "contains disallowed terms", "status": "REJECTED", "data": {"reason": "disallowed_terms"}}

    if len(text) < 50:
        return {"summary": "draft too short", "status": "NEEDS_CHANGES", "data": {"reason": "too_short"}}

    # otherwise approve
    return {"summary": "approved", "status": "APPROVED", "data": {}}
