"""Pinned offline PR2 preparation or PR3 replay; no online models or business DB.

All-step output is for the administrator. Give a human reviewer only their current
single-step packet, following ANNOTATION_GUIDE.md; exporting is not distribution.
"""

import argparse
import re
from pathlib import Path

from .contracts import Manifest
from .exceptions import ContractError, DatasetValidationError
from .hashing import canonical_json, sha256_bytes
from .provenance import SENSITIVE, controlled_path


def _manifest_location(value):
    path = Path(value).absolute()
    if (path.name != "dataset_manifest.json" or path.parent.name != "manifests"
            or any(p.casefold() in SENSITIVE or p.casefold().startswith(".env")
                   for p in path.parts)):
        raise ContractError("MANIFEST_PATH_INVALID")
    root = path.parent.parent.resolve()
    return root, controlled_path(root, "manifests/dataset_manifest.json")


def _read_input(root, entry):
    raw = controlled_path(root, entry.path).read_bytes()
    if sha256_bytes(raw) != entry.sha256:
        raise ContractError("SHA_MISMATCH", field=entry.path)
    return raw  # Parse the same verified bytes, never reopen them for parsing.


def _output_location(value, bundle_root):
    path = Path(value).absolute().resolve()
    if (path.is_relative_to(bundle_root)
            or any(p.casefold() in {".git", "dev-diaries"}
                   or p.casefold().startswith(".env") or p.endswith((".", " "))
                   or p.casefold().endswith((".db", ".db-wal", ".db-shm")) for p in path.parts)):
        raise ContractError("OUTPUT_PATH_INVALID")
    if path.exists() or path.is_symlink():
        raise ContractError("OUTPUT_EXISTS")
    return path


def export_pilot(manifest_path, *, manifest_sha256, timeline_id, out, step_id=None):
    """Validate a pinned bundle, prepare bytes in memory, then write a NEW directory."""
    from .pilot import annotation_packet
    from .validate import RECORD_MODELS, validate_dataset

    pin = manifest_sha256.lower()
    if re.fullmatch(r"[0-9a-f]{64}", pin) is None:
        raise ContractError("MANIFEST_SHA_MISMATCH")
    root, path = _manifest_location(manifest_path)
    raw_manifest = path.read_bytes()
    if sha256_bytes(raw_manifest) != pin:
        raise ContractError("MANIFEST_SHA_MISMATCH")
    report = validate_dataset(path)
    if report.manifest_sha256 != pin:
        raise ContractError("MANIFEST_SHA_MISMATCH")
    manifest = Manifest.model_validate_json(raw_manifest)
    rows = {role: [] for role in ("documents", "personas", "coverage", "steps")}
    template = None
    for entry in manifest.file_hashes:
        if entry.role in rows:
            raw = _read_input(root, entry)
            rows[entry.role].extend(RECORD_MODELS[entry.role].model_validate_json(line)
                                    for line in raw.splitlines())
        elif entry.path == "DEV-01/annotation_template.json" and entry.role == "support":
            template = _read_input(root, entry)
    if template is None:
        raise ContractError("UNLISTED_INPUT", field="annotation_template")
    if timeline_id != "DEV-01":
        raise ContractError("REFERENCE_NOT_FOUND", field="timeline_id")
    steps = sorted((s for s in rows["steps"] if s.timeline_id == timeline_id
                    and (step_id is None or s.step_id == step_id)), key=lambda s: (s.as_of, s.step_id))
    if not steps:
        raise ContractError("REFERENCE_NOT_FOUND", field="step_id")
    output = _output_location(out, root)
    payloads, visibility, hashes = {}, [], []
    for step in steps:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", step.step_id) is None:
            raise ContractError("OUTPUT_PATH_INVALID", field="step_id")
        packet = annotation_packet(rows["documents"], rows["personas"], rows["coverage"], step=step)
        payloads[f"packets/{step.step_id}/packet.json"] = packet
        payloads[f"packets/{step.step_id}/blank_form.json"] = template
        visibility.append({"step_id": step.step_id, "as_of": step.model_dump(mode="json")["as_of"],
                           "persona_version_id": step.persona_version_id,
                           "visible_doc_version_ids": list(step.visible_doc_version_ids)})
        hashes.append({"step_id": step.step_id, "packet_sha256": sha256_bytes(packet)})
    metadata = {"mode": "pr2_dry_run", "timeline_id": timeline_id,
                "manifest_sha256": pin, "dataset_revision": manifest.dataset_revision,
                "packets": hashes, "distribution": "not_distributed",
                "human_annotation": "not_confirmed", "semantic_support": "not_measured"}
    payloads["visible_steps.jsonl"] = "".join(canonical_json(r) + "\n" for r in visibility).encode()
    payloads["run_metadata.json"] = (canonical_json(metadata) + "\n").encode()
    # No output files exist until every input, pin, step and packet has passed.
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    return metadata


