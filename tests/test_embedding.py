from tests.conftest import mock_embed_document, mock_embed_query


def test_mock_embedding_dimension():
    vec = mock_embed_document("hello world")
    assert len(vec) == 768


def test_mock_embedding_deterministic():
    v1 = mock_embed_document("test input")
    v2 = mock_embed_document("test input")
    assert v1 == v2


def test_mock_embedding_normalized():
    vec = mock_embed_document("something")
    norm = sum(v * v for v in vec) ** 0.5
    assert abs(norm - 1.0) < 0.01


def test_different_inputs_different_embeddings():
    v1 = mock_embed_document("alpha")
    v2 = mock_embed_document("beta")
    assert v1 != v2


def test_query_vs_document_different():
    """Query and document embeddings for the same text should differ (different prefixes)."""
    vd = mock_embed_document("test")
    vq = mock_embed_query("test")
    assert vd != vq
