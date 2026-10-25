"""PR5 contracts are separate from immutable PR4 rule items."""

import argparse
from typing import Annotated, Literal, Protocol

from pydantic import Field, TypeAdapter

from evals.intelligence_g2.contracts import PACKAGE, ArtifactDigest, G2Error, json_bytes
from evals.intelligence_g2.contracts import data as data
from evals.intelligence_g2.contracts import digest as digest
from evals.intelligence_g2.pr2.contracts import ReplayCursor
from evals.intelligence_g2.pr3.contracts import Citation, ClaimCandidate
from evals.intelligence_g2.pr4.contracts import (
    GenerationInput,
    GenerationResult,
    IntelligenceItem,
    PR4Config,
    RiskNote,
)
from evals.intelligence_g2.pr4.contracts import parse as parse
from evals.intelligence_v1.contracts import Instant, NonEmpty, Sha256, StrictModel

REVISION = "g2-pr5-1"
Mode = Literal["ordinary", "secondary", "corrects", "retracts", "conflict"]
Count = Annotated[int, Field(ge=0)]
Finite = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Code = Literal[
    "CONFIGURATION", "NETWORK_DISABLED", "INVALID_ENVELOPE", "AUTHENTICATION", "QUOTA",
    "RATE_LIMIT", "PROVIDER_HTTP", "CONNECTION", "TIMEOUT", "OUTPUT_TOO_LARGE",
    "OUTPUT_TRUNCATED", "CONTENT_FILTERED", "INVALID_JSON", "SCHEMA_INVALID",
    "TOOL_CALL_FORBIDDEN", "CITATION_NOT_ALLOWED", "FUTURE_EVIDENCE", "SPAN_MISMATCH",
    "NUMERIC_SCOPE_MISMATCH", "ATTRIBUTION_ESCALATION", "EXPRESSION_NOT_CLOSED",
    "SENSITIVE_OUTPUT", "BUDGET_EXCEEDED", "CANCELLED", "STALE_RESULT",
    "G2_PR5_PARENT_RUN_MISMATCH", "G2_PR5_STATE_CHAIN_INVALID", "G2_PR5_OUTPUT_INVALID",
    "G2_PR5_REFERENCE_CONFLICT",
]


def fail(code, stage, field, record_id=""):
    raise G2Error(code, stage=stage, field=field, record_id=record_id)


class Record(StrictModel):
    schema_revision: Literal["g2-pr5-1"] = REVISION


class PR5Config(Record):
    config_revision: Literal["g2-pr5-config-v1"] = "g2-pr5-config-v1"
    prompt_revision: Literal["g2-expression-prompt-v1"] = "g2-expression-prompt-v1"
    style_revision: Literal["g2-expression-styles-v1"] = "g2-expression-styles-v1"
    guard_revision: Literal["g2-expression-guards-v1"] = "g2-expression-guards-v1"
    adapter_revision: Literal["g2-mock-completion-v1"] = "g2-mock-completion-v1"
    prompt_sha256: Literal["a21a3d970e150954071d372cc5dbca4d1ca8f1bea1b7124d06fd2f67eca1a5e4"] = "a21a3d970e150954071d372cc5dbca4d1ca8f1bea1b7124d06fd2f67eca1a5e4"
    style_sha256: Literal["c9fe9bd68cf4448d4f51b474fdfec782c2197d436ce883ea51461683d1754935"] = "c9fe9bd68cf4448d4f51b474fdfec782c2197d436ce883ea51461683d1754935"
    mock_manifest_sha256: Sha256
    max_request_bytes: Literal[32768] = 32768
    max_response_bytes: Literal[8192] = 8192
    max_claims: Literal[3] = 3
    max_refs: Literal[8] = 8
    max_documents: Literal[8] = 8
    max_output_tokens: Literal[1024] = 1024
    max_requests_per_item: Literal[1] = 1
    max_requests_per_step: Literal[16] = 16
    max_requests_per_run: Literal[128] = 128
    max_request_bytes_per_run: Literal[4194304] = 4194304
    max_response_bytes_per_run: Literal[1048576] = 1048576
    timeout_seconds: Literal[2] = 2
    concurrency: Literal[1] = 1
    repair_count: Literal[0] = 0
    retry_count: Literal[0] = 0


