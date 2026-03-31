"""Permission handler protocols for tool authorization."""

from typing import Protocol, runtime_checkable

from .types import PermissionRequest, PermissionResult


@runtime_checkable
class PermissionHandler(Protocol):
    """Synchronous handler invoked when a permission rule returns ASK.

    Implementations decide whether to allow or deny a tool call,
    typically by prompting the user or consulting an external policy
    service.

    Example:
        ```python
        class CLIPermissionHandler:
            def handle(self, request: PermissionRequest) -> PermissionResult:
                answer = input(f"Allow {request.tool_name}? [y/N] ")
                return PermissionResult.ALLOW if answer.lower() == "y" else PermissionResult.DENY
        ```
    """

    def handle(self, request: PermissionRequest) -> PermissionResult: ...


@runtime_checkable
class AsyncPermissionHandler(Protocol):
    """Asynchronous handler invoked when a permission rule returns ASK.

    Same contract as PermissionHandler but for async contexts.

    Example:
        ```python
        class WebSocketPermissionHandler:
            async def handle(self, request: PermissionRequest) -> PermissionResult:
                response = await ws.ask_user(request.tool_name, request.reason)
                return PermissionResult.ALLOW if response == "yes" else PermissionResult.DENY
        ```
    """

    async def handle(self, request: PermissionRequest) -> PermissionResult: ...
