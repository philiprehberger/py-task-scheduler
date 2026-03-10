"""Cron-like task scheduler with overlap prevention and interval support."""

from __future__ import annotations

import asyncio
import signal
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

__all__ = ["Scheduler", "Job"]

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
    fn: Callable
    cron_parsed: tuple[set[int], ...] | None = None
    interval_seconds: float | None = None
    delay_seconds: float | None = None
    overlap: bool = True
    is_async: bool = False
    _running: bool = field(default=False, repr=False)
    _last_run: datetime | None = field(default=None, repr=False)
    _next_run: datetime | None = field(default=None, repr=False)
    _once: bool = field(default=False, repr=False)
    _executed: bool = field(default=False, repr=False)

    def should_run(self, now: datetime) -> bool:
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
        if self._once:
            return self._next_run if not self._executed else None
        if self.cron_parsed:
            return _next_cron_time(self.cron_parsed)
        if self.interval_seconds and self._last_run:
            return self._last_run + timedelta(seconds=self.interval_seconds)
        return None


class Scheduler:
    """Cron-like task scheduler."""

    def __init__(self) -> None:
        self._jobs: list[Job] = []
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def jobs(self) -> list[Job]:
        return list(self._jobs)

    def cron(
        self,
        expression: str,
        overlap: bool = True,
        name: str | None = None,
    ) -> Callable:
        """Decorator to schedule a function with a cron expression."""
        parsed = _parse_cron(expression)

        def decorator(fn: Callable) -> Callable:
            job = Job(
                name=name or fn.__name__,
                fn=fn,
                cron_parsed=parsed,
                overlap=overlap,
                is_async=asyncio.iscoroutinefunction(fn),
            )
            self._jobs.append(job)
            return fn

        return decorator

    def interval(
        self,
        seconds: float = 0,
        minutes: float = 0,
        hours: float = 0,
        overlap: bool = True,
        name: str | None = None,
    ) -> Callable:
        """Decorator to schedule a function at a fixed interval."""
        total_seconds = seconds + minutes * 60 + hours * 3600
        if total_seconds <= 0:
            raise ValueError("Interval must be positive")

        def decorator(fn: Callable) -> Callable:
            job = Job(
                name=name or fn.__name__,
                fn=fn,
                interval_seconds=total_seconds,
                overlap=overlap,
                is_async=asyncio.iscoroutinefunction(fn),
            )
            self._jobs.append(job)
            return fn

        return decorator

    def once(
        self,
        delay: float = 0,
        name: str | None = None,
    ) -> Callable:
        """Decorator to schedule a function to run once after a delay."""
        def decorator(fn: Callable) -> Callable:
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
        fn: Callable,
        cron: str | None = None,
        interval_seconds: float | None = None,
        overlap: bool = True,
    ) -> Job:
        """Programmatically add a job."""
        job = Job(
            name=name,
            fn=fn,
            cron_parsed=_parse_cron(cron) if cron else None,
            interval_seconds=interval_seconds,
            overlap=overlap,
            is_async=asyncio.iscoroutinefunction(fn),
        )
        self._jobs.append(job)
        return job

    def remove(self, name: str) -> bool:
        """Remove a job by name."""
        before = len(self._jobs)
        self._jobs = [j for j in self._jobs if j.name != name]
        return len(self._jobs) < before

    def _run_job(self, job: Job) -> None:
        """Execute a job."""
        job._running = True
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
            # Swallow exceptions to keep scheduler running
            pass
        finally:
            job._running = False
            job._last_run = datetime.now()
            if job._once:
                job._executed = True

    def _tick(self) -> None:
        now = datetime.now()
        for job in self._jobs:
            if job.should_run(now):
                if job.overlap or not job._running:
                    thread = threading.Thread(
                        target=self._run_job,
                        args=(job,),
                        daemon=True,
                    )
                    thread.start()

    def start(self, background: bool = False) -> None:
        """Start the scheduler.

        Args:
            background: If True, run in a background thread.
        """
        self._running = True

        if background:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        else:
            self._loop()

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False

    def _loop(self) -> None:
        while self._running:
            self._tick()
            time.sleep(1)

    def next_runs(self) -> list[tuple[str, datetime | None]]:
        """Get the next run time for each job."""
        return [(job.name, job.next_run) for job in self._jobs]
