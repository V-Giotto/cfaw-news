"""Maintenance artifact paths and durable receipts; no SQLite or domain mutations."""

import os
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from .contracts import LedgerError, canonical

SIDECARS = ("-journal", "-wal", "-shm")


class MaintenanceFailure(LedgerError):
    def __init__(self, code, *, database_state="not_started", operation=None):
        super().__init__(code)
        self.database_state = database_state
        self.operation = operation


@dataclass(frozen=True)
class ArtifactPaths:
    database: Path
    backup: Path | None = None
    manifest: Path | None = None
    receipt: Path | None = None
    staging: Path | None = None


def resolve_paths(database, backup=None, receipt=None):
    def resolve(value):
        raw = Path(value)
        if os.name == "nt" and any(
                part not in {raw.anchor, ".", ".."} and (":" in part or part.endswith((".", " ")))
                for part in raw.parts):
            # NTFS streams and Win32 trailing-character aliases are not artifact filenames.
            raise MaintenanceFailure("G4_PATH_INVALID")
        return raw.resolve()
    try:
        db = resolve(database)
        copy = resolve(backup) if backup is not None else None
        out = resolve(receipt) if receipt is not None else None
        return ArtifactPaths(db, copy, Path(str(copy) + ".manifest.json").resolve() if copy else None,
                             out, Path(str(out) + ".pending").resolve() if out else None)
    except (OSError, ValueError, RuntimeError):
        raise MaintenanceFailure("G4_PATH_INVALID") from None


def aliases(left, right):
    return left == right or (left.exists() and right.exists() and left.samefile(right))


def overlaps(left, right):
    return aliases(left, right) or left in right.parents or right in left.parents


def validate_paths(paths, *, receipt_only=False):
    """Resolve links/normalization, detect existing hard links and reserve SQLite namespaces.

    Receipt-only validation permits a safe failure receipt before checking an invalid DB/backup
    pair. Full validation still happens inside every SQLite entry point before opening the DB.
    """
    products = {name: value for name in ("database", "backup", "manifest", "receipt", "staging")
                if (value := getattr(paths, name)) is not None}
    receipt_names = {"receipt", "staging"}
    try:
        for (a, left), (b, right) in combinations(products.items(), 2):
            if (not receipt_only or receipt_names & {a, b}) and overlaps(left, right):
                raise MaintenanceFailure("G4_PATH_CONFLICT")
        for base_name in ("database", "backup"):
            base = products.get(base_name)
            if base is None:
                continue
            for name, candidate in products.items():
                if name == base_name or (receipt_only and name not in receipt_names):
                    continue
                reserved = [Path(str(base) + suffix).resolve() for suffix in SIDECARS]
                if (any(overlaps(candidate, sidecar) for sidecar in reserved)
                        or any(p.parent == base.parent and p.name.startswith(base.name + "-mj")
                               for p in (candidate, *candidate.parents))):
                    raise MaintenanceFailure("G4_PATH_RESERVED")
    except (OSError, RuntimeError):
        raise MaintenanceFailure("G4_PATH_INVALID") from None
    return paths


def write_synced(stream, value):
    payload = canonical(value)
    stream.seek(0)
    stream.truncate()
    stream.write(payload)
    stream.flush()
    os.fsync(stream.fileno())
    stream.seek(0)
    if stream.read() != payload:
        raise OSError("G4_RECEIPT_READBACK_FAILED")


class Receipt:
    """Reserve both outputs before DB work; final failure preserves the PREPARED record."""

    def __init__(self, paths):
        self.paths = paths
        self.primary = self.pending = None

    def prepare(self, action):
        validate_paths(self.paths, receipt_only=True)
        self.paths.receipt.parent.mkdir(parents=True, exist_ok=True)
        self.primary = self.paths.receipt.open("x+b")
        self.pending = self.paths.staging.open("x+b")
        write_synced(self.primary, dict(status="PREPARED", action=action,
            phase="prepared_before_database_operation", database_state="unknown",
            receipt_written=False))
        self.pending.flush()
        os.fsync(self.pending.fileno())

    def finish(self, value):
        write_synced(self.pending, value)
        # Never replace an unrelated file substituted for our reserved output.
        for stream, path in ((self.primary, self.paths.receipt), (self.pending, self.paths.staging)):
            if not os.path.samestat(os.fstat(stream.fileno()), path.stat()):
                raise OSError("G4_RECEIPT_IDENTITY_CHANGED")
        self.close()
        os.replace(self.paths.staging, self.paths.receipt)
        if self.paths.receipt.read_bytes() != canonical(value):
            raise OSError("G4_RECEIPT_READBACK_FAILED")

    def close(self):
        for stream in (self.primary, self.pending):
            if stream is not None and not stream.closed:
                stream.close()
