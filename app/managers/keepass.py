"""Thread-safe KeePass database manager."""

from __future__ import annotations

import threading
import uuid
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pykeepass import PyKeePass
    from app.models import SSHSessionConfig

try:
    from pykeepass import PyKeePass as _PyKeePass  # noqa: F401
    PYKEEPASS_AVAILABLE = True
except ImportError:
    PYKEEPASS_AVAILABLE = False


class KeePassManager:
    """Thread-safe wrapper around a pykeepass database."""

    def __init__(self) -> None:
        self._db: Optional["PyKeePass"] = None
        self._lock = threading.Lock()
        self._db_path: str = ""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._db is not None

    @property
    def db_path(self) -> str:
        return self._db_path

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self, path: str, password: str, keyfile: str = "") -> None:
        """Open and unlock a .kdbx database.  Raises on failure."""
        if not PYKEEPASS_AVAILABLE:
            raise RuntimeError(
                "pykeepass is not installed.  Run: pip install pykeepass"
            )
        from pykeepass import PyKeePass as _KP
        with self._lock:
            self._db = _KP(
                path,
                password=password or None,
                keyfile=keyfile or None,
            )
            self._db_path = path

    def lock(self) -> None:
        """Clear the in-memory database (credentials are gone)."""
        with self._lock:
            self._db = None
            self._db_path = ""

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_all_entries(self) -> list:
        with self._lock:
            if self._db is None:
                return []
            return list(self._db.entries)

    def get_entry_by_uuid(self, uuid_str: str):
        with self._lock:
            if self._db is None:
                return None
            try:
                target = uuid.UUID(uuid_str)
                for entry in self._db.entries:
                    if entry.uuid == target:
                        return entry
            except Exception:
                pass
            return None

    def get_password_for_session(self, session: "SSHSessionConfig") -> Optional[str]:
        """Return the KeePass password linked to *session*, or None."""
        if not session.keepass_entry_uuid:
            return None
        entry = self.get_entry_by_uuid(session.keepass_entry_uuid)
        return entry.password if entry else None


# Global singleton shared across the application
keepass_manager = KeePassManager()
