"""Parser for MobaXterm .mxtsessions session-export files."""

from __future__ import annotations

import configparser
from typing import Optional

from app.models import SSHSessionConfig


class MobaXtermImporter:
    """
    Parses MobaXterm session export files (.mxtsessions).

    File format (INI-style)::

        [Bookmarks]
        SubRep=
        ImgNum=42
        MyServer=#0#192.168.1.1#22#admin#...

    Session type codes:
        0 = SSH  (imported)
        4 = RDP  (skipped)
        ...  others skipped

    INI section names other than "Bookmarks" become the ``folder`` field.
    """

    _SSH_TYPE = "0"
    _SKIP_KEYS = frozenset({"subrep", "imgnum"})

    @classmethod
    def parse_file(cls, path: str) -> list[SSHSessionConfig]:
        """Return all SSH sessions found in *path*."""
        sessions: list[SSHSessionConfig] = []
        cfg = configparser.RawConfigParser()
        cfg.read(path, encoding="utf-8-sig")
        for section in cfg.sections():
            folder = "" if section in ("Bookmarks", "Bookmarks_0") else section
            for key, value in cfg.items(section):
                if key.lower() in cls._SKIP_KEYS:
                    continue
                parsed = cls._parse_entry(key, value, folder)
                if parsed is not None:
                    sessions.append(parsed)
        return sessions

    @classmethod
    def _parse_entry(
        cls, name: str, value: str, folder: str
    ) -> Optional[SSHSessionConfig]:
        if not value.startswith("#"):
            return None
        parts = value.split("#")
        # parts[0] is always empty (text before the leading '#')
        if len(parts) < 2 or parts[1] != cls._SSH_TYPE:
            return None
        hostname = parts[2] if len(parts) > 2 else ""
        port_str = parts[3] if len(parts) > 3 else "22"
        username = parts[4] if len(parts) > 4 else ""
        try:
            port = int(port_str)
        except ValueError:
            port = 22
        return SSHSessionConfig(
            name=name,
            hostname=hostname,
            port=port,
            username=username,
            folder=folder,
        )
