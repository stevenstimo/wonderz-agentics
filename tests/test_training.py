import pytest
from app.services.training import validate_url, extract_text, chunk_text, TrainingError


def test_validate_url_valid():
    url = validate_url("https://example.com/page")
    assert url == "https://example.com/page"


def test_validate_url_invalid():
    with pytest.raises(TrainingError):
        validate_url("ftp://example.com")


def test_extract_text():
    html = "<html><script>bad</script><p>Good text</p></html>"
    text = extract_text(html)
    assert "Good text" in text
    assert "bad" not in text


def test_chunk_text():
    text = " ".join(["word"] * 1000)
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) > 5
    assert chunks[0][1] == 0
