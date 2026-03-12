# assumption-based: use chunk_text from training.py (returns List[Tuple[str, int]])
import pytest
from app.services.training import chunk_text


def test_chunk_basic():
    """~1000 words -> multiple chunks with overlap."""
    text = " ".join([f"woord{i}" for i in range(1000)])
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    texts = [c[0] if isinstance(c, tuple) else c for c in chunks]
    assert len(texts) > 1
    end_words = set(texts[0].split()[-50:])
    start_words = set(texts[1].split()[:50])
    assert len(end_words & start_words) > 0


def test_chunk_short_text():
    """Shorter than chunk_size -> exactly one chunk."""
    text = " ".join([f"woord{i}" for i in range(100)])
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    texts = [c[0] if isinstance(c, tuple) else c for c in chunks]
    assert len(texts) == 1


def test_chunk_no_empty():
    """No empty or too-short chunks (< 50 words)."""
    text = " ".join([f"woord{i}" for i in range(600)])
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    texts = [c[0] if isinstance(c, tuple) else c for c in chunks]
    for t in texts:
        assert len(t.split()) >= 50
