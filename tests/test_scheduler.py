"""Tests for Scheduler core functionality."""

from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta

from philiprehberger_task_scheduler import Scheduler, Job


def test_scheduler_creation() -> None:
    """Scheduler initializes with empty job list."""
    scheduler = Scheduler()
    assert scheduler.jobs == []


def test_cron_decorator() -> None:
    """Cron decorator registers a job."""
    scheduler = Scheduler()

    @scheduler.cron("*/5 * * * *")
    def my_task() -> None:
        pass

    assert len(scheduler.jobs) == 1
    assert scheduler.jobs[0].name == "my_task"
    assert scheduler.jobs[0].cron_parsed is not None


def test_cron_decorator_custom_name() -> None:
    """Cron decorator uses custom name when provided."""
    scheduler = Scheduler()

    @scheduler.cron("0 * * * *", name="custom-name")
    def my_task() -> None:
        pass

    assert scheduler.jobs[0].name == "custom-name"


def test_interval_decorator() -> None:
    """Interval decorator registers a job."""
    scheduler = Scheduler()

    @scheduler.interval(seconds=30)
    def poller() -> None:
        pass

    assert len(scheduler.jobs) == 1
    assert scheduler.jobs[0].interval_seconds == 30


def test_interval_minutes_hours() -> None:
    """Interval supports minutes and hours."""
    scheduler = Scheduler()

    @scheduler.interval(minutes=2, hours=1)
    def task() -> None:
        pass

    assert scheduler.jobs[0].interval_seconds == 3720  # 1h + 2m


def test_interval_zero_raises() -> None:
    """Interval with zero total raises ValueError."""
    scheduler = Scheduler()
    try:
        @scheduler.interval(seconds=0)
        def task() -> None:
            pass
        assert False, "Should have raised"
    except ValueError:
        pass


def test_once_decorator() -> None:
    """Once decorator registers a one-shot job."""
    scheduler = Scheduler()

    @scheduler.once(delay=5)
    def startup() -> None:
        pass

    assert len(scheduler.jobs) == 1
    job = scheduler.jobs[0]
    assert job._once is True
    assert job._next_run is not None


def test_add_remove() -> None:
    """Programmatic add and remove works."""
    scheduler = Scheduler()
    job = scheduler.add("test-job", fn=lambda: None, interval_seconds=10)
    assert len(scheduler.jobs) == 1
    assert job.name == "test-job"

    removed = scheduler.remove("test-job")
    assert removed is True
    assert len(scheduler.jobs) == 0


def test_remove_nonexistent() -> None:
    """Removing a non-existent job returns False."""
    scheduler = Scheduler()
    assert scheduler.remove("ghost") is False


def test_overlap_prevention() -> None:
    """Job with overlap=False won't re-run while running."""
    scheduler = Scheduler()

    @scheduler.interval(seconds=1, overlap=False)
    def slow_task() -> None:
        time.sleep(5)

    job = scheduler.jobs[0]
    job._running = True
    assert job.should_run(datetime.now()) is False


def test_next_runs() -> None:
    """Next runs returns job names with next times."""
    scheduler = Scheduler()
    scheduler.add("job-a", fn=lambda: None, interval_seconds=60)
    result = scheduler.next_runs()
    assert len(result) == 1
    assert result[0][0] == "job-a"


def test_background_start_stop() -> None:
    """Background mode starts and stops cleanly."""
    scheduler = Scheduler()
    counter = {"value": 0}

    @scheduler.interval(seconds=1)
    def tick() -> None:
        counter["value"] += 1

    scheduler.start(background=True)
    time.sleep(2.5)
    scheduler.stop()
    assert counter["value"] >= 1


def test_job_should_run_interval_first_time() -> None:
    """Interval job should run immediately on first tick."""
    job = Job(name="test", fn=lambda: None, interval_seconds=10)
    assert job.should_run(datetime.now()) is True


def test_job_should_run_interval_elapsed() -> None:
    """Interval job should run after interval elapsed."""
    job = Job(name="test", fn=lambda: None, interval_seconds=5)
    job._last_run = datetime.now() - timedelta(seconds=10)
    assert job.should_run(datetime.now()) is True


def test_job_should_run_interval_not_elapsed() -> None:
    """Interval job should not run before interval elapsed."""
    job = Job(name="test", fn=lambda: None, interval_seconds=60)
    job._last_run = datetime.now()
    assert job.should_run(datetime.now()) is False


def test_job_next_run_interval() -> None:
    """Job.next_run returns correct time for interval jobs."""
    job = Job(name="test", fn=lambda: None, interval_seconds=30)
    now = datetime.now()
    job._last_run = now
    expected = now + timedelta(seconds=30)
    diff = abs((job.next_run - expected).total_seconds())  # type: ignore[operator]
    assert diff < 1


def test_once_job_runs_once() -> None:
    """Once job should only fire once."""
    job = Job(name="test", fn=lambda: None)
    job._once = True
    job._next_run = datetime.now() - timedelta(seconds=1)
    assert job.should_run(datetime.now()) is True

    job._executed = True
    assert job.should_run(datetime.now()) is False


def test_once_job_next_run_after_executed() -> None:
    """Once job next_run is None after execution."""
    job = Job(name="test", fn=lambda: None)
    job._once = True
    job._next_run = datetime.now()
    job._executed = True
    assert job.next_run is None


def test_async_job_detection() -> None:
    """Async functions are detected correctly."""
    scheduler = Scheduler()

    async def async_task() -> None:
        pass

    scheduler.add("async-job", fn=async_task, interval_seconds=10)
    assert scheduler.jobs[0].is_async is True


def test_pause_and_resume():
    scheduler = Scheduler()
    called = False

    def job_fn():
        nonlocal called
        called = True

    scheduler.add("test-job", fn=job_fn, interval_seconds=1)
    scheduler.pause("test-job")

    job = scheduler._get_job("test-job")
    assert job is not None
    assert job._paused is True
    assert job.should_run(datetime.now()) is False

    scheduler.resume("test-job")
    assert job._paused is False


def test_pause_nonexistent():
    scheduler = Scheduler()
    assert scheduler.pause("nonexistent") is False


def test_resume_nonexistent():
    scheduler = Scheduler()
    assert scheduler.resume("nonexistent") is False


def test_job_count():
    scheduler = Scheduler()
    assert scheduler.job_count == 0
    scheduler.add("job1", fn=lambda: None, interval_seconds=60)
    assert scheduler.job_count == 1
    scheduler.add("job2", fn=lambda: None, interval_seconds=60)
    assert scheduler.job_count == 2
    scheduler.remove("job1")
    assert scheduler.job_count == 1


def test_clear():
    scheduler = Scheduler()
    scheduler.add("job1", fn=lambda: None, interval_seconds=60)
    scheduler.add("job2", fn=lambda: None, interval_seconds=60)
    assert scheduler.job_count == 2
    scheduler.clear()
    assert scheduler.job_count == 0
    assert scheduler.jobs == []


def test_is_running():
    scheduler = Scheduler()
    assert scheduler.is_running is False
    scheduler.start(background=True)
    assert scheduler.is_running is True
    scheduler.stop()
    assert scheduler.is_running is False
