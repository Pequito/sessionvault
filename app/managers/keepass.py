"""Thread-safe KeePass database manager – multi-database, read + write.

Multiple .kdbx databases can be open simultaneously.  All single-database
methods (``get_all_entries``, ``add_entry``, …) operate on the *active*
database.  Use :meth:`set_active` to switch between databases and
:attr:`open_paths` to list all currently-open ones.
"""

from __future__ import annotations

import threading
import uuid
from typing import TYPE_CHECKING, Optional

from app.managers.logger import get_logger

if TYPE_CHECKING:
    from pykeepass import PyKeePass
    from app.models import SSHSessionConfig

try:
    from pykeepass import PyKeePass as _PyKeePass  # noqa: F401
    PYKEEPASS_AVAILABLE = True
except ImportError:
    PYKEEPASS_AVAILABLE = False

log = get_logger(__name__)


class KeePassManager:
    """Thread-safe manager supporting multiple open .kdbx databases.

    All single-database convenience methods operate on the *active* database.
    Switch the active database with :meth:`set_active` or :meth:`open`
    (opening always makes the new database active).
    """

    def __init__(self) -> None:
        self._dbs: dict[str, "PyKeePass"] = {}  # path → db instance
        self._active_path: str = ""
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """True if at least one database is open."""
        with self._lock:
            return bool(self._dbs)

    @property
    def db_path(self) -> str:
        """Path of the active database (empty string if none open)."""
        return self._active_path

    @property
    def open_paths(self) -> list[str]:
        """All currently open database paths (in insertion order)."""
        with self._lock:
            return list(self._dbs.keys())

    # ------------------------------------------------------------------
    # Active-database selection
    # ------------------------------------------------------------------

    def set_active(self, path: str) -> None:
        """Make *path* the active database.  No-op if it is not open."""
        with self._lock:
            if path in self._dbs:
                self._active_path = path
                log.debug("Active KeePass database → %s", path)

    def _active_db(self) -> Optional["PyKeePass"]:
        """Return the active :class:`PyKeePass` instance (caller holds lock)."""
        return self._dbs.get(self._active_path)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self, path: str, password: str, keyfile: str = "") -> None:
        """Open / unlock a .kdbx file and make it the active database.

        Raises :class:`RuntimeError` when pykeepass is not installed, and
        re-raises pykeepass exceptions on bad credentials or corrupt files.
        """
        if not PYKEEPASS_AVAILABLE:
            raise RuntimeError(
                "pykeepass is not installed.  Run: pip install pykeepass"
            )
        log.info("Opening KeePass database: %s", path)
        from pykeepass import PyKeePass as _KP  # noqa: PLC0415
        db = _KP(path, password=password or None, keyfile=keyfile or None)
        with self._lock:
            self._dbs[path] = db
            self._active_path = path
        log.info("KeePass database opened: %s", path)

    def close_db(self, path: str) -> None:
        """Close (lock) a single database; switches active to another if needed."""
        with self._lock:
            if path not in self._dbs:
                return
            self._dbs.pop(path)
            if self._active_path == path:
                self._active_path = next(iter(self._dbs), "")
        log.info("KeePass database closed: %s", path)

    def create_database(
        self,
        path: str,
        password: str,
        keyfile: str = "",
        kdf: str = "argon2",
    ) -> None:
        """Create a blank .kdbx database and open it as the active database.

        kdf='argon2'  → KDBX4 with ChaCha20 + Argon2  (recommended)
        kdf='aeskdf'  → KDBX3.1 with AES-256 + PBKDF2 (max compatibility)
        """
        if not PYKEEPASS_AVAILABLE:
            raise RuntimeError(
                "pykeepass is not installed.  Run: pip install pykeepass"
            )
        log.info("Creating new KeePass database: %s  kdf=%s", path, kdf)
        from pykeepass import create_database as _create  # noqa: PLC0415

        kwargs: dict = dict(
            filename=path,
            password=password or None,
            keyfile=keyfile or None,
        )
        # pykeepass ≥ 4.1 accepts encryption=; older versions raise TypeError
        kwargs["encryption"] = "chacha20" if kdf == "argon2" else "aes256"
        try:
            db = _create(**kwargs)
        except TypeError:
            kwargs.pop("encryption", None)
            db = _create(**kwargs)

        with self._lock:
            self._dbs[path] = db
            self._active_path = path
        log.info("KeePass database created: %s", path)

    def lock(self) -> None:
        """Clear *all* in-memory databases (wipes credentials from memory)."""
        with self._lock:
            count = len(self._dbs)
            self._dbs.clear()
            self._active_path = ""
        log.info("All KeePass databases locked (%d db(s) cleared)", count)

    def save(self, path: str = "") -> None:
        """Persist in-memory changes to disk.

        Saves the specified *path* database, or the active one if omitted.
        """
        with self._lock:
            target = path or self._active_path
            db = self._dbs.get(target)
            if db is not None:
                db.save()
                log.debug("KeePass database saved: %s", target)

    # ------------------------------------------------------------------
    # Read queries  (operate on the active database unless path given)
    # ------------------------------------------------------------------

    def get_all_entries(self, path: str = "") -> list:
        """All entries in the active (or specified) database."""
        with self._lock:
            db = self._dbs.get(path or self._active_path)
            return list(db.entries) if db else []

    def get_groups(self, path: str = "") -> list:
        """All groups in the active (or specified) database."""
        with self._lock:
            db = self._dbs.get(path or self._active_path)
            return list(db.groups) if db else []

    def get_entry_by_uuid(self, uuid_str: str, path: str = ""):
        """Find an entry by UUID string in the active (or specified) database."""
        with self._lock:
            db = self._dbs.get(path or self._active_path)
            if db is None:
                return None
            try:
                target = uuid.UUID(uuid_str)
                for entry in db.entries:
                    if entry.uuid == target:
                        return entry
            except Exception:
                pass
            return None

    def get_password_for_session(self, session: "SSHSessionConfig") -> Optional[str]:
        """Return the KeePass password linked to *session*, or None.

        Searches all open databases; tries the active one first.
        """
        if not session.keepass_entry_uuid:
            return None
        # Active db first
        entry = self.get_entry_by_uuid(session.keepass_entry_uuid)
        if entry:
            return entry.password
        # Fallback: search other open dbs
        for path in self.open_paths:
            if path == self._active_path:
                continue
            entry = self.get_entry_by_uuid(session.keepass_entry_uuid, path)
            if entry:
                return entry.password
        return None

    # ------------------------------------------------------------------
    # Write operations  (operate on the active database)
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
        """Add a new entry to the active database.  Returns the entry or None."""
        with self._lock:
            db = self._active_db()
            if db is None:
                log.warning("add_entry called with no active database")
                return None
            group = db.find_groups(name=group_name, first=True)
            if group is None:
                group = db.add_group(db.root_group, group_name)
            entry = db.add_entry(
                group, title, username, password,
                url=url or None, notes=notes or None,
            )
            db.save()
            log.info("KeePass entry added: %s / %s", group_name, title)
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
        """Update fields on an existing entry in the active database."""
        with self._lock:
            db = self._active_db()
            if db is None:
                return False
            try:
                target = uuid.UUID(uuid_str)
                for entry in db.entries:
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
                        db.save()
                        log.info("KeePass entry updated: %s", uuid_str)
                        return True
            except Exception as exc:
                log.error("Error updating entry %s: %s", uuid_str, exc)
            return False

    def delete_entry(self, uuid_str: str) -> bool:
        """Delete an entry by UUID from the active database."""
        with self._lock:
            db = self._active_db()
            if db is None:
                return False
            try:
                target = uuid.UUID(uuid_str)
                for entry in list(db.entries):
                    if entry.uuid == target:
                        db.delete_entry(entry)
                        db.save()
                        log.info("KeePass entry deleted: %s", uuid_str)
                        return True
            except Exception as exc:
                log.error("Error deleting entry %s: %s", uuid_str, exc)
            return False


# Global singleton shared across the application
keepass_manager = KeePassManager()
