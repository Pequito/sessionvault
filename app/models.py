"""Data models for SessionVault.

Classes
-------
TunnelConfig
    Represents a single SSH local-port-forward tunnel:
    local_port → remote_host:remote_port.
    Provides ``to_dict()`` / ``from_dict()`` for JSON round-trips.

SSHSessionConfig
    Stores all parameters for one saved session.  Supports SSH, RDP,
    VNC, and Telnet.  Key fields:

    name             Display name shown in the session tree.
    hostname         Target host (IP or DNS name).
    port             TCP port (default per protocol).
    protocol         One of "ssh", "rdp", "vnc", "telnet".
    username         Login username (may be empty for password-only auth).
    key_path         Path to an SSH private key file (SSH only).
    folder           Optional grouping label shown in the tree.
    keepass_entry_uuid  UUID of a linked KeePass entry (empty = none).
    x11_forwarding   Enable X11 forwarding for the SSH session.
    local_tunnels    Serialised list of TunnelConfig dicts.
    rdp_width/height RDP session resolution.
    rdp_fullscreen   Launch RDP client in full-screen mode.

    ``tunnels()`` yields ``TunnelConfig`` objects from ``local_tunnels``.
    ``to_dict()`` / ``from_dict()`` handle JSON persistence.

Written by Christopher Malo
"""

from __future__ import annotations

import dataclasses
import uuid


@dataclasses.dataclass
class TunnelConfig:
    """A single local-port-forward tunnel entry."""

    local_port: int = 0
    remote_host: str = ""
    remote_port: int = 0

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TunnelConfig":
        valid = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid})

    def __str__(self) -> str:
        return f"localhost:{self.local_port} → {self.remote_host}:{self.remote_port}"


@dataclasses.dataclass
class SSHSessionConfig:
    """Persistent configuration for a single session.

    Supports protocols: ssh | rdp | vnc | telnet
    """

    name: str
    hostname: str
    port: int = 22
    username: str = ""
    key_path: str = ""
    keepass_entry_uuid: str = ""
    folder: str = ""
    id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))

    # ── Protocol ──────────────────────────────────────────────────────
    protocol: str = "ssh"   # ssh | rdp | vnc | telnet

    # ── SSH-specific options ──────────────────────────────────────────
    x11_forwarding: bool = False
    # Each entry: {"local_port": int, "remote_host": str, "remote_port": int}
    local_tunnels: list = dataclasses.field(default_factory=list)

    # ── RDP-specific options ──────────────────────────────────────────
    rdp_width: int = 1280
    rdp_height: int = 800
    rdp_fullscreen: bool = False

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SSHSessionConfig":
        valid = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid})

    def tunnels(self) -> list[TunnelConfig]:
        """Return local_tunnels as TunnelConfig objects."""
        return [TunnelConfig.from_dict(t) for t in self.local_tunnels]
