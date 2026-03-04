"""Application settings persistence (~/.sessionvault/settings.json).

:class:`SettingsManager` is a lightweight key-value store backed by a JSON
file.  All values default to sensible defaults when not yet set by the user.

Default values
--------------
theme                   "Catppuccin Mocha"
font_size_terminal      11   (points)
autotype_delay_ms       50   (milliseconds between keystrokes)
clipboard_clear_timeout_s  15  (seconds; 0 = disabled)
browser_integration     False
browser_port            19456
app_icon                ""   (empty = use built-in icon)
keepass_last_paths      []   (MRU list of .kdbx paths, max 5)

Usage::

    from app.managers.settings import settings_manager

    theme = settings_manager.get("theme", "Catppuccin Mocha")
    settings_manager.set("theme", "Dracula")

Written by Christopher Malo
"""

from __future__ import annotations

import json
from typing import Any

from app.constants import DATA_DIR, SETTINGS_FILE


class SettingsManager:
    """Load/save application-wide preferences."""

    _DEFAULTS: dict[str, Any] = {
        "theme":                      "Catppuccin Mocha",
        "app_icon":                   "",
        "font_size_terminal":         11,
        "autotype_delay_ms":          50,
        "plugins_enabled":            True,
        "clipboard_clear_timeout_s":  15,
        "browser_integration":        False,
        "browser_port":               19456,
        "keepass_last_paths":         [],
    }

    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(self._DEFAULTS)
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
                    stored = json.load(fh)
                self._data.update(stored)
            except Exception:
                pass

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        if default is None:
            default = self._DEFAULTS.get(key)
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()


# Global singleton
settings_manager = SettingsManager()
