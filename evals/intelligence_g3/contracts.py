"""Additive G3 contracts wrapping native, unchanged G1/G2 objects."""

import argparse
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator

from evals.intelligence_g2.contracts import G2ReplayInput, VersionIdentity, json_bytes
from evals.intelligence_g2.pr2.contracts import EventSnapshot, IdentityState
from evals.intelligence_g2.pr3.contracts import EvidenceBundle, EvidenceResult
from evals.intelligence_g2.pr4.contracts import IntelligenceItem, ItemSnapshot
from evals.intelligence_g2.pr5.contracts import IntelligencePresentation
from evals.intelligence_g2.pr6.contracts import FilePin, StepRecord
from evals.intelligence_v1.contracts import (
    CoverageWindow,
    Delivery,
    ExposureKind,
    Instant,
    NonEmpty,
    Origin,
    PersonaVersion,
    Sha256,
    StrictModel,
)
from evals.intelligence_v1.exceptions import ContractError

REVISION = "g3-pr1-1"
REPLAY_REVISION = "g3-pr1-3"
PACKAGE = Path(__file__).parent
ROOT = PACKAGE.parents[1]
Count = Annotated[int, Field(ge=0)]
Kind = Literal["accepted_g2", "synthetic_contract_probe"]


def fail(code, field):
    raise ContractError(code, field=field)


def parse(model, value):
    try:
        return model.model_validate_json(json_bytes(value))
    except ValidationError:
        fail("G3_SCHEMA_INVALID", model.__name__)


class Record(StrictModel):
    schema_revision: Literal["g3-pr1-1"] = REVISION


class DirectoryPin(StrictModel):
    path: NonEmpty
    manifest_sha256: Sha256


class G3Config(Record):
    config_revision: Literal["g3-pr1-config-v1"] = "g3-pr1-config-v1"
    parent_schema_revision: Literal["g2-pr6-1"] = "g2-pr6-1"
    selection: Literal["r1_standard_mock_seed1_canonical_full_prefix"] = (
        "r1_standard_mock_seed1_canonical_full_prefix"
    )
    registered_budgets: tuple[Literal[180, 420, 900], ...] = (180, 420, 900)
    future_policy: Literal["reject_explicit_inputs_report_parent_selection"] = (
        "reject_explicit_inputs_report_parent_selection"
    )

    @model_validator(mode="after")
    def fixed(self):
        if self.registered_budgets != (180, 420, 900):
            fail("G3_CONFIG_INVALID", "registered_budgets")
        return self


class PersonaSnapshot(Record):
    persona: PersonaVersion
    record_origin: Origin
    provenance_uri: NonEmpty

    @model_validator(mode="after")
    def origin(self):
        if (self.persona.persona_origin == "constructed") != (self.record_origin == "synthetic"):
            fail("G3_PROVENANCE_INVALID", "persona_origin")
        return self


class PublishedItemRef(StrictModel):
    event_key: NonEmpty
    event_revision: Sha256
    item_id: NonEmpty
    snapshot_id: NonEmpty
    as_of: Instant


class Interaction(Record):
    interaction_id: NonEmpty
    persona_id: NonEmpty
    delivery_id: NonEmpty
    target: PublishedItemRef
    kind: ExposureKind
    occurred_at: Instant
    available_at: Instant
    source: NonEmpty
    record_origin: Origin
    provenance_uri: NonEmpty

    @model_validator(mode="after")
    def interval(self):
        if not self.target.as_of <= self.occurred_at <= self.available_at:
            fail("G3_INVALID_INTERVAL", "interaction")
        return self


class DeliverySnapshot(Record):
    delivery: Delivery
    persona_id: NonEmpty
    available_at: Instant
    items: tuple[PublishedItemRef, ...]
    record_origin: Origin
    provenance_uri: NonEmpty

    @model_validator(mode="after")
    def interval(self):
        if self.delivery.generated_at > self.available_at:
            fail("G3_INVALID_INTERVAL", "delivery.available_at")
        ids = [i.snapshot_id for i in self.items]
        if len(ids) != len(set(ids)):
            fail("G3_DUPLICATE_ID", "delivery.items")
        if any(i.as_of > self.delivery.as_of for i in self.items):
            fail("G3_INVALID_INTERVAL", "delivery.items")
        return self


