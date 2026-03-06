from __future__ import annotations

import struct
import threading
from typing import TYPE_CHECKING

from claude_crowed.config import EMBEDDING_MODEL

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None
_model_ready = threading.Event()
_model_error: Exception | None = None
_loading_started = False


def start_loading() -> None:
    """Begin loading the embedding model in a background thread.
    Call this at server startup so the model loads during MCP handshake."""
    global _loading_started
    if _loading_started:
        return
    _loading_started = True
    thread = threading.Thread(target=_load_model_background, daemon=True)
    thread.start()


def _load_model_background() -> None:
    global _model, _model_error
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(
            EMBEDDING_MODEL, trust_remote_code=True, device="cpu"
        )
    except Exception as e:
        _model_error = e
    finally:
        _model_ready.set()


def _get_model() -> SentenceTransformer:
    if not _loading_started:
        start_loading()
    _model_ready.wait()
    if _model_error is not None:
        raise RuntimeError(
            f"Embedding model failed to load: {_model_error}. Run: uv sync"
        ) from _model_error
    assert _model is not None
    return _model


def embed_document(text: str) -> list[float]:
    """Embed a memory document (title + content) for storage."""
    model = _get_model()
    embedding = model.encode(
        f"search_document: {text}",
        normalize_embeddings=True,
    )
    return embedding.tolist()


def embed_query(query: str) -> list[float]:
    """Embed a search query for retrieval."""
    model = _get_model()
    embedding = model.encode(
        f"search_query: {query}",
        normalize_embeddings=True,
    )
    return embedding.tolist()


def serialize_embedding(embedding: list[float]) -> bytes:
    """Serialize embedding to raw bytes for sqlite-vec."""
    return struct.pack(f"{len(embedding)}f", *embedding)


def default_embed_fn(text: str) -> list[float]:
    """Default embedding function for documents. Used by rebuild_embeddings."""
    return embed_document(text)
