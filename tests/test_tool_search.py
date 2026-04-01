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

    def test_search_returns_schema_for_deferred(self):
        """Deferred tools should include schema in search results."""
        registry = ToolRegistry()

        def hidden_tool(x: int) -> int:
            """A deferred tool with params."""
            return x

        registry.register(
            Tool.from_function(
                hidden_tool,
                metadata=ToolMetadata(defer=True),
            )
        )
        searcher = ToolSearchTool(registry)
        results = searcher.search("hidden tool")
        assert len(results) > 0
        assert results[0]["deferred"] is True
        assert "schema" in results[0]
        schema = results[0]["schema"]
        # Schema should be a valid tool definition dict
        assert "function" in schema or "name" in schema

    def test_search_no_schema_for_non_deferred(self):
        """Non-deferred tools should not include schema in results."""
        registry = ToolRegistry()

        def normal_tool(x: int) -> int:
            """A normal tool."""
            return x

        registry.register(normal_tool)
        searcher = ToolSearchTool(registry)
        results = searcher.search("normal tool")
        assert len(results) > 0
        assert results[0]["deferred"] is False
        assert "schema" not in results[0]


class TestToolSearchIntegration:
    """Test cases for enable_tool_search() / disable_tool_search()."""

    def test_enable_tool_search(self):
        """After enable_tool_search(), search_tools appears in schemas."""
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add numbers."""
            return a + b

        registry.register(add)
        registry.enable_tool_search()

        schemas = registry.get_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "search_tools" in names

    def test_disable_tool_search(self):
        """After disable_tool_search(), search_tools is removed."""
        registry = ToolRegistry()
        registry.enable_tool_search()
        registry.disable_tool_search()

        schemas = registry.get_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "search_tools" not in names

    def test_get_schemas_include_deferred_false(self):
        """include_deferred=False should exclude deferred tools."""
        registry = ToolRegistry()

        def visible(x: int) -> int:
            """Visible tool."""
            return x

        def hidden(x: int) -> int:
            """Hidden deferred tool."""
            return x

        registry.register(visible)
        registry.register(Tool.from_function(hidden, metadata=ToolMetadata(defer=True)))

        all_schemas = registry.get_schemas()
        filtered = registry.get_schemas(include_deferred=False)

        all_names = [s["function"]["name"] for s in all_schemas]
        filtered_names = [s["function"]["name"] for s in filtered]

        assert "hidden" in all_names
        assert "hidden" not in filtered_names
        assert "visible" in filtered_names

    def test_get_schemas_include_deferred_default(self):
        """Default include_deferred=True preserves backward compat."""
        registry = ToolRegistry()

        def hidden(x: int) -> int:
            """Hidden deferred tool."""
            return x

        registry.register(Tool.from_function(hidden, metadata=ToolMetadata(defer=True)))

        schemas = registry.get_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "hidden" in names

    def test_search_auto_rebuild(self):
        """Registering new tools should auto-rebuild the search index."""
        registry = ToolRegistry()

        def first(x: int) -> int:
            """The first tool."""
            return x

        registry.register(first)
        registry.enable_tool_search()

        # Register a new tool after enabling search
        def second(y: int) -> int:
            """The second tool."""
            return y

        registry.register(second)

        searcher = registry._tool_search
        results = searcher.search("second tool")
        assert len(results) > 0
        assert results[0]["name"] == "second"

    def test_tool_search_init_param(self):
        """ToolRegistry(tool_search=True) should enable search."""
        registry = ToolRegistry(tool_search=True)

        def my_func(x: int) -> int:
            """A tool."""
            return x

        registry.register(my_func)

        assert registry._tool_search is not None
        schemas = registry.get_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "search_tools" in names

    def test_search_tool_not_deferred(self):
        """The search tool itself should not be deferred."""
        registry = ToolRegistry()
        registry.enable_tool_search()

        # Even with include_deferred=False, search_tools should appear
        schemas = registry.get_schemas(include_deferred=False)
        names = [s["function"]["name"] for s in schemas]
        assert "search_tools" in names

    def test_search_tool_not_in_own_results(self):
        """search_tools should not appear in its own search results."""
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add numbers."""
            return a + b

        registry.register(add)
        registry.enable_tool_search()

        searcher = registry._tool_search
        results = searcher.search("search tools")
        result_names = [r["name"] for r in results]
        assert "search_tools" not in result_names

    def test_enable_idempotent(self):
        """Calling enable_tool_search() twice returns the same instance."""
        registry = ToolRegistry()
        s1 = registry.enable_tool_search()
        s2 = registry.enable_tool_search()
        assert s1 is s2
