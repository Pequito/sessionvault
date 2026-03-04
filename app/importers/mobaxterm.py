"""Parser for MobaXterm .mxtsessions session-export files.

MobaXterm exports sessions as an INI-style file.  Two value formats exist:

Old format (MobaXterm ≤ 10.x)::

    MyServer=#0#192.168.1.1#22#admin#...
             │ │ │           │   └─ username
             │ │ │           └───── port
             │ │ └─────────────────  hostname
             │ └───────────────────  session type  (0=SSH, 4=RDP, …)
             └─────────────────────  leading #

New format (MobaXterm ≥ 11.x, used in practice)::

    MyServer=#109#0%192.168.1.1%22%admin%...
              │   │ │            │   └─ username
              │   │ │            └───── port
              │   │ └──────────────────  hostname
              │   └────────────────────  session type  (0=SSH, 4=RDP, 11=browser …)
              └────────────────────────  internal format code (ignored)

Within each INI section, ``SubRep=`` gives the human-readable folder name;
``ImgNum=`` is a UI icon index.  Both are metadata and are skipped.

This parser handles:
  • Both old and new value formats.
  • Duplicate session names within a section (renamed with counter suffix).
  • BOM markers (utf-8-sig) and comment lines (; / #).
  • ``SubRep`` folder names instead of raw section identifiers.

Written by Christopher Malo
"""

from __future__ import annotations

import re
from typing import Optional

from app.models import SSHSessionConfig
from app.managers.logger import get_logger

log = get_logger(__name__)

# INI keys that carry section metadata, not session data
_META_KEYS = frozenset({"subrep", "imgnum"})

# Session type code for SSH (applies to both formats)
_SSH_TYPE = "0"


class MobaXtermImporter:
    """Parse MobaXterm ``.mxtsessions`` files into :class:`SSHSessionConfig` objects."""

    @classmethod
    def parse_file(cls, path: str) -> list[SSHSessionConfig]:
        """Return all SSH sessions found in *path*.

        Folder names come from the ``SubRep=`` line inside each section.
        Duplicate session names within the same folder are disambiguated with
        a counter suffix so that no sessions are silently dropped.
        """
        sessions: list[SSHSessionConfig] = []

        try:
            sections = cls._read_sections(path)
        except Exception as exc:
            log.error("MobaXterm import: could not read '%s': %s", path, exc)
            raise

        for folder, entries in sections.values():
            for name, value in entries:
                parsed = cls._parse_entry(name, value, folder)
                if parsed is not None:
                    sessions.append(parsed)

        log.info(
            "MobaXterm import: %d SSH session(s) parsed from '%s'",
            len(sessions), path,
        )
        return sessions

    # ------------------------------------------------------------------
    # File reader  (duplicate-key safe, SubRep-aware)
    # ------------------------------------------------------------------

    @classmethod
    def _read_sections(
        cls, path: str
    ) -> dict[str, tuple[str, list[tuple[str, str]]]]:
        """Read *path* and return a mapping of::

            section_name → (folder_name, [(key, value), …])

        ``folder_name`` comes from ``SubRep=`` inside the section; it falls
        back to the section name when ``SubRep`` is absent.

        Duplicate keys within a section are renamed:
        ``name``, ``name (2)``, ``name (3)``, …
        """
        # section_name → [folder, entries_list]
        sections: dict[str, list] = {}
        current: str | None = None
        seen: dict[str, dict[str, int]] = {}   # section → {lower_key → count}

        _section_re = re.compile(r"^\[(.+)\]\s*$")
        _kv_re      = re.compile(r"^([^=]+?)\s*=\s*(.*?)\s*$")

        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.strip()

                if not line or line.startswith((";", "#")):
                    continue

                # ── Section header ─────────────────────────────────────
                m = _section_re.match(line)
                if m:
                    current = m.group(1).strip()
                    if current not in sections:
                        # [folder_name, entries_list]
                        sections[current] = [current, []]
                        seen[current] = {}
                    continue

                if current is None:
                    continue

                # ── Key = value ────────────────────────────────────────
                m = _kv_re.match(line)
                if not m:
                    continue

                key   = m.group(1).strip()
                value = m.group(2)

                # Capture SubRep as folder name
                if key.lower() == "subrep":
                    folder = value.strip()
                    if folder:
                        sections[current][0] = folder
                    continue

                # Skip other metadata keys
                if key.lower() in _META_KEYS:
                    continue

                # Disambiguate duplicate session names
                key_lower = key.lower()
                count = seen[current].get(key_lower, 0) + 1
                seen[current][key_lower] = count
                unique_key = key if count == 1 else f"{key} ({count})"

                sections[current][1].append((unique_key, value))

        # Convert to immutable tuples: section → (folder, entries)
        return {sec: (data[0], data[1]) for sec, data in sections.items()}

    # ------------------------------------------------------------------
    # Entry parser  (handles old and new value formats)
    # ------------------------------------------------------------------

    @classmethod
    def _parse_entry(
        cls, name: str, value: str, folder: str
    ) -> Optional[SSHSessionConfig]:
        """Parse one session entry; return ``None`` if it is not an SSH session.

        Supports both MobaXterm value formats:

        * Old: ``#<type>#<host>#<port>#<user>#…``   (``#`` separator throughout)
        * New: ``#<code>#<type>%<host>%<port>%<user>%…``  (``%`` after the code)
        """
        if not value.startswith("#"):
            return None

        parts = value.split("#")
        # parts[0] is always "" (text before the leading '#')
        if len(parts) < 3:
            return None

        second = parts[2]   # everything after #<code>#

        if "%" in second:
            # ── New format: #<code>#<type>%<host>%<port>%<user>%… ──
            params       = second.split("%")
            session_type = params[0]
            hostname     = params[1] if len(params) > 1 else ""
            port_str     = params[2] if len(params) > 2 else "22"
            username     = params[3] if len(params) > 3 else ""
        else:
            # ── Old format: #<type>#<host>#<port>#<user>#… ──────────
            session_type = parts[1]
            hostname     = parts[2] if len(parts) > 2 else ""
            port_str     = parts[3] if len(parts) > 3 else "22"
            username     = parts[4] if len(parts) > 4 else ""

        if session_type != _SSH_TYPE:
            return None

        try:
            port = int(port_str)
        except ValueError:
            port = 22

        # Strip the root folder name from nested SubRep paths
        # e.g. "Avaya App Serv\CM ESS LSP" → keep as-is for now
        return SSHSessionConfig(
            name=name,
            hostname=hostname,
            port=port,
            username=username,
            folder=folder,
        )
