"""Persistence and status hook for tool sources.

The admin panel can preview and register a source, but it does not own a
configuration file.  A downstream server that does own one installs a hook;
the panel then hands every source change to it and exposes the hook's status
view in ``GET /api/sources``.

Core makes no file-format decision: the hook receives a structured
:class:`SourceChange` and decides how to store it.  A hook that cannot persist
raises :class:`SourcePersistenceError`; the registration response then reports
``persisted: false`` while the tools stay registered, because the registry
mutation has already happened.  Answering 5xx would claim the registration
failed when it did not.

Example:
    >>> class ConfigHook:
    ...     def __init__(self, manager):
    ...         self.manager = manager
    ...
    ...     def persist(self, change):
    ...         return self.manager.apply(change).to_dict()
    ...
    ...     def writable(self):
    ...         return self.manager.config_path is not None
    ...
    ...     def statuses(self):
    ...         return self.manager.to_dicts()
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

#: Actions a hook may be asked to persist.  The admin panel emits ``add``;
#: a downstream caller that owns a source diff may persist the other two.
SOURCE_CHANGE_ACTIONS = ("add", "remove", "replace")


class SourcePersistenceError(RuntimeError):
    """A source change could not be persisted.

    The message is shown to the operator in the registration response, so it
    must not contain credentials from the source declaration.
    """


@dataclass(frozen=True)
class SourceChange:
    """A structured source change handed to a persistence hook.

    Attributes:
        action: ``add``, ``remove`` or ``replace``.  The admin panel emits
            ``add``; remove and replace come from downstream callers that
            already own the source diff.
        kind: Source kind, one of ``openapi``, ``mcp`` or ``python``.
        payload: The serialisable declaration as submitted to the panel.  It
            may contain credentials (an auth token, headers, ``env`` or
            command arguments); a hook must neither log nor echo it.
        namespace: Namespace requested for the source, or ``None``.
        selected: Tool names the operator kept, or ``None`` for every tool
            the source offers.
        source_id: Existing source id for remove or replace, or ``None``.
    """

    action: str
    kind: str
    #: Hidden from ``repr``: a stray log must not print credentials.
    payload: Mapping[str, Any] = field(repr=False)
    namespace: str | None
    selected: tuple[str, ...] | None = None
    source_id: str | None = None

    def __post_init__(self) -> None:
        if self.action not in SOURCE_CHANGE_ACTIONS:
            raise ValueError(
                f"action must be one of {', '.join(SOURCE_CHANGE_ACTIONS)}, "
                f"got {self.action!r}"
            )


@runtime_checkable
class SourcePersistenceHook(Protocol):
    """Persistence and status interface a downstream server installs.

    The admin app reads the three members below.  A hook is optional: without
    one, the panel keeps its response shapes unchanged and nothing is
    persisted.
    """

    def persist(self, change: SourceChange) -> Mapping[str, Any]:
        """Persist *change* and return its status record.

        The record is passed through verbatim in ``GET /api/sources`` under
        ``source_status`` and as ``source`` in the registration response.  It
        must carry at least ``id``, ``kind``, ``detail``, ``namespace``,
        ``status`` and ``last_error`` so a client can join it to a source
        entry.  ``detail`` must stay redacted, because the panel shows it.

        Args:
            change: The structured change to persist.

        Returns:
            The persisted source's status record.

        Raises:
            SourcePersistenceError: When the change cannot be stored.  The
                message is shown to the operator and must not contain
                credentials.
        """

    def writable(self) -> bool:
        """Return whether the backing configuration can be written.

        The panel exposes this as ``config_writable`` so an operator can see
        that a read-only configuration will not survive a restart.
        """

    def statuses(self) -> Sequence[Mapping[str, Any]]:
        """Return every source's status record.

        Records are passed through verbatim; failed and excluded sources with
        no registered tools must be included, because they are invisible in
        the tool-derived ``sources`` list.
        """
