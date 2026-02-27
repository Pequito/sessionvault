"""Plugin loader – imports Python files from ~/.sessionvault/plugins/.

Plugin contract
---------------
Each .py file may optionally define::

    def setup(api: PluginAPI) -> None:
        ...

The ``api`` object lets plugins register hooks and menu actions.

Example plugin (~/.sessionvault/plugins/hello.py)::

    def setup(api):
        api.add_menu_action("Say Hello", lambda: print("Hello from plugin!"))
        api.on_session_connect(lambda s: print(f"Connected to {s.hostname}"))
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Callable

from app.constants import PLUGINS_DIR


# ---------------------------------------------------------------------------
# Plugin API surface
# ---------------------------------------------------------------------------

class PluginAPI:
    """API object passed to each plugin's ``setup()`` function."""

    def __init__(self) -> None:
        self._connect_hooks: list[Callable] = []
        self._output_hooks: list[Callable] = []
        self._menu_actions: list[tuple[str, Callable]] = []

    # Public registration methods

    def on_session_connect(self, callback: Callable) -> None:
        """Register ``callback(session_config)`` called on SSH connect."""
        self._connect_hooks.append(callback)

    def on_session_output(self, callback: Callable) -> None:
        """Register ``callback(session_config, text)`` called on terminal output."""
        self._output_hooks.append(callback)

    def add_menu_action(self, label: str, callback: Callable) -> None:
        """Register a top-level Plugins menu item."""
        self._menu_actions.append((label, callback))

    # Internal – called by the application

    def fire_connect(self, session) -> None:
        for cb in self._connect_hooks:
            try:
                cb(session)
            except Exception as exc:
                print(f"[plugin] connect hook error: {exc}")

    def fire_output(self, session, text: str) -> None:
        for cb in self._output_hooks:
            try:
                cb(session, text)
            except Exception as exc:
                print(f"[plugin] output hook error: {exc}")

    @property
    def menu_actions(self) -> list[tuple[str, Callable]]:
        return list(self._menu_actions)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class PluginLoader:
    """Discovers and imports plugins from ``PLUGINS_DIR``."""

    def __init__(self) -> None:
        self.api = PluginAPI()
        self._loaded: list[str] = []
        self._errors: dict[str, str] = {}

    def load_all(self) -> list[str]:
        """Load all plugins.  Returns list of successfully loaded plugin names."""
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        self._loaded = []
        self._errors = {}

        for path in sorted(PLUGINS_DIR.glob("*.py")):
            name = path.stem
            try:
                spec = importlib.util.spec_from_file_location(
                    f"_sv_plugin_{name}", path
                )
                if spec is None or spec.loader is None:
                    raise ImportError("Could not create module spec")
                mod = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = mod
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                if hasattr(mod, "setup"):
                    mod.setup(self.api)
                self._loaded.append(name)
            except Exception as exc:
                self._errors[name] = str(exc)
                print(f"[plugins] failed to load '{name}': {exc}")

        return self._loaded

    @property
    def loaded(self) -> list[str]:
        return list(self._loaded)

    @property
    def errors(self) -> dict[str, str]:
        return dict(self._errors)


# Global singleton
plugin_loader = PluginLoader()
