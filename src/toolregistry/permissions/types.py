"""Core types for the permission system."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from ..tool import ToolMetadata


class PermissionResult(str, Enum):
    """Three-state permission decision.

    Attributes:
        ALLOW: The tool call is permitted.
        DENY: The tool call is rejected.
        ASK: The decision should be delegated to a PermissionHandler.
    """

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionRequest(BaseModel):
    """Context passed to a PermissionHandler when a rule returns ASK.

    Attributes:
        tool_name: Name of the tool being invoked.
        parameters: Arguments the caller intends to pass.
        reason: Human-readable explanation of why confirmation is needed.
        rule_name: Name of the rule that triggered the ASK result.
        metadata: The tool's ToolMetadata for handler reference.
    """

    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    rule_name: str = ""
    metadata: ToolMetadata = Field(default_factory=ToolMetadata)
