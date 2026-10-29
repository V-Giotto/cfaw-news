"""Offline synthetic JSONL append writer. No update, truncate or delete API."""

import os

from evals.intelligence_g2.contracts import data, json_bytes, read_json
from evals.intelligence_g2.replay import safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import ROOT, fail
from .history import append_event
from .history_contracts import HistoryEvent, HistoryJournal
from .history_contracts import parse_history as parse

AREAS = (ROOT / ".tmp/evals/g3", ROOT / ".local/evals/g3")


def _path(path):
    return safe_path(path, areas=AREAS, code="G3_PATH_INVALID")


def _decode(raw):
    if raw and not raw.endswith(b"\n"):
        fail("G3_HISTORY_CHAIN_INVALID", "truncated_jsonl")
    rows = raw.splitlines()
    journal = parse(HistoryJournal, dict(entries=[read_json(row) for row in rows]))
    if raw != b"".join(json_bytes(e) for e in journal.entries):
        fail("G3_HISTORY_CHAIN_INVALID", "noncanonical_jsonl")
    return journal


def load_journal(path, *, expected_sha256):
    raw = _path(path).read_bytes()
    if sha256_bytes(raw) != expected_sha256:
        fail("G3_SHA_MISMATCH", "journal_file")
    return _decode(raw)


def append_interaction(path, event, *, expected_head):
    """Compare-and-append under an exclusive sidecar lock; stale writes fail closed.

    Locks survive a crashed writer and require explicit offline investigation.
    Callers retain the trusted head/file digest outside the journal to detect rollback.
    """
    path = _path(path)
    lock = _path(path.with_name(path.name + ".lock"))
    event = parse(HistoryEvent, data(event))
    descriptor = None
    try:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            fail("G3_HISTORY_CONCURRENT_WRITE", "journal_lock")
        journal = _decode(path.read_bytes()) if path.exists() else HistoryJournal()
        if journal.head != expected_head:
            fail("G3_HISTORY_HEAD_MISMATCH", "expected_head")
        updated = append_event(journal, event)
        with path.open("ab") as stream:
            stream.write(json_bytes(updated.entries[-1]))
            stream.flush()
            os.fsync(stream.fileno())
        return updated
    finally:
        if descriptor is not None:
            os.close(descriptor)
            lock.unlink()
