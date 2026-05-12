import asyncio
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from api.qdrant_manager import QdrantManager

logger = logging.getLogger(__name__)

GIT_DIFF_STATUS_RE = re.compile(r"^([AMD])\s+(.+)$")
REPOS_DIR_NAME = "repos"
DIFF_BATCH_MAX_FILES = 120

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RepoDiff:
    added: List[str] = field(default_factory=list)
    modified: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.deleted)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_adalflow_root() -> str:
    return os.path.expanduser(os.path.join("~", ".adalflow"))


def _get_repos_dir() -> str:
    return os.path.join(_get_adalflow_root(), REPOS_DIR_NAME)


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------


def _run_git(repo_dir: str, args: List[str], timeout: int = 120) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def git_pull(repo_dir: str) -> Optional[str]:
    """Pull latest changes. Returns the previous HEAD commit hash, or None on failure/skip."""
    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        logger.warning("%s is not a git repository; skipping pull.", repo_dir)
        return None

    # Only pull repos that have a configured remote
    try:
        remotes = _run_git(repo_dir, ["remote"])
        if not remotes.strip():
            logger.info("%s has no git remote; skipping pull (local-only repo).", repo_dir)
            return None
    except subprocess.CalledProcessError:
        logger.warning("Cannot check remotes for %s; skipping pull.", repo_dir)
        return None

    try:
        old_head = _run_git(repo_dir, ["rev-parse", "HEAD"])
    except subprocess.CalledProcessError as exc:
        logger.warning("Failed to get HEAD for %s: %s", repo_dir, exc)
        return None

    try:
        _run_git(repo_dir, ["pull", "--ff-only"], timeout=180)
        logger.info("git pull succeeded for %s", repo_dir)
    except subprocess.CalledProcessError as exc:
        logger.warning("git pull failed for %s: %s", repo_dir, exc)
        try:
            _run_git(repo_dir, ["fetch", "origin"])
            _run_git(repo_dir, ["reset", "--hard", "origin/HEAD"])
            logger.info("Hard reset to origin/HEAD for %s", repo_dir)
        except subprocess.CalledProcessError:
            logger.error("Could not reset %s; skipping.", repo_dir)
            return None

    return old_head


def get_changed_files(repo_dir: str, old_head: str) -> RepoDiff:
    """Return files changed between *old_head* and the current HEAD."""
    diff = RepoDiff()

    try:
        new_head = _run_git(repo_dir, ["rev-parse", "HEAD"])
    except subprocess.CalledProcessError:
        logger.warning("Cannot get new HEAD for %s", repo_dir)
        return diff

    if old_head == new_head:
        logger.info("No new commits in %s", repo_dir)
        return diff

    try:
        output = _run_git(repo_dir, ["diff", "--name-status", old_head, new_head])
    except subprocess.CalledProcessError:
        logger.warning("git diff failed for %s", repo_dir)
        return diff

    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = GIT_DIFF_STATUS_RE.match(line)
        if not match:
            continue
        status, fpath = match.group(1), match.group(2)
        if status == "A":
            diff.added.append(fpath)
        elif status == "M":
            diff.modified.append(fpath)
        elif status == "D":
            diff.deleted.append(fpath)

    logger.info(
        "Diff for %s: +%d ~%d -%d",
        os.path.basename(repo_dir),
        len(diff.added),
        len(diff.modified),
        len(diff.deleted),
    )
    return diff


# ---------------------------------------------------------------------------
# Document reading (targeted)
# ---------------------------------------------------------------------------


def _read_specific_files(
    repo_dir: str,
    file_paths: List[str],
) -> List:
    """Read *file_paths* (relative to *repo_dir*) as Document objects."""
    from adalflow.core.types import Document
    from api.data_pipeline import count_tokens

    MAX_EMBEDDING_TOKENS = 8000
    code_extensions = {
        ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".hpp",
        ".go", ".rs", ".jsx", ".tsx", ".html", ".css", ".php",
        ".swift", ".cs",
    }

    documents = []
    for fpath in file_paths:
        abs_path = os.path.join(repo_dir, fpath)
        if not os.path.isfile(abs_path):
            continue
        ext = os.path.splitext(fpath)[1].lower()

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as exc:
            logger.warning("Cannot read %s: %s", fpath, exc)
            continue

        token_count = count_tokens(content)
        if token_count > MAX_EMBEDDING_TOKENS * 10 and ext in code_extensions:
            logger.warning("Skipping large file %s (%d tokens)", fpath, token_count)
            continue
        if token_count > MAX_EMBEDDING_TOKENS and ext not in code_extensions:
            logger.warning("Skipping large file %s (%d tokens)", fpath, token_count)
            continue

        is_code = ext in code_extensions
        is_implementation = not fpath.startswith("test_") and "test" not in fpath.lower()

        doc = Document(
            text=content,
            meta_data={
                "file_path": fpath,
                "type": ext.lstrip("."),
                "is_code": is_code,
                "is_implementation": is_implementation,
                "title": fpath,
                "token_count": token_count,
            },
        )
        documents.append(doc)

    return documents


