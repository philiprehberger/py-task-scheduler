# philiprehberger-task-scheduler

[![Tests](https://github.com/philiprehberger/py-task-scheduler/actions/workflows/publish.yml/badge.svg)](https://github.com/philiprehberger/py-task-scheduler/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/philiprehberger-task-scheduler.svg)](https://pypi.org/project/philiprehberger-task-scheduler/)
[![Last updated](https://img.shields.io/github/last-commit/philiprehberger/py-task-scheduler)](https://github.com/philiprehberger/py-task-scheduler/commits/main)

Cron-like task scheduler with overlap prevention and interval support.

## Installation

```bash
pip install philiprehberger-task-scheduler
```

## Usage

```python
from philiprehberger_task_scheduler import Scheduler

scheduler = Scheduler()

@scheduler.cron("*/5 * * * *")  # every 5 minutes
def check_health():
    ping_server()

scheduler.start()  # blocks
```

### Interval Scheduling

```python
from philiprehberger_task_scheduler import Scheduler

scheduler = Scheduler()

@scheduler.interval(seconds=30)
def poll_queue():
    process_messages()

@scheduler.interval(minutes=5, overlap=False)
def sync_data():
    pull_latest_data()
```

### One-Shot Tasks

```python
from philiprehberger_task_scheduler import Scheduler

scheduler = Scheduler()

@scheduler.once(delay=10)  # run once after 10 seconds
def startup_task():
    warm_cache()
```

### Background Mode

```python
from philiprehberger_task_scheduler import Scheduler

scheduler = Scheduler()
scheduler.start(background=True)
# ... your app continues running ...
scheduler.stop()
```

### Programmatic API

```python
from philiprehberger_task_scheduler import Scheduler

scheduler = Scheduler()
scheduler.add("my-job", fn=my_function, cron="0 * * * *")
scheduler.add("poller", fn=poll, interval_seconds=60)
scheduler.remove("my-job")
```

### Execution History

```python
from philiprehberger_task_scheduler import Scheduler

scheduler = Scheduler(history_limit=50)
scheduler.add("job", fn=my_function, interval_seconds=60)
scheduler.start(background=True)

# Get all history (newest first)
for record in scheduler.history:
    print(f"{record.job_name}: {record.status.value} in {record.duration_seconds:.2f}s")

# Get history for a specific job
for record in scheduler.get_job_history("job"):
    if record.error:
        print(f"Error: {record.error}")
```

### Next Run Preview

```python
from philiprehberger_task_scheduler import Scheduler

scheduler = Scheduler()
scheduler.add("job", fn=my_function, cron="0 * * * *")

for name, next_time in scheduler.next_runs():
    print(f"{name}: next at {next_time}")
```

### Task Dependencies

```python
from philiprehberger_task_scheduler import Scheduler

scheduler = Scheduler()

@scheduler.interval(seconds=60, name="fetch-data")
def fetch_data():
    download_latest()

@scheduler.interval(seconds=60, name="process-data", depends_on="fetch-data")
def process_data():
    transform_and_store()
```

### Graceful Shutdown

```python
from philiprehberger_task_scheduler import Scheduler

scheduler = Scheduler()
scheduler.start(background=True)

# Wait for running tasks to finish before stopping
scheduler.stop(wait=True)

# Or set a timeout (seconds)
scheduler.stop(wait=True, timeout=10)
```

### Missed Job Handling

```python
from philiprehberger_task_scheduler import Scheduler, MissedJobPolicy

scheduler = Scheduler()

@scheduler.cron("0 * * * *", missed_policy=MissedJobPolicy.RUN_ONCE)
def hourly_sync():
    sync_data()

@scheduler.cron("*/5 * * * *", missed_policy=MissedJobPolicy.RUN_ALL)
def critical_check():
    check_systems()
```

## Cron Syntax

Standard 5-field cron expressions:

```
minute (0-59)
hour (0-23)
day of month (1-31)
month (1-12)
day of week (0-6, Mon-Sun)
```

Supports: `*`, ranges (`1-5`), lists (`1,3,5`), steps (`*/5`).

## API

| Function / Class | Description |
|------------------|-------------|
| `Scheduler(history_limit)` | Task scheduler with cron, interval, and one-shot scheduling |
| `Scheduler.cron(expression, overlap, name, depends_on, missed_policy)` | Decorator to schedule with a cron expression |
| `Scheduler.interval(seconds, minutes, hours, overlap, name, depends_on, missed_policy)` | Decorator to schedule at a fixed interval |
| `Scheduler.once(delay, name)` | Decorator to schedule a one-shot task |
| `Scheduler.add(name, fn, cron, interval_seconds, overlap, depends_on, missed_policy)` | Programmatically add a job |
| `Scheduler.remove(name)` | Remove a job by name |
| `Scheduler.start(background)` | Start the scheduler (blocks unless `background=True`) |
| `Scheduler.stop(wait, timeout)` | Stop the scheduler with optional graceful shutdown |
| `Scheduler.next_runs()` | Get the next run time for each job |
| `Scheduler.history` | Execution history (newest first) |
| `Scheduler.get_job_history(name)` | Execution history for a specific job |
| `Job` | A scheduled job with name, function, schedule config, and `next_run` property |
| `ExecutionRecord` | Record of a job execution with status, duration, and error |
| `ExecutionStatus` | Enum: `SUCCESS`, `FAILED` |
| `MissedJobPolicy` | Enum: `SKIP`, `RUN_ONCE`, `RUN_ALL` |

## Development

```bash
pip install -e .
python -m pytest tests/ -v
```

## Support

If you find this project useful:

⭐ [Star the repo](https://github.com/philiprehberger/py-task-scheduler)

🐛 [Report issues](https://github.com/philiprehberger/py-task-scheduler/issues?q=is%3Aissue+is%3Aopen+label%3Abug)

💡 [Suggest features](https://github.com/philiprehberger/py-task-scheduler/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)

❤️ [Sponsor development](https://github.com/sponsors/philiprehberger)

🌐 [All Open Source Projects](https://philiprehberger.com/open-source-packages)

💻 [GitHub Profile](https://github.com/philiprehberger)

🔗 [LinkedIn Profile](https://www.linkedin.com/in/philiprehberger)

## License

[MIT](LICENSE)
