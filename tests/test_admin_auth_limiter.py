"""Tests for the per-source throttle on failed admin authentication (#405).

The limiter is exercised with an injectable clock so the window can be
crossed without sleeping.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from toolregistry.admin.auth import (
    AUTH_FAILURE_LIMIT,
    AUTH_FAILURE_MAX_SOURCES,
    AUTH_FAILURE_WINDOW_SECONDS,
    AuthAttempt,
    AuthFailureLimiter,
)

SOURCE = "203.0.113.7"


class _Clock:
    """A monotonic clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


@pytest.fixture
def limiter(clock: _Clock) -> AuthFailureLimiter:
    return AuthFailureLimiter(clock=clock)


class TestDefaults:
    def test_constants_are_the_documented_values(self) -> None:
        assert AUTH_FAILURE_LIMIT == 5
        assert AUTH_FAILURE_WINDOW_SECONDS == 60.0
        assert AUTH_FAILURE_MAX_SOURCES == 1024

    def test_invalid_settings_are_refused(self) -> None:
        with pytest.raises(ValueError):
            AuthFailureLimiter(limit=0)
        with pytest.raises(ValueError):
            AuthFailureLimiter(window=0)
        with pytest.raises(ValueError):
            AuthFailureLimiter(max_sources=0)


class TestSlidingWindow:
    def test_failures_below_the_limit_are_allowed(self, limiter) -> None:
        for _ in range(AUTH_FAILURE_LIMIT - 1):
            limiter.record_failure(SOURCE)
            assert limiter.retry_after(SOURCE) is None

    def test_the_limit_blocks_the_source(self, limiter) -> None:
        for _ in range(AUTH_FAILURE_LIMIT):
            limiter.record_failure(SOURCE)
        wait = limiter.retry_after(SOURCE)
        assert wait is not None
        assert 0 < wait <= AUTH_FAILURE_WINDOW_SECONDS

    def test_the_wait_counts_down_and_expires(self, limiter, clock) -> None:
        for _ in range(AUTH_FAILURE_LIMIT):
            limiter.record_failure(SOURCE)
        clock.advance(30)
        wait = limiter.retry_after(SOURCE)
        assert wait is not None
        assert 29 <= wait <= 30

        clock.advance(AUTH_FAILURE_WINDOW_SECONDS)
        assert limiter.retry_after(SOURCE) is None

    def test_a_success_clears_the_source(self, limiter) -> None:
        for _ in range(AUTH_FAILURE_LIMIT):
            limiter.record_failure(SOURCE)
        assert limiter.retry_after(SOURCE) is not None

        limiter.clear(SOURCE)
        assert limiter.retry_after(SOURCE) is None

        # The count starts from zero again.
        for _ in range(AUTH_FAILURE_LIMIT - 1):
            limiter.record_failure(SOURCE)
        assert limiter.retry_after(SOURCE) is None

    def test_one_source_does_not_block_another(self, limiter) -> None:
        for _ in range(AUTH_FAILURE_LIMIT):
            limiter.record_failure(SOURCE)
        assert limiter.retry_after(SOURCE) is not None
        assert limiter.retry_after("198.51.100.4") is None

    def test_only_recent_failures_are_kept(self, limiter, clock) -> None:
        for _ in range(AUTH_FAILURE_LIMIT * 4):
            limiter.record_failure(SOURCE)
            clock.advance(1)
        assert len(limiter._failures[SOURCE]) <= AUTH_FAILURE_LIMIT


class TestReservations:
    """``begin`` reserves under the lock; ``release`` records a success."""

    def test_begin_allows_the_limit_then_blocks(self, limiter) -> None:
        attempts = [limiter.begin(SOURCE) for _ in range(AUTH_FAILURE_LIMIT)]
        assert all(attempt is not None for attempt in attempts)
        assert limiter.begin(SOURCE) is None
        assert limiter.retry_after(SOURCE) is not None

    def test_a_blocked_source_is_admitted_after_the_window(
        self, limiter, clock
    ) -> None:
        for _ in range(AUTH_FAILURE_LIMIT):
            limiter.begin(SOURCE)
        assert limiter.begin(SOURCE) is None

        clock.advance(AUTH_FAILURE_WINDOW_SECONDS)
        assert limiter.begin(SOURCE) is not None

    def test_release_clears_the_attempt_and_earlier_failures(self, limiter) -> None:
        for _ in range(AUTH_FAILURE_LIMIT - 1):
            limiter.begin(SOURCE)
        success = limiter.begin(SOURCE)
        assert success is not None

        limiter.release(success)
        # The success clears every failure reserved before it, so the count
        # starts from zero again instead of leaving the source one short.
        assert limiter.retry_after(SOURCE) is None
        assert SOURCE not in limiter._failures

        for _ in range(AUTH_FAILURE_LIMIT - 1):
            assert limiter.begin(SOURCE) is not None
        assert limiter.retry_after(SOURCE) is None

    def test_release_keeps_failures_reserved_after_it(self, limiter) -> None:
        success = limiter.begin(SOURCE)
        later = [limiter.begin(SOURCE) for _ in range(2)]
        assert success is not None
        assert all(attempt is not None for attempt in later)

        limiter.release(success)
        # A success racing with a concurrent burst must not erase the
        # failures the other attempts reserved.
        assert len(limiter._failures[SOURCE]) == 2

    def test_release_of_an_unknown_source_is_a_no_op(self, limiter) -> None:
        attempt = limiter.begin(SOURCE)
        assert attempt is not None
        limiter.release(attempt)
        limiter.release(attempt)
        assert limiter.retry_after(SOURCE) is None


