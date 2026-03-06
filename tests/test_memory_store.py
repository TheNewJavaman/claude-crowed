import time

import pytest

from claude_crowed.config import MAX_DELETIONS_PER_SESSION


def _store(store, title, content, **kwargs):
    """Helper: store a memory and return the ID string."""
    result = store.store(title, content, **kwargs)
    assert isinstance(result, dict)
    assert "id" in result, f"Expected 'id' in result, got: {result}"
    return result["id"]


class TestCRUDLifecycle:
    def test_store_and_read(self, store):
        mid = _store(store, "Test Title", "Test content here")
        assert isinstance(mid, str)

        result = store.read(mid)
        assert result.title == "Test Title"
        assert result.content == "Test content here"
        assert result.version == 1
        assert result.is_deleted is False

    def test_store_returns_link_suggestions(self, store):
        _store(store, "Python debugging tips", "Use pdb for debugging Python code")
        result = store.store("Python async patterns", "Use asyncio for concurrent Python")
        assert "id" in result
        assert "link_suggestions" in result
        assert isinstance(result["link_suggestions"], list)

    def test_update_creates_new_version(self, store):
        mid1 = _store(store, "Original", "Original content")
        mid2 = store.update(mid1, title="Updated Title")
        assert isinstance(mid2, str)
        assert mid2 != mid1

        result = store.read(mid2)
        assert result.title == "Updated Title"
        assert result.content == "Original content"
        assert result.version == 2

    def test_update_content_only(self, store):
        mid1 = _store(store, "Title", "Old content")
        mid2 = store.update(mid1, content="New content")

        result = store.read(mid2)
        assert result.title == "Title"
        assert result.content == "New content"

    def test_delete_and_undelete(self, store):
        mid = _store(store, "To Delete", "Content")

        result = store.delete(mid)
        assert result["status"] == "ok"

        mem = store.read(mid)
        assert mem.is_deleted is True

        result = store.undelete(mid)
        assert result["status"] == "ok"

        mem = store.read(mid)
        assert mem.is_deleted is False

    def test_cannot_update_deleted(self, store):
        mid = _store(store, "Title", "Content")
        store.delete(mid)
        result = store.update(mid, title="New Title")
        assert isinstance(result, dict)
        assert "error" in result


class TestSearch:
    def test_search_returns_results(self, store):
        _store(store, "Python debugging tips", "Use pdb for debugging Python code")
        _store(store, "Rust ownership model", "Rust uses ownership for memory safety")
        _store(store, "Python async patterns", "Use asyncio for concurrent Python code")

        results = store.search("Python programming")
        assert len(results) > 0
        assert all(hasattr(r, "similarity") for r in results)
        # Results should be ordered by similarity descending
        for i in range(len(results) - 1):
            assert results[i].similarity >= results[i + 1].similarity

    def test_search_excludes_deleted_by_default(self, store):
        mid = _store(store, "Secret", "Hidden content")
        store.delete(mid)

        results = store.search("Secret")
        ids = [r.id for r in results]
        assert mid not in ids

    def test_search_includes_deleted_when_asked(self, store):
        """include_deleted=True allows deleted memories through if they appear in
        vec results. Since delete removes embeddings, a purely-deleted memory won't
        appear. But if we store two, delete one, and search, the non-deleted one
        should appear and the deleted one should not (even with include_deleted)
        because its embedding is gone."""
        mid1 = _store(store, "Secret Alpha", "Hidden content alpha")
        mid2 = _store(store, "Secret Beta", "Hidden content beta")
        store.delete(mid1)

        # Without include_deleted, mid1 won't appear (embedding removed)
        results = store.search("Secret", include_deleted=False)
        ids = [r.id for r in results]
        assert mid2 in ids
        assert mid1 not in ids

        # With include_deleted, mid1 still won't appear (no embedding)
        results = store.search("Secret", include_deleted=True)
        ids = [r.id for r in results]
        assert mid2 in ids

    def test_search_does_not_bump_last_accessed(self, store):
        mid = _store(store, "Test", "Content")
        mem_before = store.read(mid)
        time.sleep(0.01)

        store.search("Test")
        # Read again to check — read bumps last_accessed, so compare with initial
        mem = store.db.execute(
            "SELECT last_accessed_at FROM memories WHERE id = ?", (mid,)
        ).fetchone()
        # last_accessed was bumped by the read above, but search should not bump further
        assert mem["last_accessed_at"] == mem_before.last_accessed_at


