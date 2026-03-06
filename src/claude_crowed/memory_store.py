import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Callable

from claude_crowed.config import (
    DEFAULT_RECALL_READ_K,
    DEFAULT_SEARCH_K,
    DEFAULT_TIMELINE_K,
    DUPLICATE_SIMILARITY_THRESHOLD,
    MAX_CONTENT_LENGTH,
    MAX_DELETIONS_PER_SESSION,
    MAX_TITLE_LENGTH,
)
from claude_crowed.embedding import serialize_embedding
from claude_crowed.models import (
    ExportData,
    MemoryFull,
    MemorySearchResult,
    MemoryStats,
    MemoryVersion,
    RelatedMemory,
    TimelineItem,
    TimelineResponse,
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryStore:
    def __init__(
        self,
        db: sqlite3.Connection,
        embed_document_fn: Callable[[str], list[float]],
        embed_query_fn: Callable[[str], list[float]],
    ):
        self.db = db
        self.embed_document = embed_document_fn
        self.embed_query = embed_query_fn
        self._deletion_count = 0

    def get_similarity_threshold(self) -> float:
        """Get the persisted duplicate similarity threshold, or the default."""
        row = self.db.execute(
            "SELECT value FROM settings WHERE key = 'similarity_threshold'"
        ).fetchone()
        if row:
            return float(row["value"])
        return DUPLICATE_SIMILARITY_THRESHOLD

    def set_similarity_threshold(self, value: float) -> dict:
        """Persist a new duplicate similarity threshold."""
        if not 0.0 <= value <= 1.0:
            return {"error": "Threshold must be between 0.0 and 1.0."}
        self.db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('similarity_threshold', ?)",
            (str(value),),
        )
        self.db.commit()
        return {"status": "ok", "similarity_threshold": value}

    def search(
        self,
        query: str,
        k: int = DEFAULT_SEARCH_K,
        include_deleted: bool = False,
    ) -> list[MemorySearchResult]:
        query_embedding = self.embed_query(query)
        rows = self.db.execute(
            """
            SELECT id, distance
            FROM memory_embeddings
            WHERE embedding MATCH ?
                AND k = ?
            ORDER BY distance
            """,
            (serialize_embedding(query_embedding), k),
        ).fetchall()

        results = []
        for row in rows:
            distance = row[1]  # distance is second column
            mem = self.db.execute(
                "SELECT * FROM memories WHERE id = ?", (row[0],)
            ).fetchone()
            if mem is None:
                continue
            if not include_deleted and mem["is_deleted"]:
                continue

            results.append(
                MemorySearchResult(
                    id=mem["id"],
                    title=mem["title"],
                    similarity=1.0 - distance,
                    created_at=mem["created_at"],
                    updated_at=mem["updated_at"],
                    last_accessed_at=mem["last_accessed_at"],
                    is_deleted=bool(mem["is_deleted"]),
                )
            )
        return results

    def recall(
        self,
        query: str,
        k: int = DEFAULT_SEARCH_K,
        read_k: int = DEFAULT_RECALL_READ_K,
        include_deleted: bool = False,
    ) -> dict:
        """Search and auto-read top results in one call."""
        results = self.search(query, k=k, include_deleted=include_deleted)
        read_results = []
        for r in results[:read_k]:
            full = self.read(r.id)
            if isinstance(full, MemoryFull):
                read_results.append(full.model_dump())
        remaining = [r.model_dump() for r in results[read_k:]]
        return {
            "memories": read_results,
            "also_matched": remaining,
        }

    def read(self, memory_id: str) -> MemoryFull | dict:
        mem = self.db.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if mem is None:
            return {"error": f"Memory not found: {memory_id}"}

        now = now_utc()
        self.db.execute(
            "UPDATE memories SET last_accessed_at = ? WHERE id = ?",
            (now, memory_id),
        )
        self.db.commit()

        return MemoryFull(
            id=mem["id"],
            version=mem["version"],
            title=mem["title"],
            content=mem["content"],
            created_at=mem["created_at"],
            updated_at=mem["updated_at"],
            last_accessed_at=now,
            source=mem["source"],
            is_deleted=bool(mem["is_deleted"]),
        )

    def _check_duplicate(
        self,
        embedding: list[float],
        threshold: float = DUPLICATE_SIMILARITY_THRESHOLD,
    ) -> dict | None:
        """Check if a near-duplicate memory already exists. Returns match info or None."""
        rows = self.db.execute(
            """
            SELECT id, distance
            FROM memory_embeddings
            WHERE embedding MATCH ?
                AND k = 1
            ORDER BY distance
            """,
            (serialize_embedding(embedding), ),
        ).fetchall()

        if not rows:
            return None

        distance = rows[0][1]
        similarity = 1.0 - distance
        if similarity >= threshold:
            mem = self.db.execute(
                "SELECT id, title FROM memories WHERE id = ?", (rows[0][0],)
            ).fetchone()
            if mem:
                return {
                    "id": mem["id"],
                    "title": mem["title"],
                    "similarity": round(similarity, 4),
                }
        return None

    def store(
        self,
        title: str,
        content: str,
        source: str = "manual",
        force: bool = False,
        similarity_threshold: float | None = None,
    ) -> str | dict:
        if len(title) > MAX_TITLE_LENGTH:
            return {
                "error": f"Title exceeds {MAX_TITLE_LENGTH} characters ({len(title)} chars). Please shorten it."
            }
        if len(content) > MAX_CONTENT_LENGTH:
            return {
                "error": f"Content exceeds {MAX_CONTENT_LENGTH} characters ({len(content)} chars). Please split into multiple memories."
            }
        if source not in ("manual", "conversation", "auto"):
            return {"error": f"Invalid source: {source}. Must be one of: manual, conversation, auto."}

        memory_id = str(uuid.uuid4())
        now = now_utc()

        embedding = self.embed_document(f"{title}\n{content}")

        if not force:
            threshold = similarity_threshold if similarity_threshold is not None else self.get_similarity_threshold()
            dup = self._check_duplicate(embedding, threshold=threshold)
            if dup:
                return {
                    "error": f"Near-duplicate memory already exists (similarity={dup['similarity']}): "
                    f"[{dup['id']}] {dup['title']}. Use force=True to store anyway."
                }

        self.db.execute(
            """
            INSERT INTO memories (id, version, title, content, created_at, updated_at, last_accessed_at, is_deleted, parent_id, source)
            VALUES (?, 1, ?, ?, ?, ?, ?, 0, NULL, ?)
            """,
            (memory_id, title, content, now, now, now, source),
        )
        self.db.execute(
            "INSERT INTO memory_embeddings (id, embedding) VALUES (?, ?)",
            (memory_id, serialize_embedding(embedding)),
        )
        self.db.commit()
        return {"id": memory_id}

    def update(
        self,
        memory_id: str,
        title: str | None = None,
        content: str | None = None,
    ) -> str | dict:
        old = self.db.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if old is None:
            return {"error": f"Memory not found: {memory_id}"}
        if old["is_deleted"]:
            return {"error": "Cannot update a deleted memory. Undelete it first with memory_undelete."}

        new_title = title if title is not None else old["title"]
        new_content = content if content is not None else old["content"]

        if len(new_title) > MAX_TITLE_LENGTH:
            return {
                "error": f"Title exceeds {MAX_TITLE_LENGTH} characters ({len(new_title)} chars). Please shorten it."
            }
        if len(new_content) > MAX_CONTENT_LENGTH:
            return {
                "error": f"Content exceeds {MAX_CONTENT_LENGTH} characters ({len(new_content)} chars). Please split into multiple memories."
            }

        new_id = str(uuid.uuid4())
        now = now_utc()

        embedding = self.embed_document(f"{new_title}\n{new_content}")

        self.db.execute(
            """
            INSERT INTO memories (id, version, title, content, created_at, updated_at, last_accessed_at, is_deleted, parent_id, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                new_id,
                old["version"] + 1,
                new_title,
                new_content,
                old["created_at"],
                now,
                now,
                memory_id,
                old["source"],
            ),
        )

        # Remove old embedding, insert new
        self.db.execute(
            "DELETE FROM memory_embeddings WHERE id = ?", (memory_id,)
        )
        self.db.execute(
            "INSERT INTO memory_embeddings (id, embedding) VALUES (?, ?)",
            (new_id, serialize_embedding(embedding)),
        )

        self.db.commit()
        return new_id

    def delete(self, memory_id: str) -> dict:
        if self._deletion_count >= MAX_DELETIONS_PER_SESSION:
            return {
                "error": f"Deletion limit reached ({MAX_DELETIONS_PER_SESSION} per session). "
                "This is a safety limit to prevent accidental mass deletion. "
                "Restart the server to reset, or ask the user to confirm bulk deletions manually."
            }

        mem = self.db.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if mem is None:
            return {"error": f"Memory not found: {memory_id}"}

        now = now_utc()
        self.db.execute(
            "UPDATE memories SET is_deleted = 1, updated_at = ? WHERE id = ?",
            (now, memory_id),
        )
        self.db.execute(
            "DELETE FROM memory_embeddings WHERE id = ?", (memory_id,)
        )
        self.db.commit()

        self._deletion_count += 1
        return {"status": "ok"}

    def undelete(self, memory_id: str) -> dict:
        mem = self.db.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if mem is None:
            return {"error": f"Memory not found: {memory_id}"}
        if not mem["is_deleted"]:
            return {"error": "Memory is not deleted."}

        self.db.execute(
            "UPDATE memories SET is_deleted = 0 WHERE id = ?", (memory_id,)
        )

        embedding = self.embed_document(f"{mem['title']}\n{mem['content']}")
        self.db.execute(
            "INSERT INTO memory_embeddings (id, embedding) VALUES (?, ?)",
            (memory_id, serialize_embedding(embedding)),
        )
        self.db.commit()
        return {"status": "ok"}

    def history(self, memory_id: str) -> list[MemoryVersion] | dict:
        mem = self.db.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if mem is None:
            return {"error": f"Memory not found: {memory_id}"}

        rows = self.db.execute(
            """
            WITH RECURSIVE chain_back AS (
                SELECT id, parent_id, version, title, content, updated_at
                FROM memories WHERE id = ?
                UNION ALL
                SELECT m.id, m.parent_id, m.version, m.title, m.content, m.updated_at
                FROM memories m JOIN chain_back c ON m.id = c.parent_id
            ),
            root AS (
                SELECT id FROM chain_back WHERE parent_id IS NULL
            ),
            chain_forward AS (
                SELECT id, parent_id, version, title, content, updated_at
                FROM memories WHERE id = (SELECT id FROM root)
                UNION ALL
                SELECT m.id, m.parent_id, m.version, m.title, m.content, m.updated_at
                FROM memories m JOIN chain_forward f ON m.parent_id = f.id
            )
            SELECT DISTINCT id, version, title, content, updated_at
            FROM chain_forward
            ORDER BY version DESC
            """,
            (memory_id,),
        ).fetchall()

        return [
            MemoryVersion(
                id=r["id"],
                version=r["version"],
                title=r["title"],
                content=r["content"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def timeline(
        self,
        k: int = DEFAULT_TIMELINE_K,
        cursor: str | None = None,
        before: str | None = None,
        after: str | None = None,
        include_deleted: bool = False,
    ) -> TimelineResponse:
        conditions = []
        params: list = []

        # Only latest versions: exclude any id that is a parent of another memory
        conditions.append(
            "m.id NOT IN (SELECT parent_id FROM memories WHERE parent_id IS NOT NULL)"
        )

        if not include_deleted:
            conditions.append("m.is_deleted = 0")

        # Apply cursor/before: use the more restrictive
        upper_bound = None
        if cursor is not None and before is not None:
            upper_bound = min(cursor, before)
        elif cursor is not None:
            upper_bound = cursor
        elif before is not None:
            upper_bound = before

        if upper_bound is not None:
            if upper_bound == before and cursor is None:
                conditions.append("m.updated_at <= ?")
            else:
                conditions.append("m.updated_at < ?")
            params.append(upper_bound)

        if after is not None:
            conditions.append("m.updated_at >= ?")
            params.append(after)

        where = " AND ".join(conditions)
        params.append(k)

        rows = self.db.execute(
            f"""
            SELECT m.*
            FROM memories m
            WHERE {where}
            ORDER BY m.updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

        items = [
            TimelineItem(
                id=r["id"],
                title=r["title"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                last_accessed_at=r["last_accessed_at"],
                is_deleted=bool(r["is_deleted"]),
            )
            for r in rows
        ]

        next_cursor = items[-1].updated_at if len(items) == k else None
        return TimelineResponse(items=items, next_cursor=next_cursor)

    def related(self, memory_id: str, k: int = 5) -> list[RelatedMemory] | dict:
        """Find semantically related memories via embedding nearest-neighbor search."""
        mem = self.db.execute(
            "SELECT 1 FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if mem is None:
            return {"error": f"Memory not found: {memory_id}"}

        emb_row = self.db.execute(
            "SELECT embedding FROM memory_embeddings WHERE id = ?", (memory_id,)
        ).fetchone()
        if emb_row is None:
            return []

        rows = self.db.execute(
            """
            SELECT id, distance
            FROM memory_embeddings
            WHERE embedding MATCH ?
                AND k = ?
            ORDER BY distance
            """,
            (emb_row[0], k + 1),
        ).fetchall()

        results = []
        for row in rows:
            mid = row[0]
            if mid == memory_id:
                continue
            m = self.db.execute(
                "SELECT id, title, updated_at, last_accessed_at FROM memories WHERE id = ? AND is_deleted = 0",
                (mid,),
            ).fetchone()
            if m:
                results.append(
                    RelatedMemory(
                        id=m["id"],
                        title=m["title"],
                        updated_at=m["updated_at"],
                        last_accessed_at=m["last_accessed_at"],
                    )
                )
            if len(results) >= k:
                break
        return results

    def export_all(self) -> ExportData:
        memories = self.db.execute("SELECT * FROM memories").fetchall()

        return ExportData(
            exported_at=now_utc(),
            memories=[dict(m) for m in memories],
        )

    def import_data(
        self,
        data: ExportData,
        overwrite: bool = False,
    ) -> dict:
        imported_memories = 0
        skipped = 0

        if overwrite:
            self.db.execute("DELETE FROM memory_embeddings")
            self.db.execute("DELETE FROM memories")
            self.db.commit()

        for mem in data.memories:
            if not overwrite:
                exists = self.db.execute(
                    "SELECT 1 FROM memories WHERE id = ?", (mem["id"],)
                ).fetchone()
                if exists:
                    skipped += 1
                    continue

            self.db.execute(
                """
                INSERT INTO memories (id, version, title, content, created_at, updated_at, last_accessed_at, is_deleted, parent_id, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mem["id"],
                    mem["version"],
                    mem["title"],
                    mem["content"],
                    mem["created_at"],
                    mem["updated_at"],
                    mem["last_accessed_at"],
                    mem["is_deleted"],
                    mem.get("parent_id"),
                    mem.get("source", "manual"),
                ),
            )
            imported_memories += 1

        # Re-embed all latest-version, non-deleted memories
        latest = self.db.execute(
            """
            SELECT id, title, content FROM memories
            WHERE is_deleted = 0
              AND id NOT IN (SELECT parent_id FROM memories WHERE parent_id IS NOT NULL)
            """
        ).fetchall()
        for row in latest:
            embedding = self.embed_document(f"{row['title']}\n{row['content']}")
            self.db.execute(
                "DELETE FROM memory_embeddings WHERE id = ?", (row["id"],)
            )
            self.db.execute(
                "INSERT INTO memory_embeddings (id, embedding) VALUES (?, ?)",
                (row["id"], serialize_embedding(embedding)),
            )

        self.db.commit()
        return {
            "imported_memories": imported_memories,
            "skipped": skipped,
        }

    def stats(self) -> MemoryStats:
        total_memories = self.db.execute(
            """
            SELECT COUNT(*) as cnt FROM memories
            WHERE is_deleted = 0
              AND id NOT IN (SELECT parent_id FROM memories WHERE parent_id IS NOT NULL)
            """
        ).fetchone()["cnt"]

        total_deleted = self.db.execute(
            "SELECT COUNT(*) as cnt FROM memories WHERE is_deleted = 1"
        ).fetchone()["cnt"]

        total_versions = self.db.execute(
            "SELECT COUNT(*) as cnt FROM memories"
        ).fetchone()["cnt"]

        oldest = self.db.execute(
            "SELECT MIN(created_at) as val FROM memories WHERE is_deleted = 0"
        ).fetchone()["val"]

        newest = self.db.execute(
            "SELECT MAX(updated_at) as val FROM memories WHERE is_deleted = 0"
        ).fetchone()["val"]

        return MemoryStats(
            total_memories=total_memories,
            total_deleted=total_deleted,
            total_versions=total_versions,
            oldest_memory=oldest,
            newest_memory=newest,
            db_size_bytes=0,  # Overridden by caller for real DB
        )


def rebuild_embeddings(
    db: sqlite3.Connection,
    embed_fn: Callable[[str], list[float]],
) -> int:
    """Drop and rebuild the memory_embeddings table from current memories."""
    db.execute("DELETE FROM memory_embeddings")

    rows = db.execute(
        """
        SELECT m.id, m.title, m.content
        FROM memories m
        WHERE m.is_deleted = 0
          AND m.id NOT IN (SELECT parent_id FROM memories WHERE parent_id IS NOT NULL)
        """
    ).fetchall()

    for row in rows:
        embedding = embed_fn(f"{row['title']}\n{row['content']}")
        db.execute(
            "INSERT INTO memory_embeddings(id, embedding) VALUES (?, ?)",
            (row["id"], serialize_embedding(embedding)),
        )
    db.commit()
    return len(rows)
