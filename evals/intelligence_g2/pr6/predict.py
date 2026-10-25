"""Prediction-only worker. No reference, evaluation, Oracle or application imports."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from evals.intelligence_g2.contracts import G2ReplayInput, read_json
from evals.intelligence_g2.pipeline import run_g2_offline
from evals.intelligence_g2.pr2.contracts import PR2Config
from evals.intelligence_g2.pr2.replay import load_sequence
from evals.intelligence_g2.pr2.replay import run_sequence as group_sequence
from evals.intelligence_g2.pr3.contracts import EvidenceInput, PR3Config
from evals.intelligence_g2.pr3.pipeline import run_evidence_step
from evals.intelligence_g2.pr4.contracts import PR4Config
from evals.intelligence_g2.pr4.pipeline import generate_items
from evals.intelligence_g2.pr4.project import project_step
from evals.intelligence_g2.pr4.sensitive import sensitive_content
from evals.intelligence_g2.pr5.adapter import MockCompletionAdapter, TransportReply
from evals.intelligence_g2.pr5.assets import load_assets
from evals.intelligence_g2.pr5.contracts import ExpressionInput, PR5Config
from evals.intelligence_g2.pr5.pipeline import execute_step
from evals.intelligence_g2.pr5.styles import closed_response
from evals.intelligence_g2.replay import load_config
from evals.intelligence_g2.validate_output import preflight_time
from evals.intelligence_v1.exceptions import ContractError

from .contracts import (
    CallObservation,
    CaseExecution,
    PredictionJob,
    SourceRelease,
    StepRecord,
    cli_entry,
    data,
    digest,
    fail,
    json_bytes,
    parse,
)
from .manifest import PACKAGE, ROOT, pinned, repo_file, seal, sha256_bytes, verify_runtime


class FrozenTransport:
    """Closed fault vocabulary; evidence cannot supply Python, paths, URLs or actions."""

    def __init__(self, assets, fault):
        self.assets, self.fault = assets, fault

    async def exchange(self, raw, *, request_sha256):
        from evals.intelligence_g2.pr5.contracts import ExpressionRequest

        wire = read_json(raw)
        request = parse(
            ExpressionRequest,
            read_json(wire["messages"][1]["content"].encode("utf-8"))["untrusted_evidence"],
        )
        if request.request_sha256 != request_sha256:
            fail("STALE_RESULT", "request_sha256")
        if self.fault in {"late429", "timely429"}:
            if self.fault == "late429":
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    await asyncio.sleep(0.02)
            return TransportReply(b'{"usage":{"total_tokens":77}}', 429)
        draft = data(closed_response(request, self.assets))
        if self.fault == "foreign_ref":
            draft["refs"][0]["doc_version_id"] = "other-event:1"
        elif self.fault == "independence":
            draft["verification_state"] = "independently_supported"
        elif self.fault == "quantity":
            draft["body"] = draft["body"].replace("40%", "400%")
        message = {"content": json_bytes(draft).decode()}
        if self.fault == "tool_call":
            message["tool_calls"] = [{"name": "read_file", "arguments": ".env"}]
        return TransportReply(
            json_bytes(dict(choices=[dict(finish_reason="stop", message=message)], usage=None))
        )


def inputs_for(job, campaign):
    if job.raw_input is None:
        values, _ = load_sequence(
            ROOT / campaign.g1_manifest.path,
            pin=campaign.g1_manifest.sha256,
            timeline_id=job.timeline_id,
            through_step=job.through_step,
        )
    else:
        if not (ROOT / job.raw_input.path).is_relative_to(PACKAGE / "fixtures/pr6/v1/prediction"):
            fail("PREDICTION_PATH_INVALID", "raw_input")
        raw = repo_file(job.raw_input)
        rows = [read_json(line) for line in raw.splitlines()]
        names = [r["context"]["step_id"] for r in rows]
        if job.through_step not in names:
            fail("REFERENCE_NOT_FOUND", "through_step")
        values = []
        for row in rows[: names.index(job.through_step) + 1]:
            preflight_time(row)
            value = parse(G2ReplayInput, row)
            if value.context.timeline_id != job.timeline_id:
                fail("G2_CONTEXT_MISMATCH", "timeline_id")
            values.append(value)
    if job.order == "reverse":
        values = [
            v.model_copy(
                update={
                    "visible_documents": tuple(reversed(v.visible_documents)),
                    "sources": tuple(reversed(v.sources)),
                }
            )
            for v in values
        ]
    return tuple(values)


async def run_job(job, campaign):
    """Pure stage APIs plus explicitly pinned fixture reads, always restart the prefix."""
    replay = inputs_for(job, campaign)
    c1, _ = load_config(ROOT / campaign.configs["pr1"].path, campaign.configs["pr1"].sha256)
    c2 = parse(PR2Config, read_json(repo_file(campaign.configs["pr2"])))
    c3 = parse(PR3Config, read_json(repo_file(campaign.configs["pr3"])))
    c4 = parse(
        PR4Config, {**read_json(repo_file(campaign.configs["pr4"])), "budget_profile": job.profile}
    )
    c5 = parse(PR5Config, read_json(repo_file(campaign.configs["pr5"])))
    # The source-frozen fault program is independent of request hashes and of research labels.
    header = read_json(repo_file(campaign.mock_manifest))
    if header["revision"] != "g2-pr6-assets-v1":
        fail("G2_PR6_ROLE_INVALID", "mock_manifest")
    if len(header["files"]) != 1:
        fail("G2_PR6_ROLE_INVALID", "mock_files")
    entry = header["files"][0]
    from .manifest import relative

    program = read_json(
        pinned(
            ROOT / relative(campaign.mock_manifest.path).parent / relative(entry["path"]),
            entry["sha256"],
        )
    )
    if entry["role"] != "mock_response" or program["revision"] != "g2-pr6-faults-v1":
        fail("G2_PR6_ROLE_INVALID", "mock_response")
    if program != dict(
        revision="g2-pr6-faults-v1",
        actions=[
            "none",
            "foreign_ref",
            "independence",
            "quantity",
            "tool_call",
            "late429",
            "timely429",
        ],
    ):
        fail("G2_PR6_ROLE_INVALID", "mock_program")
    assets = load_assets(c5)
    generator = MockCompletionAdapter(assets, FrozenTransport(assets, job.fault))
    group_inputs, groups = group_sequence(replay, strategy=job.strategy, config=c2)
    prior_e, prior_r, prior_x = None, None, None
    records, traces = [], []
    for grouping_input, grouped in zip(group_inputs, groups, strict=True):
        # All stages share the bridge's canonical, revalidated pool.
        from evals.intelligence_g2.pr2.validate_output import checked_grouping_input

        grouping_input, _ = checked_grouping_input(grouping_input, c2)
        value = grouping_input.replay_input
        e_input = EvidenceInput(
            grouping_input=grouping_input,
            grouping_result=grouped,
            grouping_config=c2,
            config_sha256=digest(c3),
            previous_state=prior_e,
            previous_state_sha256=digest(prior_e) if prior_e else None,
        )
        evidence = run_evidence_step(evidence_input=e_input, config=c3)
        r_input = project_step(
            e_input, evidence, previous_state=prior_r, config=c4, evidence_config=c3
        )
        rule = generate_items(generation_input=r_input, config=c4)
        x_input = ExpressionInput(
            generation_input=r_input,
            rule_result=rule,
            rule_config=c4,
            mode=job.mode,
            config_sha256=digest(c5),
            previous_state=prior_x,
            previous_state_sha256=digest(prior_x) if prior_x else None,
        )
        expression = await execute_step(
            expression_input=x_input, generator=generator, config=c5, assets=assets
        )
        old = run_g2_offline(replay_input=value, config=c1)
        owner = {m: e.event_key for e in grouped.events for m in e.member_doc_version_ids}
        old_claims = tuple(
            dict(claim=data(c), predicted_event_key=owner[c.evidence_refs[0].doc_version_id])
            for bundle in old.bundles
            for c in bundle.claim_candidates
        )
        pool = digest(
            dict(
                context=data(value.context),
                documents=[data(d) for d in value.visible_documents],
                sources=[data(s) for s in value.sources],
                manifest=value.input_manifest_sha256,
            )
        )
        record = StepRecord(
            grouping=grouped,
            evidence=evidence,
            rule=rule,
            expression=expression.result,
            call_observations=tuple(
                parse(CallObservation, t.model_dump(mode="json", exclude={"elapsed_ms"}))
                for t in expression.traces
            ),
            old_claims=old_claims,
            pool_sha256=pool,
            reading_budget_seconds={"low": 180, "standard": 420, "high": 900}[job.profile],
            estimated_read_seconds=sum(i.estimated_read_seconds for i in rule.items),
        )
        if sensitive_content(record):
            fail("G2_PR6_SENSITIVE_EXPORT", "semantic_artifact")
        records.append(record)
        traces.append(
            dict(cursor=data(grouped.cursor), attempts=[data(t) for t in expression.traces])
        )
        prior_e, prior_r, prior_x = (
            evidence.next_state,
            rule.next_state,
            expression.result.next_state,
        )
    return tuple(records), tuple(traces)


def audit_prediction(output):
    """Capability audit starts after the trusted event loop's local self-pipe setup."""
    forbidden = {
        "reference",
        "labels",
        "annotations",
        "adjudications",
        "review",
        "reviews",
        "dev-diaries",
        ".local",
        "reports",
        "gold",
        "draft",
        "revisions",
    }
    original_stat, original_lstat = Path.stat, Path.lstat
    original_os_stat, original_os_lstat = os.stat, os.lstat

    def check(value):
        path = Path(value).absolute()
        if any(
            x.casefold() in forbidden
            or x.casefold().startswith(".env")
            or x.casefold().endswith((".db", ".sqlite", ".db-wal", ".db-shm"))
            for x in path.parts
        ):
            fail("G2_PR6_CAPABILITY_DENIED", "private_or_reference")
        if path.is_relative_to(ROOT / "evals/intelligence_v1") and path.name in {
            "events.jsonl",
            "claims.jsonl",
            "event_relations.jsonl",
            "gold.jsonl",
        }:
            fail("G2_PR6_CAPABILITY_DENIED", "g1_reference")
        bases = (ROOT, Path(sys.prefix), Path(sys.base_prefix))
        if not any(path.is_relative_to(base) or path in base.parents for base in bases):
            fail("G2_PR6_CAPABILITY_DENIED", "outside_metadata")
        return path

    def stat(self, *args, **kwargs):
        check(self)
        return original_stat(self, *args, **kwargs)

    def lstat(self, *args, **kwargs):
        check(self)
        return original_lstat(self, *args, **kwargs)

    def os_stat(path, *args, **kwargs):
        if isinstance(path, (str, bytes, os.PathLike)):
            check(os.fsdecode(path))
        return original_os_stat(path, *args, **kwargs)

    def os_lstat(path, *args, **kwargs):
        check(os.fsdecode(path))
        return original_os_lstat(path, *args, **kwargs)

    Path.stat, Path.lstat = stat, lstat
    os.stat, os.lstat = os_stat, os_lstat

    def audit(event, args):
        if (
            event == "import"
            and isinstance(args[0], str)
            and args[0].startswith(("evals.intelligence_", "cfaw_news."))
            and (
                args[0].endswith((".evaluate", ".reference_loader", ".oracle", ".validate"))
                and args[0] != "evals.intelligence_g2.validate_output"
                or args[0].startswith(
                    ("cfaw_news.providers", "cfaw_news.database", "cfaw_news.config")
                )
            )
        ):
            fail("G2_PR6_CAPABILITY_DENIED", "forbidden_import")
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.system"}:
            fail("G2_PR6_CAPABILITY_DENIED", "network_or_tool")
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = check(args[0])
            if args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                if not path.is_relative_to(output):
                    fail("G2_PR6_CAPABILITY_DENIED", "outside_write")
            else:
                runtime = any(path.is_relative_to(Path(p)) for p in (sys.prefix, sys.base_prefix))
                allowed = (
                    path.is_relative_to(ROOT / "evals")
                    or path.is_relative_to(output)
                    or path == ROOT / "backend/cfaw_news/retrieval.py"
                    or path in {ROOT / "requirements.lock", ROOT / "frontend/package-lock.json"}
                )
                if not (runtime or allowed):
                    fail("G2_PR6_CAPABILITY_DENIED", "outside_read")
        if event == "os.rename" and not all(check(p).is_relative_to(output) for p in args[:2]):
            fail("G2_PR6_CAPABILITY_DENIED", "outside_rename")

    sys.addaudithook(audit)