class CallBudget(StrictModel):
    max_request_bytes: Literal[32768] = 32768
    max_response_bytes: Literal[8192] = 8192
    max_output_tokens: Literal[1024] = 1024
    timeout_seconds: Literal[2] = 2


class ExpressionRequest(Record):
    request_sha256: Sha256
    base_item_id: NonEmpty
    event_key: NonEmpty
    event_revision: Sha256
    fact_revision: Sha256
    as_of: Instant
    mode: Mode
    claims: tuple[ClaimCandidate, ...]
    citations: tuple[Citation, ...]
    required_risks: tuple[RiskNote, ...]
    style_ids: tuple[NonEmpty, ...]
    max_visible_chars: Count
    prompt_sha256: Sha256
    style_sha256: Sha256


class ModelRef(StrictModel):
    ref_id: NonEmpty
    doc_version_id: NonEmpty
    paragraph_id: NonEmpty
    start: Count
    end: Count
    quote_sha256: Sha256
    available_at: Instant


class ClosedDraft(StrictModel):
    kind: Literal["closed"]
    style_id: NonEmpty
    claim_order: tuple[NonEmpty, ...]
    refs: tuple[ModelRef, ...]
    headline: NonEmpty
    body: NonEmpty


class FreeDraft(StrictModel):
    kind: Literal["free_text"]
    text: NonEmpty
    refs: tuple[ModelRef, ...]


ModelDraft = Annotated[ClosedDraft | FreeDraft, Field(discriminator="kind")]
DRAFT_ADAPTER = TypeAdapter(ModelDraft)


class CompletionResult(StrictModel):
    content: str
    response_sha256: Sha256
    response_bytes: Count
    finish_reason: Literal["stop"] = "stop"
    usage: dict[str, Count] | None = None
    usage_origin: Literal["mock_fixture"] = "mock_fixture"


class IntelligenceGeneratorProtocol(Protocol):
    async def generate(self, request: ExpressionRequest, *, budget: CallBudget) -> CompletionResult: ...


class ExpressionAssessment(StrictModel):
    base_item_id: NonEmpty
    status: Literal["accepted", "fallback", "skipped"]
    code: Code | None = None
    locator_status: Literal["passed", "failed", "not_evaluated"]
    numeric_scope_status: Literal["passed", "failed", "not_evaluated"]
    closed_render_status: Literal["passed", "failed", "not_evaluated"]
    semantic_truth: Literal["not_evaluated"] = "not_evaluated"
    ai_semantic_review: Literal["separate_development_process"] = "separate_development_process"


class IntelligencePresentation(Record):
    presentation_id: NonEmpty
    content_revision: Sha256
    base_item: IntelligenceItem
    event_key: NonEmpty
    event_revision: Sha256
    fact_revision: Sha256
    selection: Literal["rule", "mock_closed"]
    headline: str | None
    body: str | None
    style_id: NonEmpty | None
    claim_order: tuple[NonEmpty, ...]


class ExpressionSnapshot(Record):
    snapshot_id: NonEmpty
    presentation_id: NonEmpty
    base_snapshot_id: NonEmpty
    event_key: NonEmpty
    as_of: Instant
    previous_snapshot_ids: tuple[NonEmpty, ...]
    lineage_ids: tuple[NonEmpty, ...]


class SafeDraft(Record):
    request_sha256: Sha256
    text: NonEmpty
    ref_ids: tuple[NonEmpty, ...]
    status: Literal["not_selected"] = "not_selected"
    semantic_support: Literal["not_verified"] = "not_verified"
    record_origin: Literal["synthetic"] = "synthetic"


class AttemptTrace(StrictModel):
    request_sha256: Sha256 | None
    base_item_id: NonEmpty
    status: Literal["accepted", "fallback", "skipped"]
    code: Code | None
    mock_calls: Annotated[int, Field(ge=0, le=1)]
    external_requests: Literal[0] = 0
    model_calls: Literal[0] = 0
    billed_cost: Literal[0] = 0
    input_tokens: None = None
    usage: dict[str, Count] | None = None
    usage_origin: Literal["mock_fixture", "not_called", "unknown"]
    usage_complete: bool
    request_bytes: Count
    response_bytes: Count
    response_sha256: Sha256 | None = None
    elapsed_ms: Finite


