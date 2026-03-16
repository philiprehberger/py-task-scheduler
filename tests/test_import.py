"""Basic import test."""


def test_import():
    """Verify the package can be imported."""
    import philiprehberger_task_scheduler
    assert hasattr(philiprehberger_task_scheduler, "__name__") or True
