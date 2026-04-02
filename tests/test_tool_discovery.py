"""Unit tests for ToolDiscoveryTool."""

import pytest

from toolregistry import Tool, ToolMetadata, ToolRegistry, ToolDiscoveryTool, ToolTag


# -- helpers ------------------------------------------------------------------


def _make_registry() -> ToolRegistry:
    """Build a registry with several diverse tools for discovery tests."""
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
def discovery_registry():
    """Registry populated with diverse tools."""
    return _make_registry()


@pytest.fixture
def discoverer(discovery_registry):
    """ToolDiscoveryTool instance built from the discovery registry."""
    return ToolDiscoveryTool(discovery_registry)


# -- tests: fuzzy search (BM25) ----------------------------------------------


class TestToolDiscoveryFuzzy:
    """Test cases for ToolDiscoveryTool fuzzy (BM25) search."""

    def test_discover_by_name(self, discoverer):
        """Discover should find tools by name tokens."""
        results = discoverer.discover("add numbers")
        assert len(results) > 0
        assert results[0]["name"] == "add_numbers"

    def test_discover_by_description(self, discoverer):
        """Discover should find tools by description keywords."""
        results = discoverer.discover("email message recipient")
        assert len(results) > 0
        assert results[0]["name"] == "send_email"

    def test_discover_by_tags(self, discoverer):
        """Discover should find tools by tag names."""
        results = discoverer.discover("file_system")
        names = [r["name"] for r in results]
        assert "read_file" in names

    def test_discover_by_params(self, discoverer):
        """Discover should find tools by parameter names."""
        results = discoverer.discover("subject body")
        assert len(results) > 0
        assert results[0]["name"] == "send_email"

    def test_discover_by_hint(self, discoverer):
        """Discover should find tools by search_hint keywords."""
        results = discoverer.discover("google internet browse")
        assert len(results) > 0
        assert results[0]["name"] == "search_web"

    def test_discover_returns_deferred_flag(self):
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
        discoverer = ToolDiscoveryTool(registry)
        results = discoverer.discover("hidden tool deferred")
        assert len(results) > 0
        assert results[0]["deferred"] is True

    def test_discover_top_k(self, discoverer):
        """top_k should limit the number of results."""
        results = discoverer.discover("numbers", top_k=1)
        assert len(results) <= 1

    def test_discover_no_results(self, discoverer):
        """Unrelated query should return empty list."""
        results = discoverer.discover("xyzzy_nonexistent_gibberish")
        assert results == []

    def test_rebuild_index(self, discovery_registry):
        """After adding a new tool, rebuild_index should find it."""
        discoverer = ToolDiscoveryTool(discovery_registry)

        def compress_file(path: str) -> str:
            """Compress a file into a zip archive."""
            return "compressed"

        discovery_registry.register(
            Tool.from_function(
                compress_file,
                metadata=ToolMetadata(search_hint="zip archive gzip tar"),
            )
        )
        discoverer.rebuild_index()

        results = discoverer.discover("compress zip archive")
        assert len(results) > 0
        assert results[0]["name"] == "compress_file"

    def test_empty_registry(self):
        """ToolDiscoveryTool should handle an empty registry gracefully."""
        registry = ToolRegistry()
        discoverer = ToolDiscoveryTool(registry)
        results = discoverer.discover("anything")
        assert results == []

    def test_discover_result_fields(self, discoverer):
        """Each result dict should contain all expected keys."""
        results = discoverer.discover("add")
        assert len(results) > 0
        result = results[0]
        assert "name" in result
        assert "description" in result
        assert "score" in result
        assert "namespace" in result
        assert "deferred" in result
        assert isinstance(result["score"], float)
        assert isinstance(result["deferred"], bool)

    def test_discover_with_namespace(self):
        """Tools with namespace should have it in results."""
        registry = ToolRegistry()

        def my_func(x: int) -> int:
            """A namespaced tool."""
            return x

        registry.register(my_func, namespace="math")
        discoverer = ToolDiscoveryTool(registry)
        results = discoverer.discover("namespaced math")
        assert len(results) > 0
        assert results[0]["namespace"] == "math"

    def test_discover_returns_schema_for_deferred(self):
        """Deferred tools should include schema in fuzzy results."""
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
        discoverer = ToolDiscoveryTool(registry)
        results = discoverer.discover("hidden tool")
        assert len(results) > 0
        assert results[0]["deferred"] is True
        assert "schema" in results[0]
        schema = results[0]["schema"]
        # Schema should be a valid tool definition dict
        assert "function" in schema or "name" in schema

    def test_discover_no_schema_for_non_deferred(self):
        """Non-deferred tools should not include schema in fuzzy results."""
        registry = ToolRegistry()

        def normal_tool(x: int) -> int:
            """A normal tool."""
            return x

        registry.register(normal_tool)
        discoverer = ToolDiscoveryTool(registry)
        results = discoverer.discover("normal tool")
        assert len(results) > 0
        assert results[0]["deferred"] is False
        assert "schema" not in results[0]


