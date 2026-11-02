"""Strict PR1 contracts. Runtime trust is separate from historical G3 acceptance."""

from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator

from evals.intelligence_g2.contracts import (
    G2SourcePolicy,
    G2VisibleDocument,
    checked_relative_path,
    data,
    json_bytes,
    read_json,
)
from evals.intelligence_g2.pr2.contracts import GroupingResult
from evals.intelligence_g2.pr3.contracts import EvidenceResult
from evals.intelligence_g2.pr4.contracts import GenerationResult
from evals.intelligence_g2.pr5.contracts import IntelligencePresentation
from evals.intelligence_g2.validate_output import check_permissions
from evals.intelligence_g3.budget_contracts import (
    BriefingPlan,
    BudgetConfig,
    CoverageDiagnostics,
    Profile,
)
from evals.intelligence_g3.contracts import PersonaSnapshot, PublishedItemRef
from evals.intelligence_g3.fact_signature import policy_sha256
from evals.intelligence_g3.history_contracts import Feedback, InteractionKind
from evals.intelligence_v1.contracts import (
    CoverageWindow,
    Instant,
    NonEmpty,
    Origin,
    Sha256,
    StrictModel,
)
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import content_sha256
from evals.intelligence_v1.provenance import https_host
from evals.intelligence_v1.temporal import parse_instant, version_chains

REVISION = "g4-pr1-runtime-contracts-v1"
RESULT_REVISION = "g4-pr1-briefing-v2"
NATIVE_STEP_REVISION = "g4-pr1-native-step-v2"
FACT_PIN = "70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450"
Code = Literal[
    "G4_SCHEMA_INVALID", "G4_FUTURE_INPUT", "G4_INVALID_INTERVAL", "G4_DUPLICATE_ID",
    "G4_PROVENANCE_INVALID", "G4_RIGHTS_INVALID", "G4_HASH_MISMATCH",
    "G4_REFERENCE_MISMATCH", "G4_SEQUENCE_INVALID", "G4_RESOURCE_LIMIT",
    "G4_CONFIG_INVALID", "G4_INPUT_PIN_MISMATCH", "G4_CANONICAL_REQUIRED",
    "G4_NATIVE_G2_REJECTED", "G4_G3_RUNTIME_ADAPTER_REQUIRED",
    "G4_EVIDENCE_NOT_ELIGIBLE", "G4_BRIEFING_NOT_READY", "G4_INTERACTION_INVALID",
    "G4_OUTPUT_MISMATCH",
]


class G4Error(ContractError):
    def __init__(self, code: Code, *, field="", native_code=None):
        super().__init__(code, field=field)
        self.native_code = native_code


def fail(code: Code, field):
    raise G4Error(code, field=field)


def parse(model, value):
    """Revalidate instances through the wire; copied/constructed models are untrusted."""
    try:
        payload = data(value)
        runtime = payload if model is RuntimeInput else (
            payload.get("input") if model is RuntimeBriefing and isinstance(payload, dict) else None)
        if isinstance(runtime, dict):
            steps = runtime.get("steps")
            for step in steps if isinstance(steps, (tuple, list)) else ():
                preflight_step(step)
        return model.model_validate_json(json_bytes(payload))
    except ValidationError as error:
        for detail in error.errors(include_input=False):
            cause = detail.get("ctx", {}).get("error")
            if isinstance(cause, G4Error):
                raise cause from None
            if isinstance(cause, ContractError):
                raise G4Error("G4_NATIVE_G2_REJECTED", field=model.__name__,
                              native_code=cause.code) from None
        fail("G4_SCHEMA_INVALID", model.__name__)
    except G4Error:
        raise
    except ContractError as error:
        raise G4Error("G4_NATIVE_G2_REJECTED", field=model.__name__,
                      native_code=error.code) from None
    except (TypeError, ValueError):
        fail("G4_SCHEMA_INVALID", model.__name__)


def provenance(origin, uri):
    if origin == "real":
        try:
            https_host(uri)
        except ContractError:
            fail("G4_PROVENANCE_INVALID", "provenance_uri")
    elif (not uri.startswith("synthetic://") or not uri.removeprefix("synthetic://")
          or "\\" in uri):
        fail("G4_PROVENANCE_INVALID", "provenance_uri")


class Record(StrictModel):
    schema_revision: Literal["g4-pr1-runtime-contracts-v1"] = REVISION


class RuntimeBudgetConfig(BudgetConfig):
    # Keep the native budget policy, but remove its implicit profile selection at this boundary.
    profile: Profile = Field(...)


