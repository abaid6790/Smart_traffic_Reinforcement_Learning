"""Run slow work (training, experiments) in a background thread.  Plain Python.

The window must keep responding while a training run or an experiment is going, so
the work runs in a thread and the screen only *reads* its progress each frame.  A job
can be paused, resumed and stopped.  If the work raises an error the job ends in the
``failed`` state with a plain-English message instead of the program crashing, and the
technical details go to the log file.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

IDLE, RUNNING, PAUSED, STOPPING, DONE, STOPPED, FAILED = (
    "idle", "running", "paused", "stopping", "done", "stopped", "failed")
ACTIVE_STATES = (RUNNING, PAUSED, STOPPING)


class BackgroundJob:
    """One piece of work running in its own thread.

    ``work(job)`` does the job.  It reports with :meth:`report`, checks
    :meth:`should_stop` regularly and calls :meth:`wait_if_paused` where pausing is safe.
    Whatever ``work`` returns is kept in :attr:`result`.
    """

    def __init__(self, name: str, work: Callable[[BackgroundJob], Any]) -> None:
        self.name = name
        self._work = work
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._running = threading.Event()
        self._running.set()
        self._thread: threading.Thread | None = None
        self._state = IDLE
        self._done = 0
        self._total = 0
        self._text = ""
        self._started = 0.0
        self._ended = 0.0
        self.result: Any = None
        self.error: str | None = None

    # ---- reading (from the window) ------------------------------------------------------

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def active(self) -> bool:
        return self.state in ACTIVE_STATES

    @property
    def finished(self) -> bool:
        return self.state in (DONE, STOPPED, FAILED)

    @property
    def progress(self) -> tuple[int, int, str]:
        with self._lock:
            return self._done, self._total, self._text

    @property
    def fraction(self) -> float:
        done, total, _ = self.progress
        return 0.0 if total <= 0 else max(0.0, min(1.0, done / total))

    @property
    def elapsed(self) -> float:
        with self._lock:
            if self._started == 0.0:
                return 0.0
            return (self._ended or time.perf_counter()) - self._started

    @property
    def eta_seconds(self) -> float | None:
        """Estimated seconds left, or None until there is something to base it on."""
        done, total, _ = self.progress
        if done <= 0 or total <= done or not self.active:
            return None
        return self.elapsed / done * (total - done)

    # ---- control (from the window) ---------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._state in ACTIVE_STATES:
                raise RuntimeError(f"{self.name} is already running.")
            self._state = RUNNING
            self._done = self._total = 0
            self._text = ""
            self._started, self._ended = time.perf_counter(), 0.0
            self.result, self.error = None, None
        self._stop.clear()
        self._running.set()
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        with self._lock:
            if self._state != RUNNING:
                return
            self._state = PAUSED
        self._running.clear()

    def resume(self) -> None:
        with self._lock:
            if self._state != PAUSED:
                return
            self._state = RUNNING
        self._running.set()

    def request_stop(self) -> None:
        """Ask the work to end soon; it finishes its current small step first."""
        with self._lock:
            if self._state not in (RUNNING, PAUSED):
                return
            self._state = STOPPING
        self._stop.set()
        self._running.set()  # wake a paused job so it can see the request

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for the thread to end (used by tests and when closing).  True if it ended."""
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    # ---- used by the work itself ---------------------------------------------------------

    def report(self, done: int, total: int, text: str = "") -> None:
        with self._lock:
            self._done, self._total, self._text = done, total, text

    def should_stop(self) -> bool:
        return self._stop.is_set()

    def wait_if_paused(self) -> None:
        self._running.wait()

    # ---- the thread ---------------------------------------------------------------------------

    def _run(self) -> None:
        try:
            result = self._work(self)
        except (ValueError, OSError, RuntimeError, ImportError) as exc:
            log.exception("%s failed", self.name)
            self._finish(FAILED, error=_friendly(exc))
        except Exception as exc:  # noqa: BLE001 - a background thread must never die silently
            log.exception("%s failed unexpectedly", self.name)
            self._finish(FAILED, error=f"Unexpected error: {_friendly(exc)} (details are in logs/application.log)")
        else:
            self._finish(STOPPED if self._stop.is_set() else DONE, result=result)

    def _finish(self, state: str, result: Any = None, error: str | None = None) -> None:
        with self._lock:
            self._state = state
            self.result = result
            self.error = error
            self._ended = time.perf_counter()


def _friendly(exc: BaseException) -> str:
    problems = getattr(exc, "problems", None)
    if problems:
        return " ".join(problems)
    return str(exc) or exc.__class__.__name__