# ---------------------------------------------------------------------------
# Core incremental indexing
# ---------------------------------------------------------------------------


def _embed_and_upsert(
    documents: List,
    qdrant_manager: QdrantManager,
    embedder_type: str,
    dimension: int = None,
) -> int:
    """Split, embed, and upsert *documents* into *qdrant_manager*. Returns chunk count."""
    if not documents:
        return 0

    from api.config import configs
    from api.data_pipeline import _get_embedding_vector
    from api.tools.embedder import get_embedder
    from api.code_splitter import TreeSitterCodeSplitter
    from api.code_splitter import split_text_fixed, EXTENSION_TO_LANGUAGE

    embedder = get_embedder(embedder_type=embedder_type, dimension=dimension)
    AVG_CHARS_PER_WORD = 6
    chunk_size = configs.get("text_splitter", {}).get("chunk_size", 1500)
    chunk_size_chars = chunk_size * AVG_CHARS_PER_WORD
    splitter = TreeSitterCodeSplitter(
        chunk_size=chunk_size_chars, chunk_overlap=chunk_size_chars // AVG_CHARS_PER_WORD,
    )

    payloads: List[dict] = []
    vectors: List[list] = []

    for doc in documents:
        meta = doc.meta_data or {}
        fpath = meta.get("file_path", "")
        is_code = bool(meta.get("is_code", False))
        ext = meta.get("type", "")

        if is_code:
            language = EXTENSION_TO_LANGUAGE.get(ext.lower(), ext.lower() or "unknown")
            chunks = splitter.split_code(doc.text, fpath, language)
        else:
            chunks = split_text_fixed(
                doc.text, fpath,
                chunk_size=chunk_size_chars,
                chunk_overlap=chunk_size_chars // AVG_CHARS_PER_WORD,
            )

        for chunk in chunks:
            vector = _get_embedding_vector(embedder, chunk.text)
            if not vector:
                continue
            payload = QdrantManager.chunk_to_payload(chunk)
            payload["is_code"] = is_code
            payload["is_implementation"] = meta.get("is_implementation", False)
            payloads.append(payload)
            vectors.append(vector)

    if payloads:
        qdrant_manager.upsert_chunks(payloads, vectors)
        logger.info("Upserted %d chunks across %d files", len(payloads), len(documents))

    return len(payloads)


def incremental_update_for_repo(
    repo_dir: str,
    repo_name: str,
    embedder_type: str = "dashscope",
    dimension: int = None,
) -> bool:
    """Run one incremental update for a single repository.

    Returns True if changes were found and applied, False if no-op.
    """
    logger.info("Incremental update: %s (%s)", repo_name, repo_dir)

    old_head = git_pull(repo_dir)
    if old_head is None:
        return False

    diff = get_changed_files(repo_dir, old_head)
    if not diff.has_changes:
        return False

    collection_exists = QdrantManager.collection_exists_for_repo(repo_name)
    if not collection_exists:
        logger.info(
            "Qdrant collection for '%s' does not exist yet; "
            "trigger full index via the normal API first.", repo_name,
        )
        return False

    # Always use the collection's actual dimension as the source of truth.
    vector_size = QdrantManager.get_collection_dimension(repo_name)
    if vector_size is None:
        vector_size = dimension or 1024
        logger.warning(
            "Cannot read collection dimension for '%s'; "
            "falling back to %d", repo_name, vector_size,
        )
    else:
        logger.info(
            "Using Qdrant collection dimension %d for '%s' "
            "(user preference ignored).", vector_size, repo_name,
        )

    qdrant_manager = QdrantManager(repo_name=repo_name, vector_size=vector_size)

    # Delete points for deleted *and* modified files
    to_delete = diff.deleted + diff.modified
    if to_delete:
        logger.info("Deleting Qdrant points for %d file(s)", len(to_delete))
        qdrant_manager.delete_points_by_file_paths(to_delete)

    # Re-index added *and* modified files
    to_index = diff.added + diff.modified
    if to_index:
        logger.info("Re-indexing %d file(s)", len(to_index))
        for i in range(0, len(to_index), DIFF_BATCH_MAX_FILES):
            batch = to_index[i: i + DIFF_BATCH_MAX_FILES]
            documents = _read_specific_files(repo_dir, batch)
            if documents:
                _embed_and_upsert(documents, qdrant_manager, embedder_type, dimension=vector_size)

    return True


