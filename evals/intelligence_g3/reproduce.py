"""Pinned full G3 prediction matrix. Reference labels are never read here."""

import argparse
import sys
import time
from itertools import product
from pathlib import Path
from unittest.mock import patch

from evals.intelligence_g2.contracts import data, digest, json_bytes, read_json
from evals.intelligence_g2.replay import safe_path

from .artifacts import (
    OUTPUT_BASE,
    command,
    fresh,
    load_campaign,
    pinned,
    relative,
    release,
    seal,
    write,
)
from .contracts import PACKAGE, fail
from .experiments import predict
from .fact_signature import policy, policy_sha256
from .history_contracts import HistoryInput, parse_history
from .pr5_contracts import VARIANTS, Job, configuration


def jobs(campaign):
    return tuple(Job(case_id=c.case_id, budget=b, variant=v)
                 for c, b, v in product(campaign.cases, (180, 420, 900), VARIANTS))


def worker_argv(manifest, pin, out, seed):
    return [sys.executable, "-B", "-m", "evals.intelligence_g3.reproduce", "--manifest", str(manifest),
            "--manifest-sha256", pin, "--out", str(out), "--worker-seed", str(seed)]


def deny_network(*args, **kwargs):
    fail("G3_OFFLINE_VIOLATION", "network")


def worker(manifest, pin, out, seed):
    out = safe_path(out, areas=(OUTPUT_BASE,), code="G3_PATH_INVALID")
    campaign = load_campaign(manifest, pin)
    sources = {c.case_id: parse_history(HistoryInput, read_json(pinned(
        PACKAGE / relative(c.input.path), c.input.sha256, PACKAGE / "fixtures/pr5")))
        for c in campaign.cases}
    fingerprints, timings = {}, []
    file = out / f"predictions-{seed}.jsonl"
    with file.open("xb") as stream, patch("socket.socket", deny_network), patch(
            "socket.create_connection", deny_network):
        for index, job in enumerate(jobs(campaign)):
            start = time.perf_counter()
            result = predict(sources[job.case_id], job)
            timings.append(dict(job_id=job.job_id, elapsed_seconds=time.perf_counter() - start))
            fingerprints[job.job_id] = digest(result)
            stream.write(json_bytes(result))
            if index % 100 == 0:
                print(f"seed={seed} jobs={index + 1}", flush=True)
    write(out, f"semantic-{seed}.json", fingerprints)
    write(out, f"timings-{seed}.json", timings)
    print(f"seed={seed} completed={len(fingerprints)} offline_network_guard=enabled", flush=True)


def reproduce(manifest, pin, out):
    manifest = Path(manifest).absolute()
    campaign = load_campaign(manifest, pin)
    source = release()
    output = fresh(out)
    write(output, "campaign.json", data(campaign))
    write(output, "configuration.json", configuration())
    write(output, "fact_signature_policy.json", policy())
    write(output, "source_release.json", source)
    for seed in (1, 719):
        command(output, f"worker-{seed}", worker_argv(manifest, pin, output, seed), seed=seed)
    a, b = (read_json((output / f"semantic-{s}.json").read_bytes()) for s in (1, 719))
    if a != b or len(a) != len(jobs(campaign)):
        fail("G3_NONDETERMINISTIC", "full_matrix")
    if release() != source:
        fail("G3_SOURCE_MISMATCH", "prediction_after")
    write(output, "summary.json", dict(jobs_per_seed=len(a), actual_prediction_runs=2 * len(a),
        all_semantics_equal=True, config_sha256=campaign.config_sha256,
        model_calls=0, external_requests=0, token_count=None, provider_cost=None,
        cost_undefined_reason="no_model_or_paid_provider_invocation"))
    pin_out = seal(output, "prediction", campaign_path=str(manifest), campaign_sha256=pin,
                   source_sha256=digest(source), fact_signature_policy_sha256=policy_sha256())
    print(json_bytes(dict(out=str(output), manifest_sha256=pin_out)).decode(), end="")
    return pin_out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--worker-seed", type=int, choices=(1, 719))
    args = parser.parse_args(argv)
    if args.worker_seed:
        worker(Path(args.manifest).absolute(), args.manifest_sha256,
               Path(args.out).absolute(), args.worker_seed)
    else:
        reproduce(args.manifest, args.manifest_sha256, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