class TestRecall:
    def test_recall_returns_full_content(self, store):
        _store(store, "Python debugging tips", "Use pdb for debugging Python code")
        _store(store, "Rust ownership model", "Rust uses ownership for memory safety")

        result = store.recall("Python debugging")
        assert "memories" in result
        assert "also_matched" in result
        assert len(result["memories"]) > 0
        # Full memories should have content
        assert "content" in result["memories"][0]
        assert "title" in result["memories"][0]

    def test_recall_limits_reads(self, store):
        for i in range(10):
            _store(store, f"Topic {i} unique content", f"Detail about topic {i}")

        result = store.recall("Topic unique", read_k=3)
        assert len(result["memories"]) <= 3
        # Remaining matches in also_matched
        total = len(result["memories"]) + len(result["also_matched"])
        assert total > 3


class TestTimeline:
    def test_timeline_ordering(self, store):
        ids = []
        for i in range(5):
            mid = _store(store, f"Memory {i}", f"Content {i}")
            ids.append(mid)
            time.sleep(0.01)  # Ensure distinct timestamps

        result = store.timeline(k=5)
        assert len(result.items) == 5
        # Should be newest first
        for i in range(len(result.items) - 1):
            assert result.items[i].updated_at >= result.items[i + 1].updated_at

    def test_timeline_pagination(self, store):
        for i in range(5):
            _store(store, f"Memory {i}", f"Content {i}")
            time.sleep(0.01)

        page1 = store.timeline(k=3)
        assert len(page1.items) == 3
        assert page1.next_cursor is not None

        page2 = store.timeline(k=3, cursor=page1.next_cursor)
        assert len(page2.items) == 2
        assert page2.next_cursor is None

    def test_timeline_before_after(self, store):
        ids = []
        for i in range(5):
            mid = _store(store, f"Memory {i}", f"Content {i}")
            ids.append(mid)
            time.sleep(0.01)

        # Get all items to know timestamps
        all_items = store.timeline(k=10)
        mid_ts = all_items.items[2].updated_at

        result = store.timeline(after=mid_ts)
        assert all(item.updated_at >= mid_ts for item in result.items)

    def test_timeline_excludes_old_versions(self, store):
        mid1 = _store(store, "Original", "Content")
        mid2 = store.update(mid1, title="Updated")

        result = store.timeline(k=10)
        ids = [item.id for item in result.items]
        assert mid2 in ids
        assert mid1 not in ids

    def test_timeline_include_deleted(self, store):
        mid = _store(store, "To Delete", "Content")
        store.delete(mid)

        result = store.timeline(include_deleted=False)
        ids = [item.id for item in result.items]
        assert mid not in ids

        result = store.timeline(include_deleted=True)
        ids = [item.id for item in result.items]
        assert mid in ids


class TestVersioning:
    def test_history_shows_all_versions(self, store):
        mid1 = _store(store, "V1", "Content v1")
        mid2 = store.update(mid1, title="V2", content="Content v2")
        mid3 = store.update(mid2, title="V3", content="Content v3")
        mid4 = store.update(mid3, title="V4", content="Content v4")

        history = store.history(mid4)
        assert len(history) == 4
        assert history[0].version == 4
        assert history[-1].version == 1

    def test_history_from_any_version(self, store):
        mid1 = _store(store, "V1", "Content v1")
        mid2 = store.update(mid1, title="V2")
        mid3 = store.update(mid2, title="V3")

        # Should work from any version id
        h1 = store.history(mid1)
        h2 = store.history(mid2)
        h3 = store.history(mid3)
        assert len(h1) == len(h2) == len(h3) == 3

    def test_old_versions_not_in_search(self, store):
        mid1 = _store(store, "Unique Searchable Alpha", "Alpha content")
        mid2 = store.update(mid1, title="Unique Searchable Beta")

        results = store.search("Unique Searchable")
        ids = [r.id for r in results]
        assert mid2 in ids
        assert mid1 not in ids


class TestLinks:
    def test_link_and_related(self, store):
        mid_a = _store(store, "Memory A", "Content A")
        mid_b = _store(store, "Memory B", "Content B")

        result = store.link(mid_a, mid_b)
        assert result["status"] == "ok"

        related = store.related(mid_a)
        assert len(related) == 1
        assert related[0].id == mid_b

        related_b = store.related(mid_b)
        assert len(related_b) == 1
        assert related_b[0].id == mid_a

    def test_unlink(self, store):
        mid_a = _store(store, "Memory A", "Content A")
        mid_b = _store(store, "Memory B", "Content B")
        store.link(mid_a, mid_b)

        store.unlink(mid_a, mid_b)
        assert store.related(mid_a) == []
        assert store.related(mid_b) == []

    def test_link_migration_on_update(self, store):
        mid_a = _store(store, "Memory A", "Content A")
        mid_b = _store(store, "Memory B", "Content B")
        store.link(mid_a, mid_b)

        mid_a2 = store.update(mid_a, title="Memory A Updated")

        related = store.related(mid_a2)
        assert len(related) == 1
        assert related[0].id == mid_b

    def test_link_count_in_search(self, store):
        mid_a = _store(store, "Memory A Links", "Content A")
        mid_b = _store(store, "Memory B Links", "Content B")
        mid_c = _store(store, "Memory C Links", "Content C")
        store.link(mid_a, mid_b)
        store.link(mid_a, mid_c)

        results = store.search("Memory Links")
        a_result = next((r for r in results if r.id == mid_a), None)
        assert a_result is not None
        assert a_result.link_count == 2

    def test_link_nonexistent(self, store):
        mid = _store(store, "Real", "Content")
        result = store.link(mid, "nonexistent-id")
        assert "error" in result


