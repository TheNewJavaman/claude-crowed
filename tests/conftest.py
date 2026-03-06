import hashlib

import pytest

from claude_crowed.db import get_connection, init_schema
from claude_crowed.memory_store import MemoryStore


def mock_embed_document(text: str) -> list[float]:
    """Generate a deterministic 768-dim embedding from text content."""
    return _mock_embed(f"search_document: {text}")


def mock_embed_query(text: str) -> list[float]:
    """Generate a deterministic 768-dim embedding from a query."""
    return _mock_embed(f"search_query: {text}")


def _mock_embed(text: str) -> list[float]:
    """Generate a deterministic 768-dim unit vector from text using a seeded RNG."""
    import random

    seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
    rng = random.Random(seed)
    values = [rng.gauss(0, 1) for _ in range(768)]
    norm = sum(v * v for v in values) ** 0.5
    return [v / norm for v in values]


@pytest.fixture
def db():
    conn = get_connection(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def store(db):
    return MemoryStore(db, mock_embed_document, mock_embed_query)
