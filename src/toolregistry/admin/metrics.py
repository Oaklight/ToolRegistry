"""HTTP request metrics for the admin server.

Collects time-to-first-byte, total response duration, completion counts,
and client disconnects from the vendored httpserver's lifecycle signals.

All methods run on the admin server's event-loop thread, so no locking is
required.  ``snapshot()`` is also called from that thread via the
``GET /api/metrics`` handler.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Iterable
from typing import Any

DEFAULT_SAMPLE_SIZE = 1024
DEFAULT_EXCLUDED_PATHS = ("/api/metrics",)


def _percentile(values: list[float], pct: float) -> float:
    """Return the *pct* percentile of *values* (linear index selection)."""
    ordered = sorted(values)
    index = round((pct / 100.0) * (len(ordered) - 1))
    return ordered[min(len(ordered) - 1, max(0, index))]


def _latency_summary(samples: deque[float]) -> dict[str, Any]:
    """Summarize a latency sample buffer in milliseconds."""
    values = list(samples)
    if not values:
        return {
            "count": 0,
            "avg_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }
    return {
        "count": len(values),
        "avg_ms": round(sum(values) / len(values) * 1000, 2),
        "p50_ms": round(_percentile(values, 50) * 1000, 2),
        "p95_ms": round(_percentile(values, 95) * 1000, 2),
        "max_ms": round(max(values) * 1000, 2),
    }


class RequestMetrics:
    """Counters and latency samples for one admin server instance.

    Intended to be registered directly as httpserver lifecycle hooks::

        app.before_request(metrics.before_request)
        app.on_response_started(metrics.response_started)
        app.on_response_completed(metrics.response_completed)
        app.on_client_disconnect(metrics.client_disconnect)

    Args:
        sample_size: Number of recent latency samples retained for the
            average/percentile summary.  Older samples are discarded.
        excluded_paths: Request paths that are counted but not sampled.  By
            default the metrics endpoint itself is excluded so scraping it
            does not dominate its own percentiles.
    """

    def __init__(
        self,
        *,
        sample_size: int = DEFAULT_SAMPLE_SIZE,
        excluded_paths: Iterable[str] = DEFAULT_EXCLUDED_PATHS,
    ) -> None:
        self._started_at = time.monotonic()
        self._ttfb: deque[float] = deque(maxlen=sample_size)
        self._duration: deque[float] = deque(maxlen=sample_size)
        self._excluded_paths = frozenset(excluded_paths)
        self.requests_total = 0
        self.responses_started = 0
        self.responses_completed = 0
        self.client_disconnects = 0

    def _should_sample(self, request: Any) -> bool:
        return getattr(request, "path", None) not in self._excluded_paths

    def before_request(self, request: Any) -> None:
        """Record the request start time and count the request."""
        self.requests_total += 1
        request.state.metrics_start = time.monotonic()

    def response_started(self, request: Any, response: Any) -> None:
        """Record time-to-first-byte when the response is ready to write."""
        self.responses_started += 1
        start = getattr(request.state, "metrics_start", None)
        if start is not None and self._should_sample(request):
            self._ttfb.append(time.monotonic() - start)

    def response_completed(self, request: Any, response: Any) -> None:
        """Record total response time after the body has been written."""
        self.responses_completed += 1
        start = getattr(request.state, "metrics_start", None)
        if start is not None and self._should_sample(request):
            self._duration.append(time.monotonic() - start)

    def client_disconnect(self, request: Any) -> None:
        """Count a client disconnect during response delivery."""
        self.client_disconnects += 1

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the collected metrics."""
        return {
            "uptime_seconds": round(time.monotonic() - self._started_at, 2),
            "requests_total": self.requests_total,
            "responses_started": self.responses_started,
            "responses_completed": self.responses_completed,
            "client_disconnects": self.client_disconnects,
            "ttfb": _latency_summary(self._ttfb),
            "duration": _latency_summary(self._duration),
        }
