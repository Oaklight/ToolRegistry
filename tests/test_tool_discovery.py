"""Unit tests for ToolDiscoveryTool."""

import logging

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


class TestToolDiscoveryScoreFloor:
    """Fuzzy hits below a fraction of the best hit are filler (#330)."""

    def test_filler_hits_are_dropped(self, discoverer):
        """'read a file' matches read_file strongly and three tools weakly."""
        results = discoverer.discover("read a file")
        assert [r["name"] for r in results] == ["read_file"]

    def test_close_hits_survive(self, discoverer):
        """A genuinely close second hit (0.39 x best here) is kept."""
        names = [r["name"] for r in discoverer.discover("add numbers")]
        assert names == ["add_numbers", "multiply_numbers"]

    def test_floor_can_be_disabled(self, discovery_registry):
        """min_score_ratio=0 returns the raw top_k list.

        ``max_df_ratio=0`` isolates the score floor: the token filter would
        otherwise remove "a" and shrink this list for a different reason.
        """
        discoverer = ToolDiscoveryTool(
            discovery_registry, min_score_ratio=0.0, max_df_ratio=0.0
        )
        results = discoverer.discover("read a file")
        assert len(results) > 1
        assert results[0]["name"] == "read_file"

    def test_weak_matches_stay_proportional(self, discovery_registry):
        """The floor is relative: when every hit is equally weak, all survive.

        BM25 scores are not comparable across queries (they depend on corpus
        size, IDF and query length), so no absolute cutoff is applied.  A
        query that matches nothing well keeps its near-tied hits rather than
        being silently emptied.  Document-frequency filtering is disabled
        here so this exercises the score floor alone.
        """
        discoverer = ToolDiscoveryTool(discovery_registry, max_df_ratio=0.0)
        results = discoverer.discover("weather forecast for a city")
        assert len(results) > 1
        assert results[0]["score"] < 1.0

    def test_exact_match_is_unaffected(self, discoverer):
        """The exact-name path short-circuits before the floor."""
        results = discoverer.discover("read_file")
        assert len(results) == 1
        assert results[0]["score"] == 1.0
        assert "schema" in results[0]

    def test_ratio_is_validated(self, discovery_registry):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            ToolDiscoveryTool(discovery_registry, min_score_ratio=-0.1)
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            ToolDiscoveryTool(discovery_registry, min_score_ratio=1.5)

    def test_enable_tool_discovery_forwards_the_ratio(self):
        """A deployment can tune or disable the floor when enabling."""
        registry = ToolRegistry()
        discoverer = registry.enable_tool_discovery(min_score_ratio=0.0)
        assert discoverer._min_score_ratio == 0.0


def _make_wide_registry() -> ToolRegistry:
    """A corpus big enough for document-frequency filtering to apply.

    Descriptions deliberately share prose ("the", "a", "for") so a query
    built from those words matches almost everything — the #332 shape.
    """
    registry = ToolRegistry()

    for name, description in (
        ("path_info", "Get metadata for a path on the filesystem."),
        ("list_dir", "List the entries of a directory."),
        ("read_file", "Read the contents of a file for the caller."),
        ("write_file", "Write contents to a file for the caller."),
        ("docker_logs", "Fetch the logs of a running container."),
        ("sql_query", "Run a query against a database."),
        ("json_parse", "Parse a JSON string into an object."),
        ("add_numbers", "Add two numbers for the sum."),
    ):

        def handler(query: str = "") -> str:
            """A tool."""
            return "ok"

        registry.register(
            Tool.from_function(handler, name=name, description=description)
        )
    return registry


