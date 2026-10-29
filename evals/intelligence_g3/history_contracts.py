"""PR3 synthetic offline history. No inferred actions or knowledge transitions."""

from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator

from evals.intelligence_g2.contracts import digest, json_bytes
from evals.intelligence_v1.contracts import Instant, NonEmpty, Sha256, StrictModel
from evals.intelligence_v1.exceptions import ContractError

from .contracts import PACKAGE, G3ReplayInput, PublishedItemRef, fail

InteractionKind = Literal["included", "rendered", "opened", "acknowledged", "dismissed",
                          "feedback", "retract"]
Feedback = Literal["helpful", "irrelevant", "known", "not_known"]


def parse_history(model, value):
    """Preserve diagnostic contract codes without exposing rejected payloads."""
    try:
        return model.model_validate_json(json_bytes(value))
    except ValidationError as error:
        for detail in error.errors():
            cause = detail.get("ctx", {}).get("error")
            if isinstance(cause, ContractError):
                raise cause from None
        fail("G3_SCHEMA_INVALID", model.__name__)


class HistoryEvent(StrictModel):
    schema_revision: Literal["g3-pr3-history-v1"] = "g3-pr3-history-v1"
    interaction_id: NonEmpty
    persona_id: NonEmpty
    delivery_id: NonEmpty
    target: PublishedItemRef
    kind: InteractionKind
    feedback: Feedback | None = None
    retracts_id: NonEmpty | None = None
    occurred_at: Instant
    available_at: Instant
    source: Literal["server", "client", "explicit_user"]
    source_id: NonEmpty
    record_origin: Literal["synthetic"] = "synthetic"
    provenance_uri: NonEmpty

    @model_validator(mode="after")
    def valid(self):
        if not self.target.as_of <= self.occurred_at <= self.available_at:
            fail("G3_INVALID_INTERVAL", "history_event")
        if ((self.kind == "feedback") != (self.feedback is not None)
                or (self.kind == "retract") != (self.retracts_id is not None)):
            fail("G3_HISTORY_INVALID", "feedback_or_retraction")
        expected = {"included": "server", "rendered": "client"}.get(self.kind, "explicit_user")
        if self.source != expected:
            fail("G3_HISTORY_INVALID", "explicit_signal_source")
        return self


class JournalEntry(StrictModel):
    sequence: Annotated[int, Field(ge=1)]
    previous_sha256: Sha256 | None
    event: HistoryEvent
    sha256: Sha256

    @model_validator(mode="after")
    def hashed(self):
        if self.sha256 != digest(self.model_dump(mode="json", exclude={"sha256"})):
            fail("G3_HISTORY_CHAIN_INVALID", "entry.sha256")
        return self


class HistoryJournal(StrictModel):
    schema_revision: Literal["g3-pr3-journal-v1"] = "g3-pr3-journal-v1"
    entries: tuple[JournalEntry, ...] = ()

    @property
    def head(self):
        return self.entries[-1].sha256 if self.entries else None

    @model_validator(mode="after")
    def chain(self):
        head, seen, retracted, available = None, {}, set(), None
        for index, entry in enumerate(self.entries, 1):
            event = entry.event
            if (entry.sequence != index or entry.previous_sha256 != head
                    or event.interaction_id in seen
                    or (available is not None and event.available_at < available)):
                fail("G3_HISTORY_CHAIN_INVALID", "sequence_id_or_available_at")
            if event.retracts_id is not None:
                old = seen.get(event.retracts_id)
                if (old is None or old.kind not in {"feedback", "acknowledged", "dismissed"}
                        or old.interaction_id in retracted
                        or (old.target, old.persona_id, old.delivery_id) !=
                           (event.target, event.persona_id, event.delivery_id)
                        or event.occurred_at < old.occurred_at):
                    fail("G3_HISTORY_INVALID", "retracts_id")
                retracted.add(old.interaction_id)
            seen[event.interaction_id] = event
            head, available = entry.sha256, event.available_at
        return self


class HistoryMapping(StrictModel):
    mapping_id: NonEmpty
    from_target: PublishedItemRef
    to_target: PublishedItemRef
    transition_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    certainty: Literal["confirmed", "uncertain"]
    available_at: Instant
    reason: NonEmpty
    record_origin: Literal["synthetic"] = "synthetic"
    provenance_uri: NonEmpty


class HistoryInput(StrictModel):
    schema_revision: Literal["g3-pr3-input-v1"] = "g3-pr3-input-v1"
    replay: G3ReplayInput
    journal: HistoryJournal
    mappings: tuple[HistoryMapping, ...] = ()

    @model_validator(mode="after")
    def linked(self):
        from .history import validate_input

        validate_input(self)
        return self


class HistoryConfig(StrictModel):
    config_revision: Literal["g3-revisit-v1"] = "g3-revisit-v1"
    base_config_revision: Literal["g3-event-ranking-v1"] = "g3-event-ranking-v1"
    included_penalty: Literal[0.1] = 0.1
    rendered_penalty: Literal[0.1] = 0.1
    acknowledged_penalty: Literal[0.25] = 0.25
    dismissed_penalty: Literal[0.2] = 0.2
    irrelevant_penalty: Literal[0.2] = 0.2
    repeated_delivery_penalty: Literal[0.05] = 0.05
    penalty_cap: Literal[0.75] = 0.75
    policy: Literal["explicit-lineage-statement-sets-protected-change-v1"] = (
        "explicit-lineage-statement-sets-protected-change-v1")
    protection: Literal["eligible-protected-before-ordinary-for-b4-p1"] = (
        "eligible-protected-before-ordinary-for-b4-p1")


MODELS = (HistoryEvent, JournalEntry, HistoryJournal, HistoryMapping, HistoryInput, HistoryConfig)


def schema_payloads():
    from .revisit import RevisitResult

    return {m.__name__ + ".schema.json": json_bytes(m.model_json_schema())
            for m in (*MODELS, RevisitResult)}


def check_schemas():
    folder = PACKAGE / "schema/v3"
    payloads = schema_payloads()
    return ({p.name for p in folder.glob("*.schema.json")} == set(payloads)
            and all((folder / name).read_bytes() == raw for name, raw in payloads.items()))
