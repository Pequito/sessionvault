"""CRUD operations and JSON persistence for SSH session configurations.

The :class:`SessionManager` singleton loads ``~/.sessionvault/sessions.json``
on startup and keeps an in-memory list of :class:`~app.models.SSHSessionConfig`
objects.  Every mutating call (``add``, ``update``, ``delete``, ``import_sessions``)
immediately writes the full list back to disk as pretty-printed JSON.

Persistence format::

    [
      {
        "id": "<uuid4-string>",
        "name": "My Server",
        "hostname": "192.168.1.1",
        "port": 22,
        "protocol": "ssh",
        ...
      },
      ...
    ]

Usage::

    from app.managers.session import session_manager

    sessions = session_manager.all()            # list[SSHSessionConfig]
    s = session_manager.get(some_id)           # SSHSessionConfig | None
    session_manager.add(new_config)
    session_manager.update(modified_config)
    session_manager.delete(some_id)
    session_manager.import_sessions([...])      # bulk add, deduplicate

Written by Christopher Malo
"""

from __future__ import annotations

import json
from typing import Optional

from app.constants import DATA_DIR, SESSIONS_FILE
from app.models import SSHSessionConfig


class SessionManager:
    """Manages the list of SSH sessions and persists them to disk."""

    def __init__(self) -> None:
        self._sessions: list[SSHSessionConfig] = []
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE, "r", encoding="utf-8") as fh:
                    raw: list[dict] = json.load(fh)
                self._sessions = [SSHSessionConfig.from_dict(d) for d in raw]
            except Exception:
                self._sessions = []

    def _save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SESSIONS_FILE, "w", encoding="utf-8") as fh:
            json.dump([s.to_dict() for s in self._sessions], fh, indent=2)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def all(self) -> list[SSHSessionConfig]:
        return list(self._sessions)

    def get_by_id(self, session_id: str) -> Optional[SSHSessionConfig]:
        return next((s for s in self._sessions if s.id == session_id), None)

    def add(self, session: SSHSessionConfig) -> None:
        self._sessions.append(session)
        self._save()

    def update(self, session: SSHSessionConfig) -> None:
        for i, s in enumerate(self._sessions):
            if s.id == session.id:
                self._sessions[i] = session
                self._save()
                return

    def delete(self, session_id: str) -> None:
        self._sessions = [s for s in self._sessions if s.id != session_id]
        self._save()

    def import_sessions(self, sessions: list[SSHSessionConfig]) -> int:
        """Add sessions not already present (deduped by host+port+user).
        Returns the count of newly added sessions."""
        existing = {(s.hostname, s.port, s.username) for s in self._sessions}
        added = 0
        for s in sessions:
            key = (s.hostname, s.port, s.username)
            if key not in existing:
                self._sessions.append(s)
                existing.add(key)
                added += 1
        if added:
            self._save()
        return added