class TestToolDiscoveryQueryTokenFilter:
    """Query tokens that appear in most tools carry no signal (#332)."""

    def test_absent_topic_returns_nothing(self):
        """No weather tool ⇒ the query's surviving tokens match nothing."""
        discoverer = ToolDiscoveryTool(_make_wide_registry())
        assert discoverer.discover("weather forecast for a city") == []

    def test_topic_tool_is_found_when_present(self):
        """The same corpus with a weather tool returns only that tool."""
        registry = _make_wide_registry()

        def weather(city: str) -> str:
            """Get the weather forecast for a city."""
            return "sunny"

        registry.register(weather)
        results = ToolDiscoveryTool(registry).discover("weather forecast for a city")
        assert [r["name"] for r in results] == ["weather"]

    def test_stopword_only_query_returns_nothing(self):
        """A query of only ubiquitous words is not a search."""
        registry = ToolRegistry()
        for i in range(6):

            def handler(query: str = "") -> str:
                """A tool for the user of a service."""
                return "ok"

            registry.register(
                Tool.from_function(
                    handler,
                    name=f"tool_{i}",
                    description="A tool for the user of a service.",
                )
            )

        discoverer = ToolDiscoveryTool(registry)
        assert discoverer.discover("the a of") == []

    def test_rare_token_is_kept(self):
        """Common words are dropped, the discriminative one is not."""
        discoverer = ToolDiscoveryTool(_make_wide_registry())
        results = discoverer.discover("the docker logs for a container")
        assert [r["name"] for r in results] == ["docker_logs"]

    def test_filter_can_be_disabled(self):
        """max_df_ratio=0 restores the unfiltered query."""
        discoverer = ToolDiscoveryTool(_make_wide_registry(), max_df_ratio=0.0)
        assert discoverer.discover("weather forecast for a city") != []

    def test_small_corpora_bypass_the_filter(self):
        """With few documents, df is not meaningful; behavior is unchanged."""
        registry = ToolRegistry()

        def only(x: int) -> int:
            """A tool the user likes for a while."""
            return x

        registry.register(only)
        discoverer = ToolDiscoveryTool(registry)
        assert discoverer.discover("a tool") != []

    def test_ratio_validation_rejects_bool(self):
        with pytest.raises(ValueError, match="must be a number"):
            ToolDiscoveryTool(_make_wide_registry(), min_score_ratio=True)
        with pytest.raises(ValueError, match="must be a number"):
            ToolDiscoveryTool(_make_wide_registry(), max_df_ratio=False)


def _make_small_widget_registry() -> ToolRegistry:
    """Four tools where "widgets" appears in two — 50% of the corpus (#334)."""
    registry = ToolRegistry()

    for name, description in (
        ("alpha_tool", "Uses widgets."),
        ("beta_tool", "Uses widgets and gears."),
        ("gamma_tool", "Uses springs."),
        ("delta_tool", "Uses levers."),
    ):

        def handler() -> str:
            """A tool."""
            return "ok"

        registry.register(
            Tool.from_function(handler, name=name, description=description)
        )
    return registry


class TestToolDiscoveryDocumentFrequencyFloor:
    """A token shared by a few tools is signal, not filler (#334)."""

    def test_shared_term_is_findable_in_small_corpus(self):
        """Two of four tools mentioning a term still matches both."""
        discoverer = ToolDiscoveryTool(_make_small_widget_registry())
        assert discoverer._doc_freq["widgets"] == 2
        assert discoverer._doc_count == 4
        names = [r["name"] for r in discoverer.discover("widgets")]
        assert names == ["alpha_tool", "beta_tool"]

    def test_shared_term_survives_alongside_ubiquitous_words(self):
        """The df floor keeps the shared term when a filler is dropped."""
        discoverer = ToolDiscoveryTool(_make_small_widget_registry())
        assert discoverer._filter_query_tokens("uses widgets") == ["widgets"]

    def test_single_token_query_is_never_filtered(self):
        """A one-word query is a keyword, not prose padded with stopwords."""
        registry = ToolRegistry()
        for i in range(6):

            def handler() -> str:
                """A tool."""
                return "ok"

            registry.register(
                Tool.from_function(
                    handler,
                    name=f"tool_{i}",
                    description="Search the service registry.",
                )
            )
        discoverer = ToolDiscoveryTool(registry)
        assert discoverer._doc_freq["search"] == 6
        assert discoverer._filter_query_tokens("search") == ["search"]
        assert discoverer.discover("search") != []


