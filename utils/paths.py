"""Where the project keeps its files, plus safe path handling.

All locations are built with ``pathlib`` relative to the project folder, so
they work the same on Windows, macOS and Linux and never depend on where the
program is started from.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

LOG_DIR = PROJECT_ROOT / "logs"
MODEL_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "results"
CSV_DIR = RESULTS_DIR / "csv"
GRAPH_DIR = RESULTS_DIR / "graphs"
REPORT_DIR = RESULTS_DIR / "reports"
SETTINGS_FILE = PROJECT_ROOT / "config" / "user_settings.json"

REQUIRED_DIRECTORIES: tuple[Path, ...] = (
    LOG_DIR,
    MODEL_DIR,
    CSV_DIR,
    GRAPH_DIR,
    REPORT_DIR,
)


def ensure_directories(directories: Iterable[Path] = REQUIRED_DIRECTORIES) -> list[Path]:
    """Create any missing folders and return the ones that were created.

    Raises ``OSError`` (for example a permission problem) if a folder cannot be
    created; callers turn that into a friendly message.
    """
    created: list[Path] = []
    for directory in directories:
        if not directory.is_dir():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(directory)
    return created


def safe_join(base: Path | str, *parts: str) -> Path:
    """Join ``parts`` onto ``base`` but refuse to leave ``base``.

    Use this for any file name that comes from a user, so that values such as
    ``../../something`` or an absolute path cannot reach outside the intended
    folder.  Raises ``ValueError`` for an unsafe or empty name.
    """
    root = Path(base).resolve()
    if not parts or any(not part for part in parts):
        raise ValueError("A file name is required.")
    candidate = root.joinpath(*parts).resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise ValueError(f"Unsafe file path: {'/'.join(parts)!r} is outside {root}.")
    return candidate
