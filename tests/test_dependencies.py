"""Tests for task dependency functionality."""

from __future__ import annotations

import time
import threading

from philiprehberger_task_scheduler import Scheduler


def test_dependency_runs_after_parent() -> None:
    """Dependent job runs after its parent completes."""
    scheduler = Scheduler()
    order: list[str] = []
    lock = threading.Lock()

    def task_a() -> None:
        with lock:
            order.append("a")

    def task_b() -> None:
        with lock:
            order.append("b")

    scheduler.add("task-a", fn=task_a, interval_seconds=1)
    scheduler.add("task-b", fn=task_b, interval_seconds=1, depends_on="task-a")

    scheduler.start(background=True)
    time.sleep(3)
    scheduler.stop()

    with lock:
        a_indices = [i for i, v in enumerate(order) if v == "a"]
        b_indices = [i for i, v in enumerate(order) if v == "b"]

    # B should have run at least once, and first A should be before first B
    assert len(a_indices) >= 1
    assert len(b_indices) >= 1
    assert a_indices[0] < b_indices[0]


def test_dependency_not_triggered_on_failure() -> None:
    """Dependent job does not run if parent fails."""
    scheduler = Scheduler()
    results: list[str] = []
    lock = threading.Lock()

    def failing_parent() -> None:
        raise RuntimeError("parent failed")

    def child_task() -> None:
        with lock:
            results.append("child_ran")

    scheduler.add("parent", fn=failing_parent, interval_seconds=1)
    scheduler.add("child", fn=child_task, interval_seconds=1, depends_on="parent")

    scheduler.start(background=True)
    time.sleep(3)
    scheduler.stop()

    with lock:
        assert "child_ran" not in results


def test_dependency_via_decorator() -> None:
    """Dependency can be set via decorator."""
    scheduler = Scheduler()
    order: list[str] = []
    lock = threading.Lock()

    @scheduler.interval(seconds=1, name="first")
    def first() -> None:
        with lock:
            order.append("first")

    @scheduler.interval(seconds=1, name="second", depends_on="first")
    def second() -> None:
        with lock:
            order.append("second")

    scheduler.start(background=True)
    time.sleep(3)
    scheduler.stop()

    with lock:
        assert "first" in order
        assert "second" in order


def test_dependency_via_cron_decorator() -> None:
    """Dependency can be set via cron decorator."""
    scheduler = Scheduler()

    @scheduler.cron("* * * * *", name="cron-parent")
    def parent() -> None:
        pass

    @scheduler.cron("* * * * *", name="cron-child", depends_on="cron-parent")
    def child() -> None:
        pass

    job = scheduler.jobs[1]
    assert job.depends_on == "cron-parent"


def test_remove_cleans_dependencies() -> None:
    """Removing a job cleans up dependency references."""
    scheduler = Scheduler()
    scheduler.add("parent", fn=lambda: None, interval_seconds=10)
    scheduler.add("child", fn=lambda: None, interval_seconds=10, depends_on="parent")

    scheduler.remove("child")
    # The dependency list for parent should be empty
    assert scheduler._dependencies.get("parent", []) == []


def test_dependency_on_nonexistent_job() -> None:
    """Job with dependency on removed parent still runs when triggered."""
    scheduler = Scheduler()
    results: list[str] = []

    def child() -> None:
        results.append("ran")

    # Add child with a dependency that doesn't exist
    job = scheduler.add("child", fn=child, interval_seconds=1, depends_on="ghost")

    # _can_run_dependency should return True for missing parent
    assert scheduler._can_run_dependency(job) is True
