"""Run the registered PR5 matrix through public offline CLIs using the existing environment."""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .acceptance import verify_matrix
from .build_pr5 import PRIMARY_TIMELINES
from .exceptions import ContractError
from .hashing import canonical_json, sha256_bytes
from .loader import load_bundle
from .replay import _output_location


def run_matrix(manifest_path, *, manifest_sha256, out, workers=4, packets=False):
    data = load_bundle(manifest_path, manifest_sha256=manifest_sha256)
    output = _output_location(out, data.root)
    output.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[2]
    common = ["--manifest", str(Path(manifest_path).resolve()), "--manifest-sha256", manifest_sha256]
    records = []

    def command(module, arguments, name, seed):
        argv = [sys.executable, "-B", "-m", "evals.intelligence_v1."+module, *common, *arguments]
        result = subprocess.run(argv, cwd=repo, env={**os.environ, "PYTHONHASHSEED": seed},
                                capture_output=True, text=True, timeout=120)
        log = output/"logs"/(name+".txt")
        log.parent.mkdir(exist_ok=True)
        log.write_text(result.stdout+result.stderr, encoding="utf-8")
        record = {"argv": argv, "cwd": str(repo), "python_hash_seed": seed,
                  "exit_code": result.returncode, "log": str(log), "log_sha256": sha256_bytes(log.read_bytes())}
        if result.returncode:
            raise ContractError("REPRODUCTION_COMMAND_FAILED", field=str(log))
        return record

    def job(config):
        timeline, algorithm, budget, half = config
        job_records, fingerprints = [], []
        for seed in ("1", "719"):
            name = f"{timeline}-{algorithm}-b{budget}-h{half}-seed{seed}"
            run = output/"primary"/name
            job_records.append(command("replay", ["--timeline", timeline, "--split", "dev", "--algo", algorithm,
                "--budget-seconds", str(budget), "--half-life-days", str(half), "--out", str(run)], name, seed))
            artifact_paths = [run/n for n in ("predictions.jsonl", "input_snapshot.json", "baseline_config.json")]
            for label in ("gold", "synthetic-fixture"):
                evaluation = output/"primary"/(name+"-"+label+"-evaluation")
                job_records.append(command("evaluate", ["--run", str(run), "--label-source", label,
                    "--out", str(evaluation)], name+"-"+label, seed))
                artifact_paths += [evaluation/n for n in ("metrics.json", "diagnostics.jsonl")]
            fingerprints.append({str(p.relative_to(output)): sha256_bytes(p.read_bytes()) for p in artifact_paths})
        if list(fingerprints[0].values()) != list(fingerprints[1].values()):
            raise ContractError("NONDETERMINISTIC_ARTIFACTS")
        return job_records, {k: v for group in fingerprints for k, v in group.items()}

    configs = [(t, a, b, 7) for t in PRIMARY_TIMELINES
               for a in ("b0", "b1", "b2-predicted", "b2-oracle", "b3", "b4") for b in (180, 420, 900)]
    configs += [(t, "b3", 420, h) for t in PRIMARY_TIMELINES for h in (3, 14)]
    hashes = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, (job_records, job_hashes) in enumerate(pool.map(job, configs), 1):
            records.extend(job_records)
            hashes.update(job_hashes)
            if index % 10 == 0:
                print(canonical_json({"completed_configurations": index, "total_configurations": len(configs)}), flush=True)
    records.append(command("report", ["--runs", str(output/"primary"), "--out", str(output/"summary")], "summary", "1"))
    summary = json.loads((output/"summary/comparison.json").read_bytes())
    verify_matrix(summary, data, output/"primary")
    if packets:
        for step in sorted((s for s in data.steps if s.timeline_id in PRIMARY_TIMELINES),
                           key=lambda s: (s.timeline_id, s.as_of)):
            payloads = []
            for reviewer in ("a", "b"):
                name = f"packet-{step.timeline_id}-{step.step_id}-{reviewer}"
                target = output/"administrator-packets"/name
                records.append(command("annotations", ["packet", "--timeline", step.timeline_id,
                    "--step", step.step_id, "--out", str(target)], name, "1"))
                payloads.append((target/"packet.json").read_bytes())
            if payloads[0] != payloads[1]:
                raise ContractError("NONDETERMINISTIC_PACKETS")
        records.append(command("annotations", ["audit", "--out", str(output/"annotation-audit")], "annotation-audit", "1"))
        records.append(command("annotations", ["agreement", "--out", str(output/"agreement")], "agreement", "1"))
    result = {"dataset_manifest_sha256": manifest_sha256, "prediction_runs": 200, "evaluation_runs": 400,
              "command_count": len(records), "deterministic_artifact_count": len(hashes),
              "all_deterministic_equal": True, "commands": records, "artifact_sha256": hashes,
              "scope": "synthetic_technical_reproduction_not_human_annotation"}
    (output/"reproduction.json").write_bytes((canonical_json(result)+"\n").encode())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=[1, 2, 4], default=4)
    parser.add_argument("--packets", action="store_true")
    args = parser.parse_args(argv)
    result = run_matrix(args.manifest, manifest_sha256=args.manifest_sha256, out=args.out,
                        workers=args.workers, packets=args.packets)
    print(canonical_json({k: result[k] for k in ("prediction_runs", "evaluation_runs", "command_count")}))


if __name__ == "__main__":
    main()
