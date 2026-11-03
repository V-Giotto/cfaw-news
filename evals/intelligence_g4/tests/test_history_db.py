"""Transaction/anchor/CAS failures on real isolated SQLite, never synthetic JSONL storage."""

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from cfaw_news.intelligence.checkpoint import PersistenceError
from cfaw_news.intelligence.contracts import digest
from cfaw_news.intelligence.history_store import HistoryStore
from cfaw_news.intelligence.persistence_models import PersonaVersionRow
from sqlalchemy import select

from .persistence_support import Clock, setup_store


def head(store, stream="real:local"):
    with store.read() as (_, heads):
        return heads[stream].sha256


def append(store, expected=None, *, key="one", value="original-persona-value", stream="real:local"):
    def apply(session, h):
        row = PersonaVersionRow(id=digest([stream, key]), stream_id=stream, version=h.sequence + 1,
                                available_at=store.clock(), data=dict(value=value))
        session.add(row)
        return dict(resource_id=row.id), [row], dict(persona_version_id=row.id)
    return store.mutate(stream, key=key, operation="test-persona", payload=dict(value=value),
                        expected_head=expected, apply=apply)


def test_append_head_atomic_and_retry_before_cas(tmp_path):
    db, store, _, anchor = setup_store(tmp_path)
    start = head(store)
    first = append(store, start)
    again = append(store, start)
    assert again["deduplicated"] and first["resource_id"] == again["resource_id"]
    assert first["head"]["sequence"] == again["head"]["sequence"] == 1
    with pytest.raises(PersistenceError, match="IDEMPOTENCY_CONFLICT"):
        append(store, start, value="different")
    with pytest.raises(PersistenceError, match="EXPECTED_HEAD_CONFLICT"):
        append(store, start, key="two")
    with HistoryStore(db, anchor).read() as (session, _):
        assert len(list(session.scalars(select(PersonaVersionRow)))) == 1
    db.engine.dispose()


@pytest.mark.parametrize("stage,committed", [("before_db_commit", False), ("after_db_commit", True),
                                           ("anchor_finalize", True)])
def test_crash_recovers_only_known_before_or_after(tmp_path, stage, committed):
    class Crash(BaseException):
        pass
    db, base, _, anchor = setup_store(tmp_path)
    start = head(base)
    def fault(name):
        if name == stage:
            raise Crash()
    broken = HistoryStore(db, anchor, fault=fault)
    with pytest.raises(Crash):
        append(broken, start)
    recovered = HistoryStore(db, anchor)
    with recovered.read() as (session, heads):
        assert heads["real:local"].sequence == int(committed)
        assert len(list(session.scalars(select(PersonaVersionRow)))) == int(committed)
    retry = append(recovered, start)
    assert retry["deduplicated"] is committed
    assert retry["head"]["sequence"] == 1
    db.engine.dispose()


@pytest.mark.parametrize("stage,committed", [("anchor_prepare", False), ("before_db_commit", False),
                                           ("anchor_finalize", True)])
def test_disk_failure_does_not_leave_half_record(tmp_path, stage, committed):
    db, store, _, anchor = setup_store(tmp_path)
    start = head(store)
    def fault(name):
        if name == stage:
            raise OSError("injected disk failure")
    with pytest.raises(PersistenceError) as failure:
        append(HistoryStore(db, anchor, fault=fault), start)
    assert failure.value.database_state == ("committed" if committed else "unchanged")
    with store.read() as (session, heads):
        assert heads["real:local"].sequence == int(committed)
        assert len(list(session.scalars(select(PersonaVersionRow)))) == int(committed)
    db.engine.dispose()


def test_two_instances_cannot_commit_same_expected_head(tmp_path):
    db, store, _, anchor = setup_store(tmp_path)
    start = head(store)
    barrier = threading.Barrier(2)
    def write(key):
        barrier.wait()
        try:
            return append(HistoryStore(db, anchor), start, key=key)
        except PersistenceError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ("left", "right")))
    assert sum(isinstance(r, dict) for r in results) == 1
    assert next(r for r in results if isinstance(r, str)) in {"G4_STORE_BUSY", "G4_PERSISTENCE_UNAVAILABLE", "G4_EXPECTED_HEAD_CONFLICT"}
    with store.read() as (session, heads):
        assert heads["real:local"].sequence == 1
        assert len(list(session.scalars(select(PersonaVersionRow)))) == 1
    db.engine.dispose()


