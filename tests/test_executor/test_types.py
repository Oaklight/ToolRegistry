"""Tests for executor value types."""

import pytest

from toolregistry.executor import (
    CancelledError,
    ExecutionContext,
    HandleStatus,
    ProgressReport,
)


class TestHandleStatus:
    def test_enum_values(self):
        assert HandleStatus.PENDING == "pending"
        assert HandleStatus.RUNNING == "running"
        assert HandleStatus.COMPLETED == "completed"
        assert HandleStatus.FAILED == "failed"
        assert HandleStatus.CANCELLED == "cancelled"

    def test_is_str_enum(self):
        assert isinstance(HandleStatus.PENDING, str)


class TestProgressReport:
    def test_defaults(self):
        r = ProgressReport()
        assert r.fraction is None
        assert r.message == ""
        assert r.detail is None

    def test_all_fields(self):
        r = ProgressReport(fraction=0.5, message="halfway", detail={"step": 3})
        assert r.fraction == 0.5
        assert r.message == "halfway"
        assert r.detail == {"step": 3}


class TestExecutionContext:
    def test_cancelled_starts_false(self):
        ctx = ExecutionContext()
        assert ctx.cancelled is False

    def test_request_cancel_sets_cancelled(self):
        ctx = ExecutionContext()
        ctx._request_cancel()
        assert ctx.cancelled is True

    def test_check_cancelled_noop_when_not_cancelled(self):
        ctx = ExecutionContext()
        ctx.check_cancelled()  # should not raise

    def test_check_cancelled_raises_when_cancelled(self):
        ctx = ExecutionContext()
        ctx._request_cancel()
        with pytest.raises(CancelledError):
            ctx.check_cancelled()

    def test_report_progress_calls_listeners(self):
        ctx = ExecutionContext()
        received = []
        ctx._add_progress_listener(lambda r: received.append(r))
        ctx.report_progress(fraction=0.5, message="half done")
        assert len(received) == 1
        assert received[0].fraction == 0.5
        assert received[0].message == "half done"

    def test_report_progress_noop_without_listeners(self):
        ctx = ExecutionContext()
        ctx.report_progress(fraction=0.1)  # should not raise

    def test_multiple_listeners(self):
        ctx = ExecutionContext()
        a, b = [], []
        ctx._add_progress_listener(lambda r: a.append(r))
        ctx._add_progress_listener(lambda r: b.append(r))
        ctx.report_progress(message="test")
        assert len(a) == 1
        assert len(b) == 1
