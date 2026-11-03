"""Real local owner handoff while a run-start return is paused; no model/network."""

import asyncio
import threading
import time
from contextlib import ExitStack

import pytest
from cfaw_news.intelligence.contracts import canonical
from cfaw_news.intelligence.persistence_models import BriefingRun
from cfaw_news.main import create_app

from .persistence_support import (
    LocalClient,
    capture,
    current_status,
    save_persona,
    setup_app,
    start,
    wait_run,
)

HEADERS = {"Origin": "http://127.0.0.1:8000"}


def until(check, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.005)
    raise AssertionError("mock boundary did not become ready")


class PhysicalWork:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = dict(old=0, new=0)
        self.calls = dict(old=0, new=0)
        self.peak = 0
        self.a_release, self.b_release, self.new_release = (threading.Event() for _ in range(3))

    def runtime(self, label):
        def block(raw, **kwargs):
            with self.lock:
                number = self.calls[label]
                self.calls[label] += 1
                self.active[label] += 1
                self.peak = max(self.peak, sum(self.active.values()))
            gate = self.new_release if label == "new" else self.a_release if number == 0 else self.b_release
            try:
                assert gate.wait(20)
                return None  # Uncooperative engineering fault; cannot form a publishable result.
            finally:
                with self.lock:
                    self.active[label] -= 1
        return block

    def release_all(self):
        for gate in (self.a_release, self.b_release, self.new_release):
            gate.set()


@pytest.mark.parametrize("cancel_waiter", [False, True])
def test_shutdown_run_start_reservation_cannot_compute_after_owner_handoff(tmp_path, cancel_waiter):
    seed, clock, _, _ = setup_app(tmp_path, mode="synthetic_development", timeout=10)
    settings = seed.state.intelligence.settings.model_copy(update=dict(intelligence_max_workers=2))
    seed.state.intelligence.compute_pool.shutdown(wait=False)
    seed.state.database.engine.dispose()
    work = PhysicalWork()
    paused, resume = threading.Event(), threading.Event()
    finishing, finish_resume = threading.Event(), threading.Event()
    app = create_app(settings)
    old = app.state.intelligence
    old.clock = old.store.clock = clock
    old.runtime = work.runtime("old")
    proof = dict(cancel_waiter=cancel_waiter, configured_workers=2)

    def replacement():
        other = create_app(settings)
        other.state.intelligence.clock = other.state.intelligence.store.clock = clock
        other.state.intelligence.runtime = work.runtime("new")
        return other

    try:
        with ExitStack() as cleanup:
            client = cleanup.enter_context(LocalClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS))
            cleanup.callback(work.release_all)
            cleanup.callback(resume.set)
            cleanup.callback(finish_resume.set)
            assert save_persona(client).status_code == 201
            capture(app, clock, origin="synthetic")
            first = start(client, key="A")
            assert first.status_code == 202, first.text
            a_id = first.json()["resource_id"]
            until(lambda: work.active["old"] == 1 and len(old.computations) == 1)
            a_future = next(iter(old.computations))
            original = old._running
            def pause_return(identifier):
                result = original(identifier)
                if identifier != a_id:
                    paused.set()
                    assert resume.wait(20)
                return result
            old._running = pause_return
            second = start(client, key="B")
            assert second.status_code == 202, second.text
            b_id = second.json()["resource_id"]
            assert paused.wait(8)
            original_finish = old.finish
            async def pause_finish(identifier, status, codes):
                if identifier == b_id and not cancel_waiter:
                    finishing.set()
                    while not finish_resume.is_set():
                        await asyncio.sleep(0.005)
                return await original_finish(identifier, status, codes)
            old.finish = pause_finish
            closing = client.portal.start_task_soon(old.close)
            until(lambda: old.closed)
            if cancel_waiter:
                client.portal.call(old.tasks[b_id].cancel)
                until(lambda: b_id not in old.tasks)
            work.a_release.set()
            until(lambda: a_future not in old.computations)
            proof.update(owner_retained_while_start_paused=old.worker_lock is not None,
                         old_close_done_while_paused=closing.done(), old_native_calls=work.calls["old"])
            (tmp_path / "shutdown-reservation-proof.json").write_bytes(canonical(proof))
            assert old.worker_lock is not None  # This exact boundary failed in the reviewed implementation.
            assert len(old.computations) == 1

            busy_app = replacement()
            with LocalClient(busy_app, base_url="http://127.0.0.1:8000", headers=HEADERS) as busy:
                assert not current_status(busy)["worker_available"]
                denied = start(busy, key="not-owner")
                assert denied.status_code == 503 and denied.json()["code"] == "G4_WORKER_UNAVAILABLE"
            proof["replacement_before_drain_http"] = denied.status_code
            resume.set()
            if not cancel_waiter:
                assert finishing.wait(8)
                until(lambda: not old.computations)
                assert old.worker_lock is not None and not closing.done()
                proof["owner_retained_during_terminal_cleanup"] = True
                finish_resume.set()
            closing.result(timeout=10)
            until(lambda: old.worker_lock is None and not old.computations)
            assert work.calls["old"] == 1  # B's native function never entered after close.
            with app.state.database.session() as session:
                assert session.get(BriefingRun, b_id).status == "interrupted"

            new_app = replacement()
            with LocalClient(new_app, base_url="http://127.0.0.1:8000", headers=HEADERS) as new:
                assert current_status(new)["worker_available"]
                responses = [start(new, key="new-" + str(i)) for i in range(2)]
                assert all(r.status_code == 202 for r in responses), [r.text for r in responses]
                until(lambda: work.active["new"] == 2)
                assert work.active["old"] == 0 and work.peak == 2
                work.new_release.set()
                assert all(wait_run(new, r.json()["resource_id"])["status"] != "completed" for r in responses)
                assert new.get("/api/intelligence/briefings/latest").status_code == 404
            proof.update(status="PASS", old_native_calls=work.calls["old"], new_native_calls=work.calls["new"],
                         total_physical_peak=work.peak, late_publications=0, owner_after_drain_reacquired=True)
            (tmp_path / "shutdown-reservation-proof.json").write_bytes(canonical(proof))
    finally:
        resume.set()
        finish_resume.set()
        work.release_all()
