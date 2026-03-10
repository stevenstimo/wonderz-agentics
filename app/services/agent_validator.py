"""
Shared agent validation logic (DRY).
Used by both POST and PATCH endpoints.

DEPRECATED: Deze validator wordt niet meer gebruikt in de Hiring Hall POST.
De Hiring Hall (app/routes/agents.py) is de enige authoritative bron voor
rol- en tool-validatie. Dit bestand blijft bestaan voor bestaande tests.
Verwijder dit bestand pas als alle tests zijn gemigreerd.
"""
from typing import Dict, List, Optional
import re


class AgentValidationError(Exception):
    """Raised when agent config is invalid."""


def validate_agent_config(
    name: str,
    role: str,
    system_instructions: str,
    tool_access_whitelist: Optional[List[str]] = None,
    specialization: Optional[str] = None,
) -> Dict[str, str]:
    """
    Validates agent configuration.

    Returns: Normalized config dict
    Raises: AgentValidationError if invalid
    """
    errors = []

    # Name validation
    if not name or len(name) < 3:
        errors.append("Name must be at least 3 characters")
    if len(name) > 100:
        errors.append("Name must be max 100 characters")

    # Role validation
    valid_roles = ["copywriter", "reviewer", "seo", "hr-manager", "support", "custom"]
    if role not in valid_roles:
        errors.append(f"Role must be one of: {', '.join(valid_roles)}")

    # System instructions validation
    if not system_instructions or len(system_instructions) < 20:
        errors.append("System instructions must be at least 20 characters")
    if len(system_instructions) > 5000:
        errors.append("System instructions must be max 5000 characters")

    # Tool whitelist validation
    if tool_access_whitelist is not None:
        valid_tools = [
            "read_product",
            "write_copy",
            "read_analytics",
            "web_search",
            "read_docs",
            "write_docs",
        ]
        for tool in tool_access_whitelist:
            if tool not in valid_tools:
                errors.append(f"Invalid tool: {tool}")

    if errors:
        raise AgentValidationError("; ".join(errors))

    # Return normalized config
    return {
        "name": name.strip(),
        "role": role,
        "specialization": specialization or role,
        "system_instructions": system_instructions.strip(),
        "tool_access_whitelist": tool_access_whitelist or [],
    }


def generate_agent_id(name: str, role: str) -> str:
    """
    Generates unique agent_id from name and role.
    Format: agent:{role}:{slug}
    Example: agent:copywriter:max-senior
    """
    # Create slug from name
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = slug[:30]  # Max 30 chars

    return f"agent:{role}:{slug}"