# ---------------------------------------------------------------------------
# Repo discovery
# ---------------------------------------------------------------------------


def discover_repos() -> Dict[str, str]:
    """Scan the repos directory and return {repo_name: repo_dir} for every git repository with a remote."""
    repos_dir = _get_repos_dir()
    if not os.path.isdir(repos_dir):
        return {}

    discovered: Dict[str, str] = {}
    for name in os.listdir(repos_dir):
        repo_dir = os.path.join(repos_dir, name)
        if not os.path.isdir(os.path.join(repo_dir, ".git")):
            continue
        # Only include repos that have a remote (skip local-only copies)
        try:
            remotes = _run_git(repo_dir, ["remote"])
            if not remotes.strip():
                logger.debug("%s has no git remote; skipping.", repo_dir)
                continue
        except subprocess.CalledProcessError:
            logger.debug("Cannot check remotes for %s; skipping.", repo_dir)
            continue
        discovered[name] = repo_dir
    return discovered


# ---------------------------------------------------------------------------
# Auto-refresh scheduler (asyncio based)
# ---------------------------------------------------------------------------

_DEFAULT_REFRESH_INTERVAL_SECONDS = 3600  # 1 hour

_refresh_task: Optional[asyncio.Task] = None
_refresh_stop: Optional[asyncio.Event] = None


async def _auto_refresh_loop(embedder_type: str = "dashscope", interval: int = _DEFAULT_REFRESH_INTERVAL_SECONDS):
    global _refresh_stop
    stop = _refresh_stop or asyncio.Event()
    logger.info(
        "Incremental index auto-refresh started (interval=%ds, embedder=%s)",
        interval, embedder_type,
    )

    while not stop.is_set():
        try:
            await asyncio.sleep(interval)
            if stop.is_set():
                break

            repos = discover_repos()
            if not repos:
                logger.debug("No repositories found for incremental refresh.")
                continue

            logger.info("Auto-refresh: checking %d repo(s)", len(repos))
            for repo_name, repo_dir in repos.items():
                try:
                    changed = incremental_update_for_repo(repo_dir, repo_name, embedder_type)
                    if changed:
                        logger.info("Auto-refresh: updated '%s'", repo_name)
                except Exception as exc:
                    logger.error("Auto-refresh failed for '%s': %s", repo_name, exc)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Auto-refresh loop error: %s", exc)


def start_auto_refresh(embedder_type: str = "dashscope", interval: int = _DEFAULT_REFRESH_INTERVAL_SECONDS):
    global _refresh_task, _refresh_stop
    stop_auto_refresh()
    _refresh_stop = asyncio.Event()
    _refresh_task = asyncio.create_task(_auto_refresh_loop(embedder_type, interval))


def stop_auto_refresh():
    global _refresh_task, _refresh_stop
    if _refresh_task and not _refresh_task.done():
        _refresh_stop.set()
        _refresh_task.cancel()
    _refresh_task = None
    _refresh_stop = None


# ---------------------------------------------------------------------------
# Manual refresh (used by API endpoint)
# ---------------------------------------------------------------------------


async def refresh_all_repos(embedder_type: str = "dashscope") -> Dict[str, bool]:
    """Refresh all discovered repos. Returns {repo_name: had_changes}."""
    repos = discover_repos()
    results: Dict[str, bool] = {}
    for repo_name, repo_dir in repos.items():
        try:
            changed = incremental_update_for_repo(repo_dir, repo_name, embedder_type)
            results[repo_name] = changed
        except Exception as exc:
            logger.error("Refresh failed for '%s': %s", repo_name, exc)
            results[repo_name] = False
    return results
