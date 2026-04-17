from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ValidationResult:
    is_valid: bool
    reasons: list[str] = field(default_factory=list)
    certificate_serials: list[str] = field(default_factory=list)
    revoked_serials: list[str] = field(default_factory=list)
    certificate_type: str | None = None
    has_banned_serial: bool = False
    has_leaked_serial: bool = False
    special_serial_violation: bool = False
    nearest_expiration_date: datetime | None = None


@dataclass
class StorageResult:
    digest: str
    sha_path: Path
    latest_path: Path
    wrote_sha_file: bool
