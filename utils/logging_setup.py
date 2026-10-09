"""Application logging.

Technical details (including error tracebacks) go to ``logs/application.log``.
The console only shows warnings and errors, so normal users are not flooded
with technical output.  No personal information is ever logged.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE_NAME = "application.log"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_MAX_LOG_BYTES = 1_000_000
_BACKUP_COUNT = 3
_MARKER = "_smart_traffic_handler"


def setup_logging(
    log_dir: Path,
    level: int = logging.INFO,
    console_level: int = logging.WARNING,
) -> Path | None:
    """Start logging to ``log_dir/application.log``.

    Safe to call more than once.  Returns the log file path, or ``None`` if the
    file could not be opened (the program then keeps running with console
    logging only).
    """
    teardown_logging()
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(console_level)
    console.setFormatter(formatter)
    setattr(console, _MARKER, True)
    root.addHandler(console)

    log_path = Path(log_dir) / LOG_FILE_NAME
    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=_MAX_LOG_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError as exc:
        logging.getLogger(__name__).warning(
            "Could not open the log file %s (%s); continuing without it.", log_path, exc
        )
        return None
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    setattr(file_handler, _MARKER, True)
    root.addHandler(file_handler)
    return log_path


def teardown_logging() -> None:
    """Close and remove the handlers installed by :func:`setup_logging`."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _MARKER, False):
            root.removeHandler(handler)
            handler.close()
