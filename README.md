# philiprehberger-task-scheduler

Cron-like task scheduler with overlap prevention and interval support.

## Install

```bash
pip install philiprehberger-task-scheduler
```

## Usage

### Cron Scheduling

```python
from philiprehberger_task_scheduler import Scheduler

scheduler = Scheduler()

@scheduler.cron("*/5 * * * *")  # every 5 minutes
def check_health():
    ping_server()

@scheduler.cron("0 9 * * 1-5", overlap=False)  # weekdays at 9am
def daily_report():
    generate_and_send_report()

scheduler.start()  # blocks
```

### Interval Scheduling

```python
@scheduler.interval(seconds=30)
def poll_queue():
    process_messages()

@scheduler.interval(minutes=5, overlap=False)
def sync_data():
    pull_latest_data()
```

### One-Shot Tasks

```python
@scheduler.once(delay=10)  # run once after 10 seconds
def startup_task():
    warm_cache()
```

### Background Mode

```python
scheduler.start(background=True)
# ... your app continues running ...
scheduler.stop()
```

### Programmatic API

```python
scheduler.add("my-job", fn=my_function, cron="0 * * * *")
scheduler.add("poller", fn=poll, interval_seconds=60)
scheduler.remove("my-job")
```

### Next Run Preview

```python
for name, next_time in scheduler.next_runs():
    print(f"{name}: next at {next_time}")
```

## Cron Syntax

Standard 5-field cron expressions:

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Mon-Sun)
│ │ │ │ │
* * * * *
```

Supports: `*`, ranges (`1-5`), lists (`1,3,5`), steps (`*/5`).

## License

MIT
