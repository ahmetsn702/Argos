import asyncio
import sys
import pytest
from unittest.mock import MagicMock, patch

from app.services.agent.rag.chunker import TextChunker
from app.services.agent.rag.embedder import LocalEmbedder
from app.services.agent.rag.store import ChromaStore

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

# ─── TextChunker Tests ────────────────────────────────────────────────────────

def test_chunker_basic_and_empty():
    chunker = TextChunker()
    # Empty cases
    assert chunker.chunk("") == []
    assert chunker.chunk(None) == []
    # Basic short text case
    text = "Hello world. This is a short test."
    chunks = chunker.chunk(text, max_chars=100)
    assert chunks == ["Hello world. This is a short test."]

def test_chunker_splits_sentence_boundary():
    chunker = TextChunker()
    text = "Sentence one. Sentence two! Sentence three?"
    # Max chars is 20, so they can't fit together
    chunks = chunker.chunk(text, max_chars=20, overlap=0)
    assert len(chunks) == 3
    assert chunks[0] == "Sentence one."
    assert chunks[1] == "Sentence two!"
    assert chunks[2] == "Sentence three?"

def test_chunker_giant_sentence():
    chunker = TextChunker()
    text = "Thisisagiantsentencewithoutanyspacesorpunctuationstodivideit"
    # Max chars 20, overlap 5.
    chunks = chunker.chunk(text, max_chars=20, overlap=5)
    assert len(chunks) > 1
    assert chunks[0] == text[0:20]
    assert chunks[1] == text[15:35]

def test_chunker_overlap_sentences():
    chunker = TextChunker()
    text = "AAAAA. BBBBB. CCCCC."
    # Max chars 15, overlap 12.
    chunks = chunker.chunk(text, max_chars=15, overlap=12)
    assert chunks == ["AAAAA. BBBBB.", "BBBBB. CCCCC."]

# ─── LocalEmbedder Tests ──────────────────────────────────────────────────────

def test_embedder_disabled_and_missing_package():
    # Test disabled
    with patch("app.core.feature_flags.AGENT_ENABLED", False):
        embedder = LocalEmbedder()
        assert embedder.embed(["test"]) == []
    # Test missing package
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch.dict(sys.modules, {"sentence_transformers": None}):
        embedder = LocalEmbedder()
        assert embedder.embed(["test"]) == []

def test_embedder_success():
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
    mock_st = MagicMock()
    mock_st.SentenceTransformer = MagicMock(return_value=mock_model)
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch.dict(sys.modules, {"sentence_transformers": mock_st}):
        embedder = LocalEmbedder()
        res = embedder.embed(["hello"])
        assert res == [[0.1, 0.2, 0.3]]
        # Check lazy load - model should be cached now
        assert embedder._model == mock_model

# ─── ChromaStore Tests ────────────────────────────────────────────────────────

def test_chroma_store_disabled_and_missing_chromadb(tmp_path):
    # Test disabled
    with patch("app.core.feature_flags.AGENT_ENABLED", False):
        store = ChromaStore(session_id="test_sess", persist_dir=str(tmp_path))
        _run(store.add("hello", {"key": "val"}))
        assert _run(store.search("hello")) == []
        _run(store.clear())
    # Test missing package
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch.dict(sys.modules, {"chromadb": None}):
        store = ChromaStore(session_id="test_sess", persist_dir=str(tmp_path))
        _run(store.add("hello", {"key": "val"}))
        assert _run(store.search("hello")) == []
        _run(store.clear())

def test_chroma_store_add_search_clear(tmp_path):
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["hello"]],
        "metadatas": [[{"key": "val"}]],
        "ids": [["id-123"]],
        "distances": [[0.1]]
    }
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb = MagicMock()
    mock_chromadb.PersistentClient = MagicMock(return_value=mock_client)

    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch.dict(sys.modules, {"chromadb": mock_chromadb}), \
         patch.object(LocalEmbedder, "embed", return_value=[[0.1, 0.2]]):
        
        store = ChromaStore(session_id="test_sess", persist_dir=str(tmp_path))
        
        # Test add
        _run(store.add("hello", {"key": "val"}))
        assert mock_collection.add.called
        
        # Test search
        results = _run(store.search("hello"))
        assert len(results) == 1
        assert results[0]["text"] == "hello"
        assert results[0]["metadata"] == {"key": "val"}
        assert results[0]["distance"] == 0.1

        # Test clear
        _run(store.clear())
        mock_client.delete_collection.assert_called_with("argos_test_sess")
