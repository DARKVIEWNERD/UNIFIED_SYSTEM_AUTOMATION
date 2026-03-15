# stop_flag.py
# ─────────────────────────────────────────────────────────────────────────────
# Single source of truth for the stop signal.
#
# ALL modules import from here — no more per-module STOP_AUTOMATION globals.
# The Automation_Tab sets it; main.py, automation_engine_initial.py, and
# apptweak_integration.py read it.
# ─────────────────────────────────────────────────────────────────────────────
import threading
import time

_lock = threading.Lock()
_stop = False


def request_stop():
    """Called by Automation_Tab when the user clicks ⏹ STOP."""
    global _stop
    with _lock:
        _stop = True


def clear_stop():
    """Called at the start of every new run to reset the flag."""
    global _stop
    with _lock:
        _stop = False


def should_stop() -> bool:
    """Checked by every loop in the engine files."""
    with _lock:
        return _stop


def interruptible_sleep(seconds: float, interval: float = 0.25):
    """
    Drop-in replacement for time.sleep() that wakes up early if stop is
    requested.  Use this everywhere the engine has a long sleep so the stop
    response is near-instant.

    Args:
        seconds:  total intended sleep duration
        interval: how often to check the stop flag (default 0.25 s)
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if should_stop():
            return
        time.sleep(min(interval, deadline - time.monotonic()))