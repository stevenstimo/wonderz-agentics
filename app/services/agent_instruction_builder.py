"""Builds context-aware system prompts and validates output formats."""

from __future__ import annotations

import json
from typing import Dict, Optional


class AgentInstructionBuilder:
    """Builds context-aware system prompts for agents."""

    OUTPUT_FORMAT_TEMPLATES: Dict[str, str] = {
        "html": (
            "When asked to create HTML content:\n"
            "- Always wrap output in proper HTML tags\n"
            "- Use semantic HTML5 elements\n"
            "- Include inline CSS if styling requested\n"
            "- Return ONLY the HTML code, no explanations"
        ),
        "json": (
            "When asked to create JSON:\n"
            "- Return valid JSON only, no markdown fences\n"
            "- Use proper escaping\n"
            "- Include all required fields"
        ),
        "markdown": (
            "When asked to create markdown:\n"
            "- Use proper markdown syntax\n"
            "- Include headers, lists, emphasis as appropriate"
        ),
        "code": (
            "When asked to write code:\n"
            "- Return executable code only\n"
            "- Include comments for clarity\n"
            "- Follow language best practices"
        ),
    }

    @staticmethod
    def detect_output_format(text: str) -> Optional[str]:
        """Heuristic detection of requested output format from user intent."""
        if not text:
            return None

        haystack = text.lower()

        if "json" in haystack:
            return "json"
        if "html" in haystack or "<html" in haystack or "html-code" in haystack:
            return "html"
        if "markdown" in haystack or "md " in haystack or "readme" in haystack:
            return "markdown"
        if any(tok in haystack for tok in ("code", "script", "python", "javascript", "typescript", "sql", "bash")):
            return "code"
        return None

    def build_prompt(
        self,
        base_prompt: str,
        output_format: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> str:
        """Construct full system prompt with optional format instructions."""
        prompt_parts = [base_prompt]

        if output_format:
            normalized = output_format.strip().lower()
            if normalized in self.OUTPUT_FORMAT_TEMPLATES:
                prompt_parts.append(self.OUTPUT_FORMAT_TEMPLATES[normalized])

        if context:
            prompt_parts.append(f"Context: {context}")

        return "\n\n".join(prompt_parts)

    def validate_output(self, output_text: str, output_format: Optional[str]) -> bool:
        """Best-effort validation of output format."""
        if not output_format:
            return True

        normalized = output_format.strip().lower()
        if normalized == "json":
            try:
                json.loads(output_text)
                return True
            except Exception:
                return False

        if normalized == "html":
            text = output_text.strip()
            return "<" in text and ">" in text

        # For markdown/code we accept any non-empty output; enforcement is prompt-based.
        return bool(output_text.strip())
