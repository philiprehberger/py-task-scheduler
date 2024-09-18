"""Tests for missed job handling."""

from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta

from philiprehberger_task_scheduler import (
    Scheduler,
    MissedJobPolicy,
)


def test_missed_job_policy_skip() -> None:
    """SKIP policy does not run missed jobs."""
    scheduler = Scheduler()
    results: list[str] = []

    def task() -> None:
        results.append("ran")

    # Simulate downtime by setting last shutdown 5 minutes ago
    scheduler._last_shutdown_time = datetime.now() - timedelta(minutes=5)
    scheduler.add(
        "skipped",
        fn=task,
        cron="* * * * *",
        missed_policy=MissedJobPolicy.SKIP,
    )

    scheduler._check_missed_jobs()
    time.sleep(0.5)
    assert len(results) == 0


def test_missed_job_policy_run_once() -> None:
    """RUN_ONCE policy runs the job exactly once for missed windows."""
    scheduler = Scheduler()
    results: list[str] = []
    lock = threading.Lock()

    def task() -> None:
        with lock:
            results.append("ran")

    # Simulate downtime of 5 minutes with every-minute cron
    scheduler._last_shutdown_time = datetime.now() - timedelta(minutes=5)
    scheduler.add(
        "catch-up",
        fn=task,
        cron="* * * * *",
        missed_policy=MissedJobPolicy.RUN_ONCE,
    )

    scheduler._check_missed_jobs()
    time.sleep(1)

    with lock:
        assert len(results) == 1


def test_missed_job_policy_run_all() -> None:
    """RUN_ALL policy runs the job for each missed window."""
    scheduler = Scheduler()
    results: list[str] = []
    lock = threading.Lock()

    def task() -> None:
        with lock:
            results.append("ran")

    # Simulate downtime of 3 minutes with every-minute cron
    scheduler._last_shutdown_time = datetime.now() - timedelta(minutes=3)
    scheduler.add(
        "catch-up-all",
        fn=task,
        cron="* * * * *",
        missed_policy=MissedJobPolicy.RUN_ALL,
    )

    scheduler._check_missed_jobs()
    time.sleep(1)

    with lock:
        # Should have run 2 times (minutes between shutdown and now, exclusive)
        assert len(results) >= 2


def test_missed_job_no_shutdown_time() -> None:
    """No missed jobs checked when there's no recorded shutdown time."""
    scheduler = Scheduler()
    results: list[str] = []

    scheduler.add(
        "job",
        fn=lambda: results.append("ran"),
        cron="* * * * *",
        missed_policy=MissedJobPolicy.RUN_ONCE,
    )

    scheduler._check_missed_jobs()
    time.sleep(0.5)
    assert len(results) == 0


def test_missed_job_interval_ignored() -> None:
    """Missed job detection only applies to cron jobs, not intervals."""
    scheduler = Scheduler()
    results: list[str] = []

    scheduler._last_shutdown_time = datetime.now() - timedelta(minutes=5)
    scheduler.add(
        "interval-job",
        fn=lambda: results.append("ran"),
        interval_seconds=60,
        missed_policy=MissedJobPolicy.RUN_ONCE,
    )

    scheduler._check_missed_jobs()
    time.sleep(0.5)
    assert len(results) == 0


def test_missed_job_policy_values() -> None:
    """MissedJobPolicy enum has correct values."""
    assert MissedJobPolicy.SKIP.value == "skip"
    assert MissedJobPolicy.RUN_ONCE.value == "run_once"
    assert MissedJobPolicy.RUN_ALL.value == "run_all"


def test_missed_jobs_checked_on_start() -> None:
    """Missed jobs are checked when the scheduler starts."""
    scheduler = Scheduler()
    results: list[str] = []
    lock = threading.Lock()

    def task() -> None:
        with lock:
            results.append("ran")

    scheduler._last_shutdown_time = datetime.now() - timedelta(minutes=3)
    scheduler.add(
        "startup-catch-up",
        fn=task,
        cron="* * * * *",
        missed_policy=MissedJobPolicy.RUN_ONCE,
    )

    scheduler.start(background=True)
    time.sleep(1.5)
    scheduler.stop()

    with lock:
        assert len(results) >= 1


def test_missed_policy_via_decorator() -> None:
    """Missed policy can be set via decorators."""
    scheduler = Scheduler()

    @scheduler.cron("* * * * *", missed_policy=MissedJobPolicy.RUN_ONCE)
    def cron_task() -> None:
        pass

    @scheduler.interval(seconds=30, missed_policy=MissedJobPolicy.RUN_ALL)
    def interval_task() -> None:
        pass

    assert scheduler.jobs[0].missed_policy == MissedJobPolicy.RUN_ONCE
    assert scheduler.jobs[1].missed_policy == MissedJobPolicy.RUN_ALL
