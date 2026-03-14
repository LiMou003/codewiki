"""
Tree-sitter based code splitter.

For code files, this module uses Tree-sitter to parse the AST and extract
functions, classes, and methods as individual chunks with metadata.
For non-code files, it falls back to a fixed-length (character) splitter.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CodeChunk:
    """Represents a chunk extracted from a source file."""
    text: str
    file_path: str
    language: str
    chunk_type: str          # 'function', 'class', 'method', 'module', 'fixed_length'
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Language / node-type configuration
# ---------------------------------------------------------------------------

# Map file extension → language identifier used internally
EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    "py":   "python",
    "js":   "javascript",
    "jsx":  "javascript",
    "ts":   "typescript",
    "tsx":  "tsx",
    "java": "java",
    "go":   "go",
    "rs":   "rust",
    "cpp":  "cpp",
    "cc":   "cpp",
    "cxx":  "cpp",
    "c":    "c",
    "h":    "c",
    "hpp":  "cpp",
    "cs":   "c_sharp",
    "php":  "php",
    "swift":"swift",
}

# AST node types that represent extractable units for each language.
# Keys are the internal chunk_type labels.
CHUNK_NODE_TYPES: Dict[str, Dict[str, List[str]]] = {
    "python": {
        "function": ["function_definition"],
        "class":    ["class_definition"],
    },
    "javascript": {
        "function": ["function_declaration", "generator_function_declaration"],
        "class":    ["class_declaration"],
        "method":   ["method_definition"],
    },
    "typescript": {
        "function": ["function_declaration"],
        "class":    ["class_declaration"],
        "method":   ["method_definition"],
    },
    "tsx": {
        "function": ["function_declaration"],
        "class":    ["class_declaration"],
        "method":   ["method_definition"],
    },
    "java": {
        "function": ["method_declaration", "constructor_declaration"],
        "class":    ["class_declaration", "interface_declaration", "enum_declaration"],
    },
    "go": {
        "function": ["function_declaration", "method_declaration"],
    },
    "rust": {
        "function": ["function_item"],
        "impl":     ["impl_item"],
    },
    "cpp": {
        "function": ["function_definition"],
    },
    "c": {
        "function": ["function_definition"],
    },
    "c_sharp": {
        "function": ["method_declaration", "constructor_declaration"],
        "class":    ["class_declaration", "interface_declaration"],
    },
}


def _load_language(language: str):
    """
    Lazily load a tree-sitter Language object.  Returns None when the language
    module is not installed or the language is not supported.
    """
    try:
        from tree_sitter import Language, Parser  # noqa: F401
        if language == "python":
            import tree_sitter_python as mod
            return Language(mod.language())
        elif language == "javascript":
            import tree_sitter_javascript as mod
            return Language(mod.language())
        elif language == "typescript":
            import tree_sitter_typescript as mod
            return Language(mod.language_typescript())
        elif language == "tsx":
            import tree_sitter_typescript as mod
            return Language(mod.language_tsx())
        elif language == "java":
            import tree_sitter_java as mod
            return Language(mod.language())
        elif language == "go":
            import tree_sitter_go as mod
            return Language(mod.language())
        elif language == "rust":
            import tree_sitter_rust as mod
            return Language(mod.language())
        elif language == "cpp":
            import tree_sitter_cpp as mod
            return Language(mod.language())
        elif language == "c":
            import tree_sitter_c as mod
            return Language(mod.language())
        elif language == "c_sharp":
            import tree_sitter_c_sharp as mod
            return Language(mod.language())
        else:
            return None
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not load tree-sitter grammar for %s: %s", language, exc)
        return None


# ---------------------------------------------------------------------------
# Name extraction helpers
# ---------------------------------------------------------------------------

def _get_node_name(node, code_bytes: bytes) -> Optional[str]:
    """
    Return the simple name (identifier) for an AST node such as a function or
    class declaration.  Returns *None* when no name can be determined.
    """
    name_types = {
        "identifier",
        "property_identifier",
        "type_identifier",
        "field_identifier",
    }
    for child in node.children:
        if child.type in name_types and child.text:
            return child.text.decode("utf-8", errors="replace")
    return None


def _get_function_name_cpp(node, code_bytes: bytes) -> Optional[str]:
    """
    For C/C++ function_definition nodes the name is buried inside a
    function_declarator child.
    """
    for child in node.children:
        if child.type == "function_declarator":
            return _get_node_name(child, code_bytes)
        # pointer_declarator → function_declarator
        if child.type == "pointer_declarator":
            for subchild in child.children:
                if subchild.type == "function_declarator":
                    return _get_node_name(subchild, code_bytes)
    return None


def _get_function_name_go_method(node, code_bytes: bytes) -> Optional[str]:
    """
    For Go method_declaration nodes the name is a field_identifier child,
    not the first identifier (which belongs to the receiver).
    """
    for child in node.children:
        if child.type == "field_identifier" and child.text:
            return child.text.decode("utf-8", errors="replace")
    return None


def _get_node_name_for_language(node, language: str, code_bytes: bytes) -> Optional[str]:
    """Dispatch to the appropriate name-extraction helper."""
    if language in ("c", "cpp"):
        return _get_function_name_cpp(node, code_bytes)
    if language == "go" and node.type == "method_declaration":
        return _get_function_name_go_method(node, code_bytes)
    return _get_node_name(node, code_bytes)


# ---------------------------------------------------------------------------
# Context (parent class) tracking
# ---------------------------------------------------------------------------

def _find_parent_class(node, code_bytes: bytes) -> Optional[str]:
    """Walk up the tree to find the enclosing class name (if any)."""
    class_node_types = {
        "class_definition", "class_declaration", "class_body",
        "interface_declaration", "impl_item",
    }
    parent = node.parent
    while parent is not None:
        if parent.type in class_node_types:
            return _get_node_name(parent, code_bytes)
        parent = parent.parent
    return None


# ---------------------------------------------------------------------------
# Tree-sitter splitter
# ---------------------------------------------------------------------------

class TreeSitterCodeSplitter:
    """
    Splits a code file into chunks using Tree-sitter AST parsing.

    For each supported language the splitter extracts top-level (and nested)
    functions, classes, and methods as individual ``CodeChunk`` objects.
    When the language is not supported by tree-sitter the file is split using
    the fixed-length fallback.
    """

    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 200):
        """
        Args:
            chunk_size: Maximum character length for a single chunk.
            chunk_overlap: Overlap in characters between adjacent fixed-length
                           chunks (used by the fallback splitter).
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._parser_cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def split_code(self, code: str, file_path: str, language: str) -> List[CodeChunk]:
        """
        Split a code file using Tree-sitter.

        Falls back to fixed-length splitting when the language is not
        supported or parsing fails.

        Args:
            code: Source code text.
            file_path: Relative path of the file (used for metadata).
            language: Language identifier from ``EXTENSION_TO_LANGUAGE``.

        Returns:
            A list of ``CodeChunk`` objects.
        """
        try:
            parser = self._get_parser(language)
            if parser is None:
                return self._fixed_length_split(code, file_path, language)
            code_bytes = code.encode("utf-8")
            tree = parser.parse(code_bytes)
            chunks = self._extract_chunks(tree, code_bytes, file_path, language)
            if not chunks:
                # If no top-level functions/classes found, treat the whole file
                # as a single module chunk (still bounded by chunk_size).
                chunks = self._fixed_length_split(code, file_path, language)
            return chunks
        except Exception as exc:
            logger.warning("Tree-sitter split failed for %s: %s", file_path, exc)
            return self._fixed_length_split(code, file_path, language)

    @staticmethod
    def extension_to_language(ext: str) -> Optional[str]:
        """Return the language identifier for a file extension, or *None*."""
        return EXTENSION_TO_LANGUAGE.get(ext.lstrip(".").lower())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_parser(self, language: str):
        """Return a cached Parser for *language*, or None if unsupported."""
        if language not in self._parser_cache:
            lang_obj = _load_language(language)
            if lang_obj is None:
                self._parser_cache[language] = None
            else:
                from tree_sitter import Parser
                self._parser_cache[language] = Parser(lang_obj)
        return self._parser_cache[language]

    def _extract_chunks(
        self,
        tree,
        code_bytes: bytes,
        file_path: str,
        language: str,
    ) -> List[CodeChunk]:
        """
        Walk the AST and collect function/class/method nodes as chunks.
        """
        node_type_map = CHUNK_NODE_TYPES.get(language, {})
        if not node_type_map:
            return []

        # Build a flat set of target node types → chunk_type label
        target_types: Dict[str, str] = {}
        for chunk_type, node_types in node_type_map.items():
            for nt in node_types:
                target_types[nt] = chunk_type

        chunks: List[CodeChunk] = []
        self._walk(
            tree.root_node,
            code_bytes,
            file_path,
            language,
            target_types,
            chunks,
            visited_bytes=set(),
        )
        return chunks

    def _walk(
        self,
        node,
        code_bytes: bytes,
        file_path: str,
        language: str,
        target_types: Dict[str, str],
        chunks: List[CodeChunk],
        visited_bytes: set,
    ) -> None:
        """Recursively walk *node* and collect matching chunks."""
        if node.type in target_types:
            byte_range = (node.start_byte, node.end_byte)
            if byte_range not in visited_bytes:
                visited_bytes.add(byte_range)
                chunk = self._node_to_chunk(
                    node, code_bytes, file_path, language,
                    target_types[node.type],
                )
                if chunk is not None:
                    chunks.append(chunk)
                    # For class nodes we still recurse to capture nested
                    # method definitions as separate, finer-grained chunks.
                    if target_types[node.type] in ("class", "impl"):
                        for child in node.children:
                            self._walk(
                                child, code_bytes, file_path, language,
                                target_types, chunks, visited_bytes,
                            )
                    return
        for child in node.children:
            self._walk(
                child, code_bytes, file_path, language,
                target_types, chunks, visited_bytes,
            )

    def _node_to_chunk(
        self,
        node,
        code_bytes: bytes,
        file_path: str,
        language: str,
        chunk_type: str,
    ) -> Optional[CodeChunk]:
        """Convert an AST node to a ``CodeChunk``."""
        text = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        if not text.strip():
            return None

        # Maximum chunk size is bounded to this multiple of chunk_size.
        # Very large AST nodes (e.g. a class with hundreds of methods) are
        # trimmed to avoid overwhelming the embedding model.
        MAX_CHUNK_SIZE_MULTIPLIER = 3

        # If the chunk is too large, trim it
        max_chars = self.chunk_size * MAX_CHUNK_SIZE_MULTIPLIER
        if len(text) > max_chars:
            text = text[:max_chars]

        name = _get_node_name_for_language(node, language, code_bytes)
        parent_class = _find_parent_class(node, code_bytes)

        start_line = node.start_point[0] + 1  # 1-indexed
        end_line = node.end_point[0] + 1

        return CodeChunk(
            text=text,
            file_path=file_path,
            language=language,
            chunk_type=chunk_type,
            function_name=name if chunk_type in ("function", "method", "impl") else None,
            class_name=name if chunk_type == "class" else parent_class,
            start_line=start_line,
            end_line=end_line,
            metadata={
                "node_type": node.type,
            },
        )

    # ------------------------------------------------------------------
    # Fixed-length fallback
    # ------------------------------------------------------------------

    def _fixed_length_split(
        self, text: str, file_path: str, language: str
    ) -> List[CodeChunk]:
        """
        Split *text* into overlapping fixed-length chunks (by characters).
        Used for non-code files and unsupported languages.
        """
        if not text.strip():
            return []

        chunks: List[CodeChunk] = []
        step = max(1, self.chunk_size - self.chunk_overlap)
        lines = text.splitlines(keepends=True)

        current: List[str] = []
        current_len = 0
        chunk_start_line = 1

        for line_no, line in enumerate(lines, start=1):
            current.append(line)
            current_len += len(line)

            if current_len >= self.chunk_size:
                chunk_text = "".join(current)
                chunks.append(
                    CodeChunk(
                        text=chunk_text,
                        file_path=file_path,
                        language=language,
                        chunk_type="fixed_length",
                        start_line=chunk_start_line,
                        end_line=line_no,
                    )
                )
                # Keep the tail for overlap
                overlap_chars = 0
                kept: List[str] = []
                for ol in reversed(current):
                    overlap_chars += len(ol)
                    kept.insert(0, ol)
                    if overlap_chars >= self.chunk_overlap:
                        break
                current = kept
                current_len = sum(len(l) for l in current)
                chunk_start_line = line_no - len(kept) + 1

        if current and "".join(current).strip():
            chunks.append(
                CodeChunk(
                    text="".join(current),
                    file_path=file_path,
                    language=language,
                    chunk_type="fixed_length",
                    start_line=chunk_start_line,
                    end_line=len(lines),
                )
            )

        return chunks if chunks else [
            CodeChunk(
                text=text,
                file_path=file_path,
                language=language,
                chunk_type="fixed_length",
                start_line=1,
                end_line=len(lines),
            )
        ]


# ---------------------------------------------------------------------------
# Module-level convenience instance
# ---------------------------------------------------------------------------

_default_splitter = TreeSitterCodeSplitter()


def split_code_file(code: str, file_path: str, extension: str) -> List[CodeChunk]:
    """
    Convenience function: split a code file using the default splitter.

    Args:
        code: Source code string.
        file_path: Relative path used as metadata.
        extension: File extension (with or without leading dot).

    Returns:
        List of ``CodeChunk`` objects.
    """
    language = EXTENSION_TO_LANGUAGE.get(extension.lstrip(".").lower())
    if language is None:
        language = extension.lstrip(".").lower() or "unknown"
    return _default_splitter.split_code(code, file_path, language)


def split_text_fixed(
    text: str,
    file_path: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> List[CodeChunk]:
    """
    Fixed-length (character-based) splitting for non-code files.

    Args:
        text: Document text.
        file_path: Used for metadata.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between adjacent chunks.

    Returns:
        List of ``CodeChunk`` objects with ``chunk_type='fixed_length'``.
    """
    splitter = TreeSitterCodeSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter._fixed_length_split(text, file_path, "text")
