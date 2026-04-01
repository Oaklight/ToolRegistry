"""Unit tests for ToolSearchTool."""

import pytest

from toolregistry import Tool, ToolMetadata, ToolRegistry, ToolSearchTool, ToolTag


# ── helpers ──────────────────────────────────────────────────────────


def _make_registry() -> ToolRegistry:
    """Build a registry with several diverse tools for search tests."""
    registry = ToolRegistry()

    def add_numbers(a: int, b: int) -> int:
        """Add two numbers together and return the sum."""
        return a + b

    def multiply_numbers(x: float, y: float) -> float:
        """Multiply two numbers and return the product."""
        return x * y

    def read_file(path: str) -> str:
        """Read the contents of a file from the filesystem."""
        return f"contents of {path}"

    def send_email(to: str, subject: str, body: str) -> str:
        """Send an email message to a recipient."""
        return "sent"

    def search_web(query: str, max_results: int = 10) -> list:
        """Search the web using a search engine."""
        return []

    registry.register(add_numbers)
    registry.register(multiply_numbers)
    registry.register(
        Tool.from_function(
            read_file,
            metadata=ToolMetadata(
                tags={ToolTag.FILE_SYSTEM, ToolTag.READ_ONLY},
                search_hint="open load text content",
            ),
        )
    )
    registry.register(
        Tool.from_function(
            send_email,
            metadata=ToolMetadata(tags={ToolTag.NETWORK}),
        )
    )
    registry.register(
        Tool.from_function(
            search_web,
            metadata=ToolMetadata(
                tags={ToolTag.NETWORK},
                search_hint="google bing internet browse",
            ),
        )
    )
    return registry


@pytest.fixture
def search_registry():
    """Registry populated with diverse tools."""
    return _make_registry()


@pytest.fixture
def searcher(search_registry):
    """ToolSearchTool instance built from the search registry."""
    return ToolSearchTool(search_registry)


# ── tests ────────────────────────────────────────────────────────────


class TestToolSearchTool:
    """Test cases for ToolSearchTool."""

    def test_search_by_name(self, searcher):
        """Search should find tools by name tokens."""
        results = searcher.search("add numbers")
        assert len(results) > 0
        assert results[0]["name"] == "add_numbers"

    def test_search_by_description(self, searcher):
        """Search should find tools by description keywords."""
        results = searcher.search("email message recipient")
        assert len(results) > 0
        assert results[0]["name"] == "send_email"

    def test_search_by_tags(self, searcher):
        """Search should find tools by tag names."""
        results = searcher.search("file_system")
        names = [r["name"] for r in results]
        assert "read_file" in names

    def test_search_by_params(self, searcher):
        """Search should find tools by parameter names."""
        results = searcher.search("subject body")
        assert len(results) > 0
        assert results[0]["name"] == "send_email"

    def test_search_by_hint(self, searcher):
        """Search should find tools by search_hint keywords."""
        results = searcher.search("google internet browse")
        assert len(results) > 0
        assert results[0]["name"] == "search_web"

    def test_search_returns_deferred_flag(self):
        """Deferred tools should have deferred=True in results."""
        registry = ToolRegistry()

        def hidden_tool(x: int) -> int:
            """A tool that should be deferred."""
            return x

        registry.register(
            Tool.from_function(
                hidden_tool,
                metadata=ToolMetadata(defer=True),
            )
        )
        searcher = ToolSearchTool(registry)
        results = searcher.search("hidden tool deferred")
        assert len(results) > 0
        assert results[0]["deferred"] is True

    def test_search_top_k(self, searcher):
        """top_k should limit the number of results."""
        results = searcher.search("numbers", top_k=1)
        assert len(results) <= 1

    def test_search_no_results(self, searcher):
        """Unrelated query should return empty list."""
        results = searcher.search("xyzzy_nonexistent_gibberish")
        assert results == []

    def test_rebuild_index(self, search_registry):
        """After adding a new tool, rebuild_index should find it."""
        searcher = ToolSearchTool(search_registry)

        def compress_file(path: str) -> str:
            """Compress a file into a zip archive."""
            return "compressed"

        search_registry.register(
            Tool.from_function(
                compress_file,
                metadata=ToolMetadata(search_hint="zip archive gzip tar"),
            )
        )
        searcher.rebuild_index()

        results = searcher.search("compress zip archive")
        assert len(results) > 0
        assert results[0]["name"] == "compress_file"

    def test_empty_registry(self):
        """ToolSearchTool should handle an empty registry gracefully."""
        registry = ToolRegistry()
        searcher = ToolSearchTool(registry)
        results = searcher.search("anything")
        assert results == []

    def test_search_result_fields(self, searcher):
        """Each result dict should contain all expected keys."""
        results = searcher.search("add")
        assert len(results) > 0
        result = results[0]
        assert "name" in result
        assert "description" in result
        assert "score" in result
        assert "namespace" in result
        assert "deferred" in result
        assert isinstance(result["score"], float)
        assert isinstance(result["deferred"], bool)

    def test_search_with_namespace(self):
        """Tools with namespace should have it in results."""
        registry = ToolRegistry()

        def my_func(x: int) -> int:
            """A namespaced tool."""
            return x

        registry.register(my_func, namespace="math")
        searcher = ToolSearchTool(registry)
        results = searcher.search("namespaced math")
        assert len(results) > 0
        assert results[0]["namespace"] == "math"
