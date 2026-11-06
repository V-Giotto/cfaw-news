"""Publish a replacement seal only after verifying every QA reference, preserving v1 evidence."""

import argparse
import importlib.metadata
import json
import shutil
import zipfile
from datetime import datetime, timezone

from audit.g4.pr6 import finalize as f
from audit.g4.pr6.freeze import ROOT, sha, write
from audit.g4.pr6.review_freeze import TARGET, check_review
from audit.g4.pr6.seal import INDEX, build_roots, pin, verify_roots, write_new

QA = ROOT / "audit/g4/pr6"
RUN = f.RUN


def commands():
    records = {p.stem.removesuffix(".command"): f.read(p) for p in RUN.glob("*.command.json")}
    for record in records.values():
        assert sha(ROOT / record["log"]) == record["log_sha256"]
    required = ("legacy-damage", "source-freeze", "full-final", "g4-final", "collect-registered",
                "seal-regressions-final", "build", "frontend-unit", "contract-fixtures-native",
                "real-pilot-native", "browser-green", "restore", "baseline", "types", "schema-final", "ruff-sealed", "control-final")
    assert all(records[n]["exit_code"] == 0 for n in required)
    assert records["browser-red"]["exit_code"] == 1
    return records


def browsers():
    paths = ("browser-green/strict-focus.command.json", "browser-green/contracts.command.json", "browser-green/pilot.command.json")
    for name in paths:
        record = f.read(RUN / name)
        env = record["environment"]
        assert record["exit_code"] == 0 and env["CFAW_PR6_RUN"] == str(RUN)
        assert env["CFAW_PR6_PILOT"] == "pilot-native"
        assert sha(ROOT / record["log"]) == record["log_sha256"]
        assert sha(ROOT / record["fixtures"]["path"]) == record["fixtures"]["sha256"]
        assert env["CFAW_PR5_OUT"] == str((ROOT / record["fixtures"]["path"]).parent)
        for service in record["active_services"]:
            assert sha(ROOT / service["config"]) == service["config_sha256"]
    for phase, names in (("red", ("contract", "development")), ("green", ("contract", "development", "pilot"))):
        lifecycle = f.read(RUN / f"browser-{phase}/lifecycle.json")
        assert lifecycle["status"] == "PASS" and all(c == 0 for c in lifecycle["service_exit_codes"])
        for name in names:
            record = f.read(RUN / f"browser-{phase}/{name}.service.json")
            assert record["exit_code"] == 0 and record["ready_http_status"] == 200 and record["stop_method"].startswith("stdin STOP")
            assert sha(ROOT / record["log"]) == record["log_sha256"]
            assert sha(ROOT / record["config"]) == record["config_sha256"]
    config = f.read(RUN / "browser-green/pilot.config.json")
    assert config["qa_delay_seconds"] == 2 and not any(config[k] for k in ("news_auto_refresh", "news_media_fetch", "news_reading_fetch"))
    focus = f.read(RUN / "browser-green/focus/focus-result.json")
    assert focus["status"] == "PASS" and focus["strict_mode"] and focus["cycles"] == 3
    assert "focus lost to BODY" in (RUN / "browser-red/strict-focus.log").read_text()
    contract = f.read(RUN / "browser-contracts-native/browser-results.json")
    pilot = f.read(RUN / "browser-pilot/result.json")
    assert contract["status"] == pilot["status"] == "PASS"
    assert len(contract["checks"]) == 26 and len(pilot["checks"]) == 10
    assert not pilot["page_errors"] and not pilot["external_attempts"]
    return dict(contract_groups=26, pilot_groups=10, development_focus_checks=5, development_focus_cycles=3,
                browser_version=pilot["browser_version"], effective_targets_and_lifecycles="PASS")


