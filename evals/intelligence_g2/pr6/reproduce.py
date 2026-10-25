"""Committed-source offline campaign. This controller never reads references."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from itertools import product

from evals.intelligence_g2.contracts import read_json

from .contracts import (
    CaseExecution,
    FilePin,
    PredictionCase,
    PredictionJob,
    cli_entry,
    data,
    digest,
    fail,
    json_bytes,
    parse,
)
from .manifest import (
    ROOT,
    finish,
    load_campaign,
    output_location,
    pinned,
    prediction_catalog,
    repo_file,
    sha256_bytes,
    source_release,
)


def make_jobs(campaign):
    header = read_json(repo_file(campaign.g1_manifest))
    by_timeline = {}
    for entry in header["file_hashes"]:
        if entry["role"] != "steps":
            continue
        path = ROOT / campaign.g1_manifest.path
        rows = pinned(
            path.parent.parent / entry["path"], entry["sha256"], areas=(path.parent.parent,)
        )
        for raw in rows.splitlines():
            row = read_json(raw)
            by_timeline.setdefault(row["timeline_id"], []).append((row["as_of"], row["step_id"]))
    cases = []
    for timeline, steps in sorted(by_timeline.items()):
        steps.sort()
        cases.append(
            dict(
                case_id=timeline,
                cohort="g1_primary" if timeline.startswith("DEV-") else "g1_auxiliary",
                timeline_id=timeline,
                through_step=steps[-1][1],
                first_step=steps[0][1],
                raw_input=None,
                fault="none",
            )
        )
    root, catalog = prediction_catalog(campaign)
    for raw in catalog:
        c = parse(PredictionCase, raw)
        rows = [read_json(v) for v in pinned(root / c.path, c.sha256).splitlines()]
        cases.append(
            dict(
                case_id=c.case_id,
                cohort=c.cohort,
                timeline_id=c.case_id,
                through_step=c.through_step,
                first_step=rows[0]["context"]["step_id"],
                raw_input=FilePin(
                    path=(root / c.path).relative_to(ROOT).as_posix(), sha256=c.sha256
                ),
                fault=c.fault,
            )
        )
    if len({c["case_id"] for c in cases}) != len(cases):
        fail("DUPLICATE_ID", "cases")
    jobs = []
    for c in cases:
        axes = list(
            product(
                campaign.strategies,
                campaign.profiles,
                campaign.modes,
                campaign.seeds,
                campaign.orders,
            )
        )
        if campaign.supplemental_r2:
            axes += [
                ("r2", "standard", m, s, o)
                for m, s, o in product(campaign.modes, campaign.seeds, campaign.orders)
            ]
        for strategy, profile, mode, seed, order in axes:
            args = {k: v for k, v in c.items() if k != "first_step"}
            args.update(
                strategy=strategy, profile=profile, mode=mode, seed=seed, order=order, prefix=False
            )
            jobs.append(PredictionJob(job_id=digest(args), **args))
        if c["first_step"] != c["through_step"]:
            for mode in campaign.modes:
                args = {k: v for k, v in c.items() if k != "first_step"}
                args.update(
                    through_step=c["first_step"],
                    strategy="r1",
                    profile="standard",
                    mode=mode,
                    seed=1,
                    order="canonical",
                    prefix=True,
                )
                jobs.append(PredictionJob(job_id=digest(args), **args))
    return tuple(sorted(jobs, key=lambda j: (j.seed, j.job_id)))


def reproduce(campaign_path, *, campaign_sha256, source_commit, out):
    campaign = load_campaign(campaign_path, campaign_sha256)
    release = source_release(source_commit)
    output = output_location(out)
    output.mkdir(parents=True)
    release_raw = json_bytes(release)
    with (output / "source_release.json").open("xb") as stream:
        stream.write(release_raw)
    jobs = make_jobs(campaign)
    commands, executions = [], []
    for seed in campaign.seeds:
        batch = tuple(j for j in jobs if j.seed == seed)
        raw = json_bytes(batch)
        path = output / ("batch-" + str(seed) + ".json")
        path.write_bytes(raw)
        argv = [
            sys.executable,
            "-B",
            "-m",
            "evals.intelligence_g2.pr6.predict",
            "--batch",
            str(path),
            "--batch-sha256",
            sha256_bytes(raw),
            "--campaign",
            str(campaign_path),
            "--campaign-sha256",
            campaign_sha256,
            "--release",
            str(output / "source_release.json"),
            "--release-sha256",
            sha256_bytes(release_raw),
            "--out",
            str(output),
        ]
        start = datetime.now(timezone.utc).isoformat()
        log = output / ("worker-" + str(seed) + ".log")
        with log.open("xb") as stream:
            process = subprocess.run(
                argv,
                cwd=ROOT,
                env={**os.environ, "PYTHONHASHSEED": str(seed)},
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=7200,
            )
        commands.append(
            dict(
                argv=argv,
                cwd=str(ROOT),
                seed=seed,
                exit_code=process.returncode,
                started_at=start,
                finished_at=datetime.now(timezone.utc).isoformat(),
                log=log.name,
                log_sha256=sha256_bytes(log.read_bytes()),
            )
        )
        if process.returncode:
            fail("G2_PR6_WORKER_FAILED", "worker")
        values = (output / ("batch-results-" + str(seed)) / "executions.jsonl").read_bytes()
        executions.extend(parse(CaseExecution, read_json(v)) for v in values.splitlines())
    if [data(e.job) for e in executions] != [data(j) for j in jobs]:
        fail("G2_PR6_MATRIX_INVALID", "executions")
    if source_release(source_commit) != release:
        fail("RUNTIME_CODE_MISMATCH", "source_after")
    payloads = {
        "campaign_snapshot.json": json_bytes(campaign),
        "jobs.jsonl": b"".join(json_bytes(j) for j in jobs),
        "commands.jsonl": b"".join(json_bytes(c) for c in commands),
        "predictions_index.json": json_bytes(executions),
        "semantic_hashes.json": json_bytes({e.job.job_id: e.semantic_sha256 for e in executions}),
    }
    pin = finish(
        output,
        payloads,
        dict(
            schema_revision="g2-pr6-1",
            role="prediction_campaign",
            source_commit=source_commit,
            source_release_sha256=sha256_bytes(release_raw),
            campaign_file_sha256=campaign_sha256,
            campaign_sha256=digest(campaign),
            jobs=len(jobs),
            controlled_rejections=sum(not e.returned for e in executions),
            model_calls=0,
            external_requests=0,
        ),
    )
    return dict(completed=True, run_manifest_sha256=pin, jobs=len(jobs), acceptance="not_evaluated")


def main(argv=None):
    p = argparse.ArgumentParser()
    for name in ("source-commit", "campaign", "campaign-sha256", "out"):
        p.add_argument("--" + name, required=True)
    args = p.parse_args(argv)
    try:
        result = reproduce(
            args.campaign,
            campaign_sha256=args.campaign_sha256,
            source_commit=args.source_commit,
            out=args.out,
        )
    except Exception as error:
        from evals.intelligence_v1.exceptions import ContractError

        if not isinstance(error, ContractError):
            raise
        print(json.dumps(dict(ok=False, code=error.code, field=error.field)))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_entry(main))
