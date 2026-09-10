"""Day 6: an end-to-end demonstration of the banking system."""

__all__ = ["run_demo"]


def run_demo(*args, **kwargs):
    """Lazily expose the runnable demo without affecting ``python -m``."""
    from .main import run_demo as _run_demo
    return _run_demo(*args, **kwargs)
