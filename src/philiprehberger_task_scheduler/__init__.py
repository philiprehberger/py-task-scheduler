"""Cron-like task scheduler with overlap prevention and interval support."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable

__all__ = [
    "Scheduler",
    "Job",
    "ExecutionRecord",
    "ExecutionStatus",
    "MissedJobPolicy",
]


class ExecutionStatus(Enum):
    """Status of a job execution."""

    SUCCESS = "success"
    FAILED = "failed"


class MissedJobPolicy(Enum):
    """Policy for handling missed jobs during downtime."""

    SKIP = "skip"
    RUN_ONCE = "run_once"
    RUN_ALL = "run_all"


@dataclass
class ExecutionRecord:
    """Record of a single job execution."""

    job_name: str
    started_at: datetime
    finished_at: datetime
    status: ExecutionStatus
    duration_seconds: float
    error: str | None = None


# Cron field parsers
def _parse_cron_field(field_str: str, min_val: int, max_val: int) -> set[int]:
    """Parse a single cron field into a set of valid values."""
    values: set[int] = set()
    for part in field_str.split(","):
        part = part.strip()
        if part == "*":
            values.update(range(min_val, max_val + 1))
        elif "/" in part:
            base, step_str = part.split("/", 1)
            step = int(step_str)
            if base == "*":
                start = min_val
            elif "-" in base:
                start = int(base.split("-")[0])
            else:
                start = int(base)
            values.update(range(start, max_val + 1, step))
        elif "-" in part:
            low, high = part.split("-", 1)
            values.update(range(int(low), int(high) + 1))
        else:
            values.add(int(part))
    return values


def _parse_cron(expression: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    """Parse a 5-field cron expression into (minute, hour, dom, month, dow)."""
    parts = expression.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression (need 5 fields): {expression}")

    minutes = _parse_cron_field(parts[0], 0, 59)
    hours = _parse_cron_field(parts[1], 0, 23)
    dom = _parse_cron_field(parts[2], 1, 31)
    months = _parse_cron_field(parts[3], 1, 12)
    dow = _parse_cron_field(parts[4], 0, 6)

    return minutes, hours, dom, months, dow


def _cron_matches(dt: datetime, parsed: tuple[set[int], ...]) -> bool:
    """Check if a datetime matches a parsed cron expression."""
    minutes, hours, dom, months, dow = parsed
    return (
        dt.minute in minutes
        and dt.hour in hours
        and dt.day in dom
        and dt.month in months
        and dt.weekday() in dow  # Python: Monday=0, Sunday=6
    )


def _next_cron_time(parsed: tuple[set[int], ...], after: datetime | None = None) -> datetime:
    """Find the next datetime that matches the cron expression."""
    dt = (after or datetime.now()).replace(second=0, microsecond=0) + timedelta(minutes=1)
    # Search up to 2 years ahead
    limit = dt + timedelta(days=730)
    while dt < limit:
        if _cron_matches(dt, parsed):
            return dt
        dt += timedelta(minutes=1)
    raise ValueError("Could not find next matching time within 2 years")


@dataclass
class Job:
    """A scheduled job."""

    name: str
    fn: Callable[..., Any]
    cron_parsed: tuple[set[int], ...] | None = None
    interval_seconds: float | None = None
    delay_seconds: float | None = None
    overlap: bool = True
    is_async: bool = False
    depends_on: str | None = None
    missed_policy: MissedJobPolicy = MissedJobPolicy.SKIP
    _running: bool = field(default=False, repr=False)
    _last_run: datetime | None = field(default=None, repr=False)
    _next_run: datetime | None = field(default=None, repr=False)
    _once: bool = field(default=False, repr=False)
    _executed: bool = field(default=False, repr=False)
    _paused: bool = field(default=False, repr=False)

    def should_run(self, now: datetime) -> bool:
        """Check if the job should run at the given time."""
        if self._paused:
            return False
        if self._once:
            if self._executed:
                return False
            if self._next_run and now >= self._next_run:
                return True
            return False

        if not self.overlap and self._running:
            return False

        if self.cron_parsed:
            return _cron_matches(now, self.cron_parsed) and (
                self._last_run is None or self._last_run.minute != now.minute
                or self._last_run.hour != now.hour
            )

        if self.interval_seconds and self._last_run:
            elapsed = (now - self._last_run).total_seconds()
            return elapsed >= self.interval_seconds

        if self.interval_seconds and self._last_run is None:
            return True

        return False

    @property
    def next_run(self) -> datetime | None:
        """Get the next scheduled run time."""
        if self._once:
            return self._next_run if not self._executed else None
        if self.cron_parsed:
            return _next_cron_time(self.cron_parsed)
        if self.interval_seconds and self._last_run:
            return self._last_run + timedelta(seconds=self.interval_seconds)
        return None


class Scheduler:
    """Cron-like task scheduler with execution history and dependency support."""

    def __init__(self, history_limit: int = 100) -> None:
        self._jobs: list[Job] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._history: deque[ExecutionRecord] = deque(maxlen=history_limit)
        self._history_limit = history_limit
        self._active_threads: list[threading.Thread] = []
        self._active_threads_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._last_shutdown_time: datetime | None = None
        self._dependencies: dict[str, list[str]] = {}

    @property
    def jobs(self) -> list[Job]:
        """Get a copy of the job list."""
        return list(self._jobs)

    @property
    def history(self) -> list[ExecutionRecord]:
        """Get a copy of the execution history, newest first."""
        return list(reversed(self._history))

    def get_job_history(self, name: str) -> list[ExecutionRecord]:
        """Get execution history for a specific job, newest first."""
        return [r for r in reversed(self._history) if r.job_name == name]

    def cron(
        self,
        expression: str,
        overlap: bool = True,
        name: str | None = None,
        depends_on: str | None = None,
        missed_policy: MissedJobPolicy = MissedJobPolicy.SKIP,
    ) -> Callable[..., Any]:
        """Decorator to schedule a function with a cron expression."""
        parsed = _parse_cron(expression)

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            job = Job(
                name=name or fn.__name__,
                fn=fn,
                cron_parsed=parsed,
                overlap=overlap,
                is_async=asyncio.iscoroutinefunction(fn),
                depends_on=depends_on,
                missed_policy=missed_policy,
            )
            self._jobs.append(job)
            if depends_on:
                self._dependencies.setdefault(depends_on, []).append(job.name)
            return fn

        return decorator

    def interval(
        self,
        seconds: float = 0,
        minutes: float = 0,
        hours: float = 0,
        overlap: bool = True,
        name: str | None = None,
        depends_on: str | None = None,
        missed_policy: MissedJobPolicy = MissedJobPolicy.SKIP,
    ) -> Callable[..., Any]:
        """Decorator to schedule a function at a fixed interval."""
        total_seconds = seconds + minutes * 60 + hours * 3600
        if total_seconds <= 0:
            raise ValueError("Interval must be positive")

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            job = Job(
                name=name or fn.__name__,
                fn=fn,
                interval_seconds=total_seconds,
                overlap=overlap,
                is_async=asyncio.iscoroutinefunction(fn),
                depends_on=depends_on,
                missed_policy=missed_policy,
            )
            self._jobs.append(job)
            if depends_on:
                self._dependencies.setdefault(depends_on, []).append(job.name)
            return fn

        return decorator

    def once(
        self,
        delay: float = 0,
        name: str | None = None,
    ) -> Callable[..., Any]:
        """Decorator to schedule a function to run once after a delay."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            job = Job(
                name=name or fn.__name__,
                fn=fn,
                is_async=asyncio.iscoroutinefunction(fn),
            )
            job._once = True
            job._next_run = datetime.now() + timedelta(seconds=delay)
            self._jobs.append(job)
            return fn

        return decorator

    def add(
        self,
        name: str,
        fn: Callable[..., Any],
        cron: str | None = None,
        interval_seconds: float | None = None,
        overlap: bool = True,
        depends_on: str | None = None,
        missed_policy: MissedJobPolicy = MissedJobPolicy.SKIP,
    ) -> Job:
        """Programmatically add a job."""
        job = Job(
            name=name,
            fn=fn,
            cron_parsed=_parse_cron(cron) if cron else None,
            interval_seconds=interval_seconds,
            overlap=overlap,
            is_async=asyncio.iscoroutinefunction(fn),
            depends_on=depends_on,
            missed_policy=missed_policy,
        )
        self._jobs.append(job)
        if depends_on:
            self._dependencies.setdefault(depends_on, []).append(name)
        return job

    def remove(self, name: str) -> bool:
        """Remove a job by name."""
        before = len(self._jobs)
        self._jobs = [j for j in self._jobs if j.name != name]
        # Clean up dependency references
        self._dependencies.pop(name, None)
        for dep_name, dependents in list(self._dependencies.items()):
            self._dependencies[dep_name] = [d for d in dependents if d != name]
        return len(self._jobs) < before

    def _get_job(self, name: str) -> Job | None:
        """Get a job by name."""
        for job in self._jobs:
            if job.name == name:
                return job
        return None

    def _can_run_dependency(self, job: Job) -> bool:
        """Check if a job's dependency has been satisfied."""
        if job.depends_on is None:
            return True
        dep_job = self._get_job(job.depends_on)
        if dep_job is None:
            return True  # Dependency removed, allow run
        # Dependency must have run and not be currently running
        return dep_job._last_run is not None and not dep_job._running

    def _run_job(self, job: Job) -> None:
        """Execute a job and record the result."""
        job._running = True
        started_at = datetime.now()
        error_msg: str | None = None
        status = ExecutionStatus.SUCCESS
        try:
            if job.is_async:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(job.fn())
                finally:
                    loop.close()
            else:
                job.fn()
        except Exception as e:
            status = ExecutionStatus.FAILED
            error_msg = str(e)
        finally:
            finished_at = datetime.now()
            job._running = False
            job._last_run = finished_at
            if job._once:
                job._executed = True

            record = ExecutionRecord(
                job_name=job.name,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                duration_seconds=(finished_at - started_at).total_seconds(),
                error=error_msg,
            )
            self._history.append(record)

            # Trigger dependent jobs on success
            if status == ExecutionStatus.SUCCESS:
                self._run_dependents(job.name)

    def _run_dependents(self, parent_name: str) -> None:
        """Run jobs that depend on the completed parent job."""
        dependent_names = self._dependencies.get(parent_name, [])
        for dep_name in dependent_names:
            dep_job = self._get_job(dep_name)
            if dep_job and not dep_job._running:
                thread = threading.Thread(
                    target=self._run_job,
                    args=(dep_job,),
                    daemon=True,
                )
                with self._active_threads_lock:
                    self._active_threads.append(thread)
                thread.start()

    def _check_missed_jobs(self) -> None:
        """Check for and handle missed jobs after downtime."""
        if self._last_shutdown_time is None:
            return

        now = datetime.now()
        for job in self._jobs:
            if job.missed_policy == MissedJobPolicy.SKIP:
                continue
            if job.cron_parsed is None:
                continue

            # Find all missed times between shutdown and now
            missed_times: list[datetime] = []
            check_time = self._last_shutdown_time.replace(second=0, microsecond=0)
            while check_time < now:
                check_time += timedelta(minutes=1)
                if check_time >= now:
                    break
                if _cron_matches(check_time, job.cron_parsed):
                    missed_times.append(check_time)

            if not missed_times:
                continue

            if job.missed_policy == MissedJobPolicy.RUN_ONCE:
                thread = threading.Thread(
                    target=self._run_job,
                    args=(job,),
                    daemon=True,
                )
                with self._active_threads_lock:
                    self._active_threads.append(thread)
                thread.start()
            elif job.missed_policy == MissedJobPolicy.RUN_ALL:
                for _ in missed_times:
                    thread = threading.Thread(
                        target=self._run_job,
                        args=(job,),
                        daemon=True,
                    )
                    with self._active_threads_lock:
                        self._active_threads.append(thread)
                    thread.start()

        self._last_shutdown_time = None

    def pause(self, name: str) -> bool:
        """Pause a job by name.

        Paused jobs are not executed during scheduler ticks but remain
        registered.

        Args:
            name: Name of the job to pause.

        Returns:
            True if the job was found and paused.
        """
        job = self._get_job(name)
        if job is None:
            return False
        job._paused = True
        return True

    def resume(self, name: str) -> bool:
        """Resume a paused job.

        Args:
            name: Name of the job to resume.

        Returns:
            True if the job was found and resumed.
        """
        job = self._get_job(name)
        if job is None:
            return False
        job._paused = False
        return True

    @property
    def job_count(self) -> int:
        """Return the number of registered jobs."""
        return len(self._jobs)

    def clear(self) -> None:
        """Remove all registered jobs."""
        self._jobs.clear()
        self._dependencies.clear()

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is currently running."""
        return self._running

    def _tick(self) -> None:
        """Execute one scheduler tick."""
        now = datetime.now()
        for job in self._jobs:
            if job.depends_on is not None:
                # Dependency-based jobs are triggered by their parent
                continue
            if job.should_run(now):
                if job.overlap or not job._running:
                    thread = threading.Thread(
                        target=self._run_job,
                        args=(job,),
                        daemon=True,
                    )
                    with self._active_threads_lock:
                        self._active_threads.append(thread)
                    thread.start()

    def start(self, background: bool = False) -> None:
        """Start the scheduler.

        Args:
            background: If True, run in a background thread.
        """
        self._running = True
        self._shutdown_event.clear()
        self._check_missed_jobs()

        if background:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        else:
            self._loop()

    def stop(self, wait: bool = False, timeout: float | None = None) -> None:
        """Stop the scheduler.

        Args:
            wait: If True, wait for running tasks to finish before returning.
            timeout: Maximum seconds to wait for running tasks (None = no limit).
        """
        self._running = False
        self._last_shutdown_time = datetime.now()

        if wait:
            self._wait_for_active_threads(timeout)

    def _wait_for_active_threads(self, timeout: float | None = None) -> None:
        """Wait for all active job threads to complete."""
        with self._active_threads_lock:
            threads = list(self._active_threads)

        deadline = time.monotonic() + timeout if timeout is not None else None
        for thread in threads:
            if not thread.is_alive():
                continue
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                thread.join(timeout=remaining)
            else:
                thread.join()

        # Clean up finished threads
        with self._active_threads_lock:
            self._active_threads = [t for t in self._active_threads if t.is_alive()]

    def _loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            self._tick()
            time.sleep(1)

    def next_runs(self) -> list[tuple[str, datetime | None]]:
        """Get the next run time for each job."""
        return [(job.name, job.next_run) for job in self._jobs]
