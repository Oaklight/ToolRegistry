"""Permission policy: composable rules with first-match-wins evaluation."""

from __future__ import annotations

from typing import Any
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from ..tool import Tool
from .handler import AsyncPermissionHandler, PermissionHandler
from .types import PermissionResult


class PermissionRule(BaseModel):
    """A single permission rule that maps a match predicate to a result.

    Rules are evaluated in order; the first rule whose ``match`` returns
    ``True`` determines the outcome.

    Attributes:
        name: Human-readable identifier for this rule.
        match: Predicate receiving ``(tool, parameters)`` and returning
            ``True`` when this rule applies.
        result: The permission decision when the rule matches.
        reason: Explanation surfaced in ``PermissionRequest`` when the
            result is ``ASK`` or ``DENY``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    match: Callable[[Tool, dict[str, Any]], bool] = Field(exclude=True)
    result: PermissionResult
    reason: str = ""


class PermissionPolicy(BaseModel):
    """An ordered collection of permission rules with a fallback.

    Evaluation follows first-match-wins semantics: rules are checked in
    list order and the first rule whose ``match`` returns ``True``
    produces the final decision (subject to handler resolution for
    ``ASK``).  If no rule matches, ``fallback`` is used.

    Attributes:
        rules: Ordered list of permission rules.
        fallback: Result when no rule matches.  Defaults to ``DENY``
            (safe by default).
        handler: Optional handler invoked when a rule returns ``ASK``.
            Takes precedence over the registry-level handler set via
            ``set_permission_handler()``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    rules: list[PermissionRule] = Field(default_factory=list)
    fallback: PermissionResult = PermissionResult.DENY
    handler: PermissionHandler | AsyncPermissionHandler | None = Field(
        default=None, exclude=True
    )

    def evaluate(
        self, tool: Tool, parameters: dict[str, Any]
    ) -> PermissionResult | PermissionRule:
        """Evaluate rules against a tool call.

        Returns:
            The matched ``PermissionRule`` if a rule matches, or the
            ``fallback`` ``PermissionResult`` if no rule matches.
        """
        for rule in self.rules:
            if rule.match(tool, parameters):
                return rule
        return self.fallback