class RuntimeConfig(Record):
    algorithm: Literal["b4"] = "b4"
    grouping_strategy: Literal["r1"] = "r1"
    expression: Literal["rule"] = "rule"
    attention_budget_seconds: Literal[180, 420, 900] = 420
    # Explicit choice required; the G3 default is not silently promoted to a product default.
    budget: RuntimeBudgetConfig
    budget_status: Literal["uncalibrated_candidate"] = "uncalibrated_candidate"
    fact_signature_revision: Literal["g3-grounded-fact-signature-v2"] = (
        "g3-grounded-fact-signature-v2")
    fact_signature_policy_sha256: Literal[FACT_PIN] = FACT_PIN
    max_documents_per_step: Literal[100] = 100
    max_steps: Literal[8] = 8
    max_sources: Literal[16] = 16

    @model_validator(mode="after")
    def fact_policy(self):
        if policy_sha256() != self.fact_signature_policy_sha256:
            fail("G4_CONFIG_INVALID", "fact_signature_policy_sha256")
        return self


class RuntimeSource(Record):
    policy: G2SourcePolicy
    policy_provenance_uri: NonEmpty

    @model_validator(mode="after")
    def origin(self):
        provenance(self.policy.record_origin, self.policy_provenance_uri)
        if ((self.policy.record_origin == "synthetic") !=
                (self.policy.redistribution_rights == "synthetic")):
            fail("G4_PROVENANCE_INVALID", "source.rights")
        if (self.policy.redistribution_rights in {"unknown", "metadata_only"}
                and set(self.policy.allowed_use) != {"metadata"}):
            fail("G4_RIGHTS_INVALID", "source.allowed_use")
        return self


class RuntimeDocument(G2VisibleDocument):
    schema_revision: Literal["g4-pr1-document-v1"] = "g4-pr1-document-v1"
    source_article_id: NonEmpty | None = None
    capture_revision: Literal["observed-immutable-capture-v1"] = "observed-immutable-capture-v1"

    @model_validator(mode="after")
    def captured(self):
        if self.record_origin == "synthetic":
            try:
                checked_relative_path(self.provenance_uri)
            except ContractError:
                fail("G4_PROVENANCE_INVALID", "document.provenance_uri")
        else:
            provenance(self.record_origin, self.provenance_uri)
        c = self.candidate
        if c.available_at < c.observed_at:
            fail("G4_INVALID_INTERVAL", "document.available_at")
        if len({p.paragraph_id for p in c.paragraphs}) != len(c.paragraphs):
            fail("G4_DUPLICATE_ID", "paragraph_id")
        if content_sha256(c.title, c.text_excerpt, c.paragraphs) != c.content_sha256:
            fail("G4_HASH_MISMATCH", "document.content_sha256")
        return self

    def native(self):
        return parse(G2VisibleDocument, self.model_dump(mode="json", exclude={
            "schema_revision", "source_article_id", "capture_revision"}))


def preflight_step(value):
    # Outside a Pydantic before-validator: preserve strict JSON array/tuple semantics.
    if isinstance(value, dict) and isinstance(value.get("as_of"), str):
        cutoff = parse_instant(value["as_of"])
        documents = value.get("documents")
        candidates = [d.get("candidate", {}) for d in (
            documents if isinstance(documents, (tuple, list)) else ())
                      if isinstance(d, dict)]
        persona = value.get("persona")
        candidates += [persona.get("persona", {}) if isinstance(persona, dict) else {}]
        windows = value.get("source_coverage")
        candidates += list(windows) if isinstance(windows, (tuple, list)) else []
        for row in candidates:
            if not isinstance(row, dict):
                continue
            for name in ("available_at", "observed_at", "end_at"):
                if isinstance(row.get(name), str) and parse_instant(row[name]) > cutoff:
                    fail("G4_FUTURE_INPUT", name)


class RuntimeStep(Record):
    step_id: NonEmpty
    as_of: Instant
    time_window_start: Instant
    time_window_end: Instant
    persona: PersonaSnapshot
    documents: Annotated[tuple[RuntimeDocument, ...], Field(max_length=100)]
    source_coverage: Annotated[tuple[CoverageWindow, ...], Field(max_length=256)]

    @model_validator(mode="after")
    def interval(self):
        if not self.time_window_start <= self.time_window_end <= self.as_of:
            fail("G4_INVALID_INTERVAL", "time_window")
        preflight_step(self.model_dump(mode="json"))
        return self


