"""Centralized logging setup for SessionVault.

All application modules should obtain loggers via::

    from app.managers.logger import get_logger
    log = get_logger(__name__)

Log file: ~/.sessionvault/logs/app.log
  - Rotates at 5 MiB, keeps 3 backups
  - Level: DEBUG
Console:
  - Level: INFO
"""

from __future__ import annotations

import logging
import logging.handlers
import pathlib

_configured = False
_LOGS_DIR: pathlib.Path | None = None


def get_logger(name: str) -> logging.Logger:
    """Return a named logger under the 'sessionvault' hierarchy."""
    _configure_once()
    # Normalise name so all app loggers share the root handlers
    if not name.startswith("sessionvault"):
        name = f"sessionvault.{name}"
    return logging.getLogger(name)


def logs_dir() -> pathlib.Path | None:
    """Return the logs directory path (None until first call to get_logger)."""
    return _LOGS_DIR


def _configure_once() -> None:
    global _configured, _LOGS_DIR
    if _configured:
        return
    _configured = True

    # Late import to avoid circular imports at module load time
    from app.constants import DATA_DIR  # noqa: PLC0415

    _LOGS_DIR = DATA_DIR / "logs"
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("sessionvault")
    if root.handlers:
        return  # already configured (e.g. imported twice)

    root.setLevel(logging.DEBUG)

    _fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Rotating file handler ─────────────────────────────────────────
    fh = logging.handlers.RotatingFileHandler(
        _LOGS_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_fmt)
    root.addHandler(fh)

    # ── Console handler ───────────────────────────────────────────────
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(levelname)-8s  %(name)s  %(message)s"))
    root.addHandler(ch)
