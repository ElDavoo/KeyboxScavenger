from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from scavenger.models import StorageResult


class KeyboxStorage:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def persist(self, xml_payload: bytes) -> StorageResult:
        digest = hashlib.sha256(xml_payload).hexdigest()
        sha_path = self.output_dir / f"{digest}.xml"
        latest_path = self.output_dir / "keybox.xml"

        wrote_sha_file = False
        if not sha_path.exists():
            self._atomic_write(sha_path, xml_payload)
            wrote_sha_file = True

        # Always refresh the latest snapshot after storing a valid keybox.
        self._atomic_write(latest_path, xml_payload)

        return StorageResult(
            digest=digest,
            sha_path=sha_path,
            latest_path=latest_path,
            wrote_sha_file=wrote_sha_file,
        )

    def _atomic_write(self, destination: Path, payload: bytes) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=".tmp-keybox-",
            suffix=".xml",
            dir=self.output_dir,
        )

        try:
            with os.fdopen(file_descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, destination)
            os.chmod(destination, 0o640)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