class TestToolDiscoveryIndexFreshness:
    """A discoverer built directly tracks later registry changes (#334)."""

    def test_register_after_construction_is_indexed(self):
        registry = _make_small_widget_registry()
        discoverer = ToolDiscoveryTool(registry)

        def epsilon_tool() -> str:
            """Uses widgets and flanges."""
            return "ok"

        registry.register(epsilon_tool)
        assert [r["name"] for r in discoverer.discover("flanges")] == ["epsilon_tool"]
        assert discoverer._doc_freq["widgets"] == 3
        assert discoverer._doc_count == 5

    def test_unregister_after_construction_leaves_the_index(self):
        registry = _make_small_widget_registry()
        discoverer = ToolDiscoveryTool(registry)
        assert discoverer.discover("gears") != []

        registry._unregister("beta_tool")
        assert discoverer.discover("gears") == []

    def test_close_stops_following_the_registry(self):
        registry = _make_small_widget_registry()
        discoverer = ToolDiscoveryTool(registry)
        discoverer.close()
        discoverer.close()  # idempotent

        def epsilon_tool() -> str:
            """Uses widgets and flanges."""
            return "ok"

        registry.register(epsilon_tool)
        assert discoverer._index_dirty is False
        assert discoverer.discover("flanges") == []

    def test_disable_tool_discovery_unsubscribes(self):
        registry = _make_small_widget_registry()
        discoverer = registry.enable_tool_discovery()
        registry.disable_tool_discovery()
        assert discoverer._closed is True

        def epsilon_tool() -> str:
            """Uses widgets and flanges."""
            return "ok"

        registry.register(epsilon_tool)
        assert discoverer._index_dirty is False


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
        assert discoverer is not None
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

    def test_discover_tools_has_object_parameters_schema(self):
        """discover_tools should have a valid object parameter schema."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()

        tool = registry.get_tool("discover_tools")
        assert tool is not None
        assert tool.parameters["type"] == "object"
        assert set(tool.parameters["properties"]) >= {"query", "top_k", "api_format"}

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
        assert discoverer is not None
        results = discoverer.discover("second tool")
        assert len(results) > 0
        assert results[0]["name"] == "second"

    def test_register_unregister_defer_index_rebuild(self, monkeypatch):
        """REGISTER/UNREGISTER mark the index dirty instead of rebuilding."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        rebuilds: list[int] = []
        original = discoverer.rebuild_index

        def counting_rebuild() -> None:
            rebuilds.append(1)
            original()

        monkeypatch.setattr(discoverer, "rebuild_index", counting_rebuild)

        def make_tool(index: int):
            def tool(x: int) -> int:
                """A searchable tool."""
                return x

            tool.__name__ = f"bulk_tool_{index}"
            return tool

        for i in range(50):
            registry.register(make_tool(i))

        assert rebuilds == []
        assert discoverer._index_dirty is True

        discoverer.discover("bulk_tool_7")
        assert len(rebuilds) == 1
        assert discoverer._index_dirty is False

        # A second discover() on a clean index must not rebuild; without
        # this, a discover() that rebuilds unconditionally would still pass.
        discoverer.discover("bulk_tool_8")
        assert len(rebuilds) == 1

        registry._unregister("bulk_tool_7")
        assert len(rebuilds) == 1
        assert discoverer._index_dirty is True

        discoverer.discover("bulk_tool_9")
        assert len(rebuilds) == 2

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
        assert discoverer is not None
        results = discoverer.discover("discover tools")
        result_names = [r["name"] for r in results]
        assert "discover_tools" not in result_names

    def test_enable_idempotent(self):
        """Calling enable_tool_discovery() twice returns the same instance."""
        registry = ToolRegistry()
        d1 = registry.enable_tool_discovery()
        d2 = registry.enable_tool_discovery()
        assert d1 is d2

    def test_repeated_enable_warns_about_ignored_options(self):
        """A second call that changes a knob must not be silently ignored (#336)."""
        registry = ToolRegistry()
        first = registry.enable_tool_discovery(min_score_ratio=0.5)

        with pytest.warns(UserWarning, match="min_score_ratio=0.0"):
            second = registry.enable_tool_discovery(min_score_ratio=0.0)

        assert second is first
        assert first._min_score_ratio == 0.5

    def test_repeated_enable_warns_for_every_ignored_option(self):
        registry = ToolRegistry()
        registry.enable_tool_discovery()

        with pytest.warns(UserWarning) as record:
            registry.enable_tool_discovery(
                field_weights={"name": 1.0},
                max_df_ratio=0.9,
            )

        message = str(record[0].message)
        assert "field_weights" in message
        assert "max_df_ratio=0.9" in message
        assert "disable_tool_discovery()" in message

    def test_repeated_enable_is_silent_when_options_match(self, recwarn):
        """Idempotent calls (config loaders, fixtures) must stay quiet."""
        registry = ToolRegistry()
        registry.enable_tool_discovery(min_score_ratio=0.0, max_df_ratio=0.4)
        registry.enable_tool_discovery(min_score_ratio=0.0, max_df_ratio=0.4)
        registry.enable_tool_discovery()

        assert [w for w in recwarn if issubclass(w.category, UserWarning)] == []

    def test_reconfigure_after_disable_uses_new_options(self):
        """disable → enable is the supported way to change the settings."""
        registry = ToolRegistry()
        registry.enable_tool_discovery(min_score_ratio=0.5)
        registry.disable_tool_discovery()

        discoverer = registry.enable_tool_discovery(min_score_ratio=0.0)
        assert discoverer._min_score_ratio == 0.0


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


# -- tests: call_deferred ----------------------------------------------------


