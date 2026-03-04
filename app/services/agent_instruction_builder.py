"""
Agent Instruction Builder Service

Purpose: Build context-aware system prompts with output format instructions.
DRY: Single source of truth for all agent prompt construction.
"""

from typing import Dict, Optional, List
from enum import Enum


class OutputFormat(str, Enum):
    """Supported output formats"""

    HTML = "html"
    JSON = "json"
    MARKDOWN = "markdown"
    CODE = "code"
    PLAIN_TEXT = "plain_text"


class AgentInstructionBuilder:
    """
    Builds dynamic, context-aware system prompts for agents.

    DRY Principle:
    - Single prompt builder for all agents
    - Reusable format templates
    - Consistent instruction structure
    """

    # Format-specific instruction templates
    OUTPUT_FORMAT_TEMPLATES = {
        OutputFormat.HTML: """
OUTPUT FORMAT: HTML

CRITICAL RULES:
- Return ONLY valid HTML code
- Use semantic HTML5 elements (<article>, <section>, <header>, etc.)
- Include inline CSS if styling is mentioned
- NO markdown, NO explanations, NO code fences
- Start directly with opening tag (e.g., <div>, <article>)

STRUCTURE:
- Proper nesting and closing tags
- Use classes for styling hooks
- Include alt text for images if mentioned

EXAMPLE OUTPUT:
<article class="product-description">
  <h1>Product Name</h1>
  <p>Description text here...</p>
</article>
        """,
        OutputFormat.JSON: """
OUTPUT FORMAT: JSON

CRITICAL RULES:
- Return ONLY valid JSON
- NO markdown code fences (```json)
- NO explanatory text before/after
- Proper escaping of quotes and special chars
- Use null for missing values

STRUCTURE:
- Start with { or [
- All keys in double quotes
- No trailing commas

EXAMPLE OUTPUT:
{
  "title": "Product Name",
  "description": "Product description",
  "price": 29.99
}
        """,
        OutputFormat.MARKDOWN: """
OUTPUT FORMAT: MARKDOWN

CRITICAL RULES:
- Use proper markdown syntax
- Headers: # ## ### (not HTML <h1>)
- Lists: - or 1. 2. 3.
- Emphasis: *italic* **bold**
- Links: [text](url)
- Code blocks: ```language

STRUCTURE:
- Logical heading hierarchy
- Proper spacing between sections
- Use appropriate list types

EXAMPLE OUTPUT:
# Product Name

## Description
This is the product description.

## Features
- Feature 1
- Feature 2
        """,
        OutputFormat.CODE: """
OUTPUT FORMAT: CODE

CRITICAL RULES:
- Return ONLY executable code
- Include language-appropriate comments
- Follow language best practices
- NO explanations outside code
- Proper indentation

STRUCTURE:
- Clear variable/function names
- Comments for complex logic
- Error handling where appropriate

EXAMPLE OUTPUT:
def calculate_price(base_price, discount):
    # Apply discount percentage
    final_price = base_price * (1 - discount)
    return round(final_price, 2)
        """,
        OutputFormat.PLAIN_TEXT: """
OUTPUT FORMAT: PLAIN TEXT

CRITICAL RULES:
- Clear, well-structured prose
- No HTML tags
- No markdown syntax (unless specifically asked)
- Natural paragraph breaks

STRUCTURE:
- Logical flow
- Clear topic sentences
- Appropriate length
        """,
    }

    def __init__(self):
        """Initialize the instruction builder"""
        pass

    def detect_output_format(self, user_request: str) -> OutputFormat:
        """
        Auto-detect desired output format from user request.

        DRY: Single detection logic for all agents.

        Args:
            user_request: User's original job description

        Returns:
            Detected output format

        Examples:
            "maak HTML voor..." -> OutputFormat.HTML
            "geef JSON output" -> OutputFormat.JSON
            "schrijf code voor..." -> OutputFormat.CODE
        """
        request_lower = user_request.lower()

        # HTML indicators
        html_keywords = ["html", "webpage", "web page", "website", "html code"]
        if any(kw in request_lower for kw in html_keywords):
            return OutputFormat.HTML

        # JSON indicators
        json_keywords = ["json", "api response", "structured data"]
        if any(kw in request_lower for kw in json_keywords):
            return OutputFormat.JSON

        # Code indicators
        code_keywords = ["code", "function", "script", "programming", "python", "javascript"]
        if any(kw in request_lower for kw in code_keywords):
            return OutputFormat.CODE

        # Markdown indicators
        markdown_keywords = ["markdown", "article", "blog post", "document"]
        if any(kw in request_lower for kw in markdown_keywords):
            return OutputFormat.MARKDOWN

        # Default to plain text
        return OutputFormat.PLAIN_TEXT

    def build_prompt(
        self,
        base_system_prompt: str,
        output_format: Optional[OutputFormat] = None,
        user_request: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> str:
        """
        Build complete system prompt with format instructions.

        DRY: Reusable across ALL agents, ALL output types.

        Args:
            base_system_prompt: Agent's core identity/role
            output_format: Desired format (auto-detected if None)
            user_request: User's request (for auto-detection)
            context: Additional context (platform, audience, etc.)

        Returns:
            Complete system prompt with format instructions
        """
        prompt_parts = [base_system_prompt]

        # Auto-detect format if not provided
        if output_format is None and user_request:
            output_format = self.detect_output_format(user_request)

        # Add format-specific instructions
        if output_format and output_format in self.OUTPUT_FORMAT_TEMPLATES:
            prompt_parts.append("\n" + "=" * 60)
            prompt_parts.append(self.OUTPUT_FORMAT_TEMPLATES[output_format])
            prompt_parts.append("=" * 60 + "\n")

        # Add context if provided
        if context:
            context_str = "\nCONTEXT:\n"
            for key, value in context.items():
                context_str += f"- {key}: {value}\n"
            prompt_parts.append(context_str)

        return "\n".join(prompt_parts)

    def validate_output(
        self,
        output: str,
        expected_format: OutputFormat,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that output matches expected format.

        DRY: Single validation logic for all outputs.

        Args:
            output: Agent's output
            expected_format: Expected format

        Returns:
            (is_valid, error_message)
        """
        output_stripped = output.strip()

        if expected_format == OutputFormat.HTML:
            # Must start with < and contain closing tags
            if not output_stripped.startswith("<"):
                return False, "HTML must start with opening tag"
            if "```" in output_stripped:
                return False, "HTML should not contain markdown code fences"
            # Basic tag balance check
            open_tags = output_stripped.count("<")
            close_tags = output_stripped.count(">")
            if open_tags != close_tags:
                return False, "Unbalanced HTML tags"

        elif expected_format == OutputFormat.JSON:
            import json

            # Remove markdown fences if present (common mistake)
            cleaned = output_stripped.replace("```json", "").replace("```", "").strip()
            try:
                json.loads(cleaned)
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON: {str(e)}"

        elif expected_format == OutputFormat.CODE:
            # Should not contain "here is the code" type explanations
            explanation_phrases = [
                "here is the code",
                "here's the code",
                "this code will",
                "this function will",
            ]
            if any(phrase in output_stripped.lower()[:100] for phrase in explanation_phrases):
                return False, "Code should not start with explanations"

        return True, None


# Singleton instance for reuse
instruction_builder = AgentInstructionBuilder()
