"""Thread-safe KeePass database manager – read + write."""

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
    """Thread-safe wrapper around a pykeepass database (read + write)."""

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

    def create_database(
        self,
        path: str,
        password: str,
        keyfile: str = "",
        kdf: str = "argon2",
    ) -> None:
        """Create a new blank .kdbx database and keep it open.

        kdf='argon2'  → KDBX4 with ChaCha20 + Argon2 (recommended)
        kdf='aeskdf'  → KDBX3.1 with AES-256 + PBKDF2 (max compat)
        """
        if not PYKEEPASS_AVAILABLE:
            raise RuntimeError(
                "pykeepass is not installed.  Run: pip install pykeepass"
            )
        from pykeepass import create_database as _create

        kwargs: dict = dict(
            filename=path,
            password=password or None,
            keyfile=keyfile or None,
        )
        # pykeepass ≥ 4.1 supports encryption= for KDBX4 / ChaCha20+Argon2.
        # Older versions raise TypeError on unknown kwargs; fall back gracefully.
        if kdf == "argon2":
            kwargs["encryption"] = "chacha20"
        else:
            kwargs["encryption"] = "aes256"

        with self._lock:
            try:
                self._db = _create(**kwargs)
            except TypeError:
                kwargs.pop("encryption", None)
                self._db = _create(**kwargs)
            self._db_path = path

    def lock(self) -> None:
        """Clear the in-memory database (credentials are wiped)."""
        with self._lock:
            self._db = None
            self._db_path = ""

    def save(self) -> None:
        """Persist in-memory changes to disk."""
        with self._lock:
            if self._db is not None:
                self._db.save()

    # ------------------------------------------------------------------
    # Read queries
    # ------------------------------------------------------------------

    def get_all_entries(self) -> list:
        with self._lock:
            if self._db is None:
                return []
            return list(self._db.entries)

    def get_groups(self) -> list:
        with self._lock:
            if self._db is None:
                return []
            return list(self._db.groups)

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

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add_entry(
        self,
        group_name: str,
        title: str,
        username: str,
        password: str,
        url: str = "",
        notes: str = "",
    ) -> Optional[object]:
        """Add a new entry.  Returns the created entry or None on error."""
        with self._lock:
            if self._db is None:
                return None
            group = self._db.find_groups(name=group_name, first=True)
            if group is None:
                group = self._db.add_group(self._db.root_group, group_name)
            entry = self._db.add_entry(
                group, title, username, password,
                url=url or None, notes=notes or None,
            )
            self._db.save()
            return entry

    def update_entry(
        self,
        uuid_str: str,
        *,
        title: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        url: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Update fields of an existing entry.  Returns True on success."""
        with self._lock:
            if self._db is None:
                return False
            try:
                target = uuid.UUID(uuid_str)
                for entry in self._db.entries:
                    if entry.uuid == target:
                        if title is not None:
                            entry.title = title
                        if username is not None:
                            entry.username = username
                        if password is not None:
                            entry.password = password
                        if url is not None:
                            entry.url = url
                        if notes is not None:
                            entry.notes = notes
                        self._db.save()
                        return True
            except Exception:
                pass
            return False

    def delete_entry(self, uuid_str: str) -> bool:
        """Delete an entry by UUID.  Returns True on success."""
        with self._lock:
            if self._db is None:
                return False
            try:
                target = uuid.UUID(uuid_str)
                for entry in list(self._db.entries):
                    if entry.uuid == target:
                        self._db.delete_entry(entry)
                        self._db.save()
                        return True
            except Exception:
                pass
            return False


# Global singleton shared across the application
keepass_manager = KeePassManager()