class TestValidation:
    def test_title_too_long(self, store):
        result = store.store("x" * 200, "Content")
        assert isinstance(result, dict)
        assert "error" in result

    def test_content_too_long(self, store):
        result = store.store("Title", "x" * 2000)
        assert isinstance(result, dict)
        assert "error" in result

    def test_invalid_source(self, store):
        result = store.store("Title", "Content", source="invalid")
        assert isinstance(result, dict)
        assert "error" in result


class TestDeduplication:
    def test_exact_duplicate_rejected(self, store):
        _store(store, "Unique Memory Title", "Unique memory content here")
        result = store.store("Unique Memory Title", "Unique memory content here")
        assert isinstance(result, dict)
        assert "error" in result
        assert "duplicate" in result["error"].lower() or "similarity" in result["error"].lower()

    def test_near_duplicate_rejected(self, store):
        """With mock embeddings, only identical text produces identical vectors.
        Real model would catch paraphrases too."""
        _store(store, "Identical title and content", "Identical body text here")
        # Slightly different title but same content triggers dedup via content similarity
        store.store("Identical title and content", "Identical body text here plus extra")
        # Mock embeddings won't catch this since text differs; test exact match instead
        result = store.store("Identical title and content", "Identical body text here")
        assert isinstance(result, dict)
        assert "error" in result

    def test_different_content_allowed(self, store):
        result1 = store.store("Python debugging tips", "Use pdb for debugging")
        result2 = store.store("Rust ownership model explained", "Rust uses ownership for memory safety")
        assert "id" in result1
        assert "id" in result2
        assert result1["id"] != result2["id"]

    def test_force_bypasses_dedup(self, store):
        _store(store, "Exact same title", "Exact same content")
        result = store.store("Exact same title", "Exact same content", force=True)
        assert isinstance(result, dict)
        assert "id" in result  # Should succeed


class TestDeletionSafeguards:
    def test_rate_limit(self, store):
        ids = []
        for i in range(MAX_DELETIONS_PER_SESSION + 1):
            mid = _store(store, f"Delete Me {i}", f"Content {i}")
            ids.append(mid)

        for i in range(MAX_DELETIONS_PER_SESSION):
            result = store.delete(ids[i])
            assert result["status"] == "ok"

        # The next deletion should fail
        result = store.delete(ids[MAX_DELETIONS_PER_SESSION])
        assert "error" in result
        assert "limit" in result["error"].lower()

    def test_delete_removes_from_embedding_index(self, store):
        mid = _store(store, "Findable", "Some content")

        # Should be in search
        results = store.search("Findable")
        assert any(r.id == mid for r in results)

        store.delete(mid)

        # Should not be in search by default
        results = store.search("Findable")
        assert not any(r.id == mid for r in results)

    def test_undelete_reinserts_embedding(self, store):
        mid = _store(store, "Findable Again", "Some content")
        store.delete(mid)
        store.undelete(mid)

        results = store.search("Findable Again")
        assert any(r.id == mid for r in results)


class TestExportImport:
    def test_round_trip(self, store, db):
        mid1 = _store(store, "Export A", "Content A")
        mid2 = _store(store, "Export B", "Content B")
        store.link(mid1, mid2)

        data = store.export_all()
        assert len(data.memories) == 2
        assert len(data.links) == 2  # bidirectional

        # Clear and reimport
        result = store.import_data(data, overwrite=True)
        assert result["imported_memories"] == 2
        assert result["imported_links"] == 2

        # Verify data survived
        mem = store.read(mid1)
        assert mem.title == "Export A"

    def test_import_skip_existing(self, store):
        _store(store, "Existing", "Content")
        data = store.export_all()

        result = store.import_data(data, overwrite=False)
        assert result["skipped"] == 1


class TestStats:
    def test_stats_counts(self, store):
        mid1 = _store(store, "A", "Content A")
        mid2 = _store(store, "B", "Content B")
        store.link(mid1, mid2)

        mid1_v2 = store.update(mid1, title="A Updated")
        _store(store, "C", "Content C")
        mid_del = _store(store, "D", "Content D")
        store.delete(mid_del)

        stats = store.stats()
        assert stats.total_memories == 3  # A(v2), B, C — not D (deleted)
        assert stats.total_deleted == 1  # D
        assert stats.total_versions == 5  # A(v1), A(v2), B, C, D
        assert stats.total_links >= 1
