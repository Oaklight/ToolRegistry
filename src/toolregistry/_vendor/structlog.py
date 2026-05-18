# /// zerodep
# version = "0.3.0"
# deps = []
# tier = "medium"
# category = "devtools"
# note = "Install/update via `zerodep add structlog`"
# ///

"""Zero-dependency structured logging with pretty console output.

Part of zerodep: https://github.com/Oaklight/zerodep
Copyright (c) 2026 Peng Ding. MIT License.

Structured logging library inspired by structlog, with a loguru-style
colored console renderer.  Provides bound loggers with context propagation,
a processor pipeline, and multiple output renderers (console, JSON, key-value).

Quick start (pretty console output, zero config)::

    from structlog import get_logger
    logger = get_logger()
    logger.info("server started", host="0.0.0.0", port=8080)

Bound logger (context propagation)::

    log = get_logger().bind(request_id="abc-123")
    log.info("handling request")
    log = log.bind(user_id=42)
    log.info("authenticated")

One-call setup with stdlib integration::

    from structlog import setup_logging
    logger = setup_logging(level="DEBUG", renderer="json")
    logger.info("structured", key="value")

Custom processor pipeline::

    from structlog import configure, add_log_level, TimeStamper, JSONRenderer
    configure(processors=[add_log_level, TimeStamper(), JSONRenderer()])
"""

from __future__ import annotations

import dataclasses
import datetime
import json as _json
import logging
import os
import sys
import traceback
from typing import IO, Any, Callable

__all__ = [
    # Type aliases
    "EventDict",
    "Processor",
    "LoggerFactory",
    # Exceptions
    "DropEvent",
    # Logger factories
    "PrintLogger",
    "PrintLoggerFactory",
    "StdlibLoggerFactory",
    # Processors
    "add_log_level",
    "add_logger_name",
    "TimeStamper",
    "format_exc_info",
    # Renderers
    "KeyValueRenderer",
    "JSONRenderer",
    "ConsoleRenderer",
    # Bound logger
    "BoundLogger",
    # Configuration
    "configure",
    "reset_defaults",
    "get_config",
    "get_logger",
    "wrap_logger",
    # Setup helper
    "setup_logging",
    # Utilities
    "truncate_string",
    "truncate_base64",
]

# ── Type Aliases ─────────────────────────────────────────────────────────────

EventDict = dict[str, Any]
"""A log event dictionary passed through the processor pipeline."""

Processor = Callable[[Any, str, EventDict], EventDict | str]
"""Signature: (logger, method_name, event_dict) -> event_dict or rendered str."""

LoggerFactory = Callable[..., Any]
"""Callable that creates an underlying logger instance."""


# ── Exceptions ───────────────────────────────────────────────────────────────


class DropEvent(Exception):
    """Raise inside a processor to silently discard the current log event."""


# ── Level Mapping ────────────────────────────────────────────────────────────

_NAME_TO_LEVEL: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "fatal": logging.CRITICAL,
    "exception": logging.ERROR,
}

_LEVEL_TO_NAME: dict[int, str] = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}


# ── ANSI Colors ──────────────────────────────────────────────────────────────


