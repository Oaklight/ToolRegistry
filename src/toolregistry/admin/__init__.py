"""Admin module for ToolRegistry.

This module provides administrative functionality for the ToolRegistry,
including execution logging, monitoring capabilities, and an HTTP admin panel.
"""

from .auth import SessionCookie, TokenAuth
from .execution_log import (
    ExecutionLog,
    ExecutionLogEntry,
    ExecutionStatus,
    warning_collector,
)
from .extensions import (
    ADMIN_EXTENSION_API,
    AdminContext,
    AdminExtension,
    AdminExtensionError,
    MountedExtension,
)
from .metrics import RequestMetrics
from .server import AdminInfo, AdminServer

__all__ = [
    "ADMIN_EXTENSION_API",
    "AdminContext",
    "AdminExtension",
    "AdminExtensionError",
    "AdminInfo",
    "AdminServer",
    "ExecutionLog",
    "ExecutionLogEntry",
    "ExecutionStatus",
    "MountedExtension",
    "RequestMetrics",
    "SessionCookie",
    "TokenAuth",
    "warning_collector",
]
