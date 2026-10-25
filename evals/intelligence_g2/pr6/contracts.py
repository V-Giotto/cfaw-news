"""Independent PR6 evidence contracts; native PR1-PR5 contracts stay frozen."""

import argparse
from typing import Annotated, Literal

from pydantic import Field, model_validator

from evals.intelligence_g2.contracts import G2Error
from evals.intelligence_g2.pr2.contracts import GroupingResult
from evals.intelligence_g2.pr3.contracts import EvidenceResult
from evals.intelligence_g2.pr4.contracts import GenerationResult
from evals.intelligence_g2.pr5.contracts import Code, ExpressionResult
from evals.intelligence_v1.contracts import NonEmpty, Sha256, StrictModel
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes

REVISION = "g2-pr6-1"
Count = Annotated[int, Field(ge=0)]
Status = Literal["PASS", "FAIL", "BLOCKED"]
Fault = Literal[
    "none",
    "future",
    "foreign_ref",
    "independence",
    "quantity",
    "scope_difference",
    "unresolved",
    "repurposed",
    "different_event",
    "body_loss",
    "empty_coverage",
    "tool_call",
    "late429",
    "timely429",
]


def data(value):
    if isinstance(value, StrictModel):
        return value.model_dump(mode="json", warnings="none")
    if isinstance(value, dict):
        return {k: data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [data(v) for v in value]
    return value


def digest(value):
    return sha256_bytes(canonical_json(data(value)).encode("utf-8"))


def json_bytes(value):
    return (canonical_json(data(value)) + "\n").encode("utf-8")


def cli_entry(callback):
    import json

    from evals.intelligence_v1.exceptions import ContractError

    try:
        result = callback()
        return 0 if result is None else result
    except ContractError as error:
        print(
            json.dumps(
                dict(
                    ok=False,
                    code=error.code,
                    stage=getattr(error, "stage", "pr6"),
                    field=error.field,
                )
            )
        )
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print(
            json.dumps(
                dict(ok=False, code="G2_PR6_INPUT_INVALID", stage="pr6", field="input_or_artifact")
            )
        )
        return 1


def fail(code, field, stage="pr6"):
    raise G2Error(code, stage=stage, field=field)


def parse(model, value):
    from pydantic import ValidationError

    try:
        return model.model_validate_json(json_bytes(value))
    except ValidationError:
        fail("G2_PR6_SCHEMA_INVALID", model.__name__)


class Record(StrictModel):
    schema_revision: Literal["g2-pr6-1"] = REVISION


class FilePin(StrictModel):
    path: NonEmpty
    sha256: Sha256


class CampaignSpec(Record):
    campaign_revision: Literal["g2-pr6-campaign-v1"] = "g2-pr6-campaign-v1"
    scope: Literal["full", "ci"] = "full"
    g1_manifest: FilePin
    prediction_manifest: FilePin
    mock_manifest: FilePin
    configs: dict[str, FilePin]
    strategies: tuple[Literal["r0", "r1"], ...] = ("r0", "r1")
    profiles: tuple[Literal["low", "standard", "high"], ...] = ("low", "standard", "high")
    modes: tuple[Literal["rule", "mock"], ...] = ("rule", "mock")
    seeds: tuple[Literal[1, 719], ...] = (1, 719)
    orders: tuple[Literal["canonical", "reverse"], ...] = ("canonical", "reverse")
    supplemental_r2: bool = True
    prefix_checks: Literal[True] = True
    workers: Literal[1] = 1

    @model_validator(mode="after")
    def fixed_matrix(self):
        if set(self.configs) != {f"pr{i}" for i in range(1, 6)}:
            raise ValueError("all parent configs required")
        axes = (self.strategies, self.profiles, self.modes, self.seeds, self.orders)
        expected = (
            ("r0", "r1"),
            ("low", "standard", "high"),
            ("rule", "mock"),
            (1, 719),
            ("canonical", "reverse"),
        )
        if self.scope == "full" and (axes != expected or not self.supplemental_r2):
            raise ValueError("incomplete full matrix")
        if any(len(a) != len(set(a)) or not a for a in axes):
            raise ValueError("duplicate/empty matrix axis")
        return self


class SourceRelease(Record):
    source_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    git_tree: NonEmpty
    files: dict[str, Sha256]
    runtime_files: dict[str, Sha256]
    schema_files: dict[str, Sha256]
    dependency_locks: dict[str, Sha256]
    reports: dict[str, Sha256]
    dependency_versions: dict[str, NonEmpty]
    required_files_match_commit: Literal[True] = True


class PredictionCase(StrictModel):
    case_id: NonEmpty
    error_mode: NonEmpty
    cohort: Literal["synthetic"]
    path: NonEmpty
    sha256: Sha256
    through_step: NonEmpty
    fault: Fault


class DevelopmentReference(StrictModel):
    case_id: NonEmpty
    error_mode: Annotated[str, Field(pattern=r"^E(?:0[1-9]|1[0-2])$")]
    side: Literal["positive", "negative"]
    expected_code: (
        Literal[
            "FUTURE_VERSION",
            "ORIGIN_MISMATCH",
            "G2_PR6_SENSITIVE_EXPORT",
            "CITATION_NOT_ALLOWED",
            "SCHEMA_INVALID",
            "NUMERIC_SCOPE_MISMATCH",
            "TOOL_CALL_FORBIDDEN",
            "TIMEOUT",
            "RATE_LIMIT",
        ]
        | None
    )
    checks: tuple[
        Literal[
            "grounded",
            "no_independent_upgrade",
            "scope_difference",
            "unresolved",
            "withdrawal",
            "correction",
            "conflict",
            "repurposed",
            "stable_identity",
            "different_event",
            "duplicate",
            "body_loss",
            "empty_coverage",
            "nonempty",
            "secondary",
        ],
        ...,
    ]

    @model_validator(mode="after")
    def explicit_checks(self):
        if not self.checks or len(self.checks) != len(set(self.checks)):
            raise ValueError("explicit unique checks required")
        return self


class PredictionJob(Record):
    job_id: NonEmpty
    case_id: NonEmpty
    cohort: Literal["g1_primary", "g1_auxiliary", "synthetic"]
    timeline_id: NonEmpty
    through_step: NonEmpty
    strategy: Literal["r0", "r1", "r2"]
    profile: Literal["low", "standard", "high"]
    mode: Literal["rule", "mock"]
    seed: Literal[1, 719]
    order: Literal["canonical", "reverse"]
    prefix: bool = False
    raw_input: FilePin | None = None
    fault: Fault = "none"


class CaseExecution(Record):
    job: PredictionJob
    execution_kind: Literal["api_in_batch_worker"] = "api_in_batch_worker"
    api: Literal["pr6.predict.run_job"] = "pr6.predict.run_job"
    returned: bool
    diagnostic: dict[str, str] | None = None
    result_path: NonEmpty | None = None
    semantic_sha256: Sha256 | None = None
    trace_path: NonEmpty | None = None
    trace_sha256: Sha256 | None = None
    pool_sha256: Sha256 | None = None
    api_exit_code: None = None

    @model_validator(mode="after")
    def consistent_outcome(self):
        artifacts = (
            self.result_path,
            self.semantic_sha256,
            self.trace_path,
            self.trace_sha256,
            self.pool_sha256,
        )
        if self.returned:
            if self.diagnostic is not None or any(a is None for a in artifacts):
                raise ValueError("returned execution needs artifacts and no rejection")
        elif (
            any(a is not None for a in artifacts)
            or self.diagnostic is None
            or set(self.diagnostic) != {"code", "stage", "field"}
        ):
            raise ValueError("rejection needs safe diagnostic only")
        return self


class CallObservation(StrictModel):
    """Native attempt telemetry with clock fields excluded, never fabricated as zero."""

    request_sha256: Sha256 | None
    base_item_id: NonEmpty
    status: Literal["accepted", "fallback", "skipped"]
    code: Code | None
    mock_calls: Annotated[int, Field(ge=0, le=1)]
    external_requests: Literal[0]
    model_calls: Literal[0]
    billed_cost: Literal[0]
    input_tokens: None
    request_bytes: Count
    response_bytes: Count
    response_sha256: Sha256 | None
    usage: dict[str, Count] | None
    usage_origin: Literal["mock_fixture", "not_called", "unknown"]
    usage_complete: bool


class StepRecord(Record):
    grouping: GroupingResult
    evidence: EvidenceResult
    rule: GenerationResult
    expression: ExpressionResult
    pool_sha256: Sha256
    call_observations: tuple[CallObservation, ...]
    old_claims: tuple[dict, ...]
    reading_budget_seconds: Literal[180, 420, 900]
    estimated_read_seconds: Count


class MetricValue(StrictModel):
    numerator: Count
    denominator: Count
    value: float | None
    status: Literal["measured", "unavailable", "not_evaluated"]
    reason: NonEmpty | None

    @model_validator(mode="after")
    def honest(self):
        if self.status == "measured":
            if (
                not self.denominator
                or self.value != self.numerator / self.denominator
                or self.reason is not None
            ):
                raise ValueError("invalid metric")
        elif self.value is not None or self.reason is None:
            raise ValueError("unavailable metrics need null and reason")
        return self


class CommandRecord(StrictModel):
    name: NonEmpty
    argv: tuple[str, ...]
    cwd: NonEmpty
    started_at: NonEmpty
    finished_at: NonEmpty
    exit_code: int
    log: FilePin
    artifacts: tuple[FilePin, ...] = ()


class ChecksBundle(Record):
    source_release: SourceRelease
    source_release_sha256: Sha256
    required_tests: FilePin
    commands: tuple[CommandRecord, ...]
    inventory: FilePin
    full_junit: FilePin
    g2_junit: FilePin
    evals_junit: FilePin
    g1_compatibility: dict
    source_unchanged: Literal[True]


class Gate(StrictModel):
    status: Status
    evidence: tuple[NonEmpty, ...]
    reason: NonEmpty


class G2AcceptanceResult(Record):
    profile: Literal["g2_development"] = "g2_development"
    source_commit: NonEmpty
    gates: dict[str, Gate]
    overall_status: Literal["PASS", "NOT_MET"]
    g3_offline_eligible: bool
    administrator_acceptance: Literal["pending"] = "pending"
    g3_planning_authorized: Literal[False] = False
    independent_validation: Literal[False] = False
    human_independent_review: Literal["not_evaluated"] = "not_evaluated"
    double_annotation: Literal["not_evaluated"] = "not_evaluated"
    user_research: Literal["not_evaluated"] = "not_evaluated"
    real_world_generalization: Literal["not_evaluated"] = "not_evaluated"
    optional_real_qualitative: Literal["deferred"] = "deferred"

    @model_validator(mode="after")
    def complete(self):
        passed = set(self.gates) == {f"H{i:02}" for i in range(1, 11)} and all(
            g.status == "PASS" and g.evidence for g in self.gates.values()
        )
        if (self.overall_status == "PASS") != passed or self.g3_offline_eligible != passed:
            raise ValueError("acceptance cannot override gates")
        return self


class G3InputView(Record):
    event_key: NonEmpty
    event_revision: Sha256
    as_of: NonEmpty
    bundle: dict
    rule_item: dict
    presentation: dict
    snapshot: dict
    source_coverage: tuple[dict, ...]
    lineage_ids: tuple[str, ...]
    trace_pointer: NonEmpty
    inference_is_source_fact: Literal[False] = False
    final_personalized_rank: None = None


MODELS = {
    c.__name__: c
    for c in (
        DevelopmentReference,
        CampaignSpec,
        SourceRelease,
        PredictionJob,
        CaseExecution,
        StepRecord,
        MetricValue,
        ChecksBundle,
        G2AcceptanceResult,
        G3InputView,
    )
}


def schema_payloads():
    return {
        name + ".schema.json": json_bytes(model.model_json_schema())
        for name, model in MODELS.items()
    }


def check_schemas():
    from evals.intelligence_g2.contracts import PACKAGE

    return all(
        (PACKAGE / "schema/v6" / n).read_bytes() == raw for n, raw in schema_payloads().items()
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-schemas", action="store_true", required=True)
    parser.parse_args(argv)
    if not check_schemas():
        fail("SCHEMA_INVALID", "schema/v6")
    print(REVISION)


if __name__ == "__main__":
    raise SystemExit(cli_entry(main))