def write_payloads(output, payloads):
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in sorted(payloads.items()):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)


def run_replay(manifest_path, *, manifest_sha256, algorithm_id, out, split=None,
                timeline_id=None, step_id=None, config_path=None, budget_seconds=None,
                half_life_days=None):
    import os
    import platform
    import subprocess
    from datetime import datetime, timezone
    from time import perf_counter

    from .baselines import get_ranker, persona_query, rank_groups
    from .budget import apply_budget
    from .contracts import BudgetPolicy
    from .loader import load_bundle, load_step

    start = perf_counter()
    if algorithm_id not in {"b0", "b1", "b2-predicted", "b2-oracle", "b3", "b4"}:
        raise ContractError("UNKNOWN_ALGORITHM")
    if step_id and not timeline_id:
        raise ContractError("TIMELINE_REQUIRED")
    data = load_bundle(manifest_path, manifest_sha256=manifest_sha256, config_path=config_path)
    half = data.config.half_life_days if half_life_days is None else half_life_days
    if (type(half) is not int or half not in data.config.registered_half_lives
            or (budget_seconds is not None and (type(budget_seconds) is not int
                or budget_seconds not in data.config.registered_budgets))):
        raise ContractError("UNREGISTERED_EXPERIMENT")
    output = _output_location(out, data.root)
    oracle = algorithm_id == "b2-oracle"
    if oracle and "oracle" not in output.name.casefold():
        raise ContractError("ORACLE_OUTPUT_PATH_REQUIRED")
    steps = sorted((s for s in data.steps if (split is None or s.split == split)
                    and (timeline_id is None or s.timeline_id == timeline_id)
                    and (step_id is None or s.step_id == step_id)),
                   key=lambda s: (s.timeline_id, s.as_of, s.step_id))
    if not steps:
        raise ContractError("REFERENCE_NOT_FOUND", field="steps")
    if half != data.config.half_life_days and any(s.split != "dev" for s in steps):
        raise ContractError("SENSITIVITY_REQUIRES_DEV")
    ranker = None if oracle else get_ranker(algorithm_id, data.config, half_life_days=half)
    snapshots, predictions, queries, step_performance = [], [], [], []
    for step in steps:
        step_start = perf_counter()
        context, candidates = load_step(data, timeline_id=step.timeline_id, step_id=step.step_id,
                                        config=data.config)
        docs = [d.model_dump(mode="json") for d in candidates]
        snapshot = {"context": context.model_dump(mode="json"), "candidates": docs}
        candidate_hash = sha256_bytes(canonical_json(docs).encode())
        context_hash = sha256_bytes(canonical_json(snapshot["context"]).encode())
        snapshots.append(snapshot)
        queries.append({"timeline_id": step.timeline_id, "step_id": step.step_id,
                        "query": persona_query(context.persona),
                        "used": algorithm_id != "b0"})
        if oracle:
            from .oracle import oracle_groups

            ranked = rank_groups(context, candidates, oracle_groups(data, candidates,
                                                                    as_of=context.as_of))
        else:
            ranked = ranker.rank(context, candidates)
        presentation = apply_budget(ranked, BudgetPolicy(max_read_seconds=(
            context.attention_budget_seconds if budget_seconds is None else budget_seconds)))
        elapsed = (perf_counter()-step_start)*1000
        step_performance.append({"timeline_id": step.timeline_id, "step_id": step.step_id,
            "candidate_doc_count": len(candidates), "execution_ms": round(elapsed, 3),
            "latency_per_100_docs_ms": elapsed*100/len(candidates) if candidates else None,
            "undefined_reason": None if candidates else "no_candidate_documents"})
        predictions.append({"algorithm_id": algorithm_id, "oracle_mode": oracle,
            "timeline_id": step.timeline_id, "step_id": step.step_id,
            "as_of": context.model_dump(mode="json")["as_of"],
            "candidate_doc_count": len(candidates), "candidate_sha256": candidate_hash,
            "ranked_item_count": len(ranked),
            "predicted_event_count": len(ranked) if algorithm_id not in {"b0", "b1"} else None,
            "available_source_count": len({d.source_id for d in candidates}),
            "coverage_gap_count": sum(c.status != "covered" for c in context.source_coverage),
            "context_sha256": context_hash, "ranked_items": [r.model_dump(mode="json") for r in ranked],
            "presentation": presentation.model_dump(mode="json"),
            "coverage_interpretation": "observed_sources_only; gaps_are_unknown"})
    payloads = {
        "input_snapshot.json": (canonical_json({"snapshot_revision": "pr4-input-v1",
                                               "steps": snapshots}) + "\n").encode(),
        "baseline_config.json": (canonical_json(data.config.model_dump(mode="json")) + "\n").encode(),
        "predictions.jsonl": "".join(canonical_json(r) + "\n" for r in predictions).encode(),
    }
    repo = Path(__file__).resolve().parents[2]
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True,
                         timeout=10)
    if git.returncode:
        raise ContractError("GIT_FINGERPRINT_UNAVAILABLE")
    lock_hashes = {name: sha256_bytes((repo/name).read_bytes())
                   for name in ("requirements.lock", "frontend/package-lock.json")}
    metadata = {"algorithm_id": algorithm_id, "oracle_mode": oracle,
        "dataset_revision": data.manifest.dataset_revision, "schema_revision": data.manifest.schema_revision,
        "annotation_version": data.manifest.annotation_version,
        "dataset_manifest_sha256": manifest_sha256.lower(), "git_sha": git.stdout.strip(),
        "python_version": platform.python_version(), "dependency_lock_sha256": lock_hashes,
        "baseline_config_sha256": data.manifest.baseline_config_sha256,
        "runtime_source_sha256": {**{k: v for k, v in data.verified_hashes.items() if k.endswith(".py")},
                                  "backend/cfaw_news/retrieval.py": data.config.retrieval_sha256},
        "validation_scope": "prediction_inputs", "full_dataset_validated": False,
        "reference_groups_read": oracle, "gold_labels_read": False,
        "network_access": False, "live_model_called": False, "model_tokens": 0,
        "random_seed": data.config.random_seed, "queries": queries, "split": split,
        "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
        "experiment": {"budget_seconds_override": budget_seconds, "half_life_days": half},
        "step_performance": step_performance, "model_cost": 0,
        "timeline_id": timeline_id, "step_id": step_id,
        "predictions_sha256": sha256_bytes(payloads["predictions.jsonl"]),
        "input_snapshot_sha256": sha256_bytes(payloads["input_snapshot.json"]),
        "config_snapshot_sha256": sha256_bytes(payloads["baseline_config.json"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution_ms": round((perf_counter() - start) * 1000, 3)}
    payloads["run_metadata.json"] = (canonical_json(metadata) + "\n").encode()
    write_payloads(output, payloads)
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).parent / "manifests/dataset_manifest.json")
    parser.add_argument("--manifest-sha256", required=True, help="Externally pinned Manifest SHA256")
    parser.add_argument("--timeline")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--algo", choices=["b0", "b1", "b2-predicted", "b2-oracle", "b3", "b4"])
    parser.add_argument("--budget-seconds", type=int, choices=[180, 420, 900])
    parser.add_argument("--half-life-days", type=int, choices=[3, 7, 14])
    parser.add_argument("--split", choices=["train", "dev", "test"])
    parser.add_argument("--config", type=Path, help="Config already listed in the pinned Manifest")
    parser.add_argument("--step", help="Export only this step; withhold later packets from annotators")
    parser.add_argument("--out", type=Path, required=True, help="New output directory; never overwritten")
    args = parser.parse_args(argv)
    if args.step and not args.timeline:
        parser.error("--step requires --timeline")
    if args.dry_run and (args.timeline != "DEV-01" or args.split or args.config
                        or args.budget_seconds is not None or args.half_life_days is not None):
        parser.error("--dry-run requires --timeline DEV-01 and accepts no ranking options")
    try:
        if args.dry_run:
            metadata = export_pilot(args.manifest, manifest_sha256=args.manifest_sha256,
                                    timeline_id=args.timeline, step_id=args.step, out=args.out)
        else:
            metadata = run_replay(args.manifest, manifest_sha256=args.manifest_sha256,
                algorithm_id=args.algo, out=args.out, split=args.split, timeline_id=args.timeline,
                step_id=args.step, config_path=args.config, budget_seconds=args.budget_seconds,
                half_life_days=args.half_life_days)
    except DatasetValidationError as error:
        print(canonical_json(error.report.to_dict()))
        return 1
    except ContractError as error:
        print(canonical_json({"ok": False, "errors": [{"code": error.code, "field": error.field}]}))
        return 1
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        print(canonical_json({"ok": False, "errors": [{"code": "EXPORT_IO_ERROR"}]}))
        return 1
    print(canonical_json({"ok": True, **metadata}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