class TestCallDeferred:
    """Test cases for ToolDiscoveryTool.call_deferred()."""

    def test_call_deferred_success(self):
        """Calling a deferred tool should execute it and return the raw result."""
        registry = ToolRegistry()

        def secret_add(a: int, b: int) -> int:
            """Add two numbers (deferred)."""
            return a + b

        registry.register(
            Tool.from_function(secret_add, metadata=ToolMetadata(defer=True))
        )
        registry.enable_tool_discovery()

        discoverer = registry._tool_discovery
        assert discoverer is not None
        result = discoverer.call_deferred(_target_tool="secret_add", a=3, b=4)
        assert result == 7

    def test_call_deferred_nonexistent_tool(self):
        """Calling a non-existent tool should raise KeyError."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()

        discoverer = registry._tool_discovery
        assert discoverer is not None
        with pytest.raises(KeyError, match="not found"):
            discoverer.call_deferred(_target_tool="no_such_tool")

    def test_call_deferred_non_deferred_tool(self):
        """Calling a non-deferred tool should raise ValueError."""
        registry = ToolRegistry()

        def normal_tool(x: int) -> int:
            """A normal tool."""
            return x

        registry.register(normal_tool)
        registry.enable_tool_discovery()

        discoverer = registry._tool_discovery
        assert discoverer is not None
        with pytest.raises(ValueError, match="not a deferred tool"):
            discoverer.call_deferred(_target_tool="normal_tool", x=5)

    def test_call_deferred_with_validation_error(self):
        """Bad parameters should propagate the exception from _invoke_raw."""
        registry = ToolRegistry()

        def typed_tool(x: int) -> int:
            """Typed deferred tool."""
            return x

        registry.register(
            Tool.from_function(typed_tool, metadata=ToolMetadata(defer=True))
        )
        registry.enable_tool_discovery()

        discoverer = registry._tool_discovery
        assert discoverer is not None
        with pytest.raises(Exception):
            discoverer.call_deferred(_target_tool="typed_tool", x="not_an_int")

    def test_call_deferred_registered_on_enable(self):
        """enable_tool_discovery() should register call_deferred in schemas."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()

        schemas = registry.get_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "call_deferred" in names

    def test_call_deferred_removed_on_disable(self):
        """disable_tool_discovery() should remove call_deferred."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()
        registry.disable_tool_discovery()

        schemas = registry.get_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "call_deferred" not in names
        assert "discover_tools" not in names

    def test_call_deferred_not_deferred_itself(self):
        """call_deferred should not be deferred — it must be in initial schema."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()

        schemas = registry.get_schemas(include_deferred=False)
        names = [s["function"]["name"] for s in schemas]
        assert "call_deferred" in names

    def test_call_deferred_has_additional_properties(self):
        """call_deferred schema should have additionalProperties: true and _target_tool param."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()

        tool = registry.get_tool("call_deferred")
        assert tool is not None
        assert tool.parameters.get("additionalProperties") is True
        assert "_target_tool" in tool.parameters.get("properties", {})

    def test_call_deferred_not_in_discovery_results(self):
        """call_deferred should not appear in discover_tools results."""
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add numbers."""
            return a + b

        registry.register(add)
        registry.enable_tool_discovery()

        discoverer = registry._tool_discovery
        assert discoverer is not None
        results = discoverer.discover("call deferred")
        result_names = [r["name"] for r in results]
        assert "call_deferred" not in result_names

    def test_call_deferred_target_tool_no_collision(self):
        """_target_tool param name should not collide with tool's own params."""
        registry = ToolRegistry()

        def tool_with_tool_name(tool_name: str, value: int) -> str:
            """A deferred tool that has its own tool_name parameter."""
            return f"{tool_name}={value}"

        registry.register(
            Tool.from_function(tool_with_tool_name, metadata=ToolMetadata(defer=True))
        )
        registry.enable_tool_discovery()

        discoverer = registry._tool_discovery
        assert discoverer is not None
        result = discoverer.call_deferred(
            _target_tool="tool_with_tool_name", tool_name="search", value=42
        )
        assert result == "search=42"


# -- tests: enabled/disabled filtering (#276) ---------------------------------


class TestDiscoveryEnabledFiltering:
    """Disabled tools must not be discoverable (#276)."""

    def test_disabled_deferred_tool_excluded_then_restored(self):
        """A disabled deferred tool leaves discover() and summaries, then returns."""
        registry = ToolRegistry()

        def hidden_tool(x: int) -> int:
            """A deferred tool about weather."""
            return x

        registry.register(
            Tool.from_function(hidden_tool, metadata=ToolMetadata(defer=True))
        )
        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        assert [r["name"] for r in discoverer.discover("hidden")] == ["hidden_tool"]
        assert [s["name"] for s in registry.get_deferred_summaries()] == ["hidden_tool"]

        registry.disable("hidden_tool")
        assert discoverer.discover("hidden") == []
        assert registry.get_deferred_summaries() == []

        registry.enable("hidden_tool")
        assert [r["name"] for r in discoverer.discover("hidden")] == ["hidden_tool"]
        assert [s["name"] for s in registry.get_deferred_summaries()] == ["hidden_tool"]

    def test_disabled_tool_exact_match_not_returned(self):
        """The exact-name path must not return a disabled tool."""
        registry = ToolRegistry()

        def my_tool(x: int) -> int:
            """Some tool."""
            return x

        registry.register(my_tool)
        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        registry.disable("my_tool")
        assert discoverer.discover("my_tool") == []

    def test_namespace_disable_excludes_tools(self):
        """Disabling a namespace must drop all of its tools from discovery."""
        registry = ToolRegistry()

        def my_tool(x: int) -> int:
            """A deferred tool."""
            return x

        registry.register(
            Tool.from_function(my_tool, metadata=ToolMetadata(defer=True)),
            namespace="weather",
        )
        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        assert discoverer.discover("weather-my_tool") != []
        assert registry.get_deferred_summaries() != []

        registry.disable("weather")
        assert discoverer.discover("weather-my_tool") == []
        assert registry.get_deferred_summaries() == []

        registry.enable("weather")
        assert discoverer.discover("weather-my_tool") != []
        assert registry.get_deferred_summaries() != []


