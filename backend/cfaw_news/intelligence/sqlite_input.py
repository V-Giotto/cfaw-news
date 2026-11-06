"""Open pinned, offline SQLite bytes only after copying them out of the input tree."""

import hashlib
import shutil
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from .maintenance_io import MaintenanceFailure


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def self_contained(path):
    # A main-file pin cannot authenticate committed WAL or rollback-journal bytes.
    # Empty leftover WAL/SHM files are never opened, copied or cleaned at the source.
    if any((side := Path(str(path) + suffix)).exists() and side.stat().st_size
           for suffix in ("-wal", "-journal")):
        raise MaintenanceFailure("G4_BACKUP_NOT_SELF_CONTAINED")


@contextmanager
def isolated_sqlite_input(path, *, expected_sha256, directory=None):
    """Caller must stop writers; validate both copied bytes and the unchanged source pin."""
    source = Path(path).resolve()
    if file_sha(source) != expected_sha256:
        raise MaintenanceFailure("G4_BACKUP_PIN_MISMATCH")
    self_contained(source)
    with TemporaryDirectory(prefix="cfaw-offline-input-", dir=directory) as folder:
        staged = Path(folder) / "input.db"
        with source.open("rb") as src, staged.open("xb") as dst:
            shutil.copyfileobj(src, dst)
        if file_sha(staged) != expected_sha256 or file_sha(source) != expected_sha256:
            raise MaintenanceFailure("G4_BACKUP_PIN_MISMATCH")
        self_contained(source)
        yield staged