class TestMemoryBound:
    def test_the_table_does_not_grow_past_max_sources(self) -> None:
        limiter = AuthFailureLimiter(max_sources=4)
        for index in range(100):
            limiter.record_failure(f"198.51.100.{index}")
        assert len(limiter._failures) <= 4

    def test_the_oldest_source_is_evicted(self) -> None:
        limiter = AuthFailureLimiter(max_sources=2)
        limiter.record_failure("first")
        limiter.record_failure("second")
        limiter.record_failure("third")
        assert "first" not in limiter._failures
        assert "second" in limiter._failures
        assert "third" in limiter._failures

    def test_expired_sources_are_pruned_before_eviction(self, clock) -> None:
        limiter = AuthFailureLimiter(max_sources=2, clock=clock)
        limiter.record_failure("expired")
        clock.advance(AUTH_FAILURE_WINDOW_SECONDS + 1)
        limiter.record_failure("second")
        limiter.record_failure("third")
        # "expired" left the window, so no live source had to be dropped.
        assert "expired" not in limiter._failures
        assert "second" in limiter._failures
        assert "third" in limiter._failures

    def test_a_blocked_source_survives_eviction_of_others(self, clock) -> None:
        limiter = AuthFailureLimiter(max_sources=2, clock=clock)
        for _ in range(AUTH_FAILURE_LIMIT):
            limiter.record_failure(SOURCE)
        limiter.record_failure("other")
        # Accessing the blocked source keeps it least-recently-used-proof.
        assert limiter.retry_after(SOURCE) is not None
        limiter.record_failure("third")
        assert limiter.retry_after(SOURCE) is not None


class TestThreadSafety:
    """Before-request hooks run through ``asyncio.to_thread`` (#405 review)."""

    def test_concurrent_failures_are_all_counted(self) -> None:
        """No failure is lost when threads race to create the source."""
        workers = 64
        limiter = AuthFailureLimiter(limit=workers, max_sources=8)
        barrier = threading.Barrier(workers)

        def fail(_: int) -> None:
            barrier.wait()
            limiter.record_failure(SOURCE)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(fail, range(workers)))

        assert len(limiter._failures[SOURCE]) == workers
        assert limiter.retry_after(SOURCE) is not None

    def test_concurrent_clear_and_retry_after_do_not_raise(self, clock) -> None:
        """``clear()`` may not leave ``retry_after()`` a dangling entry."""
        limiter = AuthFailureLimiter(limit=10_000, max_sources=4, clock=clock)
        for _ in range(100):
            limiter.record_failure(SOURCE)
        # Expired entries make ``retry_after`` prune and remove the key while
        # ``clear`` may be doing the same.
        clock.advance(AUTH_FAILURE_WINDOW_SECONDS + 1)

        def churn(index: int) -> None:
            for _ in range(50):
                if index % 2:
                    limiter.clear(SOURCE)
                else:
                    limiter.retry_after(SOURCE)

        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(churn, range(32)))

        # A failure recorded after the churn is still counted exactly once.
        limiter.clear(SOURCE)
        limiter.record_failure(SOURCE)
        assert len(limiter._failures[SOURCE]) == 1

    def test_a_burst_cannot_admit_more_than_the_limit(self) -> None:
        """A check-then-record race would admit all ``limit + 1`` requests."""
        workers = AUTH_FAILURE_LIMIT + 1
        limiter = AuthFailureLimiter()
        barrier = threading.Barrier(workers)

        def attempt(_: int) -> AuthAttempt | None:
            barrier.wait()
            return limiter.begin(SOURCE)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            attempts = list(pool.map(attempt, range(workers)))

        admitted = [attempt for attempt in attempts if attempt is not None]
        assert len(admitted) == AUTH_FAILURE_LIMIT
        assert len(limiter._failures[SOURCE]) == AUTH_FAILURE_LIMIT
        assert limiter.begin(SOURCE) is None