class _Colors:
    """ANSI escape codes for terminal colorization."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    STRIKETHROUGH = "\033[9m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


_LEVEL_STYLES: dict[str, str] = {
    "debug": _Colors.BLUE,
    "info": _Colors.BRIGHT_WHITE,
    "warning": _Colors.YELLOW,
    "warn": _Colors.YELLOW,
    "error": _Colors.RED,
    "critical": _Colors.BRIGHT_RED + _Colors.BOLD,
    "fatal": _Colors.BRIGHT_RED + _Colors.BOLD,
    "exception": _Colors.RED,
}

_LEVEL_LABEL_STYLES: dict[str, str] = {
    "debug": _Colors.CYAN,
    "info": _Colors.GREEN,
    "warning": _Colors.YELLOW,
    "warn": _Colors.YELLOW,
    "error": _Colors.RED,
    "critical": _Colors.BRIGHT_RED + _Colors.BOLD,
    "fatal": _Colors.BRIGHT_RED + _Colors.BOLD,
    "exception": _Colors.RED,
}

_LEVEL_LABELS: dict[str, str] = {
    "debug": "DEBUG   ",
    "info": "INFO    ",
    "warning": "WARNING ",
    "warn": "WARNING ",
    "error": "ERROR   ",
    "critical": "CRITICAL",
    "fatal": "FATAL   ",
    "exception": "ERROR   ",
}


def _supports_color(stream: Any = None) -> bool:
    """Check if the output stream supports ANSI color codes.

    Respects the ``FORCE_COLOR`` and ``NO_COLOR`` environment variables
    (see https://force-color.org/ and https://no-color.org/).

    Args:
        stream: The output stream to check.  Defaults to ``sys.stderr``.

    Returns:
        True if the stream is a color-capable terminal.
    """
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("NO_COLOR"):
        return False
    s = stream or sys.stderr
    if not hasattr(s, "isatty") or not s.isatty():
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    return True


# ── Logger Factories ─────────────────────────────────────────────────────────


class PrintLogger:
    """Minimal logger that writes to a file handle via ``print()``.

    This is the default underlying logger.  It has no filtering, no
    handler chain -- just ``print()`` to the configured stream.

    Args:
        file: Output stream.  Defaults to ``sys.stderr``.
    """

    def __init__(self, file: IO[str] | None = None) -> None:
        self._file = file or sys.stderr
        self._write = self._file.write
        self._flush = self._file.flush

    def msg(self, message: str) -> None:
        """Write *message* followed by a newline."""
        self._write(message + "\n")
        self._flush()

    debug = info = warning = warn = error = critical = fatal = msg


class PrintLoggerFactory:
    """Factory that creates :class:`PrintLogger` instances.

    Args:
        file: Output stream passed to each ``PrintLogger``.
    """

    def __init__(self, file: IO[str] | None = None) -> None:
        self._file = file

    def __call__(self, *args: Any) -> PrintLogger:
        return PrintLogger(file=self._file)


class StdlibLoggerFactory:
    """Factory that returns a :class:`logging.Logger` from the stdlib.

    Args:
        name: Logger name passed to ``logging.getLogger()``.
            If *None*, uses the root logger.
    """

    def __init__(self, name: str | None = None) -> None:
        self._name = name

    def __call__(self, *args: Any) -> logging.Logger:
        if args:
            return logging.getLogger(args[0])
        return logging.getLogger(self._name)


# ── Built-in Processors ──────────────────────────────────────────────────────


def add_log_level(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add ``level`` key derived from the log method name.

    Example:
        ``logger.info(...)`` -> ``event_dict["level"] = "info"``
    """
    event_dict["level"] = method_name
    return event_dict


def add_logger_name(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add ``logger`` key from the underlying logger's name."""
    name = getattr(logger, "name", None) or ""
    event_dict["logger"] = name
    return event_dict


class TimeStamper:
    """Processor that adds a timestamp to the event dict.

    Args:
        fmt: Timestamp format.  ``"iso"`` for ISO 8601, ``None`` for a
            UNIX float, or a :func:`~datetime.datetime.strftime` format
            string.  Defaults to ``"iso"``.
        utc: If *True*, use UTC; otherwise local time.
        key: Dict key for the timestamp.  Defaults to ``"timestamp"``.
    """

    __slots__ = ("_fmt", "_utc", "_key")

    def __init__(
        self,
        fmt: str | None = "iso",
        utc: bool = True,
        key: str = "timestamp",
    ) -> None:
        self._fmt = fmt
        self._utc = utc
        self._key = key

    def __call__(
        self, logger: Any, method_name: str, event_dict: EventDict
    ) -> EventDict:
        now = (
            datetime.datetime.now(datetime.timezone.utc)
            if self._utc
            else datetime.datetime.now()
        )
        if self._fmt is None:
            event_dict[self._key] = now.timestamp()
        elif self._fmt == "iso":
            event_dict[self._key] = now.isoformat()
        else:
            event_dict[self._key] = now.strftime(self._fmt)
        return event_dict


def format_exc_info(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Replace ``exc_info`` with a formatted ``exception`` string.

    If ``exc_info`` is *True*, captures the current exception via
    :func:`sys.exc_info`.  If it is an exception tuple, formats it
    directly.  The ``exc_info`` key is removed and replaced with
    ``exception``.
    """
    exc_info = event_dict.pop("exc_info", None)
    if exc_info is None or exc_info is False:
        return event_dict

    if exc_info is True:
        exc_info = sys.exc_info()

    if isinstance(exc_info, BaseException):
        exc_info = (type(exc_info), exc_info, exc_info.__traceback__)

    if isinstance(exc_info, tuple) and exc_info[0] is not None:
        event_dict["exception"] = "".join(
            traceback.format_exception(*exc_info)
        ).rstrip()

    return event_dict


# ── Renderers (final processors) ─────────────────────────────────────────────


class KeyValueRenderer:
    """Render the event dict as ``key=value`` pairs.

    Args:
        key_order: Keys to render first, in this order.
        sort_keys: Sort remaining keys alphabetically.
        drop_missing: Skip *key_order* keys that are absent from the dict.
    """

    __slots__ = ("_key_order", "_sort_keys", "_drop_missing")

    def __init__(
        self,
        key_order: list[str] | None = None,
        sort_keys: bool = False,
        drop_missing: bool = True,
    ) -> None:
        self._key_order = key_order or []
        self._sort_keys = sort_keys
        self._drop_missing = drop_missing

    def __call__(self, logger: Any, method_name: str, event_dict: EventDict) -> str:
        ordered: list[tuple[str, Any]] = []
        remaining = dict(event_dict)

        for key in self._key_order:
            if key in remaining:
                ordered.append((key, remaining.pop(key)))
            elif not self._drop_missing:
                ordered.append((key, None))

        rest = sorted(remaining.items()) if self._sort_keys else list(remaining.items())
        ordered.extend(rest)

        parts = [
            f"{k}={v!r}" if not isinstance(v, str) else f"{k}={v}" for k, v in ordered
        ]
        return " ".join(parts)


class JSONRenderer:
    """Render the event dict as a JSON string.

    Args:
        serializer: JSON serialization function.  Defaults to
            :func:`json.dumps`.
        **dumps_kw: Extra keyword arguments passed to *serializer*.
    """

    __slots__ = ("_serializer", "_dumps_kw")

    def __init__(
        self,
        serializer: Callable[..., str] = _json.dumps,
        **dumps_kw: Any,
    ) -> None:
        self._serializer = serializer
        self._dumps_kw = dumps_kw
        if "default" not in self._dumps_kw:
            self._dumps_kw["default"] = _json_default

    def __call__(self, logger: Any, method_name: str, event_dict: EventDict) -> str:
        return self._serializer(event_dict, **self._dumps_kw)


def _json_default(obj: Any) -> Any:
    """Fallback serializer for objects that ``json.dumps`` cannot handle."""
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if isinstance(obj, set | frozenset):
        return sorted(obj, key=str)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return str(obj)


class ConsoleRenderer:
    """Render the event dict as colorized, loguru-style console output.

    Output format::

        2026-03-27 14:30:00.123 | INFO     | event message    key=val key=val

    Args:
        colors: Enable ANSI color codes.  *None* auto-detects terminal
            support.
        pad_event: Pad the event field to this width for alignment.
        level_styles: Override per-level ANSI color strings.
    """

    __slots__ = ("_colors", "_pad_event", "_level_styles")

    def __init__(
        self,
        colors: bool | None = None,
        pad_event: int = 30,
        level_styles: dict[str, str] | None = None,
    ) -> None:
        self._colors = _supports_color() if colors is None else colors
        self._pad_event = pad_event
        self._level_styles = level_styles or _LEVEL_STYLES

    def __call__(self, logger: Any, method_name: str, event_dict: EventDict) -> str:
        # Extract well-known keys
        event = str(event_dict.pop("event", ""))
        level = event_dict.pop("level", method_name)
        timestamp = event_dict.pop("timestamp", None)
        event_dict.pop("logger", None)
        exception = event_dict.pop("exception", None)

        # Build timestamp string
        if timestamp is None:
            now = datetime.datetime.now()
            ms = now.microsecond // 1000
            ts_str = now.strftime("%Y-%m-%d %H:%M:%S.") + f"{ms:03d}"
        elif isinstance(timestamp, str):
            # Try to format ISO timestamps more compactly
            ts_str = _compact_iso(timestamp)
        elif isinstance(timestamp, float):
            dt = datetime.datetime.fromtimestamp(timestamp)
            ts_str = dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d}"
        else:
            ts_str = str(timestamp)

        # Build level label
        level_str = _LEVEL_LABELS.get(level, f"{level.upper():<8s}")

        # Build key=value pairs from remaining context
        kv_parts: list[str] = []
        for k, v in event_dict.items():
            kv_parts.append(f"{k}={v!r}" if not isinstance(v, str) else f"{k}={v}")
        kv_str = " ".join(kv_parts)

        # Pad event
        padded_event = event.ljust(self._pad_event) if kv_str else event

        # Assemble
        if self._colors:
            msg_color = self._level_styles.get(level, _Colors.WHITE)
            label_color = _LEVEL_LABEL_STYLES.get(level, _Colors.WHITE)

            line = (
                f"{_Colors.GREEN}{ts_str}{_Colors.RESET} | "
                f"{label_color}{_Colors.BOLD}{level_str}{_Colors.RESET} | "
                f"{msg_color}{padded_event}{_Colors.RESET}"
            )
            if kv_str:
                line += f" {_Colors.DIM}{kv_str}{_Colors.RESET}"
            if exception:
                line += f"\n{_Colors.RED}{exception}{_Colors.RESET}"
        else:
            line = f"{ts_str} | {level_str} | {padded_event}"
            if kv_str:
                line += f" {kv_str}"
            if exception:
                line += f"\n{exception}"

        return line


def _compact_iso(ts: str) -> str:
    """Convert an ISO 8601 timestamp to ``YYYY-MM-DD HH:MM:SS.mmm`` format."""
    try:
        dt = datetime.datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d}"
    except (ValueError, AttributeError):
        return ts


# ── BoundLogger ──────────────────────────────────────────────────────────────


class BoundLogger:
    """A logger that carries bound context through a processor pipeline.

    Do not instantiate directly; use :func:`get_logger` or
    :func:`wrap_logger` instead.

    Args:
        logger: The underlying logger instance (e.g. ``PrintLogger``).
        processors: Ordered list of processors to run on each log event.
        context: Initial context dictionary.
    """

    __slots__ = ("_logger", "_processors", "_context")

    def __init__(
        self,
        logger: Any,
        processors: list[Processor],
        context: dict[str, Any],
    ) -> None:
        self._logger = logger
        self._processors = processors
        self._context = context

    def bind(self, **new_values: Any) -> BoundLogger:
        """Return a new logger with *new_values* merged into the context."""
        new_ctx = {**self._context, **new_values}
        return BoundLogger(self._logger, self._processors, new_ctx)

    def unbind(self, *keys: str) -> BoundLogger:
        """Return a new logger with *keys* removed from the context."""
        new_ctx = {k: v for k, v in self._context.items() if k not in keys}
        return BoundLogger(self._logger, self._processors, new_ctx)

    def new(self, **new_values: Any) -> BoundLogger:
        """Return a new logger with *new_values* replacing the context."""
        return BoundLogger(self._logger, self._processors, dict(new_values))

    # ── Log methods ──

    def debug(self, event: str | None = None, /, **kw: Any) -> None:
        self._process("debug", event, kw)

    def info(self, event: str | None = None, /, **kw: Any) -> None:
        self._process("info", event, kw)

    def warning(self, event: str | None = None, /, **kw: Any) -> None:
        self._process("warning", event, kw)

    def warn(self, event: str | None = None, /, **kw: Any) -> None:
        self._process("warning", event, kw)

    def error(self, event: str | None = None, /, **kw: Any) -> None:
        self._process("error", event, kw)

    def critical(self, event: str | None = None, /, **kw: Any) -> None:
        self._process("critical", event, kw)

    def fatal(self, event: str | None = None, /, **kw: Any) -> None:
        self._process("critical", event, kw)

    def exception(self, event: str | None = None, /, **kw: Any) -> None:
        kw.setdefault("exc_info", True)
        self._process("error", event, kw)

    def log(self, level: int, event: str | None = None, /, **kw: Any) -> None:
        method_name = _LEVEL_TO_NAME.get(level, "info")
        self._process(method_name, event, kw)

    # ── Internal ──

    def _process(self, method_name: str, event: str | None, kw: dict[str, Any]) -> None:
        """Merge context, run processors, and emit via the underlying logger."""
        event_dict: EventDict = {**self._context, **kw}
        if event is not None:
            event_dict["event"] = event
        elif "event" not in event_dict:
            event_dict["event"] = ""

        try:
            for proc in self._processors:
                event_dict_or_str = proc(self._logger, method_name, event_dict)
                if isinstance(event_dict_or_str, str):
                    # Final renderer returned a string -- emit and stop.
                    _emit(self._logger, method_name, event_dict_or_str)
                    return
                event_dict = event_dict_or_str
        except DropEvent:
            return

        # If no processor returned a string, emit the repr of event_dict.
        _emit(self._logger, method_name, str(event_dict))


def _emit(logger: Any, method_name: str, message: str) -> None:
    """Dispatch *message* to the underlying logger."""
    if isinstance(logger, logging.Logger):
        level = _NAME_TO_LEVEL.get(method_name, logging.INFO)
        logger.log(level, "%s", message)
    else:
        func = getattr(logger, method_name, None) or getattr(logger, "msg", None)
        if func:
            func(message)


# ── Configuration ────────────────────────────────────────────────────────────


@dataclasses.dataclass
class _Configuration:
    """Global structlog configuration."""

    processors: list[Processor]
    wrapper_class: type[BoundLogger]
    context_class: type
    logger_factory: LoggerFactory
    cache_logger_on_first_use: bool


def _make_defaults() -> _Configuration:
    return _Configuration(
        processors=[add_log_level, TimeStamper(), ConsoleRenderer()],
        wrapper_class=BoundLogger,
        context_class=dict,
        logger_factory=PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


_config: _Configuration = _make_defaults()
_logger_cache: dict[Any, BoundLogger] = {}


def configure(
    processors: list[Processor] | None = None,
    wrapper_class: type[BoundLogger] | None = None,
    context_class: type[dict] | None = None,
    logger_factory: LoggerFactory | None = None,
    cache_logger_on_first_use: bool | None = None,
) -> None:
    """Override the global configuration.

    Only non-*None* arguments are changed.  Call :func:`reset_defaults` to
    restore factory settings.

    Args:
        processors: Ordered processor list.
        wrapper_class: BoundLogger subclass to use.
        context_class: Dict-like class for context storage.
        logger_factory: Factory for the underlying logger.
        cache_logger_on_first_use: Cache loggers returned by
            :func:`get_logger`.
    """
    global _config
    _logger_cache.clear()
    p = _config
    _config = _Configuration(
        processors=(processors if processors is not None else p.processors),
        wrapper_class=(wrapper_class if wrapper_class is not None else p.wrapper_class),
        context_class=(context_class if context_class is not None else p.context_class),
        logger_factory=(
            logger_factory if logger_factory is not None else p.logger_factory
        ),
        cache_logger_on_first_use=(
            cache_logger_on_first_use
            if cache_logger_on_first_use is not None
            else p.cache_logger_on_first_use
        ),
    )


def reset_defaults() -> None:
    """Restore the global configuration to factory defaults."""
    global _config
    _logger_cache.clear()
    _config = _make_defaults()


def get_config() -> _Configuration:
    """Return the current global configuration (read-only snapshot)."""
    return _config


# ── Logger Creation ──────────────────────────────────────────────────────────


def get_logger(*args: Any, **initial_values: Any) -> BoundLogger:
    """Create a :class:`BoundLogger` using the global configuration.

    Positional arguments are forwarded to the logger factory (e.g. a
    logger name).  Keyword arguments become the initial bound context.

    Returns:
        A configured :class:`BoundLogger`.
    """
    cache_key = args if not initial_values else None

    if cache_key is not None and _config.cache_logger_on_first_use:
        cached = _logger_cache.get(cache_key)
        if cached is not None:
            return cached

    underlying = _config.logger_factory(*args)
    ctx = (
        _config.context_class(initial_values)
        if initial_values
        else _config.context_class()
    )
    bound = _config.wrapper_class(
        logger=underlying,
        processors=list(_config.processors),
        context=ctx,
    )

    if cache_key is not None and _config.cache_logger_on_first_use:
        _logger_cache[cache_key] = bound

    return bound


def wrap_logger(
    logger: Any,
    processors: list[Processor] | None = None,
    **initial_values: Any,
) -> BoundLogger:
    """Wrap an existing logger with a processor pipeline.

    Args:
        logger: Any object with ``debug``/``info``/... methods.
        processors: Processor list.  Defaults to the global config.
        **initial_values: Initial bound context.

    Returns:
        A :class:`BoundLogger` wrapping *logger*.
    """
    procs = processors if processors is not None else list(_config.processors)
    ctx = dict(initial_values)
    return BoundLogger(logger=logger, processors=procs, context=ctx)


# ── Convenience Setup ────────────────────────────────────────────────────────


def _resolve_level(level: int | str) -> int:
    """Convert a level name or int to a logging level int."""
    if isinstance(level, int):
        return level
    return _NAME_TO_LEVEL.get(level.lower(), logging.INFO)


def setup_logging(
    level: int | str = logging.INFO,
    renderer: str = "console",
    colors: bool | None = None,
    processors: list[Processor] | None = None,
    logger_name: str | None = None,
    stream: IO[str] | None = None,
) -> BoundLogger:
    """One-call logging setup with stdlib integration.

    Configures both stdlib ``logging`` and the structlog processor
    pipeline in a single call.

    Args:
        level: Log level (name or int).  Defaults to ``INFO``.
        renderer: Output renderer: ``"console"``, ``"json"``, or ``"kv"``.
        colors: Enable ANSI colors.  *None* auto-detects.
        processors: Custom processor list.  Overrides *renderer* if given.
        logger_name: stdlib logger name.
        stream: Output stream.  Defaults to ``sys.stderr``.

    Returns:
        A ready-to-use :class:`BoundLogger`.
    """
    resolved_level = _resolve_level(level)
    out = stream or sys.stderr

    if processors is None:
        base: list[Processor] = [add_log_level, TimeStamper()]
        if renderer == "json":
            base.append(JSONRenderer())
        elif renderer == "kv":
            base.append(KeyValueRenderer(key_order=["event", "level", "timestamp"]))
        else:
            base.append(ConsoleRenderer(colors=colors))
        processors = base

    # Configure stdlib logging to pass through rendered strings.
    stdlib_logger = logging.getLogger(logger_name)
    stdlib_logger.setLevel(resolved_level)
    stdlib_logger.propagate = False

    # Remove existing handlers to avoid duplicate output on repeated calls.
    stdlib_logger.handlers.clear()

    handler = logging.StreamHandler(out)
    handler.setLevel(resolved_level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    stdlib_logger.addHandler(handler)

    configure(
        processors=processors,
        logger_factory=StdlibLoggerFactory(name=logger_name),
    )

    return get_logger()


# ── Utilities ────────────────────────────────────────────────────────────────


def truncate_string(s: str, max_length: int, suffix: str = "...") -> str:
    """Truncate *s* to *max_length*, appending a count of remaining chars.

    Args:
        s: The string to truncate.
        max_length: Maximum number of characters to keep.
        suffix: Separator between the kept text and the count.

    Returns:
        The original string if short enough, otherwise truncated with a
        ``"...[N more chars]"`` suffix.
    """
    if len(s) <= max_length:
        return s
    remaining = len(s) - max_length
    return f"{s[:max_length]}{suffix}[{remaining} more chars]"


def truncate_base64(data_url: str, max_length: int = 100) -> str:
    """Truncate base64 data-URLs for cleaner logging.

    Args:
        data_url: A ``data:`` URL or any string.
        max_length: Maximum base64 payload chars to keep.

    Returns:
        The truncated URL, or the original string if not a data-URL.
    """
    if not data_url.startswith("data:"):
        return data_url
    if ";base64," in data_url:
        header, base64_data = data_url.split(";base64,", 1)
        if len(base64_data) > max_length:
            remaining = len(base64_data) - max_length
            return (
                f"{header};base64,{base64_data[:max_length]}...[{remaining} more chars]"
            )
    return data_url