class InputManifest(Record):
    input_revision: Literal["g3-pr1-input-v1"] = "g3-pr1-input-v1"
    kind: Kind
    acceptance: DirectoryPin | None = None
    campaign: DirectoryPin | None = None
    fixture: FilePin | None = None
    config: FilePin
    personas: FilePin
    deliveries: FilePin
    history: FilePin
    job_id: NonEmpty
    timeline_id: NonEmpty
    step_id: NonEmpty
    as_of: Instant
    persona_version_id: NonEmpty
    attention_budget_seconds: Literal[180, 420, 900]

    @model_validator(mode="after")
    def boundary(self):
        parent_variant(self)
        return self


class NativeStep(Record):
    """Synthetic probe storage, not a G2 acceptance result."""
    replay_input: G2ReplayInput
    record: StepRecord
    trace: FilePin
    handoff_trace_pointer: NonEmpty | None = None
    handoff: tuple[dict, ...]


class SyntheticParent(Record):
    purpose: Literal["synthetic_contract_probe_only"] = "synthetic_contract_probe_only"
    record_origin: Literal["synthetic"] = "synthetic"
    provenance_uri: NonEmpty
    job_id: NonEmpty
    source_release: FilePin
    steps: tuple[NativeStep, ...]


class ParentBinding(Record):
    kind: Kind
    input_manifest_sha256: Sha256
    acceptance: DirectoryPin | None
    campaign: DirectoryPin | None
    fixture: FilePin | None
    job_id: NonEmpty
    source_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    source_release_sha256: Sha256
    g2_input_manifest_sha256: Sha256
    pool_sha256: Sha256
    config_file_sha256: Sha256
    config_sha256: Sha256

    @model_validator(mode="after")
    def boundary(self):
        parent_variant(self)
        return self


def parent_variant(value):
    if value.kind == "accepted_g2":
        if value.acceptance is None or value.campaign is None or value.fixture is not None:
            fail("G3_PARENT_INVALID", "accepted_parent")
    elif value.fixture is None or value.acceptance is not None or value.campaign is not None:
        fail("G3_PARENT_INVALID", "synthetic_parent")


class G3Candidate(Record):
    event: EventSnapshot
    bundle: EvidenceBundle
    rule_item: IntelligenceItem
    presentation: IntelligencePresentation
    snapshot: ItemSnapshot
    trace: FilePin
    trace_pointer: NonEmpty
    g2_view_sha256: Sha256

    @model_validator(mode="after")
    def linked(self):
        e, b, i, p, s = self.event, self.bundle, self.rule_item, self.presentation, self.snapshot
        if not (e.event_key == b.event_key == i.event_key == p.event_key == s.event_key
                and e.event_revision == b.event_revision == i.event_revision == p.event_revision
                and p.base_item == i and p.fact_revision == i.fact_revision
                and s.item_id == i.item_id and s.bundle_id == b.bundle_id
                and s.bundle_sha256 == b.bundle_sha256 and s.as_of == b.as_of
                and s.lineage_ids == e.lineage_ids):
            fail("G3_REFERENCE_MISMATCH", "candidate")
        from .integrity import validate_candidate

        validate_candidate(self)
        return self


class ReplayObservation(Record):
    """Unchanged native outputs and coverage binding at one visible prefix step."""
    identity_state: IdentityState
    evidence: EvidenceResult
    candidates: tuple[G3Candidate, ...]
    source_coverage: tuple[CoverageWindow, ...]
    source_coverage_digest: Sha256


class SelectionDiagnostic(StrictModel):
    withheld_parent_steps: Count = 0
    withheld_handoff_views: Count = 0
    filtered_explicit_inputs: Literal[0] = 0
    unresolved_g1_exposures: tuple[NonEmpty, ...] = ()
    g1_visible_history_not_imported: Count = 0
    g1_source_future_exposure_records: Count | None = None
    g1_history_policy: Literal["retained_by_parent_pin_not_mapped_or_inferred"] = (
        "retained_by_parent_pin_not_mapped_or_inferred"
    )


