"""Persistent state for the TUI: machine profiles + last-used settings."""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def config_dir() -> Path:
    """XDG-style config directory for deuspy."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "deuspy"


def machines_path() -> Path:
    return config_dir() / "machines.json"


@dataclass
class MachineProfile:
    """A saved machine configuration."""

    name: str
    port: str = ""           # e.g. "/dev/ttyUSB0"; empty means autodetect
    baud: int = 115200
    units: str = "MM"        # "MM" or "INCH"
    safe_z: float = 5.0
    tool_diameter: float = 3.0
    stock_x: float = 100.0
    stock_y: float = 100.0
    stock_z: float = 20.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MachineProfile:
        return cls(**data)


@dataclass
class ProfileStore:
    """JSON-backed list of MachineProfile records."""

    profiles: list[MachineProfile] = field(default_factory=list)
    active: str | None = None  # name of the active profile, if any

    def save(self) -> None:
        path = machines_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "profiles": [p.to_dict() for p in self.profiles],
                    "active": self.active,
                },
                indent=2,
            )
        )

    @classmethod
    def load(cls) -> ProfileStore:
        path = machines_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
            profiles = [MachineProfile.from_dict(p) for p in data.get("profiles", [])]
            return cls(profiles=profiles, active=data.get("active"))
        except (json.JSONDecodeError, TypeError, KeyError):
            # Corrupt file — keep a backup and start fresh.
            backup = path.with_suffix(".json.bak")
            with contextlib.suppress(OSError):
                path.rename(backup)
            return cls()

    def get(self, name: str) -> MachineProfile | None:
        for p in self.profiles:
            if p.name == name:
                return p
        return None

    def upsert(self, profile: MachineProfile) -> None:
        for i, p in enumerate(self.profiles):
            if p.name == profile.name:
                self.profiles[i] = profile
                return
        self.profiles.append(profile)

    def delete(self, name: str) -> bool:
        for i, p in enumerate(self.profiles):
            if p.name == name:
                del self.profiles[i]
                if self.active == name:
                    self.active = None
                return True
        return False
