"""
Data models for agy-multiprofile.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    """Return current UTC timestamp formatted in ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProfileMetadata:
    """Metadata describing an Antigravity profile."""
    name: str
    description: str = ""
    email: str | None = None
    gcloud_config: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    options: dict[str, Any] = field(default_factory=lambda: {
        "sync_gcloud": True,
        "sync_google_account": True,
    })

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfileMetadata:
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            email=data.get("email"),
            gcloud_config=data.get("gcloud_config"),
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
            options=data.get("options", {"sync_gcloud": True, "sync_google_account": True}),
        )


@dataclass
class Manifest:
    """Global manifest tracking active profile and metadata."""
    version: str = "1.0.0"
    active_profile: str = "default"
    last_switched: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Manifest:
        return cls(
            version=data.get("version", "1.0.0"),
            active_profile=data.get("active_profile", "default"),
            last_switched=data.get("last_switched"),
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
        )


@dataclass
class SnapshotMetadata:
    """Metadata describing a backup snapshot."""
    id: str
    timestamp: str
    trigger: str
    source_profile: str | None = None
    files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SnapshotMetadata:
        return cls(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", utc_now_iso()),
            trigger=data.get("trigger", "unknown"),
            source_profile=data.get("source_profile"),
            files=data.get("files", []),
        )


@dataclass
class TrashMetadata:
    """Metadata describing a soft-deleted profile in trash."""
    trash_id: str
    profile_name: str
    deleted_at: str = field(default_factory=utc_now_iso)
    profile_meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrashMetadata:
        return cls(
            trash_id=data.get("trash_id", ""),
            profile_name=data.get("profile_name", ""),
            deleted_at=data.get("deleted_at", utc_now_iso()),
            profile_meta=data.get("profile_meta", {}),
        )


@dataclass
class ValidationResult:
    """Result of integrity and diagnostic checks."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_info(self, message: str) -> None:
        self.info.append(message)
