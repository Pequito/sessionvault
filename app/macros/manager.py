"""Macro manager – record and replay command sequences per named macro."""

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