# -- tests: call_deferred name normalization (#277) ---------------------------


class TestCallDeferredNameNormalization:
    """call_deferred must tolerate client-normalized tool names (#277)."""

    def test_normalized_hyphen_hit(self):
        """'weather_get_current' resolves to the registered hyphenated name."""
        registry = ToolRegistry()

        def get_current(city: str) -> str:
            """Deferred weather tool."""
            return f"weather in {city}"

        registry.register(
            Tool.from_function(get_current, metadata=ToolMetadata(defer=True)),
            namespace="weather",
        )
        assert "weather-get_current" in registry._tools

        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        result = discoverer.call_deferred(
            _target_tool="weather_get_current", city="NYC"
        )
        assert result == "weather in NYC"

    def test_normalized_slash_hit(self):
        """A registered '/' name is reachable through its '_' spelling."""
        registry = ToolRegistry()

        def get_weather(city: str) -> str:
            """Deferred weather tool."""
            return f"weather in {city}"

        registry.register(
            Tool.from_function(
                get_weather,
                name="weather/get",
                metadata=ToolMetadata(defer=True),
            )
        )
        assert "weather/get" in registry._tools

        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        result = discoverer.call_deferred(_target_tool="weather_get", city="LA")
        assert result == "weather in LA"

    def test_miss_includes_suggestions(self):
        """A miss lists close registered names in normalized space."""
        registry = ToolRegistry()

        def now() -> str:
            """Deferred datetime tool."""
            return "now"

        registry.register(
            Tool.from_function(now, metadata=ToolMetadata(defer=True)),
            namespace="datetime",
        )
        assert "datetime-now" in registry._tools

        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        with pytest.raises(KeyError, match="Did you mean: datetime-now"):
            discoverer.call_deferred(_target_tool="datetime_nowx")

    def test_not_deferred_echoes_canonical_name(self):
        """The not-deferred error reports the registered spelling."""
        registry = ToolRegistry()

        def gear(x: int) -> int:
            """A normal tool."""
            return x

        registry.register(Tool.from_function(gear), namespace="normal")
        assert "normal-gear" in registry._tools

        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        with pytest.raises(ValueError, match="'normal-gear' is not a deferred tool"):
            discoverer.call_deferred(_target_tool="normal_gear", x=1)


# -- tests: input validation and CJK search (#278) ----------------------------