class G3ReplayInput(Record):
    schema_revision: Literal["g3-pr1-3"] = REPLAY_REVISION
    parent: ParentBinding
    timeline_id: NonEmpty
    step_id: NonEmpty
    as_of: Instant
    persona: PersonaSnapshot
    deliveries: tuple[DeliverySnapshot, ...]
    history: tuple[Interaction, ...]
    attention_budget_seconds: Literal[180, 420, 900]
    time_window_start: Instant
    time_window_end: Instant
    source_coverage: tuple[CoverageWindow, ...]
    candidates: tuple[G3Candidate, ...]
    identity_state: IdentityState
    evidence: EvidenceResult
    published_refs: tuple[PublishedItemRef, ...]
    document_archive: tuple[VersionIdentity, ...]
    item_snapshots: tuple[ItemSnapshot, ...]
    observations: Annotated[tuple[ReplayObservation, ...], Field(min_length=1)]
    diagnostic: SelectionDiagnostic

    @model_validator(mode="after")
    def visible(self):
        from .bridge import preflight
        from .integrity import validate_replay

        preflight((self.candidates, self.identity_state, self.evidence, self.published_refs,
                   self.deliveries, self.document_archive, self.item_snapshots, self.observations), self.as_of)
        if not self.time_window_start <= self.time_window_end <= self.as_of:
            fail("G3_INVALID_INTERVAL", "time_window")
        if self.persona.persona.available_at > self.as_of:
            fail("G3_FUTURE_PERSONA", "persona.available_at")
        if any(h.occurred_at > self.as_of or h.available_at > self.as_of for h in self.history):
            fail("G3_FUTURE_HISTORY", "history")
        if any(c.observed_at > self.as_of or c.end_at > self.as_of for c in self.source_coverage):
            fail("G3_FUTURE_COVERAGE", "source_coverage")
        for rows, key, name in (
            (self.candidates, lambda c: c.event.event_key, "candidate.event_key"),
            (self.candidates, lambda c: c.rule_item.item_id, "candidate.item_id"),
            (self.history, lambda h: h.interaction_id, "interaction_id"),
            (self.deliveries, lambda d: d.delivery.delivery_id, "delivery_id"),
            (self.published_refs, lambda r: r.snapshot_id, "snapshot_id"),
        ):
            ids = [key(v) for v in rows]
            if len(ids) != len(set(ids)):
                fail("G3_DUPLICATE_ID", name)
        if (self.identity_state.cursor != self.evidence.cursor
                or (self.identity_state.cursor.timeline_id, self.identity_state.cursor.step_id,
                    self.identity_state.cursor.as_of) != (self.timeline_id, self.step_id, self.as_of)
                or any(c.snapshot.as_of != self.as_of for c in self.candidates)):
            fail("G3_REFERENCE_MISMATCH", "output.cursor")
        refs = {r.snapshot_id: r for r in self.published_refs}
        deliveries = {d.delivery.delivery_id: d for d in self.deliveries}
        for delivery in self.deliveries:
            if delivery.persona_id != self.persona.persona.persona_id:
                fail("G3_REFERENCE_MISMATCH", "delivery.persona_id")
            if any(refs.get(r.snapshot_id) != r for r in delivery.items):
                fail("G3_REFERENCE_NOT_FOUND", "delivery.target")
        for h in self.history:
            d = deliveries.get(h.delivery_id)
            if d is None or refs.get(h.target.snapshot_id) != h.target:
                fail("G3_REFERENCE_NOT_FOUND", "history.target_or_delivery")
            if (h.persona_id != self.persona.persona.persona_id or h.target not in d.items
                    or h.occurred_at < d.delivery.generated_at):
                fail("G3_REFERENCE_MISMATCH", "history")
        validate_replay(self)
        return self


class ValidationResult(Record):
    schema_revision: Literal["g3-pr1-3"] = REPLAY_REVISION
    ok: Literal[True] = True
    input_sha256: Sha256
    candidate_count: Count
    history_count: Count
    diagnostic: SelectionDiagnostic
    scope: Literal["pr1_contracts_only_not_ranking_or_research"] = (
        "pr1_contracts_only_not_ranking_or_research"
    )


MODELS = (G3Config, PersonaSnapshot, Interaction, DeliverySnapshot, InputManifest, NativeStep, SyntheticParent,
          ParentBinding, G3Candidate, ReplayObservation, G3ReplayInput, ValidationResult)


def schema_payloads():
    return {m.__name__ + ".schema.json": json_bytes(m.model_json_schema()) for m in MODELS}


def check_schemas():
    return all((PACKAGE / "schema/v1" / n).read_bytes() == raw
               for n, raw in schema_payloads().items())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-schemas", action="store_true", required=True)
    parser.parse_args()
    if not check_schemas():
        fail("G3_SCHEMA_INVALID", "schema/v1")
    print(REPLAY_REVISION)


if __name__ == "__main__":
    main()
