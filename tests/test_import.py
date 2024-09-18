"""Basic import test."""


def test_import() -> None:
    """Verify the package can be imported."""
    import philiprehberger_task_scheduler
    assert hasattr(philiprehberger_task_scheduler, "__name__") or True


def test_all_exports() -> None:
    """Verify all expected exports are in __all__."""
    from philiprehberger_task_scheduler import __all__
    expected = ["Scheduler", "Job", "ExecutionRecord", "ExecutionStatus", "MissedJobPolicy"]
    for name in expected:
        assert name in __all__


def test_import_public_api() -> None:
    """Verify all public symbols can be imported."""
    from philiprehberger_task_scheduler import (
        Scheduler,
        Job,
        ExecutionRecord,
        ExecutionStatus,
        MissedJobPolicy,
    )
    assert Scheduler is not None
    assert Job is not None
    assert ExecutionRecord is not None
    assert ExecutionStatus is not None
    assert MissedJobPolicy is not None