# -- tests: exact match ------------------------------------------------------


class TestToolDiscoveryExact:
    """Test cases for exact-match discovery."""

    def test_discover_exact_match(self):
        """Exact tool name should return a single result with full schema."""
        registry = ToolRegistry()

        def add_numbers(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        registry.register(add_numbers)
        discoverer = ToolDiscoveryTool(registry)
        results = discoverer.discover("add_numbers")
        assert len(results) == 1
        result = results[0]
        assert result["name"] == "add_numbers"
        assert result["score"] == 1.0
        assert "schema" in result

    def test_discover_exact_match_deferred(self):
        """Exact match on deferred tool returns full schema."""
        registry = ToolRegistry()

        def hidden_tool(x: int) -> int:
            """A deferred tool."""
            return x

        registry.register(
            Tool.from_function(hidden_tool, metadata=ToolMetadata(defer=True))
        )
        discoverer = ToolDiscoveryTool(registry)
        results = discoverer.discover("hidden_tool")
        assert len(results) == 1
        assert results[0]["deferred"] is True
        assert "schema" in results[0]

    def test_discover_exact_match_non_deferred_includes_schema(self):
        """Exact match on non-deferred tool also returns schema."""
        registry = ToolRegistry()

        def my_func(x: int) -> int:
            """Some tool."""
            return x

        registry.register(my_func)
        discoverer = ToolDiscoveryTool(registry)
        results = discoverer.discover("my_func")
        assert len(results) == 1
        assert results[0]["deferred"] is False
        assert "schema" in results[0]

    def test_discover_exact_match_skips_self(self):
        """Exact match on 'discover_tools' should not return the tool itself."""
        registry = ToolRegistry()

        def dummy(x: int) -> int:
            """Dummy."""
            return x

        registry.register(dummy)
        registry.enable_tool_discovery()

        discoverer = registry._tool_discovery
        results = discoverer.discover("discover_tools")
        # Should not return discover_tools as an exact match
        names = [r["name"] for r in results]
        assert "discover_tools" not in names

    def test_discover_fuzzy_fallback(self):
        """Non-exact query falls back to BM25 fuzzy search."""
        registry = ToolRegistry()

        def calculate_sum(a: int, b: int) -> int:
            """Calculate the sum of two integers."""
            return a + b

        registry.register(calculate_sum)
        discoverer = ToolDiscoveryTool(registry)
        # "calculate sum" is not an exact tool name
        results = discoverer.discover("calculate sum")
        assert len(results) > 0
        assert results[0]["name"] == "calculate_sum"
        # Fuzzy results don't include schema for non-deferred
        assert "schema" not in results[0]


# -- tests: integration with ToolRegistry ------------------------------------


class TestToolDiscoveryIntegration:
    """Test cases for enable_tool_discovery() / disable_tool_discovery()."""

    def test_enable_tool_discovery(self):
        """After enable_tool_discovery(), discover_tools appears in schemas."""
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add numbers."""
            return a + b

        registry.register(add)
        registry.enable_tool_discovery()

        schemas = registry.get_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "discover_tools" in names

    def test_disable_tool_discovery(self):
        """After disable_tool_discovery(), discover_tools is removed."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()
        registry.disable_tool_discovery()

        schemas = registry.get_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "discover_tools" not in names

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

    def test_discovery_auto_rebuild(self):
        """Registering new tools should auto-rebuild the discovery index."""
        registry = ToolRegistry()

        def first(x: int) -> int:
            """The first tool."""
            return x

        registry.register(first)
        registry.enable_tool_discovery()

        # Register a new tool after enabling discovery
        def second(y: int) -> int:
            """The second tool."""
            return y

        registry.register(second)

        discoverer = registry._tool_discovery
        results = discoverer.discover("second tool")
        assert len(results) > 0
        assert results[0]["name"] == "second"

    def test_tool_discovery_init_param(self):
        """ToolRegistry(tool_discovery=True) should enable discovery."""
        registry = ToolRegistry(tool_discovery=True)

        def my_func(x: int) -> int:
            """A tool."""
            return x

        registry.register(my_func)

        assert registry._tool_discovery is not None
        schemas = registry.get_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "discover_tools" in names

    def test_discovery_tool_not_deferred(self):
        """The discovery tool itself should not be deferred."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()

        # Even with include_deferred=False, discover_tools should appear
        schemas = registry.get_schemas(include_deferred=False)
        names = [s["function"]["name"] for s in schemas]
        assert "discover_tools" in names

    def test_discovery_tool_not_in_own_results(self):
        """discover_tools should not appear in its own fuzzy results."""
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add numbers."""
            return a + b

        registry.register(add)
        registry.enable_tool_discovery()

        discoverer = registry._tool_discovery
        results = discoverer.discover("discover tools")
        result_names = [r["name"] for r in results]
        assert "discover_tools" not in result_names

    def test_enable_idempotent(self):
        """Calling enable_tool_discovery() twice returns the same instance."""
        registry = ToolRegistry()
        d1 = registry.enable_tool_discovery()
        d2 = registry.enable_tool_discovery()
        assert d1 is d2


# -- tests: get_deferred_summaries() -----------------------------------------


class TestGetDeferredSummaries:
    """Test cases for ToolRegistry.get_deferred_summaries()."""

    def test_returns_deferred_tools_only(self):
        """Only deferred tools should appear in summaries."""
        registry = ToolRegistry()

        def visible(x: int) -> int:
            """A visible tool."""
            return x

        def hidden(x: int) -> int:
            """A hidden deferred tool. It does many things."""
            return x

        registry.register(visible)
        registry.register(Tool.from_function(hidden, metadata=ToolMetadata(defer=True)))

        summaries = registry.get_deferred_summaries()
        names = [s["name"] for s in summaries]
        assert "hidden" in names
        assert "visible" not in names

    def test_first_sentence_truncation(self):
        """Description should be truncated to the first sentence."""
        registry = ToolRegistry()

        def my_tool(x: int) -> int:
            """Read a file from disk. Supports multiple encodings and formats."""
            return x

        registry.register(
            Tool.from_function(my_tool, metadata=ToolMetadata(defer=True))
        )

        summaries = registry.get_deferred_summaries()
        assert len(summaries) == 1
        assert summaries[0]["description"] == "Read a file from disk."

    def test_single_sentence_no_truncation(self):
        """Single sentence without period-space should be kept as-is."""
        registry = ToolRegistry()

        def my_tool(x: int) -> int:
            """Read a file from disk"""
            return x

        registry.register(
            Tool.from_function(my_tool, metadata=ToolMetadata(defer=True))
        )

        summaries = registry.get_deferred_summaries()
        assert summaries[0]["description"] == "Read a file from disk"

    def test_multiline_uses_first_line(self):
        """Multi-line descriptions should use only the first line."""
        registry = ToolRegistry()

        def my_tool(x: int) -> int:
            """Read a file from disk.

            This function reads files from the local filesystem and
            returns their contents as a string.
            """
            return x

        registry.register(
            Tool.from_function(my_tool, metadata=ToolMetadata(defer=True))
        )

        summaries = registry.get_deferred_summaries()
        assert summaries[0]["description"] == "Read a file from disk."

    def test_includes_namespace(self):
        """Summaries should include namespace info."""
        registry = ToolRegistry()

        def my_tool(x: int) -> int:
            """A deferred tool."""
            return x

        registry.register(
            Tool.from_function(my_tool, metadata=ToolMetadata(defer=True)),
            namespace="utils",
        )

        summaries = registry.get_deferred_summaries()
        assert len(summaries) == 1
        assert summaries[0]["namespace"] == "utils"

    def test_excludes_disabled_deferred_tools(self):
        """Disabled deferred tools should not appear in summaries."""
        registry = ToolRegistry()

        def my_tool(x: int) -> int:
            """A deferred tool."""
            return x

        registry.register(
            Tool.from_function(my_tool, metadata=ToolMetadata(defer=True))
        )
        registry.disable("my_tool")

        summaries = registry.get_deferred_summaries()
        assert len(summaries) == 0

    def test_empty_registry(self):
        """Empty registry should return empty list."""
        registry = ToolRegistry()
        assert registry.get_deferred_summaries() == []

    def test_no_deferred_tools(self):
        """Registry with no deferred tools returns empty list."""
        registry = ToolRegistry()

        def normal(x: int) -> int:
            """Normal tool."""
            return x

        registry.register(normal)
        assert registry.get_deferred_summaries() == []
