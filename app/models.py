"""Data models for SessionVault."""

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