class TestDiscoveryInputValidation:
    """discover() must reject empty queries and invalid top_k (#278)."""

    def test_empty_query_raises(self, discoverer):
        """An empty query raises instead of silently returning []."""
        with pytest.raises(ValueError, match="empty query"):
            discoverer.discover("")

    def test_whitespace_query_raises(self, discoverer):
        """A whitespace-only query raises."""
        with pytest.raises(ValueError, match="empty query"):
            discoverer.discover("   ")

    @pytest.mark.parametrize("top_k", [0, -3])
    def test_invalid_top_k_raises(self, discoverer, top_k):
        """top_k below 1 raises instead of being silently ignored."""
        with pytest.raises(ValueError, match="top_k must be >= 1"):
            discoverer.discover("add numbers", top_k=top_k)

    def test_schema_declares_constraints(self):
        """The generated discover_tools schema carries minLength and minimum."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()
        tool = registry.get_tool("discover_tools")
        assert tool is not None
        props = tool.parameters["properties"]
        assert props["query"]["minLength"] == 1
        # ``Match`` fullmatches, so the pattern must span the whole query;
        # ``\S`` alone only accepted one character (#326).
        assert props["query"]["pattern"] == r"[\s\S]*\S[\s\S]*"
        assert props["top_k"]["minimum"] == 1


class TestDiscoveryCjkSearch:
    """Non-English (CJK) queries must match CJK tool descriptions (#278)."""

    def test_cjk_query_returns_weather_tools(self):
        """A CJK query matches a tool described in CJK text."""
        registry = ToolRegistry()

        def weather_get_current(city: str) -> str:
            """查询指定城市的当前天气情况，返回温度与天气描述。"""
            return city

        registry.register(
            Tool.from_function(
                weather_get_current,
                metadata=ToolMetadata(defer=True, search_hint="天气 查询"),
            )
        )
        discoverer = ToolDiscoveryTool(registry)
        names = [r["name"] for r in discoverer.discover("天气")]
        assert "weather_get_current" in names

    def test_ascii_tokenization_unchanged(self):
        """The CJK-aware tokenizer leaves ASCII tokenization identical."""
        from toolregistry._vendor.sparse_search import _default_tokenize
        from toolregistry.llm.discovery import _tokenize_for_search

        for text in [
            "add numbers",
            "read_file",
            "subject body",
            "google bing internet browse",
            "file_system",
        ]:
            assert _tokenize_for_search(text) == _default_tokenize(text)

    def test_cjk_bigrams_generated(self):
        """CJK runs yield within-run character bigrams only."""
        from toolregistry.llm.discovery import _tokenize_for_search

        tokens = _tokenize_for_search("天气 查询")
        assert {"天气", "查询"} <= set(tokens)
        # bigrams must not span the space between the two runs
        assert "气查" not in tokens

    def test_cjk_bigrams_do_not_span_boundaries(self):
        """A separator between CJK runs must not create a boundary bigram."""
        from toolregistry.llm.discovery import _tokenize_for_search

        tokens = _tokenize_for_search("今日天气晴朗，查询温度")
        assert "朗查" not in tokens  # would span the comma
        assert {"天气", "查询"} <= set(tokens)
        assert all("," not in tok and " " not in tok for tok in tokens)

    def test_cjk_query_with_separate_runs_matches(self):
        """Two separate CJK runs in the query still match a CJK tool."""
        registry = ToolRegistry()

        def weather_get_current(city: str) -> str:
            """查询指定城市的当前天气情况。"""
            return city

        registry.register(Tool.from_function(weather_get_current))
        discoverer = ToolDiscoveryTool(registry)
        names = [r["name"] for r in discoverer.discover("城市 天气")]
        assert "weather_get_current" in names


# -- tests: discover() name resolution (#277 / Milo item 2) -------------------


class TestDiscoverNameResolution:
    """discover() must resolve the same spellings call_deferred() accepts."""

    @staticmethod
    def _namespaced_registry():
        registry = ToolRegistry()

        def get_current(city: str) -> str:
            """Weather tool."""
            return city

        registry.register(Tool.from_function(get_current), namespace="weather")
        registry.enable_tool_discovery()
        return registry

    def test_rewritten_spelling_resolves(self):
        """'weather_get_current' resolves to the registered hyphenated name."""
        registry = self._namespaced_registry()
        discoverer = registry._tool_discovery
        assert discoverer is not None
        assert [r["name"] for r in discoverer.discover("weather_get_current")] == [
            "weather-get_current"
        ]

    def test_case_variant_resolves(self):
        """A case-variant spelling resolves to the registered name."""
        registry = self._namespaced_registry()
        discoverer = registry._tool_discovery
        assert discoverer is not None
        assert [r["name"] for r in discoverer.discover("WEATHER-GET_CURRENT")] == [
            "weather-get_current"
        ]

    def test_exact_spelling_wins_when_two_names_collide(self):
        """The exact registered spelling always wins over a normalized match."""
        for order in ("hyphen-first", "underscore-first"):
            registry = ToolRegistry()

            def bar() -> str:
                """Namespaced hyphen tool."""
                return "H"

            def foo_bar() -> str:
                """Flat underscore tool."""
                return "U"

            hyphen = Tool.from_function(bar, metadata=ToolMetadata(defer=True))
            under = Tool.from_function(foo_bar, metadata=ToolMetadata(defer=True))
            if order == "hyphen-first":
                registry.register(hyphen, namespace="foo")  # key foo-bar
                registry.register(under)  # key foo_bar
            else:
                registry.register(under)
                registry.register(hyphen, namespace="foo")
            registry.enable_tool_discovery()
            discoverer = registry._tool_discovery
            assert discoverer is not None

            assert [r["name"] for r in discoverer.discover("foo-bar")] == ["foo-bar"]
            assert [r["name"] for r in discoverer.discover("foo_bar")] == ["foo_bar"]
            # call_deferred must use the same exact-first resolution: the
            # exact registered spelling dispatches to its own tool.
            assert discoverer.call_deferred(_target_tool="foo-bar") == "H"
            assert discoverer.call_deferred(_target_tool="foo_bar") == "U"


# -- tests: lazy index refresh on metadata / bulk changes ---------------------


class TestLazyIndexRefresh:
    """Metadata changes and bulk disables refresh the index lazily."""

    def test_metadata_search_hint_reindexed(self):
        """A new search_hint becomes searchable; the old hint retires."""
        registry = ToolRegistry()

        def probe(value: str = "x") -> str:
            """A probe tool."""
            return value

        registry.register(
            Tool.from_function(
                probe, metadata=ToolMetadata(search_hint="giraffe stripes")
            )
        )
        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        assert [r["name"] for r in discoverer.discover("giraffe")] == ["probe"]

        registry.update_tool_metadata("probe", search_hint="quagga unicorn")

        assert [r["name"] for r in discoverer.discover("quagga unicorn")] == ["probe"]
        assert discoverer.discover("giraffe stripes") == []

    def test_metadata_defer_reflected_in_discover(self):
        """defer=True must show up in discover() as deferred + schema."""
        registry = ToolRegistry()

        def probe(value: str = "x") -> str:
            """A probe tool."""
            return value

        registry.register(probe)
        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        before = discoverer.discover("probe tool")[0]
        assert before["deferred"] is False
        assert "schema" not in before

        registry.update_tool_metadata("probe", defer=True)

        after = discoverer.discover("probe tool")[0]
        assert after["deferred"] is True
        assert "schema" in after
        # Both halves of the discovery contract now agree.
        assert [s["name"] for s in registry.get_deferred_summaries()] == ["probe"]

    def test_bulk_disable_defers_rebuild(self, monkeypatch):
        """N disables must not trigger N index rebuilds."""
        registry = ToolRegistry()
        for i in range(20):
            registry.register(Tool.from_function(lambda i=i: i, name=f"bulk_{i}"))
        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        count = {"n": 0}
        real = discoverer.rebuild_index

        def counting() -> None:
            count["n"] += 1
            real()

        monkeypatch.setattr(discoverer, "rebuild_index", counting)

        for i in range(20):
            registry.disable(f"bulk_{i}")
        assert count["n"] == 0  # lazily deferred, not one rebuild per event

        discoverer.discover("bulk 5")
        assert count["n"] == 1  # one rebuild on the next discover()


# -- tests: plain-string tags (#286 non-blocking) -----------------------------


class TestPlainStringTags:
    """Plain-string tags must not break the discovery index."""

    def test_plain_string_tags_classify_safely(self):
        """ToolMetadata.all_tags accepts plain strings."""
        assert ToolMetadata(tags={"zzz_unique_tag"}).all_tags == {"zzz_unique_tag"}

    def test_update_tags_then_disable_does_not_break_index(self, caplog):
        """A plain-string tag update must not corrupt the index on disable."""
        registry = ToolRegistry()

        def first() -> str:
            """First tool."""
            return "1"

        def second() -> str:
            """Second tool."""
            return "2"

        registry.register(first)
        registry.register(second)
        registry.enable_tool_discovery()
        discoverer = registry._tool_discovery
        assert discoverer is not None

        registry.update_tool_metadata("first", tags=["zzz_unique_tag"])

        with caplog.at_level(logging.WARNING, logger="toolregistry._mixins.callbacks"):
            registry.disable("second")

        assert "raised exception" not in caplog.text
        assert [r["name"] for r in discoverer.discover("first tool")] == ["first"]


# -- tests: model-visible guidance and dependency-free import -----------------


class TestDiscoveryGuidanceAndDeps:
    """The discover_tools description and the pydantic-free import path."""

    def test_description_mentions_matching_scope(self):
        """The description tells the model how queries are matched."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()
        tool = registry.get_tool("discover_tools")
        assert tool is not None
        assert "English" in (tool.description or "")

    def test_import_toolregistry_without_pydantic(self):
        """import toolregistry must work when pydantic is unavailable."""
        import os
        import pathlib
        import subprocess
        import sys
        import textwrap

        import toolregistry as _tr

        src = pathlib.Path(_tr.__file__).resolve().parent.parent
        script = textwrap.dedent("""
            import sys

            class _BlockPydantic:
                def find_spec(self, name, path=None, target=None):
                    if name == "pydantic" or name.startswith("pydantic."):
                        raise ModuleNotFoundError(f"No module named {name!r}")
                    return None

            for mod in [m for m in sys.modules
                        if m == "pydantic" or m.startswith("pydantic.")]:
                del sys.modules[mod]
            sys.meta_path.insert(0, _BlockPydantic())

            import toolregistry
            assert "pydantic" not in sys.modules

            registry = toolregistry.ToolRegistry()
            registry.enable_tool_discovery()
            props = registry.get_tool("discover_tools").parameters["properties"]
            assert props["query"]["minLength"] == 1, props["query"]
            assert props["query"].get("pattern"), props["query"]
            assert props["top_k"]["minimum"] == 1, props["top_k"]
            print("OK")
        """)
        env = dict(os.environ, PYTHONPATH=str(src))
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=env,
        )
        assert proc.returncode == 0, proc.stderr
        assert "OK" in proc.stdout


class TestDiscoverQueryValidation:
    """``discover_tools`` must accept real, multi-word queries (#326).

    ``Match`` validates with ``re.fullmatch``, so the old ``\S`` pattern
    accepted exactly one character. The registered tool is exercised
    through parameter validation, which is where a host call enters.
    """

    @pytest.fixture
    def registry(self, discovery_registry):
        discovery_registry.enable_tool_discovery()
        return discovery_registry

    def test_multi_word_query_is_accepted(self, registry):
        tool = registry.get_tool("discover_tools")
        assert tool.validate_parameters({"query": "read file"})["query"] == (
            "read file"
        )

    def test_surrounding_whitespace_is_tolerated(self, registry):
        tool = registry.get_tool("discover_tools")
        validated = tool.validate_parameters({"query": "  read file  "})
        assert validated["query"] == "  read file  "

    def test_newlines_are_tolerated(self, registry):
        """Models sometimes emit a trailing or embedded newline (#326)."""
        tool = registry.get_tool("discover_tools")
        assert tool.validate_parameters({"query": "search\n"})["query"] == "search\n"
        assert (
            tool.validate_parameters({"query": "search\nfile"})["query"]
            == "search\nfile"
        )

    def test_whitespace_only_query_is_rejected(self, registry):
        from toolregistry._vendor.validate import ValidationError

        tool = registry.get_tool("discover_tools")
        with pytest.raises(ValidationError):
            tool.validate_parameters({"query": "   "})
        with pytest.raises(ValidationError):
            tool.validate_parameters({"query": " \n\t "})

    def test_multi_word_query_returns_matches(self, registry):
        import json

        result = registry.invoke("discover_tools", {"query": "read file"})
        assert not hasattr(result, "message"), result
        names = {item["name"] for item in json.loads(result.result)}
        assert "read_file" in names


class TestDiscoverOutputSchema:
    """Declared output schemas travel with discovery results (#337)."""

    _OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {"temperature": {"type": "number"}},
        "additionalProperties": True,
    }

    def _registry(self) -> ToolRegistry:
        registry = ToolRegistry()

        def weather_current(city: str) -> dict:
            """Current weather conditions for a city."""
            return {"temperature": 21.0}

        def plain_tool(query: str) -> str:
            """Plain lookup with no declared result shape."""
            return query

        registry.register(
            Tool.from_function(
                weather_current,
                metadata=ToolMetadata(
                    defer=True,
                    extra={"output_schema": self._OUTPUT_SCHEMA},
                ),
            )
        )
        registry.register(plain_tool)
        return registry

    def test_fuzzy_result_carries_the_output_schema(self):
        discoverer = ToolDiscoveryTool(self._registry())

        results = discoverer.discover("weather conditions", top_k=3)

        assert results, "expected a fuzzy hit"
        schema = results[0]["schema"]
        assert schema["function"]["output_schema"] == self._OUTPUT_SCHEMA
        assert "parameters" in schema["function"]

    def test_exact_match_carries_the_output_schema(self):
        discoverer = ToolDiscoveryTool(self._registry())

        result = discoverer.discover("weather_current")

        assert result[0]["schema"]["function"]["output_schema"] == (self._OUTPUT_SCHEMA)

    def test_tool_without_a_declared_schema_gains_nothing(self):
        discoverer = ToolDiscoveryTool(self._registry())

        result = discoverer.discover("plain_tool")

        assert "output_schema" not in result[0]["schema"]["function"]

    @pytest.mark.parametrize(
        "api_format, location",
        [
            ("openai-chat", "function"),
            ("openai-responses", "top"),
            ("anthropic", "top"),
            ("gemini", "top"),
        ],
    )
    def test_output_schema_follows_the_provider_shape(self, api_format, location):
        discoverer = ToolDiscoveryTool(self._registry())

        result = discoverer.discover("weather_current", api_format=api_format)

        schema = result[0]["schema"]
        if location == "function":
            assert schema["function"]["output_schema"] == self._OUTPUT_SCHEMA
        else:
            assert schema["output_schema"] == self._OUTPUT_SCHEMA


class TestDiscoveryToolAnnotations:
    """The discovery proxies declare what a host needs to gate them (#280)."""

    def test_discover_tools_is_read_only(self):
        registry = ToolRegistry()
        registry.enable_tool_discovery()
        hints = registry.get_tool("discover_tools").execution_hints
        assert hints["read_only_hint"] is True
        assert hints["destructive_hint"] is False
        assert hints["idempotent_hint"] is True
        assert hints["open_world_hint"] is False

    def test_call_deferred_makes_no_read_only_claim(self):
        """Its effect is whatever the target tool does, so it cannot claim."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()
        hints = registry.get_tool("call_deferred").execution_hints
        assert "read_only_hint" not in hints
