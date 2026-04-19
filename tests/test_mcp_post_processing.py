"""Tests for MCP post-processing and tool creation logic."""

from unittest.mock import MagicMock

import pytest

mcp_types = pytest.importorskip("mcp.types")

from mcp.types import (  # noqa: E402
    BlobResourceContents,
    EmbeddedResource,
    ImageContent,
    TextContent,
    TextResourceContents,
)
from mcp.types import Tool as MCPToolSpec  # noqa: E402

from toolregistry.integrations.mcp.integration import MCPTool, MCPToolWrapper  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wrapper(name="test_tool", params=None):
    """Create an MCPToolWrapper with a mock connection."""
    mock_connection = MagicMock()
    return MCPToolWrapper(connection=mock_connection, name=name, params=params)


class FakeResult:
    """Mimics a CallToolResult without importing the exact class."""

    def __init__(self, content, is_error=False):
        self.content = content
        self.isError = is_error
        self.is_error = is_error


# ===========================================================================
# TestMCPPostProcessResult
# ===========================================================================


class TestMCPPostProcessResult:
    """Tests for MCPToolWrapper._post_process_result()."""

    def test_single_text_content(self):
        """Single TextContent returns a plain string."""
        wrapper = _make_wrapper()
        result = FakeResult(content=[TextContent(type="text", text="hello world")])
        output = wrapper._post_process_result(result)
        assert output == "hello world"

    def test_multiple_text_content(self):
        """Multiple TextContent items return a list of content blocks."""
        wrapper = _make_wrapper()
        result = FakeResult(
            content=[
                TextContent(type="text", text="first"),
                TextContent(type="text", text="second"),
            ]
        )
        output = wrapper._post_process_result(result)
        assert isinstance(output, list)
        assert len(output) == 2
        assert output[0] == {"type": "text", "text": "first"}
        assert output[1] == {"type": "text", "text": "second"}

    def test_image_content(self):
        """ImageContent is converted to base64 block."""
        wrapper = _make_wrapper()
        result = FakeResult(
            content=[
                ImageContent(
                    type="image", data="abc123base64data", mimeType="image/png"
                )
            ]
        )
        output = wrapper._post_process_result(result)
        assert isinstance(output, list)
        assert output[0]["type"] == "image"
        assert output[0]["source"]["type"] == "base64"
        assert output[0]["source"]["media_type"] == "image/png"
        assert output[0]["source"]["data"] == "abc123base64data"

    def test_mixed_text_and_image(self):
        """Mixed TextContent + ImageContent returns list."""
        wrapper = _make_wrapper()
        result = FakeResult(
            content=[
                TextContent(type="text", text="A caption"),
                ImageContent(type="image", data="imgdata", mimeType="image/jpeg"),
            ]
        )
        output = wrapper._post_process_result(result)
        assert isinstance(output, list)
        assert len(output) == 2
        assert output[0]["type"] == "text"
        assert output[1]["type"] == "image"

    def test_embedded_text_resource(self):
        """EmbeddedResource with TextResourceContents extracts text."""
        wrapper = _make_wrapper()
        text_resource = TextResourceContents(
            uri="file:///test.txt", text="embedded text", mimeType="text/plain"
        )
        result = FakeResult(
            content=[EmbeddedResource(type="resource", resource=text_resource)]
        )
        output = wrapper._post_process_result(result)
        assert output == "embedded text"

    def test_embedded_blob_image_resource(self):
        """EmbeddedResource with BlobResourceContents (image) returns image block."""
        wrapper = _make_wrapper()
        blob_resource = BlobResourceContents(
            uri="file:///test.png",
            blob="blobdata123",
            mimeType="image/png",
        )
        result = FakeResult(
            content=[EmbeddedResource(type="resource", resource=blob_resource)]
        )
        output = wrapper._post_process_result(result)
        assert isinstance(output, list)
        assert output[0]["type"] == "image"
        assert output[0]["source"]["data"] == "blobdata123"

    def test_embedded_blob_non_image_resource(self):
        """EmbeddedResource with non-image BlobResourceContents returns text summary."""
        wrapper = _make_wrapper()
        blob_resource = BlobResourceContents(
            uri="file:///test.bin",
            blob="binarydata",
            mimeType="application/octet-stream",
        )
        result = FakeResult(
            content=[EmbeddedResource(type="resource", resource=blob_resource)]
        )
        output = wrapper._post_process_result(result)
        assert "Blob" in output
        assert "application/octet-stream" in output

    def test_is_error_returns_raw(self):
        """isError=True returns the raw result unchanged."""
        wrapper = _make_wrapper()
        result = FakeResult(content=[], is_error=True)
        output = wrapper._post_process_result(result)
        assert output is result

    def test_empty_content_returns_raw(self):
        """Empty content list returns the raw result."""
        wrapper = _make_wrapper()
        result = FakeResult(content=[], is_error=False)
        output = wrapper._post_process_result(result)
        assert output is result

    def test_list_input_bypasses_result_check(self):
        """When input is a plain list, processes directly."""
        wrapper = _make_wrapper()
        contents = [TextContent(type="text", text="direct")]
        output = wrapper._post_process_result(contents)
        assert output == "direct"

    def test_unsupported_content_type_raises(self):
        """Unsupported content type raises NotImplementedError."""
        wrapper = _make_wrapper()

        class UnknownContent:
            pass

        result = FakeResult(content=[UnknownContent()])
        with pytest.raises(NotImplementedError, match="No handler"):
            wrapper._post_process_result(result)

    def test_multiple_embedded_resources(self):
        """Multiple EmbeddedResources are processed correctly."""
        wrapper = _make_wrapper()
        text_res = TextResourceContents(
            uri="file:///a.txt", text="text A", mimeType="text/plain"
        )
        blob_res = BlobResourceContents(
            uri="file:///b.png", blob="imgblob", mimeType="image/png"
        )
        result = FakeResult(
            content=[
                EmbeddedResource(type="resource", resource=text_res),
                EmbeddedResource(type="resource", resource=blob_res),
            ]
        )
        output = wrapper._post_process_result(result)
        assert isinstance(output, list)
        assert len(output) == 2
        assert output[0]["type"] == "text"
        assert output[1]["type"] == "image"

    def test_single_image_returns_list(self):
        """Single image content returns a list (not string)."""
        wrapper = _make_wrapper()
        result = FakeResult(
            content=[ImageContent(type="image", data="data", mimeType="image/gif")]
        )
        output = wrapper._post_process_result(result)
        assert isinstance(output, list)
        assert len(output) == 1


