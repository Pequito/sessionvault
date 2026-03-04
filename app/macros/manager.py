"""Macro manager – record and replay command sequences per named macro.

A *macro* is an ordered list of UTF-8 command strings that can be replayed
into an SSH terminal one-by-one (each followed by a newline).  Macros are
named and persisted to ``~/.sessionvault/macros.json``.

Usage::

    from app.macros.manager import macro_manager

    macro_manager.save_macro("Deploy", ["cd /app", "git pull", "systemctl restart myapp"])
    commands = macro_manager.get("Deploy")   # ["cd /app", ...]
    macro_manager.delete_macro("Deploy")

JSON format::

    {
      "Deploy": ["cd /app", "git pull", "systemctl restart myapp"],
      ...
    }

Written by Christopher Malo
"""

from __future__ import annotations

import json

from app.constants import DATA_DIR, MACROS_FILE


class MacroManager:
    """Store named macros as ordered lists of byte strings (commands)."""

    def __init__(self) -> None:
        # {macro_name: [cmd_str, ...]}
        self._macros: dict[str, list[str]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if MACROS_FILE.exists():
            try:
                with open(MACROS_FILE, "r", encoding="utf-8") as fh:
                    self._macros = json.load(fh)
            except Exception:
                self._macros = {}

    def _save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(MACROS_FILE, "w", encoding="utf-8") as fh:
            json.dump(self._macros, fh, indent=2)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def all(self) -> dict[str, list[str]]:
        return dict(self._macros)

    def get(self, name: str) -> list[str]:
        return list(self._macros.get(name, []))

    def save_macro(self, name: str, commands: list[str]) -> None:
        self._macros[name] = list(commands)
        self._save()

    def delete_macro(self, name: str) -> None:
        self._macros.pop(name, None)
        self._save()

    def names(self) -> list[str]:
        return sorted(self._macros)


# Global singleton
macro_manager = MacroManager()
