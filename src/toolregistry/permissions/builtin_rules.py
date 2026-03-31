"""Built-in permission rules for common tool classification patterns."""

from ..tool import ToolTag
from .policy import PermissionRule
from .types import PermissionResult

ALLOW_READONLY = PermissionRule(
    name="allow_readonly",
    match=lambda t, p: ToolTag.READ_ONLY in t.metadata.tags,
    result=PermissionResult.ALLOW,
    reason="Tool is read-only",
)

ASK_DESTRUCTIVE = PermissionRule(
    name="ask_destructive",
    match=lambda t, p: ToolTag.DESTRUCTIVE in t.metadata.tags,
    result=PermissionResult.ASK,
    reason="Tool is marked as destructive",
)

DENY_PRIVILEGED = PermissionRule(
    name="deny_privileged",
    match=lambda t, p: ToolTag.PRIVILEGED in t.metadata.tags,
    result=PermissionResult.DENY,
    reason="Tool requires elevated permissions",
)

ASK_NETWORK = PermissionRule(
    name="ask_network",
    match=lambda t, p: ToolTag.NETWORK in t.metadata.tags,
    result=PermissionResult.ASK,
    reason="Tool requires network access",
)

ASK_FILE_SYSTEM = PermissionRule(
    name="ask_file_system",
    match=lambda t, p: ToolTag.FILE_SYSTEM in t.metadata.tags,
    result=PermissionResult.ASK,
    reason="Tool accesses the file system",
)
