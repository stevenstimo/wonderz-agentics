from app.services.agent_instruction_builder import AgentInstructionBuilder, OutputFormat


def test_detect_output_format():
    builder = AgentInstructionBuilder()
    assert builder.detect_output_format("Maak HTML code voor product") == OutputFormat.HTML
    assert builder.detect_output_format("Geef JSON output met details") == OutputFormat.JSON
    assert builder.detect_output_format("Schrijf code voor een functie") == OutputFormat.CODE
    assert builder.detect_output_format("Maak een markdown artikel") == OutputFormat.MARKDOWN
    assert builder.detect_output_format("Schrijf een korte tekst") == OutputFormat.PLAIN_TEXT


def test_build_prompt_includes_format_and_context():
    builder = AgentInstructionBuilder()
    prompt = builder.build_prompt(
        base_system_prompt="Base prompt",
        output_format=OutputFormat.HTML,
        context={"platform": "web", "audience": "developers"},
    )
    assert "OUTPUT FORMAT: HTML" in prompt
    assert "CONTEXT:" in prompt
    assert "- platform: web" in prompt
    assert "- audience: developers" in prompt


def test_validate_output_html():
    builder = AgentInstructionBuilder()
    valid, error = builder.validate_output("<div>Ok</div>", OutputFormat.HTML)
    assert valid is True
    assert error is None

    valid, error = builder.validate_output("Not HTML", OutputFormat.HTML)
    assert valid is False
    assert error == "HTML must start with opening tag"


def test_validate_output_json():
    builder = AgentInstructionBuilder()
    valid, error = builder.validate_output('{"a": 1}', OutputFormat.JSON)
    assert valid is True
    assert error is None

    valid, error = builder.validate_output("{bad json", OutputFormat.JSON)
    assert valid is False
    assert error is not None


def test_validate_output_code_explanations():
    builder = AgentInstructionBuilder()
    valid, error = builder.validate_output("Here is the code:\nprint('ok')", OutputFormat.CODE)
    assert valid is False
    assert error == "Code should not start with explanations"
