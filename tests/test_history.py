"""Tests for execution history tracking."""

from __future__ import annotations

import time
from datetime import datetime

from philiprehberger_task_scheduler import (
    Scheduler,
    ExecutionRecord,
    ExecutionStatus,
)


def test_history_recorded_on_success() -> None:
    """Successful job execution is recorded in history."""
    scheduler = Scheduler()
    scheduler.add("job-a", fn=lambda: None, interval_seconds=1)
    scheduler.start(background=True)
    time.sleep(2.5)
    scheduler.stop()

    history = scheduler.history
    assert len(history) >= 1
    record = history[0]
    assert record.job_name == "job-a"
    assert record.status == ExecutionStatus.SUCCESS
    assert record.error is None
    assert record.duration_seconds >= 0
    assert isinstance(record.started_at, datetime)
    assert isinstance(record.finished_at, datetime)


def test_history_recorded_on_failure() -> None:
    """Failed job execution is recorded with error."""
    scheduler = Scheduler()

    def failing_task() -> None:
        raise RuntimeError("task broke")

    scheduler.add("fail-job", fn=failing_task, interval_seconds=1)
    scheduler.start(background=True)
    time.sleep(2.5)
    scheduler.stop()

    history = scheduler.history
    assert len(history) >= 1
    record = history[0]
    assert record.status == ExecutionStatus.FAILED
    assert record.error == "task broke"


def test_history_limit() -> None:
    """History respects the configured limit."""
    scheduler = Scheduler(history_limit=3)
    counter = {"value": 0}

    def counting_task() -> None:
        counter["value"] += 1

    scheduler.add("counter", fn=counting_task, interval_seconds=0.3)
    scheduler.start(background=True)
    time.sleep(3)
    scheduler.stop()

    assert len(scheduler.history) <= 3


def test_history_newest_first() -> None:
    """History returns records newest first."""
    scheduler = Scheduler()
    scheduler.add("job", fn=lambda: None, interval_seconds=0.5)
    scheduler.start(background=True)
    time.sleep(2.5)
    scheduler.stop()

    history = scheduler.history
    if len(history) >= 2:
        assert history[0].started_at >= history[1].started_at


def test_get_job_history() -> None:
    """Per-job history filtering works."""
    scheduler = Scheduler()
    scheduler.add("alpha", fn=lambda: None, interval_seconds=0.5)
    scheduler.add("beta", fn=lambda: None, interval_seconds=0.5)
    scheduler.start(background=True)
    time.sleep(2.5)
    scheduler.stop()

    alpha_history = scheduler.get_job_history("alpha")
    beta_history = scheduler.get_job_history("beta")
    assert all(r.job_name == "alpha" for r in alpha_history)
    assert all(r.job_name == "beta" for r in beta_history)


def test_empty_history() -> None:
    """History is empty before any jobs run."""
    scheduler = Scheduler()
    assert scheduler.history == []
    assert scheduler.get_job_history("nothing") == []


def test_execution_record_fields() -> None:
    """ExecutionRecord has all expected fields."""
    record = ExecutionRecord(
        job_name="test",
        started_at=datetime(2026, 1, 1, 12, 0, 0),
        finished_at=datetime(2026, 1, 1, 12, 0, 1),
        status=ExecutionStatus.SUCCESS,
        duration_seconds=1.0,
        error=None,
    )
    assert record.job_name == "test"
    assert record.duration_seconds == 1.0
    assert record.error is None


def test_execution_status_values() -> None:
    """ExecutionStatus has correct values."""
    assert ExecutionStatus.SUCCESS.value == "success"
    assert ExecutionStatus.FAILED.value == "failed"
