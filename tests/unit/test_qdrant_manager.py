"""
Unit tests for the Qdrant vector database manager (api/qdrant_manager.py).
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from api.qdrant_manager import QdrantManager, _collection_name
from api.code_splitter import CodeChunk


# ---------------------------------------------------------------------------
# Collection name helper
# ---------------------------------------------------------------------------

class TestCollectionName:
    def test_basic(self):
        name = _collection_name("myrepo")
        assert name.startswith("codewiki_")
        assert "myrepo" in name

    def test_special_chars_sanitized(self):
        name = _collection_name("owner/repo-name.git")
        assert "/" not in name
        assert "." not in name

    def test_dash_allowed(self):
        name = _collection_name("my-repo")
        assert "my-repo" in name


# ---------------------------------------------------------------------------
# QdrantManager (in-memory)
# ---------------------------------------------------------------------------

VECTOR_SIZE = 4


@pytest.fixture
def manager():
    return QdrantManager(repo_name="test_repo", vector_size=VECTOR_SIZE)


class TestQdrantManagerInit:
    def test_collection_exists_after_init(self, manager):
        assert manager.collection_exists()

    def test_correct_collection_name(self, manager):
        assert manager.collection_name == "codewiki_test_repo"

    def test_initial_count_zero(self, manager):
        assert manager.count() == 0


class TestUpsert:
    def test_upsert_single_chunk(self, manager):
        chunks = [{"text": "hello", "file_path": "a.py"}]
        vectors = [[0.1, 0.2, 0.3, 0.4]]
        manager.upsert_chunks(chunks, vectors)
        assert manager.count() == 1

    def test_upsert_multiple_chunks(self, manager):
        chunks = [
            {"text": f"chunk {i}", "file_path": "a.py"}
            for i in range(10)
        ]
        vectors = [[float(i) / 10] * VECTOR_SIZE for i in range(10)]
        manager.upsert_chunks(chunks, vectors)
        assert manager.count() == 10

    def test_upsert_empty_no_crash(self, manager):
        manager.upsert_chunks([], [])
        assert manager.count() == 0

    def test_upsert_mismatch_raises(self, manager):
        with pytest.raises(ValueError):
            manager.upsert_chunks([{"text": "a"}], [[0.1, 0.2, 0.3, 0.4], [0.1, 0.2, 0.3, 0.4]])

    def test_payload_stored(self, manager):
        chunks = [{"text": "def foo():\n    pass", "file_path": "src/foo.py",
                   "function_name": "foo", "chunk_type": "function"}]
        vectors = [[0.5, 0.5, 0.5, 0.5]]
        manager.upsert_chunks(chunks, vectors)
        results = manager.search([0.5, 0.5, 0.5, 0.5], top_k=1)
        assert len(results) == 1
        assert results[0]["function_name"] == "foo"
        assert results[0]["file_path"] == "src/foo.py"


class TestSearch:
    def test_search_returns_correct_count(self, manager):
        chunks = [{"text": f"text {i}", "file_path": "a.py"} for i in range(5)]
        vectors = [[float(i) / 5] * VECTOR_SIZE for i in range(5)]
        manager.upsert_chunks(chunks, vectors)
        results = manager.search([0.5, 0.5, 0.5, 0.5], top_k=3)
        assert len(results) <= 3

    def test_search_includes_score(self, manager):
        manager.upsert_chunks([{"text": "hello", "file_path": "a.py"}], [[1.0, 0.0, 0.0, 0.0]])
        results = manager.search([1.0, 0.0, 0.0, 0.0], top_k=1)
        assert "_score" in results[0]
        assert isinstance(results[0]["_score"], float)

    def test_search_on_empty_collection(self, manager):
        results = manager.search([0.1, 0.2, 0.3, 0.4], top_k=5)
        assert results == []


class TestRecreate:
    def test_recreate_clears_data(self, manager):
        manager.upsert_chunks([{"text": "x", "file_path": "a.py"}], [[0.1, 0.2, 0.3, 0.4]])
        assert manager.count() == 1
        manager.recreate_collection()
        assert manager.count() == 0


class TestChunkToPayload:
    def test_converts_code_chunk(self):
        chunk = CodeChunk(
            text="def foo(): pass",
            file_path="src/foo.py",
            language="python",
            chunk_type="function",
            function_name="foo",
            class_name=None,
            start_line=1,
            end_line=1,
            metadata={"node_type": "function_definition"},
        )
        payload = QdrantManager.chunk_to_payload(chunk)
        assert payload["text"] == "def foo(): pass"
        assert payload["file_path"] == "src/foo.py"
        assert payload["language"] == "python"
        assert payload["chunk_type"] == "function"
        assert payload["function_name"] == "foo"
        assert payload["class_name"] is None
        assert payload["start_line"] == 1
        assert payload["end_line"] == 1
        assert payload["node_type"] == "function_definition"

    def test_roundtrip_upsert_and_search(self):
        """Payload survives a round-trip through Qdrant."""
        mgr = QdrantManager(repo_name="roundtrip_test", vector_size=VECTOR_SIZE)
        chunk = CodeChunk(
            text="class Foo: pass",
            file_path="foo.py",
            language="python",
            chunk_type="class",
            function_name=None,
            class_name="Foo",
            start_line=5,
            end_line=5,
        )
        payload = QdrantManager.chunk_to_payload(chunk)
        vec = [0.25, 0.25, 0.25, 0.25]
        mgr.upsert_chunks([payload], [vec])
        results = mgr.search(vec, top_k=1)
        assert results[0]["class_name"] == "Foo"
        assert results[0]["start_line"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