def test_materialized_record_damage_detected_without_changing_schema(tmp_path):
    db, store, path, anchor = setup_store(tmp_path)
    append(store, head(store))
    db.engine.dispose()
    raw = path.read_bytes()
    assert b"original-persona-value" in raw
    path.write_bytes(raw.replace(b"original-persona-value", b"tampered-persona-value"))
    with pytest.raises(PersistenceError, match="HISTORY_RECORD_MISMATCH"):
        with HistoryStore(db, anchor).read():
            pass
    db.engine.dispose()


def test_capacity_and_clock_rollback_are_explicit(tmp_path):
    clock = Clock()
    db, store, _, _ = setup_store(tmp_path, clock=clock, max_entries=1)
    append(store, head(store))
    with pytest.raises(PersistenceError, match="CAPACITY"):
        append(store, head(store, "synthetic:local"), key="two", stream="synthetic:local")
    db.engine.dispose()


@pytest.mark.parametrize("stage,committed", [("before_db_commit", False), ("after_db_commit", True)])
def test_actual_process_exit_recovers_pending_intent(tmp_path, stage, committed):
    db, store, path, anchor = setup_store(tmp_path)
    initial = head(store)
    script = ("import os,sys;from cfaw_news.database import Database;"
        "from cfaw_news.intelligence.history_store import HistoryStore;"
        "from evals.intelligence_g4.tests.test_history_db import append;"
        "db=Database('sqlite:///'+sys.argv[1]);"
        "store=HistoryStore(db,sys.argv[2],fault=lambda s:os._exit(83) if s==sys.argv[3] else None);"
        "append(store,sys.argv[4])")
    argv = [sys.executable, "-B", "-c", script, str(path), str(anchor), stage, initial]
    child = subprocess.run(argv, env={**os.environ}, capture_output=True)
    assert child.returncode == 83, child.stderr
    with store.read() as (session, heads):
        assert heads["real:local"].sequence == int(committed)
        assert len(list(session.scalars(select(PersonaVersionRow)))) == int(committed)
    (tmp_path / "crash-proof.json").write_text(json.dumps(dict(argv=argv, exit_code=83,
        recovered_sequence=int(committed), actual_process_exit=True)), encoding="utf-8")
    db.engine.dispose()


def test_broken_entry_hash_is_detected_before_materialized_rows(tmp_path):
    db, store, path, _ = setup_store(tmp_path)
    append(store, head(store))
    db.engine.dispose()
    raw = path.read_bytes()
    assert b"test-persona" in raw
    path.write_bytes(raw.replace(b"test-persona", b"test-pers0na"))
    with pytest.raises(PersistenceError, match="HISTORY_CHAIN_INVALID"):
        with store.read():
            pass
    db.engine.dispose()


def test_backwards_clock_cannot_append_a_backdated_entry(tmp_path):
    clock = Clock()
    db, store, _, _ = setup_store(tmp_path, clock=clock)
    append(store, head(store))
    initial = head(store)
    clock.advance(-1)
    with pytest.raises(PersistenceError, match="CLOCK_ROLLBACK"):
        append(store, initial, key="backdated")
    assert head(store) == initial
    with store.read() as (session, _):
        assert len(list(session.scalars(select(PersonaVersionRow)))) == 1
    db.engine.dispose()


def test_checkpoint_temp_collision_never_removes_unowned_file(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from cfaw_news.intelligence import checkpoint
    monkeypatch.setattr(checkpoint, "uuid4", lambda: SimpleNamespace(hex="collision"))
    anchor = tmp_path / "head.json"
    other = tmp_path / "head.json.write-collision"
    other.write_bytes(b"preexisting unrelated artifact")
    with pytest.raises(FileExistsError):
        checkpoint.Checkpoint(anchor).initialize("database", {})
    assert other.read_bytes() == b"preexisting unrelated artifact" and not anchor.exists()