# ===========================================================================
# TestMCPToolFromJson
# ===========================================================================


class TestMCPToolFromJson:
    """Tests for MCPTool.from_tool_json()."""

    def _make_tool_spec(
        self, name="test_tool", description="A test", input_schema=None
    ):
        if input_schema is None:
            input_schema = {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
            }
        return MCPToolSpec(
            name=name,
            description=description,
            inputSchema=input_schema,
        )

    def test_basic_creation(self):
        """Creates an MCPTool from a tool spec."""
        spec = self._make_tool_spec()
        mock_conn = MagicMock()
        tool = MCPTool.from_tool_json(spec, mock_conn)
        assert tool.name == "test_tool"
        assert tool.description == "A test"

    def test_params_extracted(self):
        """Parameter names are extracted from input schema properties."""
        spec = self._make_tool_spec()
        mock_conn = MagicMock()
        tool = MCPTool.from_tool_json(spec, mock_conn)
        assert tool.callable.params == ["query"]

    def test_with_namespace(self):
        """Namespace is applied to tool name."""
        spec = self._make_tool_spec()
        mock_conn = MagicMock()
        tool = MCPTool.from_tool_json(spec, mock_conn, namespace="myserver")
        assert "myserver" in tool.name

    def test_empty_description(self):
        """Empty description defaults to empty string."""
        spec = MCPToolSpec(
            name="no_desc",
            inputSchema={"type": "object", "properties": {}},
        )
        mock_conn = MagicMock()
        tool = MCPTool.from_tool_json(spec, mock_conn)
        assert tool.description == ""

    def test_empty_input_schema(self):
        """Tool with empty input schema creates wrapper with empty params."""
        spec = MCPToolSpec(
            name="bare_tool",
            inputSchema={"type": "object", "properties": {}},
        )
        mock_conn = MagicMock()
        tool = MCPTool.from_tool_json(spec, mock_conn)
        assert tool.callable.params == []


# ===========================================================================
# TestMCPToolWrapperEdgeCases
# ===========================================================================


class TestMCPToolWrapperEdgeCases:
    """Edge case tests for MCPToolWrapper."""

    def test_transport_property(self):
        """transport property returns connection transport."""
        mock_conn = MagicMock()
        mock_conn.transport = "http://example.com"
        wrapper = MCPToolWrapper(connection=mock_conn, name="t", params=[])
        assert wrapper.transport == "http://example.com"

    def test_name_and_params(self):
        """Name and params are correctly stored."""
        mock_conn = MagicMock()
        wrapper = MCPToolWrapper(
            connection=mock_conn, name="my_tool", params=["a", "b"]
        )
        assert wrapper.name == "my_tool"
        assert wrapper.params == ["a", "b"]

    def test_no_params(self):
        """Wrapper with no params."""
        mock_conn = MagicMock()
        wrapper = MCPToolWrapper(connection=mock_conn, name="t", params=None)
        assert wrapper.params is None