def capture_document(document, archive, identities):
    """One immutable complete chain per document across the entire observed prefix."""
    c = document.candidate
    if c.doc_version_id in archive and archive[c.doc_version_id] != document:
        fail("G4_HASH_MISMATCH", "immutable_document_version")
    for identity in document.visible_lineage:
        known = identities.get(identity.doc_version_id)
        if known is not None and known != identity:
            fail("G4_HASH_MISMATCH", "immutable_predecessor_identity")
        old = document if identity.doc_version_id == c.doc_version_id else archive.get(
            identity.doc_version_id)
        if old is None or any(getattr(old.candidate, k) != getattr(identity, k)
                              for k in ("document_id", "available_at", "content_sha256")):
            fail("G4_REFERENCE_MISMATCH", "captured_predecessor")
    try:
        local = version_chains(document.visible_lineage)
        if set(local) != {c.document_id} or local[c.document_id][-1].doc_version_id != c.doc_version_id:
            fail("G4_SEQUENCE_INVALID", "visible_lineage_tail")
        # Only the selected document has newly captured body text. Older metadata was
        # checked above against the exact stored identity, including its predecessor.
        identities[c.doc_version_id] = local[c.document_id][-1]
        archive[c.doc_version_id] = document
        chain = version_chains(identities.values())[c.document_id]
    except G4Error:
        raise
    except ContractError as error:
        raise G4Error("G4_SEQUENCE_INVALID", field="captured_document_chain",
                      native_code=error.code) from None
    if chain[-1].doc_version_id != c.doc_version_id:
        fail("G4_SEQUENCE_INVALID", "current_document_must_be_captured_tail")
    if tuple(chain) != document.visible_lineage:
        fail("G4_SEQUENCE_INVALID", "complete_captured_lineage")


class RuntimeInput(Record):
    kind: Literal["runtime_local_v1"] = "runtime_local_v1"
    record_origin: Origin
    provenance_uri: NonEmpty
    timeline_id: NonEmpty
    config: RuntimeConfig
    sources: Annotated[tuple[RuntimeSource, ...], Field(min_length=1, max_length=16)]
    steps: Annotated[tuple[RuntimeStep, ...], Field(min_length=1, max_length=8)]

    @model_validator(mode="after")
    def linked(self):
        provenance(self.record_origin, self.provenance_uri)
        sources = {s.policy.source_id: s.policy for s in self.sources}
        if len(sources) != len(self.sources):
            fail("G4_DUPLICATE_ID", "source_id")
        seen_steps, archive, identities, last = set(), {}, {}, None
        persona_id, personas, last_persona = None, {}, None
        for step in self.steps:
            if step.step_id in seen_steps:
                fail("G4_DUPLICATE_ID", "step_id")
            seen_steps.add(step.step_id)
            if last is not None and step.as_of <= last:
                fail("G4_SEQUENCE_INVALID", "as_of")
            last = step.as_of
            p = step.persona
            if (p.record_origin != self.record_origin or
                    (persona_id is not None and p.persona.persona_id != persona_id)):
                fail("G4_PROVENANCE_INVALID", "persona")
            persona_id = p.persona.persona_id
            version = p.persona.persona_version_id
            if version in personas and personas[version] != p:
                fail("G4_HASH_MISMATCH", "immutable_persona_version")
            if last_persona is not None and (p.persona.available_at < last_persona.persona.available_at
                    or p != last_persona and p.persona.available_at == last_persona.persona.available_at):
                fail("G4_SEQUENCE_INVALID", "latest_persona_version")
            personas[version], last_persona = p, p
            if p.persona.attention_budget_seconds != self.config.attention_budget_seconds:
                fail("G4_CONFIG_INVALID", "persona.attention_budget_seconds")
            if any(s.record_origin != self.record_origin for s in sources.values()):
                fail("G4_PROVENANCE_INVALID", "source.record_origin")
            windows = {w.source_id for w in step.source_coverage}
            if windows != set(sources):
                fail("G4_REFERENCE_MISMATCH", "complete_source_coverage")
            if len({w.coverage_window_id for w in step.source_coverage}) != len(step.source_coverage):
                fail("G4_DUPLICATE_ID", "coverage_window_id")
            if len({d.candidate.document_id for d in step.documents}) != len(step.documents):
                fail("G4_DUPLICATE_ID", "visible_document_id")
            if len({d.candidate.doc_version_id for d in step.documents}) != len(step.documents):
                fail("G4_DUPLICATE_ID", "doc_version_id")
            for document in step.documents:
                c = document.candidate
                if document.record_origin != self.record_origin:
                    fail("G4_PROVENANCE_INVALID", "document.record_origin")
                if c.source_id not in sources:
                    fail("G4_REFERENCE_MISMATCH", "document.source_id")
                try:
                    check_permissions(document, sources[c.source_id])
                except ContractError as error:
                    code = ("G4_RIGHTS_INVALID" if error.code.startswith(("RIGHTS_", "SOURCE_NOT_ALLOWED"))
                            else "G4_PROVENANCE_INVALID")
                    raise G4Error(code, field=error.field, native_code=error.code) from None
                capture_document(document, archive, identities)
        return self


