"""Data models for SessionVault."""

from __future__ import annotations

import dataclasses
import uuid


@dataclasses.dataclass
class SSHSessionConfig:
    """Persistent configuration for a single SSH session."""

    name: str
    hostname: str
    port: int = 22
    username: str = ""
    key_path: str = ""
    keepass_entry_uuid: str = ""
    folder: str = ""
    id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SSHSessionConfig":
        valid = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid})
