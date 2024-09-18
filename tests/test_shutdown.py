"""Tests for graceful shutdown functionality."""

from __future__ import annotations

import time
import threading

from philiprehberger_task_scheduler import Scheduler


def test_graceful_shutdown_waits() -> None:
    """Graceful shutdown waits for running tasks."""
    scheduler = Scheduler()
    completed = {"value": False}

    def slow_task() -> None:
        time.sleep(2)
        completed["value"] = True

    scheduler.add("slow", fn=slow_task, interval_seconds=1)
    scheduler.start(background=True)
    time.sleep(1.5)  # Let the task start
    scheduler.stop(wait=True)

    assert completed["value"] is True


def test_graceful_shutdown_with_timeout() -> None:
    """Graceful shutdown respects timeout."""
    scheduler = Scheduler()

    def very_slow_task() -> None:
        time.sleep(30)

    scheduler.add("very-slow", fn=very_slow_task, interval_seconds=1)
    scheduler.start(background=True)
    time.sleep(1.5)

    start = time.monotonic()
    scheduler.stop(wait=True, timeout=1.0)
    elapsed = time.monotonic() - start

    # Should not wait longer than timeout + some margin
    assert elapsed < 3.0


def test_stop_without_wait() -> None:
    """Stop without wait returns immediately."""
    scheduler = Scheduler()

    def slow_task() -> None:
        time.sleep(10)

    scheduler.add("slow", fn=slow_task, interval_seconds=1)
    scheduler.start(background=True)
    time.sleep(1.5)

    start = time.monotonic()
    scheduler.stop(wait=False)
    elapsed = time.monotonic() - start

    assert elapsed < 1.0


def test_stop_records_shutdown_time() -> None:
    """Stop records the shutdown time for missed job detection."""
    scheduler = Scheduler()
    scheduler.start(background=True)
    time.sleep(0.5)
    scheduler.stop()

    assert scheduler._last_shutdown_time is not None


def test_stop_idempotent() -> None:
    """Calling stop multiple times is safe."""
    scheduler = Scheduler()
    scheduler.start(background=True)
    time.sleep(0.5)
    scheduler.stop()
    scheduler.stop()  # Should not raise
    scheduler.stop(wait=True)  # Should not raise
