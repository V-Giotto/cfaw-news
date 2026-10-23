"""G1-a development acceptance with a separate optional human research profile.

Only reads explicit local run/check artifacts. Never runs commands, changes gold,
contacts providers or accesses a business database.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from .annotations import audit_bundle, reference_records
from .build_pr5 import PRIMARY_TIMELINES
from .contracts import AcceptanceResult
from .exceptions import ContractError, DatasetValidationError
from .hashing import canonical_json, sha256_bytes
from .loader import json_value, load_bundle, read_entry
from .replay import _output_location, write_payloads
from .report import build_report
from .validate import validate_dataset

TECHNICAL_GATES = ("prior_review", "dataset", "temporal", "contracts", "provenance", "baselines",
                   "reproduction", "metrics", "regression", "limitations")
CHECK_NAMES = {"ruff", "schemas", "validate", "pip", "pytest-evals", "pytest-full", "seed", "frontend-build", "diff"}


def source_fingerprints(repo):
    paths = set()
    for directory, pattern in (("evals/intelligence_v1", "*.py"), ("tests", "*.py"),
                               ("backend", "*.py"), ("frontend/src", "*")):
        paths.update(p for p in (repo/directory).rglob(pattern) if p.is_file() and "__pycache__" not in p.parts)
    paths.update(repo/p for p in ("requirements.lock", "frontend/package-lock.json", "frontend/package.json",
                                 "AGENTS.md", "docs/CFAW_News_V1.md", "docs/plans/G1_IMPLEMENTATION_PLAN.md",
                                 "docs/plans/G1_AI_DEVELOPMENT_RULES.md"))
    return {p.relative_to(repo).as_posix(): sha256_bytes(p.read_bytes()) for p in sorted(paths)}


def decide_acceptance(statuses, *, human_gate, profile="ai_development"):
    if profile not in {"ai_development", "human_research"}:
        raise ContractError("ACCEPTANCE_PROFILE_INVALID")
    gates = {name: {"status": statuses.get(name, "BLOCKED"),
                    "reason": "Verified evidence" if statuses.get(name) == "PASS" else "Missing or failed evidence"}
             for name in TECHNICAL_GATES}
    gates["human_annotation"] = {"status": human_gate if profile == "human_research" else "N/A", "reason": (
        "Optional human research audit; actual status is " + human_gate if profile == "ai_development" else
        "Real independently frozen submissions and adjudication confirmed" if human_gate == "PASS"
        else "Real human annotation gate not met; programmatic tests do not replace people")}
    if profile == "ai_development":
        gates["development_labels"] = {"status": statuses.get("development_labels", "BLOCKED"),
            "reason": ("Frozen synthetic development expectations cover every visible reference event"
                       if statuses.get("development_labels") == "PASS" else "Missing or incomplete frozen development labels")}
    gates["migration"] = {"status": "N/A", "reason": "G1 does not access or migrate the production database"}
    states = [gates[n]["status"] for n in TECHNICAL_GATES]
    technical = "FAIL" if "FAIL" in states else "BLOCKED" if any(s != "PASS" for s in states) else "PASS"
    human_passed = technical == "PASS" and human_gate == "PASS"
    passed = (technical == "PASS" and gates["development_labels"]["status"] == "PASS"
              if profile == "ai_development" else human_passed)
    result = {"acceptance_profile": profile, "overall_status": "PASS" if passed else "NOT_MET",
              "technical_gate": technical, "human_annotation_gate": human_gate,
              "human_research_passed": human_passed, "g1a_passed": passed, "g2_eligible": passed, "gates": gates}
    return AcceptanceResult.model_validate_json(canonical_json(result)).model_dump(mode="json")


def development_labels_complete(data, primary, expected):
    """Require exact event/step coverage; validation separately checks evidence and hashes."""
    events = reference_records(data, "events")
    required = {(s.timeline_id, s.step_id, s.persona_version_id, e["event_id"])
                for s in primary for e in events
                if set(e["document_version_ids"]) & set(s.visible_doc_version_ids)}
    actual = [(e["timeline_id"], e["step_id"], e["persona_version_id"], e["event_id"])
              for e in expected if e["timeline_id"] in PRIMARY_TIMELINES]
    return bool(required) and len(actual) == len(set(actual)) and set(actual) == required


def verify_required_tests(data, checks):
    entry = next((e for e in data.manifest.file_hashes
                  if e.path == "manifests/required_tests.json" and e.role == "support"), None)
    if entry is None:
        raise ContractError("TEST_REQUIREMENTS_MISSING")
    required = json_value(read_entry(data.root, entry))
    nodes = required.get("nodes", [])
    requirements = required.get("requirements", {})
    ids = {f"T{i:02}" for i in range(1, 27) if i != 25}
    if (required.get("revision") != "g1-required-tests-v1" or not nodes
            or any(not isinstance(n, str) or "::" not in n for n in nodes)
            or len(set(nodes)) != len(nodes) or set(requirements) != ids
            or any(not values or not set(values) <= set(nodes) for values in requirements.values())
            or required.get("not_applicable") != {"T25": "No production migration"}):
        raise ContractError("TEST_REQUIREMENTS_INVALID")
    sources = {p: h for p, h in checks["source_fingerprints"].items() if p.startswith("tests/")}
    if not sources or required.get("test_source_sha256") != sources:
        raise ContractError("TEST_REQUIREMENTS_STALE")
    exemptions = required.get("skip_exemptions", [])
    for name in ("pytest-full", "pytest-evals"):
        command = next(c for c in checks["commands"] if c["name"] == name)
        junit = [a for a in command["artifacts"] if a["path"].endswith(".xml")]
        if len(junit) != 1:
            raise ContractError("CHECK_EVIDENCE_INCOMPLETE", field=name)
        try:
            suites = ET.fromstring(Path(junit[0]["path"]).read_bytes())
        except ET.ParseError:
            raise ContractError("CHECK_EVIDENCE_INVALID", field=name) from None
        cases = list(suites.iter("testcase"))
        actual = [t.get("classname", "")+"::"+t.get("name", "") for t in cases]
        expected = [n for n in nodes if name == "pytest-full" or n.startswith("tests.evals.")]
        if Counter(actual) != Counter(expected):
            raise ContractError("REQUIRED_TESTS_INCOMPLETE", field=name)
        if (any(int(s.get("failures", 0)) or int(s.get("errors", 0)) for s in suites.iter("testsuite"))
                or any(t.find("failure") is not None or t.find("error") is not None for t in cases)):
            raise ContractError("REQUIRED_TEST_FAILED", field=name)
        for node, case in zip(actual, cases, strict=True):
            skipped = case.find("skipped")
            if skipped is not None and not any(e.get("node") == node and e.get("platform") == sys.platform
                    and e.get("reason") == skipped.get("message") for e in exemptions):
                raise ContractError("UNEXEMPT_TEST_SKIP", field=node)


def verify_checks(data, checks_path):
    checks_path = Path(checks_path).resolve()
    repo = Path(__file__).resolve().parents[2]
    if not checks_path.is_relative_to(repo/".local/evals/g1/pr5"):
        raise ContractError("CHECK_EVIDENCE_PATH_INVALID")
    checks = json.loads(checks_path.read_bytes())
    if (checks["dataset_manifest_sha256"] != sha256_bytes((data.root/"manifests/dataset_manifest.json").read_bytes())
            or checks["source_fingerprints"] != source_fingerprints(repo)):
        raise ContractError("CHECK_EVIDENCE_MISMATCH")
    commands = checks["commands"]
    if Counter(c["name"] for c in commands) != Counter(CHECK_NAMES):
        raise ContractError("CHECK_EVIDENCE_INCOMPLETE")
    for command in commands:
        if command["exit_code"] != 0:
            raise ContractError("CHECK_COMMAND_FAILED", field=command["name"])
        for artifact in command["artifacts"]:
            path = Path(artifact["path"]).resolve()
            if not path.is_relative_to(checks_path.parent):
                raise ContractError("CHECK_EVIDENCE_PATH_INVALID")
            if sha256_bytes(path.read_bytes()) != artifact["sha256"]:
                raise ContractError("SHA_MISMATCH", field=command["name"])
        if not command["argv"] or not command["artifacts"]:
            raise ContractError("CHECK_EVIDENCE_INCOMPLETE")
    verify_required_tests(data, checks)
    review = checks["prior_review"]
    if (review["status"] != "PASS" or review["head"] != "e1ce349895b06dc57b40b5c5e1f75b50caf411ec"
            or review["manifest_sha256"] != "f2782a4da6ff8e4e34e7fd348d534422219a688564dcfc3553a96f56ad2f46ab"
            or not review["thread_id"] or not review["turn_id"]):
        raise ContractError("PRIOR_REVIEW_NOT_MET")
    return checks


def verify_matrix(summary, data, runs):
    expected_steps = {(s.timeline_id, s.step_id) for s in data.steps if s.timeline_id in PRIMARY_TIMELINES}
    if len(expected_steps) != 26:
        raise ContractError("PRIMARY_COHORT_INCOMPLETE")
    expected_configs = {(a, budget, 7, label) for a in ("b0", "b1", "b2-predicted", "b2-oracle", "b3", "b4")
                        for budget in (180, 420, 900) for label in ("gold", "synthetic-fixture")}
    expected_configs.update(("b3", 420, half, label) for half in (3, 14)
                            for label in ("gold", "synthetic-fixture"))
    configurations = set()
    for cohort in summary["cohorts"]:
        exp = cohort["experiment"]
        key = (cohort["algorithm_id"], exp["budget_seconds_override"], exp["half_life_days"], cohort["label_source"])
        configurations.add(key)
        actual_steps = {(s["timeline_id"], s["step_id"]) for s in cohort["steps"]}
        if actual_steps != expected_steps or set(cohort["replicates_by_step"].values()) != {2}:
            raise ContractError("PRIMARY_COHORT_INCOMPLETE")
    if configurations != expected_configs:
        raise ContractError("REPRODUCTION_MATRIX_INCOMPLETE")
    canonical, seeds = {}, {}
    groups = Counter()
    for path in sorted(Path(runs).rglob("run_metadata.json")):
        metadata = json.loads(path.read_bytes())
        if metadata.get("algorithm_id") is None:
            continue
        if metadata.get("python_hash_seed") not in {"1", "719"}:
            raise ContractError("REPRODUCTION_SEED_MISSING")
        key = (metadata["algorithm_id"], metadata["timeline_id"], canonical_json(metadata["experiment"]))
        groups[key] += 1
        seeds.setdefault(key, set()).add(metadata["python_hash_seed"])
        signature = tuple((path.parent/name).read_bytes() for name in (
            "predictions.jsonl", "input_snapshot.json", "baseline_config.json"))
        if canonical.setdefault(key, signature) != signature:
            raise ContractError("NONDETERMINISTIC_PREDICTIONS")
    if len(groups) != 100 or set(groups.values()) != {2} or any(s != {"1", "719"} for s in seeds.values()):
        raise ContractError("REPRODUCTION_MATRIX_INCOMPLETE")


def build_acceptance(manifest_path, *, manifest_sha256, runs, checks_path, out, profile="ai_development"):
    data = load_bundle(manifest_path, manifest_sha256=manifest_sha256)
    output = _output_location(out, data.root)
    statuses, reasons = {}, {}
    validation = validate_dataset(manifest_path, strict=True)
    audit = audit_bundle(data)
    primary = [s for s in data.steps if s.timeline_id in PRIMARY_TIMELINES]
    counts = Counter(s.timeline_id for s in primary)
    families = {f for s in primary for f in s.family_scope_ids}
    docs = [d for d in data.documents if d.family_id in families]
    expected = reference_records(data, "fixture_expectations")
    statuses["development_labels"] = "PASS" if (getattr(data.manifest, "status", None) == "frozen"
        and development_labels_complete(data, primary, expected)) else "FAIL"
    development_audit = None
    if profile == "ai_development" and statuses["development_labels"] == "PASS":
        from .ai_development import audit_development

        try:
            development_audit = audit_development(data)
        except (ContractError, OSError, ValueError, KeyError, TypeError) as exc:
            statuses["development_labels"] = "FAIL"
            reasons["development_labels"] = getattr(exc, "code", "AI_DEVELOPMENT_INVALID")
    valid_stories = all(any(e["timeline_id"] == t and e["material_change"] == "no_change" for e in expected)
                        for t in PRIMARY_TIMELINES)
    statuses["dataset"] = "PASS" if counts == {t: 6 if t == "DEV-01" else 5 for t in PRIMARY_TIMELINES} and len(families) == 5 and len(docs) == 35 and valid_stories else "FAIL"
    statuses["contracts"] = "PASS" if validation.ok else "FAIL"
    statuses["provenance"] = "PASS" if validation.ok and data.manifest.record_origin_breakdown.real == 0 else "FAIL"
    statuses["limitations"] = "PASS" if not data.manifest.record_origin_breakdown.real and data.manifest.limitations else "FAIL"
    try:
        checks = verify_checks(data, checks_path)
        for name in ("prior_review", "temporal", "regression"):
            statuses[name] = "PASS"
    except (ContractError, OSError, ValueError, KeyError, StopIteration) as exc:
        checks = None
        for name in ("prior_review", "temporal", "regression"):
            statuses[name] = "BLOCKED"
            reasons[name] = getattr(exc, "code", "CHECK_EVIDENCE_INVALID")
    try:
        summary = build_report(runs, manifest_path, manifest_sha256=manifest_sha256)
        verify_matrix(summary, data, runs)
        for name in ("baselines", "reproduction", "metrics"):
            statuses[name] = "PASS"
    except (ContractError, OSError, ValueError, KeyError) as exc:
        summary = None
        for name in ("baselines", "reproduction", "metrics"):
            statuses[name] = "FAIL"
            reasons[name] = getattr(exc, "code", "RUN_EVIDENCE_INVALID")
    result = decide_acceptance(statuses, human_gate=audit["human_gate"], profile=profile)
    for name, reason in reasons.items():
        result["gates"][name]["reason"] = reason
    payload = {**result, "dataset_manifest_sha256": manifest_sha256,
        "dataset_revision": data.manifest.dataset_revision, "primary_step_count": len(primary),
        "primary_document_version_count": len(docs), "auxiliary_step_count": len(data.steps)-len(primary),
        "origin_counts": data.manifest.record_origin_breakdown.model_dump(),
        "annotation_audit": audit, "ai_development_audit": development_audit, "checks_verified": checks is not None,
        "matrix_verified": summary is not None, "T25": "N/A",
        "scope": "offline_synthetic_development_reproducibility_not_production_or_user_efficacy"}
    lines = ["# G1 acceptance", "", f"Profile: `{profile}`.", "", f"Overall: **{result['overall_status']}**; technical: **{result['technical_gate']}**; "
             f"human: **{result['human_annotation_gate']}**.", "", f"Manifest: `{manifest_sha256}`.", "",
             "| Gate | Status | Reason |", "|---|---|---|"]
    lines += [f"| {name} | {value['status']} | {value['reason']} |" for name, value in result["gates"].items()]
    lines += ["", "Five synthetic primary stories / 26 steps / 35 document versions; auxiliary fixtures are separate.",
              ("Development acceptance uses authored synthetic expectations; optional human research is reported separately."
               if profile == "ai_development" else
               "Missing real independent annotation prevents human research acceptance."
               if audit["human_gate"] != "PASS" else "Human attestation and lineage checked; identity was confirmed by the administrator."),
              "Formal change classification and algorithm-output semantic support remain unmeasured.",
              "T25=N/A. No production database access, migration, online collection or live model calls.",
              "No generalization, real-user efficacy or production-readiness claim.", ""]
    write_payloads(output, {"acceptance.json": (canonical_json(payload)+"\n").encode(),
                            "G1_ACCEPTANCE.md": "\n".join(lines).encode()})
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--checks", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--profile", choices=["ai_development", "human_research"], default="ai_development")
    args = parser.parse_args(argv)
    try:
        result = build_acceptance(args.manifest, manifest_sha256=args.manifest_sha256,
                                  runs=args.runs, checks_path=args.checks, out=args.out, profile=args.profile)
    except (ContractError, DatasetValidationError, OSError, ValueError, KeyError) as exc:
        print(canonical_json({"ok": False, "code": getattr(exc, "code", "ACCEPTANCE_INPUT_INVALID")}))
        return 1
    print(canonical_json({"ok": result["g1a_passed"], "acceptance_profile": result["acceptance_profile"],
                          "technical_gate": result["technical_gate"],
                          "human_annotation_gate": result["human_annotation_gate"], "g2_eligible": result["g2_eligible"]}))
    return 0 if result["g1a_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
