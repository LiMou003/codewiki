"""
Unit tests for the Tree-sitter based code splitter (api/code_splitter.py).
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from api.code_splitter import (
    TreeSitterCodeSplitter,
    CodeChunk,
    EXTENSION_TO_LANGUAGE,
    split_code_file,
    split_text_fixed,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PYTHON_SOURCE = '''\
class Greeter:
    """A simple greeter class."""

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}!"


def standalone_function(x: int, y: int) -> int:
    """Return the sum of x and y."""
    return x + y
'''

JAVASCRIPT_SOURCE = '''\
function greet(name) {
    return `Hello, ${name}!`;
}

class MyClass {
    constructor(x) {
        this.x = x;
    }

    getValue() {
        return this.x;
    }
}
'''

JAVA_SOURCE = '''\
public class Calculator {
    private int value;

    public Calculator(int initial) {
        this.value = initial;
    }

    public int add(int x) {
        return this.value + x;
    }
}
'''

GO_SOURCE = '''\
package main

func Add(a int, b int) int {
    return a + b
}

type Counter struct {
    count int
}

func (c Counter) Increment() int {
    return c.count + 1
}
'''

RUST_SOURCE = '''\
fn add(a: i32, b: i32) -> i32 {
    a + b
}

struct Point {
    x: f64,
    y: f64,
}

impl Point {
    fn distance(&self) -> f64 {
        (self.x * self.x + self.y * self.y).sqrt()
    }
}
'''

CPP_SOURCE = '''\
int add(int a, int b) {
    return a + b;
}

class Vector {
public:
    float x, y;
    Vector(float x, float y) : x(x), y(y) {}
};
'''

TYPESCRIPT_SOURCE = '''\
function greet(name: string): string {
    return `Hello, ${name}!`;
}

class Person {
    constructor(private name: string) {}

    getName(): string {
        return this.name;
    }
}
'''


# ---------------------------------------------------------------------------
# Extension mapping tests
# ---------------------------------------------------------------------------

class TestExtensionMapping:
    def test_python(self):
        assert EXTENSION_TO_LANGUAGE["py"] == "python"

    def test_javascript(self):
        assert EXTENSION_TO_LANGUAGE["js"] == "javascript"
        assert EXTENSION_TO_LANGUAGE["jsx"] == "javascript"

    def test_typescript(self):
        assert EXTENSION_TO_LANGUAGE["ts"] == "typescript"
        assert EXTENSION_TO_LANGUAGE["tsx"] == "tsx"

    def test_java(self):
        assert EXTENSION_TO_LANGUAGE["java"] == "java"

    def test_go(self):
        assert EXTENSION_TO_LANGUAGE["go"] == "go"

    def test_rust(self):
        assert EXTENSION_TO_LANGUAGE["rs"] == "rust"

    def test_cpp(self):
        assert EXTENSION_TO_LANGUAGE["cpp"] == "cpp"
        assert EXTENSION_TO_LANGUAGE["cc"] == "cpp"
        assert EXTENSION_TO_LANGUAGE["hpp"] == "cpp"

    def test_c(self):
        assert EXTENSION_TO_LANGUAGE["c"] == "c"
        assert EXTENSION_TO_LANGUAGE["h"] == "c"

    def test_csharp(self):
        assert EXTENSION_TO_LANGUAGE["cs"] == "c_sharp"


# ---------------------------------------------------------------------------
# Python splitting tests
# ---------------------------------------------------------------------------

class TestPythonSplitter:
    def setup_method(self):
        self.splitter = TreeSitterCodeSplitter()

    def test_extracts_functions(self):
        chunks = self.splitter.split_code(PYTHON_SOURCE, "test.py", "python")
        func_names = {c.function_name for c in chunks if c.chunk_type == "function"}
        assert "standalone_function" in func_names

    def test_extracts_class(self):
        chunks = self.splitter.split_code(PYTHON_SOURCE, "test.py", "python")
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert any(c.class_name == "Greeter" for c in class_chunks)

    def test_extracts_methods(self):
        chunks = self.splitter.split_code(PYTHON_SOURCE, "test.py", "python")
        all_names = {c.function_name for c in chunks if c.function_name}
        assert "__init__" in all_names or "greet" in all_names

    def test_chunk_has_text(self):
        chunks = self.splitter.split_code(PYTHON_SOURCE, "test.py", "python")
        for chunk in chunks:
            assert chunk.text.strip()

    def test_chunk_has_file_path(self):
        chunks = self.splitter.split_code(PYTHON_SOURCE, "test.py", "python")
        for chunk in chunks:
            assert chunk.file_path == "test.py"

    def test_chunk_has_line_numbers(self):
        chunks = self.splitter.split_code(PYTHON_SOURCE, "test.py", "python")
        for chunk in chunks:
            assert chunk.start_line >= 1
            assert chunk.end_line >= chunk.start_line

    def test_chunk_language_set(self):
        chunks = self.splitter.split_code(PYTHON_SOURCE, "test.py", "python")
        for chunk in chunks:
            assert chunk.language == "python"


# ---------------------------------------------------------------------------
# JavaScript splitting tests
# ---------------------------------------------------------------------------

class TestJavaScriptSplitter:
    def setup_method(self):
        self.splitter = TreeSitterCodeSplitter()

    def test_extracts_function_declaration(self):
        chunks = self.splitter.split_code(JAVASCRIPT_SOURCE, "test.js", "javascript")
        func_names = {c.function_name for c in chunks if c.chunk_type == "function"}
        assert "greet" in func_names

    def test_extracts_class(self):
        chunks = self.splitter.split_code(JAVASCRIPT_SOURCE, "test.js", "javascript")
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert any(c.class_name == "MyClass" for c in class_chunks)


# ---------------------------------------------------------------------------
# Java splitting tests
# ---------------------------------------------------------------------------

class TestJavaSplitter:
    def setup_method(self):
        self.splitter = TreeSitterCodeSplitter()

    def test_extracts_class(self):
        chunks = self.splitter.split_code(JAVA_SOURCE, "Calculator.java", "java")
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert any(c.class_name == "Calculator" for c in class_chunks)

    def test_extracts_methods(self):
        chunks = self.splitter.split_code(JAVA_SOURCE, "Calculator.java", "java")
        method_names = {c.function_name for c in chunks if c.chunk_type == "function"}
        assert "add" in method_names


# ---------------------------------------------------------------------------
# Go splitting tests
# ---------------------------------------------------------------------------

class TestGoSplitter:
    def setup_method(self):
        self.splitter = TreeSitterCodeSplitter()

    def test_extracts_top_level_function(self):
        chunks = self.splitter.split_code(GO_SOURCE, "main.go", "go")
        func_names = {c.function_name for c in chunks if c.chunk_type == "function"}
        assert "Add" in func_names

    def test_extracts_method(self):
        chunks = self.splitter.split_code(GO_SOURCE, "main.go", "go")
        func_names = {c.function_name for c in chunks if c.chunk_type == "function"}
        assert "Increment" in func_names


# ---------------------------------------------------------------------------
# Rust splitting tests
# ---------------------------------------------------------------------------

class TestRustSplitter:
    def setup_method(self):
        self.splitter = TreeSitterCodeSplitter()

    def test_extracts_function(self):
        chunks = self.splitter.split_code(RUST_SOURCE, "lib.rs", "rust")
        func_names = {c.function_name for c in chunks if c.chunk_type == "function"}
        assert "add" in func_names


# ---------------------------------------------------------------------------
# C/C++ splitting tests
# ---------------------------------------------------------------------------

class TestCppSplitter:
    def setup_method(self):
        self.splitter = TreeSitterCodeSplitter()

    def test_extracts_function(self):
        chunks = self.splitter.split_code(CPP_SOURCE, "main.cpp", "cpp")
        func_names = {c.function_name for c in chunks if c.chunk_type == "function"}
        assert "add" in func_names


# ---------------------------------------------------------------------------
# TypeScript splitting tests
# ---------------------------------------------------------------------------

class TestTypeScriptSplitter:
    def setup_method(self):
        self.splitter = TreeSitterCodeSplitter()

    def test_extracts_function(self):
        chunks = self.splitter.split_code(TYPESCRIPT_SOURCE, "app.ts", "typescript")
        func_names = {c.function_name for c in chunks if c.chunk_type == "function"}
        assert "greet" in func_names

    def test_extracts_class(self):
        chunks = self.splitter.split_code(TYPESCRIPT_SOURCE, "app.ts", "typescript")
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert any(c.class_name == "Person" for c in class_chunks)


# ---------------------------------------------------------------------------
# Fixed-length splitter tests
# ---------------------------------------------------------------------------

class TestFixedLengthSplitter:
    def test_basic_split(self):
        text = "a" * 5000
        chunks = split_text_fixed(text, "readme.md", chunk_size=1000, chunk_overlap=100)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.chunk_type == "fixed_length"

    def test_short_text_single_chunk(self):
        text = "Hello, world!"
        chunks = split_text_fixed(text, "note.txt", chunk_size=1000, chunk_overlap=100)
        assert len(chunks) == 1

    def test_file_path_preserved(self):
        chunks = split_text_fixed("hello " * 500, "doc.txt", chunk_size=200)
        for chunk in chunks:
            assert chunk.file_path == "doc.txt"

    def test_empty_text(self):
        chunks = split_text_fixed("", "empty.txt")
        assert chunks == []

    def test_whitespace_only_text(self):
        chunks = split_text_fixed("   \n\t  ", "ws.txt")
        assert chunks == []


# ---------------------------------------------------------------------------
# Convenience function tests
# ---------------------------------------------------------------------------

class TestSplitCodeFile:
    def test_python_extension(self):
        chunks = split_code_file(PYTHON_SOURCE, "test.py", "py")
        assert any(c.language == "python" for c in chunks)

    def test_unknown_extension_fallback(self):
        chunks = split_code_file("Hello world " * 200, "file.xyz", "xyz")
        # Should fall back to fixed-length splitting
        assert len(chunks) >= 1

    def test_empty_source_no_crash(self):
        chunks = split_code_file("", "empty.py", "py")
        # Empty file should return empty list or fallback list
        assert isinstance(chunks, list)


# ---------------------------------------------------------------------------
# CodeChunk dataclass tests
# ---------------------------------------------------------------------------

class TestCodeChunk:
    def test_defaults(self):
        chunk = CodeChunk(text="hello", file_path="a.py", language="python", chunk_type="function")
        assert chunk.function_name is None
        assert chunk.class_name is None
        assert chunk.start_line == 0
        assert chunk.end_line == 0
        assert chunk.metadata == {}

    def test_metadata_isolated(self):
        c1 = CodeChunk(text="a", file_path="a.py", language="python", chunk_type="function")
        c2 = CodeChunk(text="b", file_path="b.py", language="python", chunk_type="function")
        c1.metadata["key"] = "value"
        assert "key" not in c2.metadata


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
