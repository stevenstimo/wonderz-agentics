"""
Tests for agent CRUD endpoints.
"""
import pytest
from app.services.agent_validator import (
    validate_agent_config,
    generate_agent_id,
    AgentValidationError,
)


def test_validate_agent_config_valid():
    """Valid config should pass."""
    config = validate_agent_config(
        name="Test Agent",
        role="copywriter",
        system_instructions="You are a helpful assistant for testing.",
    )
    assert config["name"] == "Test Agent"
    assert config["role"] == "copywriter"


def test_validate_agent_config_invalid_name():
    """Too short name should fail."""
    with pytest.raises(AgentValidationError):
        validate_agent_config(
            name="AB",  # Too short
            role="copywriter",
            system_instructions="Valid instructions here.",
        )


def test_generate_agent_id():
    """Agent ID should be properly formatted."""
    agent_id = generate_agent_id("Max Senior Copywriter", "copywriter")
    assert agent_id.startswith("agent:copywriter:")
    assert "max-senior" in agent_id


def test_generate_agent_id_special_chars():
    """Special characters should be removed."""
    agent_id = generate_agent_id("Test@Agent#123!", "seo")
    assert "@" not in agent_id
    assert "#" not in agent_id
    assert "!" not in agent_id
