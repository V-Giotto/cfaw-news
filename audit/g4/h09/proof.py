"""Read only isolated H09 SQLite files and validate actual test control receipts."""

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime

from cfaw_news.intelligence.sqlite_input import isolated_sqlite_input

from audit.g4.pr6.freeze import ROOT, sha
from audit.g4.pr6.seal import write_new
from evals.intelligence_g3.junit_inventory import verify_inventory, verify_junit
from evals.intelligence_g3.pytest_runner import verify_execution

RUN = ROOT / ".tmp/evals/g3/g4-h09-20261106-001"
PROTECTED = ("evals/intelligence_v1/", "evals/intelligence_g2/", "evals/intelligence_g3/", "tests/", "data/archive/")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def readonly(path):
    assert path.resolve().is_relative_to(ROOT / ".tmp/evals/g3")
    with isolated_sqlite_input(path, expected_sha256=sha(path)) as staged:
        with closing(sqlite3.connect(staged.as_uri() + "?mode=ro", uri=True)) as connection:
            yield connection


def controls():
    inventory = read(RUN / "inventory.json")
    verify_execution(read(RUN / "full-final-control.json"), mode="full", junit=str(RUN / "full-final.xml"),
                     basetemp=str(ROOT / ".tmp/evals/g3/h09-full-final"))
    verify_execution(read(RUN / "collect-control.json"), mode="collect", inventory=str(RUN / "inventory.json"))
    required = verify_inventory(inventory)
    result = verify_junit(required, RUN / "full-final.xml")
    return dict(status="PASS", junit=result, full_execution="PASS", collect_execution="PASS",
                g3_nodes=sum(n.startswith("tests/evals/g3/") for n in inventory["nodes"]),
                required_test_source_sha256=required["test_source_sha256"], matrix_2574="not_evaluated")


def protected():
    entry = read(RUN / "entry.json")
    selected = {n: h for n, h in entry["files"].items() if n.startswith(PROTECTED)}
    assert selected and all(sha(ROOT / n) == h for n, h in selected.items())
    dependencies = {n: entry["files"][n] for n in ("frontend/package-lock.json", "frontend/package.json", "pyproject.toml")}
    assert all(sha(ROOT / n) == h for n, h in dependencies.items())
    old = ROOT / "audit/G4_RELEASE_MANIFEST.json"
    assert sha(old) == "a1f406a4c73627919afe231cc52670c624d8ca4d04df52aba75c486f7a5b876b"
    from audit.g4.pr6.seal import verify_roots
    prior_tree = verify_roots(read(old)["index_roots"])
    return dict(status="PASS", frozen_files=selected, dependency_files=dependencies, prior_seal_sha256=sha(old),
                prior_tree=prior_tree)


def sqlite_proof():
    browser = read(RUN / "browser-pilot-retry/result.json")
    pilot = read(RUN / "pilot-retry/result.json")
    assert browser["status"] == "PASS" and [s["budget"] for s in browser["budget_snapshots"]] == [180, 900, 420]
    db = RUN / "pilot-retry/pilot.db"
    before = sha(db)
    results = []
    with readonly(db) as conn:
        initial = read(RUN / "pilot-retry/initial-snapshots.json")[-1]
        initial_input = json.loads(conn.execute("SELECT runtime FROM intelligence_snapshots WHERE id=?", (initial["id"],)).fetchone()[0])["input"]
        assert conn.execute("SELECT count(*) FROM intelligence_interactions WHERE snapshot_id=?", (initial["id"],)).fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM intelligence_snapshots WHERE version>?", (initial["version"],)).fetchone()[0] > 0
        for item in browser["budget_snapshots"]:
            view, runtime = conn.execute("SELECT data,runtime FROM intelligence_snapshots WHERE id=?", (item["snapshot_id"],)).fetchone()
            view, runtime = json.loads(view), json.loads(runtime)
            value = runtime["input"]
            actual = conn.execute("SELECT available_at,data FROM intelligence_persona_versions WHERE id=?", (item["persona_version_id"],)).fetchone()
            assert value["versions"] == initial_input["versions"]
            assert value["config"]["attention_budget_seconds"] == item["budget"]
            assert runtime["stages"][-1]["replay_input"]["context"]["attention_budget_seconds"] == item["budget"]
            assert datetime.fromisoformat(actual[0]) == datetime.fromisoformat(value["persona"]["persona"]["available_at"].replace("Z", "+00:00"))
            assert datetime.fromisoformat(value["persona_history"][0]["persona"]["available_at"].replace("Z", "+00:00")) > datetime.fromisoformat(pilot["observed_at"])
            assert view["archive"][0]["event_key"] == initial["archive"][0]["event_key"]
            assert runtime["context"] is not None and runtime["ranking"]["history_status"] == "validated_sqlite_prefix_native_rules_v1"
            assert not view["deliveries"] and view["evidence_status"] == "raw_news_only"
            assert runtime["context"]["journal"]["ignored_archive_interaction_ids"]
            window = value["visit_window"]
            assert window["through_sequence"] < value["history_prefix"]["sequence"]
            results.append(dict(**item, original_observation_and_event_identity_preserved=True,
                                persona_time_matches_sqlite=True, window=window))
        visits = conn.execute("SELECT sequence,created_at FROM intelligence_entries WHERE kind='visit'").fetchall()
        assert visits
    assert sha(db) == before
    # Preserve the first full run's exact failure; minute-boundary explanation is an inference.
    failed = ROOT / ".tmp/evals/g3/h09-full/test_retire_demo_news_keeps_fe0/test.db"
    with readonly(failed) as conn:
        calendar = conn.execute("SELECT start,end,created_at FROM schedules").fetchall()
        events = conn.execute("SELECT kind,created_at FROM run_events ORDER BY id").fetchall()
    return dict(status="PASS", database_sha256=before, database_unchanged_by_probe=True,
        budgets=results, unobserved_raw_snapshot_id=initial["id"], still_zero_interactions=True,
        home_visit_receipts=len(visits), source_qualification="raw_news_only", original_user_database_used=False,
        first_full_failure=dict(node="tests/test_workflow.py::test_retire_demo_news_keeps_feed_history_and_user_records",
            schedules=calendar, events=events, diagnosis="inference: approval at 17:50:59.982 UTC; interval() recomputes minute each call, retry crosses minute; unchanged targeted rerun passed", test_source_unchanged=True))


def main():
    write_new(RUN / "control-verification.json", controls())
    write_new(RUN / "protected-verification.json", protected())
    write_new(RUN / "sqlite-proof.json", sqlite_proof())
    print("PASS: registered controls, frozen assets/dependencies, actual browser budget SQLite and raw directory proof")


if __name__ == "__main__":
    main()