def snapshots(files):
    snapshot = RUN / "source-snapshot"
    assert not snapshot.exists()
    names = set(files) | set(f.DOCS)
    names.update(p.relative_to(ROOT).as_posix() for p in QA.iterdir() if p.suffix in (".py", ".cjs", ".mjs", ".md"))
    names.update({"audit/g4/pr6/ENTRY_FREEZE.json", "audit/g4/pr6/REVIEW_FIX_SOURCE_FREEZE.json", "audit/g4/pr6/INVALIDATED_RELEASE_MANIFEST_V1.json"})
    names.update(p.relative_to(ROOT).as_posix() for p in (QA / "samples/vite-8.3.4").iterdir() if p.name != "MANIFEST.json")
    for name in sorted(names):
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        assert sha(target) == sha(ROOT / name)
    seed = RUN / "seed-baseline/result.json"
    seed.parent.mkdir()
    shutil.copyfile(ROOT / ".local/evals/baseline.json", seed)
    # The sealer's negative tests deliberately contain occupied/corrupt QA index names.
    # Preserve their exact bytes in a hash-pinned archive instead of overriding those fixtures.
    members = {}
    with zipfile.ZipFile(RUN / "seal-regression-cases.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for area in ("p6-fix-seal-tests", "p6-fix-seal-tests-final"):
            folder = ROOT / ".tmp/evals/g3" / area
            for path in sorted(folder.rglob("*")):
                if path.is_file() and not path.is_symlink():
                    name = area + "/" + path.relative_to(folder).as_posix()
                    archive.write(path, name)
                    members[name] = pin(path)
    write_new(RUN / "seal-regression-cases.json", dict(note="Negative index fixtures are opaque test data; not accepted QA directory indexes", members=members))
    return {name: sha(ROOT / name) for name in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    original, current = check_review()
    distributions = sorted({(d.metadata["Name"], d.version) for d in importlib.metadata.distributions()})
    assert [list(d) for d in distributions] == original["python_distributions"], "dependency drift"
    controls = f.verify_controls()
    if args.verify_only:
        print(json.dumps(dict(status="PASS", controls=controls["junit"]["nodes"], source_files=len(current["files"]))))
        return
    write(RUN / "control-verification.json", controls)
    records = commands()
    browser = browsers()
    full, g4 = f.cases(RUN / "full-final.xml"), f.cases(RUN / "g4-final.xml")
    assert len(full) == 1754 and sum(c["status"] == "SKIPPED" for c in full) == 1
    assert len(g4) == 321 and all(c["status"] == "PASS" for c in g4)
    legacy = f.read(RUN / "legacy-seal-audit.json")
    assert len(legacy["mismatches"]) == 9 and legacy["status"] == "INVALID_V1_SEAL_DO_NOT_USE"
    regenerated = []
    for item in legacy["mismatches"]:
        name = item["path"].replace("/p6-full/", "/p6-fix-full-final/").replace("/p6-g4/", "/p6-fix-g4-final/")
        path = ROOT / name
        payload = f.read(path)
        assert not isinstance(payload, dict) or payload.get("revision") != "g4-pr6-directory-manifest-v1"
        regenerated.append(dict(previous_path=item["path"], fresh_path=name, before_indexing=pin(path),
                                provenance="Fresh complete test run, not a reconstruction from the lost v1 hash"))
    fault_matrix = {}
    for group, needles in {
        "migration_backup_restore": ("migrat", "backup", "restore"),
        "duplicate_rss": ("duplicate", "idempotent", "parser_write_path"),
        "correction_retraction": ("correction", "retract", "supersed", "assessment", "revision"),
        "symbols_units": ("symbol", "unit", "number"),
        "unknown_rights": ("unknown_rights", "metadata_only", "policy_never_inferred"),
        "long_content": ("long_input", "oversize", "quote", "long_paragraph"),
        "failure_offline_restart": ("failure", "offline", "restart", "failed"),
        "damaged_head_prefix": ("head", "prefix", "rollback", "corrupt", "checkpoint"),
        "concurrent_conflict": ("concurrent", "conflict", "race", "cas_"),
    }.items():
        selected = [case for case in g4 if any(n in case["node"] for n in needles)]
        assert selected, group
        fault_matrix[group] = dict(status="PASS_LOCAL_ENGINEERING", junit=f.rel(RUN / "g4-final.xml"), cases=selected)
    f.toolchain()
    source_pins = snapshots(current["files"])
    names = ("p6-fix-full-final", "p6-fix-g4-final", "p6-fix-full", "p6-fix-g4", "p6-fix-full-native", "p6-fix-g4-native")
    roots = [RUN] + [ROOT / ".tmp/evals/g3" / name for name in names]
    indexes = build_roots(roots)
    verified = verify_roots(indexes)
    for item in regenerated:
        path = ROOT / item["fresh_path"]
        assert pin(path) == item["before_indexing"] and not path.samefile(path.parent / INDEX)
        item.update(after_indexing=pin(path), distinct_from_qa_index=True)
    assert all(sha(ROOT / name) == value for name, value in source_pins.items())
    check_review()
    result = dict(revision="g4-pr6-review-fix-results-v2", status="SELF_TESTED_PENDING_INDEPENDENT_REVIEW",
        tracks=f.TRACKS, gates=f.gates(), invalidated_v1=legacy, source_delta=current["authorized_delta"],
        source_files=len(current["files"]), original_files_unchanged=1145, controls=controls,
        full_counts=dict(passed=1753, skipped=1), g4_counts=dict(passed=321, skipped=0),
        seal_regression_tests=7, browser=browser, frontend_unit_passed=14,
        commands=records, recursive_verification=verified, roots=indexes,
        regenerated_business_manifests=regenerated,
        fault_matrix=fault_matrix, upstream_review=f.upstream_review(),
        interrupted_attempts=f.read(RUN / "interrupted-attempts.json"),
        original_user_database_used=False, external_network_smoke="not_evaluated",
        independent_review="PENDING", owner_beta_approval="PENDING", git_mutations=0)
    target = QA / "REVIEW_FIX_RESULTS.json"
    write_new(target, result)
    release = dict(revision="g4-release-candidate-pr6-review-fix-v2", generated_at=datetime.now(timezone.utc).isoformat(),
        status="CONDITIONAL_PENDING_INDEPENDENT_REVIEW_AND_OWNER_APPROVAL", tracks=f.TRACKS, gates=f.gates(),
        head=original["head"], committed_release=False, original_entry=pin(QA / "ENTRY_FREEZE.json"),
        review_source_freeze=pin(TARGET), source_files_sha256=current["files"], source_snapshot=str((RUN / "source-snapshot").relative_to(ROOT)),
        index_name=INDEX, index_roots=indexes, recursive_verification=verified, results=pin(target),
        documents={name: pin(ROOT / name) for name in f.DOCS}, qa_source_sha256={name: value for name, value in source_pins.items() if name.startswith("audit/g4/pr6/")},
        invalidated_previous=pin(QA / "INVALIDATED_RELEASE_MANIFEST_V1.json"), invalidation_audit=pin(RUN / "legacy-seal-audit.json"),
        runtime_config=original["native_runtime_config"], fact_policy=original["fact_policy"], rank_policy=original["rank_policy"],
        api_contract=original["g4_api_contract"], database_schema_sha256=original["database_schema_sha256"],
        migration_source_sha256=original["migration_source_sha256"], production_source_registry=original["production_source_registry"],
        toolchain=pin(RUN / "toolchain.json"), browser=browser,
        complete_test_roots=["p6-fix-full-final", "p6-fix-g4-final"],
        interrupted_roots="Other test roots are explicitly preserved incomplete attempts; their contents being sealed does not make those tests PASS",
        boundaries=dict(real_user_database_used=False, new_external_fetches=0, public_deployment=False,
                        system_or_email_push=0, unapproved_third_party_actions=0, product_algorithm_changes=0, git_writes=0),
        self_hash="Excluded to avoid circularity; actual tool output records final SHA256")
    # This is the sole replacement pointer. The original v1 release is retained verbatim.
    write(f.RELEASE, release)
    print(json.dumps(dict(status=release["status"], release_sha256=sha(f.RELEASE), recursive_verification=verified)))


if __name__ == "__main__":
    main()
