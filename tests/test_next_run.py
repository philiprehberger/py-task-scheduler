"""Tests for next_run functionality."""

from __future__ import annotations

from datetime import datetime, timedelta

from philiprehberger_task_scheduler import Scheduler, Job


def test_next_run_cron_job() -> None:
    """Cron job returns a valid next run time."""
    scheduler = Scheduler()

    @scheduler.cron("0 12 * * *", name="noon-job")
    def noon_task() -> None:
        pass

    job = scheduler.jobs[0]
    next_time = job.next_run
    assert next_time is not None
    assert next_time.hour == 12
    assert next_time.minute == 0


def test_next_run_interval_after_last_run() -> None:
    """Interval job next_run is last_run + interval."""
    job = Job(name="test", fn=lambda: None, interval_seconds=120)
    now = datetime.now()
    job._last_run = now

    next_time = job.next_run
    assert next_time is not None
    diff = abs((next_time - (now + timedelta(seconds=120))).total_seconds())
    assert diff < 1


def test_next_run_interval_no_last_run() -> None:
    """Interval job with no last_run returns None."""
    job = Job(name="test", fn=lambda: None, interval_seconds=60)
    assert job.next_run is None


def test_next_run_once_pending() -> None:
    """Pending once job returns its scheduled time."""
    job = Job(name="test", fn=lambda: None)
    job._once = True
    future = datetime.now() + timedelta(seconds=30)
    job._next_run = future

    assert job.next_run == future


def test_next_run_once_executed() -> None:
    """Executed once job returns None."""
    job = Job(name="test", fn=lambda: None)
    job._once = True
    job._next_run = datetime.now()
    job._executed = True

    assert job.next_run is None


def test_next_runs_method() -> None:
    """Scheduler.next_runs returns list of (name, time) tuples."""
    scheduler = Scheduler()
    scheduler.add("job-a", fn=lambda: None, cron="0 * * * *")
    scheduler.add("job-b", fn=lambda: None, interval_seconds=60)

    runs = scheduler.next_runs()
    assert len(runs) == 2
    assert runs[0][0] == "job-a"
    assert runs[0][1] is not None  # cron job always has next time
    assert runs[1][0] == "job-b"


def test_next_run_cron_is_future() -> None:
    """Cron next_run is always in the future."""
    scheduler = Scheduler()

    @scheduler.cron("* * * * *", name="every-minute")
    def task() -> None:
        pass

    next_time = scheduler.jobs[0].next_run
    assert next_time is not None
    assert next_time > datetime.now()


def test_next_run_no_schedule() -> None:
    """Job with no schedule returns None."""
    job = Job(name="test", fn=lambda: None)
    assert job.next_run is None
