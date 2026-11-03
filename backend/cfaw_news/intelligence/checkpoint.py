"""Separate durable high-water mark with a recoverable SQLite commit intent."""

import json
import os
import threading
import time
from pathlib import Path
from uuid import uuid4

from .contracts import LedgerError, canonical

_LOCKS = {}
_GUARD = threading.Lock()


class PersistenceError(LedgerError):
    def __init__(self, code, *, database_state="unchanged", status=409):
        super().__init__(code)
        self.database_state, self.status = database_state, status


class FileMutex:
    """Nonblocking process/thread lock; never unlink a shared lock inode."""
    def __init__(self, path, *, timeout=0):
        self.path = Path(path).resolve()
        with _GUARD:
            self.thread_lock = _LOCKS.setdefault(str(self.path), threading.Lock())
        self.stream = None
        self.timeout = timeout

    def __enter__(self):
        if not self.thread_lock.acquire(timeout=self.timeout):
            raise PersistenceError("G4_STORE_BUSY", status=503)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.stream = self.path.open("a+b")
            if self.path.stat().st_size == 0:
                self.stream.write(b"0")
                self.stream.flush()
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    self.stream.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise PersistenceError("G4_STORE_BUSY", status=503) from None
                    time.sleep(0.005)
            return self
        except BaseException:
            if self.stream:
                self.stream.close()
            self.thread_lock.release()
            raise

    def __exit__(self, *_):
        try:
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        finally:
            self.stream.close()
            self.thread_lock.release()


class Checkpoint:
    def __init__(self, path, *, fault=lambda _: None):
        self.path = Path(path).resolve()
        self.lock_path = Path(str(self.path) + ".lock")
        self.worker_path = Path(str(self.path) + ".worker.lock")
        self.fault = fault

    def write(self, value, *, create=False):
        self.fault("anchor_write")
        payload = canonical(value)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".write-" + uuid4().hex)
        owned = None
        try:
            with temporary.open("xb") as stream:
                owned = os.fstat(stream.fileno())
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if create:
                # Reserve a new anchor; never silently bless an existing checkpoint.
                with self.path.open("xb"):
                    pass
            identity = self.path.stat()
            for attempt in range(8):
                current = self.path.stat()
                if (not os.path.samestat(identity, current)
                        or (identity.st_mtime_ns, identity.st_size) != (current.st_mtime_ns, current.st_size)):
                    raise OSError("G4_CHECKPOINT_IDENTITY_CHANGED")
                try:
                    os.replace(temporary, self.path)
                    break
                except PermissionError:
                    if attempt == 7:
                        raise
                    # Windows scanners/open handles can briefly deny atomic replacement.
                    # Retry only this reserved, unchanged inode; failure remains explicit.
                    time.sleep(0.01 * (attempt + 1))
            if self.path.read_bytes() != payload:
                raise OSError("G4_CHECKPOINT_READBACK_FAILED")
            if os.name != "nt":
                descriptor = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            if owned is not None and temporary.exists() and os.path.samestat(owned, temporary.stat()):
                temporary.unlink()

    def read(self):
        try:
            raw = self.path.read_bytes()
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError
            if value.get("revision") == "g4-checkpoint-v1":
                raise PersistenceError("G4_CORPUS_EPOCH_ADOPTION_REQUIRED", status=503)
            if (raw != canonical(value) or set(value) != {"revision", "database_id", "epoch", "heads", "pending", "corpus", "recovery_required"}
                    or value["revision"] != "g4-checkpoint-v2" or not isinstance(value["heads"], dict)):
                raise ValueError
            if value["recovery_required"] not in {None, "G4_CORPUS_PREFIX_LOST", "G4_CORPUS_CHAIN_INVALID", "G4_CORPUS_BINDING_INVALID"}:
                raise ValueError
            from .corpus_trust import unpack
            unpack(value["corpus"])
            for token in value["heads"].values():
                if (set(token) != {"sequence", "sha256"} or type(token["sequence"]) is not int
                        or token["sequence"] < 0 or len(token["sha256"]) != 64):
                    raise ValueError
            return value
        except PersistenceError:
            raise
        except (OSError, ValueError, TypeError, KeyError):
            raise PersistenceError("G4_CHECKPOINT_INVALID", status=503) from None

    def initialize(self, database_id, heads, corpus=None):
        from .corpus_trust import TABLES, CorpusPrefix, packed
        baseline = corpus or CorpusPrefix(immutable={t: {} for t in TABLES}, documents={})
        self.write(dict(revision="g4-checkpoint-v2", database_id=database_id,
                        epoch=uuid4().hex, heads=heads, pending=None, corpus=packed(baseline), recovery_required=None), create=True)

    def verify_corpus_or_latch(self, value, verify):
        try:
            verify(value["corpus"])
        except PersistenceError as error:
            if error.code in {"G4_CORPUS_PREFIX_LOST", "G4_CORPUS_CHAIN_INVALID", "G4_CORPUS_BINDING_INVALID"}:
                try:
                    self.write({**value, "recovery_required": error.code})
                except OSError:
                    raise PersistenceError("G4_CORPUS_RECOVERY_MARK_FAILED", status=503) from None
            raise

    def reconcile(self, database_id, heads, verify):
        value = self.read()
        if value["recovery_required"] is not None:
            raise PersistenceError("G4_CORPUS_EPOCH_ADOPTION_REQUIRED", status=503)
        if value["database_id"] != database_id or set(heads) != set(value["heads"]):
            raise PersistenceError("G4_RESTORE_EPOCH_REQUIRED", status=503)
        pending = value["pending"]
        expected = dict(value["heads"])
        if pending is None:
            if heads != expected:
                raise PersistenceError("G4_TRUSTED_HEAD_MISMATCH", status=503)
            self.verify_corpus_or_latch(value, verify)
            return value
        try:
            stream = pending["stream_id"]
            if (set(pending) != {"stream_id", "before", "after"} or expected[stream] != pending["before"]
                    or heads[stream] not in (pending["before"], pending["after"])):
                raise ValueError
            expected[stream] = heads[stream]
            if expected != heads:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise PersistenceError("G4_COMMIT_INTENT_MISMATCH", status=503) from None
        self.verify_corpus_or_latch(value, verify)
        self.write({**value, "heads": heads, "pending": None})
        return {**value, "heads": heads, "pending": None}

    def prepare(self, value, stream, before, after):
        if value["pending"] is not None or value["heads"][stream] != before:
            raise PersistenceError("G4_CHECKPOINT_NOT_READY", status=503)
        self.fault("anchor_prepare")
        prepared = {**value, "pending": dict(stream_id=stream, before=before, after=after)}
        self.write(prepared)
        return prepared

    def finish(self, prepared):
        self.fault("anchor_finalize")
        heads = {**prepared["heads"], prepared["pending"]["stream_id"]: prepared["pending"]["after"]}
        self.write({**prepared, "heads": heads, "pending": None})
