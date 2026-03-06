"""Tests for MCP server tool functions.

These test the tool functions directly (not via MCP protocol).
"""

import pytest

from claude_crowed.db import get_connection, init_schema
from claude_crowed.memory_store import MemoryStore
from claude_crowed import server
from tests.conftest import mock_embed_document, mock_embed_query


@pytest.fixture(autouse=True)
def setup_server_store():
    """Override the global store with a test one."""
    db = get_connection(":memory:")
    init_schema(db)
    server._store = MemoryStore(db, mock_embed_document, mock_embed_query)
    yield
    server._store = None
    db.close()


def test_memory_store_tool():
    result = server.memory_store("Test Memory", "Some content about testing")
    assert "id" in result
    assert "error" not in result


def test_memory_read_tool():
    stored = server.memory_store("Read Test", "Content for reading")
    result = server.memory_read(stored["id"])
    assert result["title"] == "Read Test"
    assert result["content"] == "Content for reading"


def test_memory_search_tool():
    server.memory_store("Python Tips", "Use list comprehensions")
    server.memory_store("Rust Tips", "Use pattern matching")

    results = server.memory_search("Python")
    assert isinstance(results, list)
    assert len(results) > 0


def test_memory_update_tool():
    stored = server.memory_store("Original", "Original content")
    updated = server.memory_update(stored["id"], title="Updated")
    assert "id" in updated
    assert updated["id"] != stored["id"]


def test_memory_delete_undelete_tool():
    stored = server.memory_store("Delete Me", "Content")
    result = server.memory_delete(stored["id"])
    assert result["status"] == "ok"

    result = server.memory_undelete(stored["id"])
    assert result["status"] == "ok"


def test_memory_timeline_tool():
    server.memory_store("Timeline 1", "Content 1")
    server.memory_store("Timeline 2", "Content 2")

    result = server.memory_timeline()
    assert "items" in result
    assert len(result["items"]) == 2


def test_memory_related_tool():
    a = server.memory_store("A", "Content A")
    b = server.memory_store("B", "Content B")

    related = server.memory_related(a["id"])
    assert isinstance(related, list)
    assert len(related) >= 1


def test_memory_history_tool():
    stored = server.memory_store("V1", "Content 1")
    updated = server.memory_update(stored["id"], title="V2")

    history = server.memory_history(updated["id"])
    assert isinstance(history, list)
    assert len(history) == 2


def test_memory_stats_tool():
    server.memory_store("Stats Test", "Content")
    result = server.memory_stats()
    assert result["total_memories"] == 1
    assert result["total_versions"] == 1


def test_memory_read_not_found():
    result = server.memory_read("nonexistent-id")
    assert "error" in result