class RuntimeInteraction(Record):
    """Wire shape only: PR4 must bind these to published DB deliveries and journal heads."""
    interaction_id: NonEmpty
    idempotency_key: Annotated[str, Field(min_length=1, max_length=128)]
    persona_id: NonEmpty
    delivery_id: NonEmpty
    target: PublishedItemRef
    expected_snapshot_version: Literal[1] = 1
    kind: InteractionKind
    feedback: Feedback | None = None
    retracts_id: NonEmpty | None = None
    occurred_at: Instant
    available_at: Instant
    source: Literal["server", "client", "explicit_user"]
    record_origin: Origin
    provenance_uri: NonEmpty

    @model_validator(mode="after")
    def valid(self):
        provenance(self.record_origin, self.provenance_uri)
        if not self.target.as_of <= self.occurred_at <= self.available_at:
            fail("G4_INVALID_INTERVAL", "interaction")
        if ((self.kind == "feedback") != (self.feedback is not None)
                or (self.kind == "retract") != (self.retracts_id is not None)
                or self.retracts_id == self.interaction_id):
            fail("G4_INTERACTION_INVALID", "feedback_or_retraction")
        if self.source != {"included": "server", "rendered": "client"}.get(
                self.kind, "explicit_user"):
            fail("G4_INTERACTION_INVALID", "source")
        return self


class RuntimeStatus(Record):
    mode: Literal["runtime_local_v1"] = "runtime_local_v1"
    record_origin: Origin
    state: Literal["raw_news_only", "insufficient_evidence"]
    code: Literal["G4_G3_RUNTIME_ADAPTER_REQUIRED", "G4_EVIDENCE_NOT_ELIGIBLE"]
    native_g2_validated: Literal[True] = True
    g3_runtime_validated: Literal[False] = False
    publishable: Literal[False] = False
    semantic_truth: Literal["not_evaluated"] = "not_evaluated"

    @model_validator(mode="after")
    def consistent(self):
        expected = ("G4_G3_RUNTIME_ADAPTER_REQUIRED" if self.state == "raw_news_only"
                    else "G4_EVIDENCE_NOT_ELIGIBLE")
        if self.code != expected:
            fail("G4_OUTPUT_MISMATCH", "status.code")
        return self


class NativeStepResult(Record):
    schema_revision: Literal["g4-pr1-native-step-v2"] = NATIVE_STEP_REVISION
    grouping: GroupingResult
    evidence: EvidenceResult
    rule: GenerationResult
    presentations: tuple[IntelligencePresentation, ...]
    coverage: CoverageDiagnostics


class RuntimeBriefing(Record):
    schema_revision: Literal["g4-pr1-briefing-v2"] = RESULT_REVISION
    input: RuntimeInput
    input_sha256: Sha256
    config_sha256: Sha256
    native_steps: tuple[NativeStepResult, ...]
    status: RuntimeStatus
    archive_snapshot_ids: tuple[NonEmpty, ...]
    display_order: tuple[NonEmpty, ...] = ()
    plan: BriefingPlan | None = None
    scope: Literal["pr1_offline_feasibility_not_application_or_g3_acceptance"] = (
        "pr1_offline_feasibility_not_application_or_g3_acceptance")

    @model_validator(mode="after")
    def consistent(self):
        from .slice import derive

        if self.plan is not None or self.display_order:
            fail("G4_G3_RUNTIME_ADAPTER_REQUIRED", "unregistered_plan")
        expected = derive(self.input, self.input_sha256)
        if self.model_dump(mode="json", exclude={"input", "schema_revision", "scope"}) != expected:
            fail("G4_OUTPUT_MISMATCH", "recomputed_native_output")
        return self


MODELS = (RuntimeBudgetConfig, RuntimeConfig, RuntimeSource, RuntimeDocument, RuntimeStep, RuntimeInput,
          RuntimeInteraction, RuntimeStatus, NativeStepResult, RuntimeBriefing)


def decode(raw):
    try:
        return parse(RuntimeInput, read_json(raw))
    except G4Error:
        raise
    except ContractError as error:
        raise G4Error("G4_SCHEMA_INVALID", field="json", native_code=error.code) from None