def execute_batch(jobs, campaign, output):
    loop = asyncio.new_event_loop()
    audit_prediction(output)
    results = []
    try:
        for job in jobs:
            path = output / "predictions" / job.job_id
            try:
                records, traces = loop.run_until_complete(run_job(job, campaign))
                raw = b"".join(json_bytes(r) for r in records)
                trace = json_bytes(traces)
                seal(path, {"steps.jsonl": raw, "trace.json": trace})
                result = CaseExecution(
                    job=job,
                    returned=True,
                    result_path=path.relative_to(output).as_posix() + "/steps.jsonl",
                    semantic_sha256=sha256_bytes(raw),
                    trace_path=path.relative_to(output).as_posix() + "/trace.json",
                    trace_sha256=sha256_bytes(trace),
                    pool_sha256=digest([r.pool_sha256 for r in records]),
                )
            except ContractError as error:
                if path.exists():
                    raise
                result = CaseExecution(
                    job=job,
                    returned=False,
                    diagnostic=dict(
                        code=error.code, stage=getattr(error, "stage", "input"), field=error.field
                    ),
                )
            results.append(result)
            print(
                json.dumps(
                    dict(completed=len(results), job_id=job.job_id, returned=result.returned)
                ),
                flush=True,
            )
    finally:
        loop.close()
    if any(
        n.startswith("cfaw_news.")
        and n != "cfaw_news.retrieval"
        or n.startswith("evals.intelligence_")
        and n.endswith((".evaluate", ".reference_loader", ".oracle"))
        for n in sys.modules
    ):
        fail("G2_PR6_CAPABILITY_DENIED", "forbidden_import")
    seal(
        output / ("batch-results-" + str(jobs[0].seed)),
        {"executions.jsonl": b"".join(json_bytes(r) for r in results)},
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    for name in (
        "batch",
        "batch-sha256",
        "campaign",
        "campaign-sha256",
        "release",
        "release-sha256",
        "out",
    ):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    from .manifest import OUTPUT_BASE, load_campaign, safe_path

    output = safe_path(args.out, areas=(OUTPUT_BASE,))
    raw = pinned(args.batch, args.batch_sha256, areas=(output,))
    jobs = tuple(parse(PredictionJob, j) for j in read_json(raw))
    if not jobs or {j.seed for j in jobs} != {int(os.environ.get("PYTHONHASHSEED", "-1"))}:
        fail("G2_PR6_MATRIX_INVALID", "batch_seed")
    campaign = load_campaign(args.campaign, args.campaign_sha256)
    release = parse(
        SourceRelease, read_json(pinned(args.release, args.release_sha256, areas=(output,)))
    )
    verify_runtime(release)
    execute_batch(jobs, campaign, output)


if __name__ == "__main__":
    raise SystemExit(cli_entry(main))
