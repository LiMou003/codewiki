"""
Qdrant vector database manager.

Provides create/upsert/search operations for storing code chunks and their
embeddings in a Qdrant collection.  Supports both a local in-memory instance
(useful for testing and development) and a remote Qdrant server.

Environment variables
---------------------
QDRANT_URL      URL of the Qdrant server  (e.g. "http://localhost:6333").
                When not set, an in-process in-memory instance is used.
QDRANT_API_KEY  Optional API key for authenticated Qdrant instances.
"""

import logging
import os
import uuid
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Qdrant collection name prefix
_COLLECTION_PREFIX = "codewiki_"


def _collection_name(repo_name: str) -> str:
    """Sanitise *repo_name* and turn it into a Qdrant collection name."""
    # Replace characters that Qdrant does not allow in collection names
    safe = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in repo_name)
    return f"{_COLLECTION_PREFIX}{safe}"


class QdrantManager:
    """
    Manages a Qdrant collection for a single repository.

    Each repository gets its own collection named
    ``codewiki_<sanitised_repo_name>``.  Points stored in the collection
    carry the full chunk payload so that retrievers can return rich metadata
    (function name, file path, start/end line, …) alongside the matched text.
    """

    def __init__(
        self,
        repo_name: str,
        vector_size: int,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
    ):
        """
        Args:
            repo_name:      Unique identifier for the repository; used to
                            derive the Qdrant collection name.
            vector_size:    Dimensionality of the embedding vectors.
            qdrant_url:     Override the ``QDRANT_URL`` environment variable.
            qdrant_api_key: Override the ``QDRANT_API_KEY`` environment variable.
        """
        self.repo_name = repo_name
        self.collection_name = _collection_name(repo_name)
        self.vector_size = vector_size

        url = qdrant_url or os.environ.get("QDRANT_URL")
        api_key = qdrant_api_key or os.environ.get("QDRANT_API_KEY")

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            if url:
                logger.info("Connecting to Qdrant at %s", url)
                self._client = QdrantClient(url=url, api_key=api_key or None)
            else:
                logger.info("Using in-memory Qdrant instance")
                self._client = QdrantClient(":memory:")

            self._Distance = Distance
            self._VectorParams = VectorParams
        except ImportError:
            raise ImportError(
                "qdrant-client is required.  "
                "Install it with: pip install qdrant-client"
            )

        self._ensure_collection()

    # ------------------------------------------------------------------
    # Collection lifecycle
    # ------------------------------------------------------------------

    def _ensure_collection(self) -> None:
        """Create the Qdrant collection if it does not yet exist."""
        from qdrant_client.models import VectorParams, Distance

        existing = {c.name for c in self._client.get_collections().collections}
        if self.collection_name not in existing:
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                "Created Qdrant collection '%s' (dim=%d)",
                self.collection_name,
                self.vector_size,
            )
        else:
            logger.info("Using existing Qdrant collection '%s'", self.collection_name)

    def recreate_collection(self) -> None:
        """Drop the collection (if it exists) and create a fresh one."""
        from qdrant_client.models import VectorParams, Distance

        existing = {c.name for c in self._client.get_collections().collections}
        if self.collection_name in existing:
            self._client.delete_collection(self.collection_name)
            logger.info("Deleted existing Qdrant collection '%s'", self.collection_name)

        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_size,
                distance=Distance.COSINE,
            ),
        )
        logger.info(
            "Recreated Qdrant collection '%s' (dim=%d)",
            self.collection_name,
            self.vector_size,
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        vectors: List[List[float]],
    ) -> None:
        """
        Store *chunks* together with their *vectors* in Qdrant.

        Args:
            chunks:  List of payload dicts.  Each dict **must** contain at
                     least ``text`` and ``file_path``.  The following optional
                     keys are stored when present:

                     - ``function_name``  – name of the function / method
                     - ``class_name``     – name of the enclosing class
                     - ``chunk_type``     – e.g. 'function', 'class', 'fixed_length'
                     - ``language``       – programming language
                     - ``start_line``     – first line of the chunk (1-indexed)
                     - ``end_line``       – last line of the chunk (1-indexed)
                     - any other key is stored as-is

            vectors: Embedding vectors, one per chunk.  Must have the same
                     length as *chunks*.
        """
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunks ({len(chunks)}) and vectors ({len(vectors)}) "
                "must have the same length"
            )
        if not chunks:
            return

        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=chunk,
            )
            for chunk, vector in zip(chunks, vectors)
        ]

        # Qdrant recommends batching large uploads
        batch_size = 256
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self._client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )

        logger.info(
            "Upserted %d points into '%s'", len(points), self.collection_name
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: List[float],
        top_k: int = 20,
        score_threshold: Optional[float] = None,
        filter_payload: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for the *top_k* most similar chunks.

        Args:
            query_vector:    Embedding of the query.
            top_k:           Number of results to return.
            score_threshold: Minimum cosine similarity (0–1).  If *None*,
                             no threshold is applied.
            filter_payload:  Optional equality filters on payload fields,
                             e.g. ``{"language": "python"}``.

        Returns:
            List of payload dicts for the matched points, sorted by
            descending similarity.  Each dict contains all fields stored at
            insertion time plus a ``_score`` key with the similarity score.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant_filter = None
        if filter_payload:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter_payload.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results = self._client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=qdrant_filter,
        )

        hits = []
        for scored in results.points:
            payload = dict(scored.payload or {})
            payload["_score"] = scored.score
            hits.append(payload)

        return hits

    def count(self) -> int:
        """Return the number of points stored in the collection."""
        info = self._client.get_collection(self.collection_name)
        return info.points_count or 0

    def collection_exists(self) -> bool:
        """Return *True* if the underlying Qdrant collection exists."""
        existing = {c.name for c in self._client.get_collections().collections}
        return self.collection_name in existing

    # ------------------------------------------------------------------
    # Class-level helpers (no collection creation side-effects)
    # ------------------------------------------------------------------

    @classmethod
    def collection_exists_for_repo(
        cls,
        repo_name: str,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
    ) -> bool:
        """Return whether the collection for *repo_name* already exists.

        This helper never creates collections and is intended for control-flow
        checks before deciding whether indexing is needed.
        """
        url = qdrant_url or os.environ.get("QDRANT_URL")
        if not url:
            # In-memory clients are isolated per process/client; treat as not
            # existing so a fresh collection is created in the current run.
            logger.debug(
                "No QDRANT_URL set; treating repo '%s' collection as non-existent.",
                repo_name,
            )
            return False

        api_key = qdrant_api_key or os.environ.get("QDRANT_API_KEY")
        collection_name = _collection_name(repo_name)

        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(url=url, api_key=api_key or None)
            existing = {c.name for c in client.get_collections().collections}
            return collection_name in existing
        except Exception as exc:
            logger.warning(
                "Could not query Qdrant for collection existence '%s': %s",
                collection_name,
                exc,
            )
            return False

    @classmethod
    def get_point_count(
        cls,
        repo_name: str,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
    ) -> int:
        """Return the number of points stored for *repo_name* without creating
        the collection if it does not yet exist.

        Uses a temporary client that never calls ``_ensure_collection``, so
        the method has **no side-effects** on the Qdrant server.

        For in-memory instances (``QDRANT_URL`` is not set) this always
        returns ``0`` because a new ``QdrantClient(":memory:")`` always
        starts with an empty store and cannot see data held by a different
        in-process client.

        Args:
            repo_name:      Repository identifier used to derive the
                            collection name (same as the ``repo_name``
                            constructor argument).
            qdrant_url:     Override the ``QDRANT_URL`` environment variable.
            qdrant_api_key: Override the ``QDRANT_API_KEY`` environment
                            variable.

        Returns:
            Number of points currently stored in the collection, or ``0``
            if the collection does not exist, Qdrant is unreachable, or the
            instance is in-memory.
        """
        url = qdrant_url or os.environ.get("QDRANT_URL")
        if not url:
            # In-memory clients are isolated; there is no way to inspect
            # another client's store without creating a new empty one.
            # Returning 0 ensures we always (re)build for in-memory instances.
            logger.debug(
                "No QDRANT_URL set; assuming in-memory instance has no "
                "existing data for repo '%s'.",
                repo_name,
            )
            return 0

        api_key = qdrant_api_key or os.environ.get("QDRANT_API_KEY")
        collection_name = _collection_name(repo_name)

        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(url=url, api_key=api_key or None)
            existing = {c.name for c in client.get_collections().collections}
            if collection_name not in existing:
                logger.info(
                    "Qdrant collection '%s' does not exist yet.",
                    collection_name,
                )
                return 0

            info = client.get_collection(collection_name)
            count = info.points_count or 0
            logger.info(
                "Qdrant collection '%s' already has %d point(s).",
                collection_name,
                count,
            )
            return count
        except Exception as exc:
            logger.warning(
                "Could not query Qdrant for collection '%s': %s",
                collection_name,
                exc,
            )
            return 0

    # ------------------------------------------------------------------
    # Convenience: build from CodeChunk list
    # ------------------------------------------------------------------

    @classmethod
    def chunk_to_payload(cls, chunk) -> Dict[str, Any]:
        """
        Convert a ``CodeChunk`` object into a plain dict suitable for
        storing as a Qdrant point payload.
        """
        return {
            "text":          chunk.text,
            "file_path":     chunk.file_path,
            "language":      chunk.language,
            "chunk_type":    chunk.chunk_type,
            "function_name": chunk.function_name,
            "class_name":    chunk.class_name,
            "start_line":    chunk.start_line,
            "end_line":      chunk.end_line,
            **(chunk.metadata or {}),
        }