class ExpressionState(Record):
    namespace: Sha256
    config_sha256: Sha256
    mode: Literal["rule", "mock"]
    cursor: ReplayCursor
    previous_state_sha256: Sha256 | None
    requests_reserved: Count
    request_bytes_reserved: Count
    response_bytes_reserved: Count
    snapshots: tuple[ExpressionSnapshot, ...]


class ExpressionInput(Record):
    generation_input: GenerationInput
    rule_result: GenerationResult
    rule_config: PR4Config
    mode: Literal["rule", "mock"] = "mock"
    config_sha256: Sha256
    previous_state: ExpressionState | None = None
    previous_state_sha256: Sha256 | None = None


class ExpressionResult(Record):
    cursor: ReplayCursor
    presentations: tuple[IntelligencePresentation, ...]
    snapshots: tuple[ExpressionSnapshot, ...]
    assessments: tuple[ExpressionAssessment, ...]
    drafts: tuple[SafeDraft, ...]
    next_state: ExpressionState
    coverage_gaps: tuple[dict[str, str | None], ...]
    semantic_truth: Literal["not_evaluated"] = "not_evaluated"


class StepExecution(StrictModel):
    result: ExpressionResult
    traces: tuple[AttemptTrace, ...]


class RunManifest(Record):
    parent_run_path: NonEmpty
    parent_manifest_sha256: Sha256
    through_step: NonEmpty
    mode: Literal["rule", "mock"]
    config_file_sha256: Sha256
    config_sha256: Sha256
    runtime_source_sha256: dict[str, Sha256]
    schema_sha256: dict[str, Sha256]
    asset_sha256: dict[str, Sha256]
    dependency_lock_sha256: dict[str, Sha256]
    dependency_versions: dict[str, NonEmpty]
    selected_input_sha256: Sha256
    git_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    artifacts: tuple[ArtifactDigest, ...]
    validation_scope: Literal["pr5_mock_constrained_expression"] = "pr5_mock_constrained_expression"


class ExpressionTrace(Record):
    run_manifest_sha256: Sha256
    generated_at: Instant
    elapsed_ms: Finite
    attempts: tuple[AttemptTrace, ...]
    mock_calls: Count
    external_requests: Literal[0] = 0
    model_calls: Literal[0] = 0
    billed_cost: Literal[0] = 0
    adapter_revision: Literal["g2-mock-completion-v1"] = "g2-mock-completion-v1"


SCHEMA_MODELS = (PR5Config, CallBudget, ExpressionRequest, ModelRef, ClosedDraft, FreeDraft,
    CompletionResult, IntelligencePresentation, ExpressionAssessment, ExpressionSnapshot,
    SafeDraft, AttemptTrace, ExpressionState, ExpressionInput, ExpressionResult,
    StepExecution, RunManifest, ExpressionTrace)


def schema_payloads():
    values = {m.__name__: m.model_json_schema() for m in SCHEMA_MODELS}
    values["ModelDraft"] = DRAFT_ADAPTER.json_schema()
    return {n + ".schema.json": json_bytes({**v, "$schema": "https://json-schema.org/draft/2020-12/schema"})
        for n, v in values.items()}


def check_schemas():
    folder, expected = PACKAGE / "schema/v5", schema_payloads()
    return ({p.name for p in folder.glob("*.schema.json")} == set(expected)
        and all((folder / name).read_bytes() == raw for name, raw in expected.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-schemas", action="store_true")
    parser.add_argument("--write-schemas", action="store_true")
    args = parser.parse_args(argv)
    if args.write_schemas:
        folder = PACKAGE / "schema/v5"
        folder.mkdir(parents=True, exist_ok=True)
        for name, raw in schema_payloads().items():
            (folder / name).write_bytes(raw)
    ok = check_schemas()
    print(json_bytes(dict(ok=ok, schema_revision=REVISION)).decode().strip())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
