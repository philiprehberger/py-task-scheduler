# Changelog

## 0.3.0 (2026-04-06)

- Add `pause(name)` and `resume(name)` to pause and resume individual jobs
- Add `job_count` property to get the number of registered jobs
- Add `clear()` to remove all registered jobs
- Add `is_running` property to check scheduler state

## 0.2.0 (2026-04-01)

- Add task execution history with configurable limit (`history`, `get_job_history()`)
- Add `ExecutionRecord` dataclass with status, duration, and error tracking
- Add `ExecutionStatus` enum for success/failure states
- Add task dependencies via `depends_on` parameter on `cron()`, `interval()`, and `add()`
- Add graceful shutdown with `stop(wait=True, timeout=...)` to finish running tasks
- Add missed job handling with `MissedJobPolicy` (SKIP, RUN_ONCE, RUN_ALL)
- Add comprehensive test suite for all features

## 0.1.9 (2026-03-31)

- Standardize README to 3-badge format with emoji Support section
- Update CI checkout action to v5 for Node.js 24 compatibility
- Add GitHub issue templates, dependabot config, and PR template

## 0.1.8 (2026-03-22)

- Add pytest and mypy configuration to pyproject.toml

## 0.1.5 (2026-03-20)

- Add basic import test

## 0.1.4 (2026-03-18)

- Add Development section to README

## 0.1.1 (2026-03-12)

- Add project URLs to pyproject.toml

## 0.1.0 (2026-03-10)

- Initial release
