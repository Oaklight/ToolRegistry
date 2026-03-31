"""Permission handler and policy mixin for ToolRegistry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .permissions import (
    AsyncPermissionHandler,
    PermissionHandler,
    PermissionPolicy,
    PermissionRequest,
    PermissionResult,
    PermissionRule,
)

if TYPE_CHECKING:
    from .events import ChangeEvent
    from .tool import Tool


class PermissionsMixin:
    """Mixin providing permission handler and policy management."""

    # Type stubs for methods from other mixins
    if TYPE_CHECKING:

        def _emit_change(self, event: ChangeEvent) -> None: ...

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._permission_handler: PermissionHandler | AsyncPermissionHandler | None = (
            None
        )
        self._permission_fallback: PermissionResult = PermissionResult.DENY
        self._permission_policy: PermissionPolicy | None = None

    # ============== Permission Handler ==============

    def set_permission_handler(
        self,
        handler: PermissionHandler | AsyncPermissionHandler,
        *,
        fallback: PermissionResult = PermissionResult.DENY,
    ) -> None:
        """Register a permission handler for tool authorization.

        The handler is invoked when a permission rule returns
        ``PermissionResult.ASK``.  If no handler is set and a rule
        returns ASK, the *fallback* result is used instead.

        Args:
            handler: A sync or async handler implementing the
                ``PermissionHandler`` / ``AsyncPermissionHandler``
                protocol.
            fallback: Result to use when the handler is absent or when
                a rule returns ASK but no handler is registered.
                Defaults to ``PermissionResult.DENY`` (safe by default).
        """
        self._permission_handler = handler
        self._permission_fallback = fallback

    def get_permission_handler(
        self,
    ) -> PermissionHandler | AsyncPermissionHandler | None:
        """Return the currently registered permission handler, if any."""
        return self._permission_handler

    def remove_permission_handler(self) -> None:
        """Remove the permission handler and reset fallback to DENY."""
        self._permission_handler = None
        self._permission_fallback = PermissionResult.DENY

    @property
    def permission_fallback(self) -> PermissionResult:
        """The fallback result used when no handler is available for ASK."""
        return self._permission_fallback

    # ============== Permission Policy ==============

    def set_permission_policy(self, policy: PermissionPolicy) -> None:
        """Set a permission policy with composable rules.

        The policy is evaluated on every tool call inside
        ``execute_tool_calls()``.  Rules are checked in order
        (first match wins).  When a rule returns ``ASK``, the
        handler is resolved as: policy handler > registry-level
        handler > fallback.

        Args:
            policy: The permission policy to apply.
        """
        self._permission_policy = policy

    def get_permission_policy(self) -> PermissionPolicy | None:
        """Return the currently set permission policy, if any."""
        return self._permission_policy

    def remove_permission_policy(self) -> None:
        """Remove the permission policy.  No permission checks
        will be performed on tool calls until a new policy is set."""
        self._permission_policy = None

    def _resolve_permission(
        self,
        tool: Tool,
        parameters: dict[str, Any],
    ) -> PermissionResult:
        """Evaluate the permission policy for a single tool call.

        Returns ``ALLOW`` when no policy is configured.

        Resolution order for ASK results:
            1. Policy-level handler
            2. Registry-level handler (``set_permission_handler``)
            3. Policy fallback / registry fallback
        """
        import asyncio

        from .events import ChangeEvent, ChangeEventType

        policy = self._permission_policy
        if policy is None:
            return PermissionResult.ALLOW

        outcome = policy.evaluate(tool, parameters)

        # No rule matched — use fallback
        if isinstance(outcome, PermissionResult):
            result = outcome
            rule_name = ""
            reason = ""
        else:
            # A PermissionRule matched
            rule: PermissionRule = outcome
            result = rule.result
            rule_name = rule.name
            reason = rule.reason

        if result == PermissionResult.ALLOW:
            return PermissionResult.ALLOW

        if result == PermissionResult.DENY:
            self._emit_change(
                ChangeEvent(
                    event_type=ChangeEventType.PERMISSION_DENIED,
                    tool_name=tool.name,
                    reason=reason,
                    metadata={"rule_name": rule_name, "parameters": parameters},
                )
            )
            return PermissionResult.DENY

        # result == ASK — resolve via handler
        handler = policy.handler or self._permission_handler
        request = PermissionRequest(
            tool_name=tool.name,
            parameters=parameters,
            reason=reason,
            rule_name=rule_name,
            metadata=tool.metadata,
        )
        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.PERMISSION_ASKED,
                tool_name=tool.name,
                reason=reason,
                metadata={"rule_name": rule_name, "parameters": parameters},
            )
        )

        if handler is None:
            fallback = (
                policy.fallback
                if policy.fallback != PermissionResult.ASK
                else self._permission_fallback
            )
            return fallback

        import inspect

        from typing import cast

        if inspect.iscoroutinefunction(handler.handle):
            try:
                asyncio.get_running_loop()
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    decision = pool.submit(
                        asyncio.run, handler.handle(request)
                    ).result()
            except RuntimeError:
                decision = asyncio.run(handler.handle(request))
        else:
            decision = handler.handle(request)

        return cast(PermissionResult, decision)
