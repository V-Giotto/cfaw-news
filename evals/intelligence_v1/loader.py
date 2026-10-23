"""Prediction-only bundle loading. Reference answers are never opened here.

Raw JSONL bytes are hash-checked as a whole. Metadata selects a historical version
before its text is validated/projected. Only the projected tuple reaches rankers.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError, model_validator

from .contracts import (
    SCHEMA_MODELS,
    SCHEMA_REVISION,
    BaselineConfig,
    CoverageWindow,
    Delivery,
    DeliveryItemSnapshot,
    DocumentVersion,
    Exposure,
    FamilySplit,
    Instant,
    Manifest,
    NonEmpty,
    PersonaVersion,
    ReplayContext,
    ReplayStep,
    Sha256,
    SourceRegistry,
    StrictModel,
    VisibleDeliveryItem,
    VisibleExposure,
    annotation_input_model,
    schema_text,
)
from .exceptions import ContractError
from .hashing import canonical_json, sha256_bytes
from .history import validate_snapshot
from .provenance import SENSITIVE, check_document, check_source, controlled_path
from .split_metadata import split_metadata_issues
from .temporal import (
    parse_instant,
    previous_delivery,
    project_candidate,
    visible_persona,
    visible_versions,
)

PREDICTION_ROLES = frozenset({"documents", "personas", "steps", "deliveries", "exposures",
                             "coverage", "families", "source_registry", "baseline_config",
                              "code", "schema", "delivery_items"})
RECORD_ROLES = frozenset({"documents", "personas", "steps", "deliveries", "exposures",
                          "coverage", "families", "delivery_items"})


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("INVALID_JSON")
        result[key] = value
    return result


def json_value(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError) as error:
        if isinstance(error, ContractError):
            raise
        raise ContractError("INVALID_JSON") from None


def parse_model(model, value):
    try:
        return annotation_input_model(model, value).model_validate_json(canonical_json(value))
    except ValidationError as error:
        cause = error.errors(include_input=False)[0].get("ctx", {}).get("error")
        if isinstance(cause, ContractError):
            raise cause from None
        raise ContractError("SCHEMA_INVALID") from None


def pinned_manifest(value, pin):
    if not isinstance(pin, str) or re.fullmatch(r"[0-9a-fA-F]{64}", pin) is None:
        raise ContractError("MANIFEST_SHA_MISMATCH")
    path = Path(value).absolute()
    if (path.name != "dataset_manifest.json" or path.parent.name != "manifests"
            or any(p.casefold() in SENSITIVE or p.casefold().startswith(".env")
                   for p in path.parts)):
        raise ContractError("MANIFEST_PATH_INVALID")
    root = path.parent.parent.resolve()
    path = controlled_path(root, "manifests/dataset_manifest.json")
    raw = path.read_bytes()
    if sha256_bytes(raw) != pin.lower():
        raise ContractError("MANIFEST_SHA_MISMATCH")
    manifest = parse_model(Manifest, json_value(raw))
    if manifest.schema_revision != SCHEMA_REVISION:
        raise ContractError("UNSUPPORTED_REVISION")
    return root, manifest


def read_entry(root, entry):
    raw = controlled_path(root, entry.path).read_bytes()
    if sha256_bytes(raw) != entry.sha256:
        raise ContractError("SHA_MISMATCH", field=entry.path)
    return raw


def read_records(raw, entry):
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or (raw and not raw.endswith(b"\n")):
        raise ContractError("INVALID_JSON", field=entry.path)
    lines = raw.splitlines()
    if len(lines) != entry.record_count:
        raise ContractError("RECORD_COUNT_MISMATCH", field=entry.path)
    rows = [json_value(line) for line in lines]
    if any(not isinstance(r, dict) for r in rows):
        raise ContractError("SCHEMA_INVALID", field=entry.path)
    return rows


def unique(rows, key):
    result = {}
    for row in rows:
        value = key(row)
        if value in result:
            raise ContractError("DUPLICATE_ID", record_id=str(value))
        result[value] = row
    return result


class DocumentIndex(StrictModel):
    doc_version_id: NonEmpty
    document_id: NonEmpty
    source_id: NonEmpty
    family_id: NonEmpty
    available_at: Instant
    observed_at: Instant
    supersedes_version_id: NonEmpty | None
    content_sha256: Sha256 | None
    canonical_url: NonEmpty | None
    upstream_document_id: NonEmpty | None = None

    @model_validator(mode="after")
    def interval(self):
        if self.available_at < self.observed_at:
            raise ContractError("AVAILABLE_BEFORE_OBSERVED")
        return self


@dataclass(frozen=True)
class PredictionBundle:
    root: Path
    manifest: Manifest
    rows: dict
    documents: tuple[DocumentIndex, ...]
    steps: tuple[ReplayStep, ...]
    sources: dict
    config: BaselineConfig
    verified_hashes: dict


def load_bundle(manifest_path, *, manifest_sha256, config_path=None):
    root, manifest = pinned_manifest(manifest_path, manifest_sha256)
    entries = unique(manifest.file_hashes, lambda e: e.path)
    rows = {role: [] for role in RECORD_ROLES}
    hashes, registries, configs, paths = {}, [], [], set()
    for entry in manifest.file_hashes:
        if entry.role not in PREDICTION_ROLES:
            continue  # No exists/stat/open of reference-answer paths.
        path = controlled_path(root, entry.path)
        if (path in paths or path == root/"manifests/dataset_manifest.json"
                or set(Path(entry.path).parts) & {"labels", "events", "claims"}):
            raise ContractError("PREDICTION_PATH_INVALID", field=entry.path)
        paths.add(path)
        if (entry.path.endswith(".jsonl") != (entry.role in RECORD_ROLES)
                or (entry.role == "code" and not entry.path.endswith(".py"))):
            raise ContractError("MANIFEST_PATH_INVALID", field=entry.path)
        raw = read_entry(root, entry)
        hashes[entry.path] = entry.sha256
        if entry.role in RECORD_ROLES:
            rows[entry.role].extend(read_records(raw, entry))
        elif entry.role == "source_registry":
            registry = parse_model(SourceRegistry, json_value(raw))
            if entry.record_count != len(registry.sources):
                raise ContractError("RECORD_COUNT_MISMATCH")
            registries.append((entry, registry))
        elif entry.role == "baseline_config":
            configs.append((entry, parse_model(BaselineConfig, json_value(raw))))
        elif entry.role == "schema":
            name = Path(entry.path).name.removesuffix(".schema.json")
            if name not in SCHEMA_MODELS or raw != schema_text(SCHEMA_MODELS[name]).encode():
                raise ContractError("SCHEMA_INVALID", field=entry.path)
    required = {f"schema/{name}.schema.json" for name in SCHEMA_MODELS}
    required.update(p.name for p in Path(__file__).parent.glob("*.py"))
    if not required.issubset(hashes):
        raise ContractError("UNLISTED_INPUT")
    # The code actually running must match the pinned code, not just a copied bundle.
    for name in (p.name for p in Path(__file__).parent.glob("*.py")):
        if sha256_bytes((Path(__file__).parent/name).read_bytes()) != hashes[name]:
            raise ContractError("RUNTIME_CODE_MISMATCH", field=name)
    if len(registries) != 1 or len(configs) != 1:
        raise ContractError("UNLISTED_INPUT")
    registry_entry, registry = registries[0]
    config_entry, config = configs[0]
    if registry.schema_revision != SCHEMA_REVISION:
        raise ContractError("UNSUPPORTED_REVISION")
    if (registry_entry.sha256 != manifest.source_registry_sha256
            or config_entry.sha256 != manifest.baseline_config_sha256):
        raise ContractError("SHA_MISMATCH")
    if config_path is not None and Path(config_path).resolve() != controlled_path(root,
                                                                                config_entry.path):
        raise ContractError("CONFIG_NOT_PINNED")
    kernel = Path(__file__).resolve().parents[2]/"backend/cfaw_news/retrieval.py"
    if config.retrieval_sha256 != sha256_bytes(kernel.read_bytes()):
        raise ContractError("RUNTIME_CODE_MISMATCH", field="retrieval.py")
    sources = unique(registry.sources, lambda s: s.source_id)
    for source in sources.values():
        check_source(source, root, set(entries))
    indexes = tuple(parse_model(DocumentIndex, {k: row[k] for k in DocumentIndex.model_fields
                                              if k in row}) for row in rows["documents"])
    unique(indexes, lambda d: d.doc_version_id)
    families = unique([parse_model(FamilySplit, r) for r in rows["families"]], lambda f: f.family_id)
    for document in indexes:
        if document.source_id not in sources:
            raise ContractError("SOURCE_NOT_FOUND")
    steps = tuple(parse_model(ReplayStep, r) for r in rows["steps"])
    unique(steps, lambda s: (s.timeline_id, s.step_id))
    personas = tuple(parse_model(_PersonaIndex, {k: r[k] for k in _PersonaIndex.model_fields})
                     for r in rows["personas"])
    unique(personas, lambda p: p.persona_version_id)
    for _, error in split_metadata_issues(indexes, {k: f.split for k, f in families.items()},
                                           personas, steps):
        raise error
    return PredictionBundle(root, manifest, rows, indexes, steps, sources, config, hashes)


def load_step(bundle, *, timeline_id, step_id, config):
    if config != bundle.config:
        raise ContractError("CONFIG_NOT_PINNED")
    selected = [s for s in bundle.steps if (s.timeline_id, s.step_id) == (timeline_id, step_id)]
    if len(selected) != 1:
        raise ContractError("REFERENCE_NOT_FOUND", field="step_id")
    step = selected[0]
    scoped = [d for d in bundle.documents if d.family_id in step.family_scope_ids]
    visible = visible_versions(scoped, as_of=step.as_of, allowed_source_ids=frozenset(bundle.sources))
    ids = tuple(d.doc_version_id for d in visible)
    if ids != step.visible_doc_version_ids:
        raise ContractError("VISIBLE_SET_MISMATCH")
    raw_documents = unique(bundle.rows["documents"], lambda r: r["doc_version_id"])
    candidates = []
    for index in visible:
        version = parse_model(DocumentVersion, raw_documents[index.doc_version_id])
        check_document(version, bundle.sources, bundle.root,
                       {e.path for e in bundle.manifest.file_hashes})
        candidates.append(project_candidate(version, as_of=step.as_of))
    raw_personas = unique(bundle.rows["personas"], lambda r: r["persona_version_id"])
    if step.persona_version_id not in raw_personas:
        raise ContractError("REFERENCE_NOT_FOUND", field="persona_version_id")
    wanted = raw_personas[step.persona_version_id]
    metadata = [parse_model(_PersonaIndex, {k: r[k] for k in _PersonaIndex.model_fields})
                for r in raw_personas.values()]
    persona = visible_persona(metadata, persona_id=wanted["persona_id"], as_of=step.as_of)
    if persona.persona_version_id != step.persona_version_id:
        if next(p for p in metadata if p.persona_version_id == step.persona_version_id
                ).available_at > step.as_of:
            raise ContractError("FUTURE_PERSONA")
        raise ContractError("VERSION_CONFLICT", field="persona_version_id")
    persona = parse_model(PersonaVersion, wanted)
    raw_coverage = unique(bundle.rows["coverage"], lambda r: r["coverage_window_id"])
    coverage = []
    for key in step.coverage_window_ids:
        if key not in raw_coverage:
            raise ContractError("REFERENCE_NOT_FOUND", field="coverage_window_ids")
        if any(parse_instant(raw_coverage[key][k]) > step.as_of for k in ("observed_at", "end_at")):
            raise ContractError("FUTURE_COVERAGE", record_id=key)
        coverage.append(parse_model(CoverageWindow, raw_coverage[key]))
    deliveries = [parse_model(Delivery, r) for r in bundle.rows["deliveries"]]
    unique(deliveries, lambda d: d.delivery_id)
    previous_delivery(deliveries, step.previous_delivery_id, as_of=step.as_of)
    allowed_deliveries = {s.previous_delivery_id for s in bundle.steps
                          if s.timeline_id == step.timeline_id and s.as_of <= step.as_of
                          and s.previous_delivery_id is not None} if step.previous_delivery_id else set()
    for delivery_id in sorted(allowed_deliveries):
        previous_delivery(deliveries, delivery_id, as_of=step.as_of)
    delivery_history = []
    unique(bundle.rows["delivery_items"], lambda r: (r["delivery_id"], r["event_prediction_id"]))
    for raw in bundle.rows["delivery_items"]:
        if raw["delivery_id"] not in allowed_deliveries:
            continue  # Future/unrelated snapshot payloads are never interpreted.
        item = parse_model(DeliveryItemSnapshot, raw)
        validate_snapshot(item, {d.delivery_id: d for d in deliveries}, bundle.documents,
                          bundle.steps, config.grouping_revision)
        delivery = previous_delivery(deliveries, item.delivery_id, as_of=step.as_of)
        delivery_history.append(VisibleDeliveryItem(**item.model_dump(),
            delivery_as_of=delivery.as_of, delivery_generated_at=delivery.generated_at))
    history = []
    unique(bundle.rows["exposures"], lambda r: r["exposure_id"])
    for raw in bundle.rows["exposures"]:
        if raw["delivery_id"] not in allowed_deliveries:
            continue
        if parse_instant(raw["occurred_at"]) > step.as_of:
            continue
        exposure = parse_model(Exposure, raw)
        delivery = previous_delivery(deliveries, exposure.delivery_id, as_of=step.as_of)
        if exposure.occurred_at < delivery.generated_at:
            raise ContractError("INVALID_INTERVAL")
        history.append(parse_model(VisibleExposure,
            exposure.model_dump(mode="json", include=set(VisibleExposure.model_fields))))
    targets = {(i.delivery_id, i.event_prediction_id) for i in delivery_history}
    for exposure in history:
        if (exposure.event_prediction_id is not None
                and (exposure.delivery_id, exposure.event_prediction_id) not in targets):
            raise ContractError("HISTORY_TARGET_NOT_FOUND")
    context = ReplayContext(timeline_id=step.timeline_id, step_id=step.step_id, as_of=step.as_of,
        persona=persona, candidate_doc_version_ids=ids, previous_delivery_id=step.previous_delivery_id,
        attention_budget_seconds=step.attention_budget_seconds,
        time_window_start=step.time_window_start, time_window_end=step.time_window_end,
        source_coverage=tuple(sorted(coverage, key=lambda c: c.coverage_window_id)),
        exposure_history=tuple(sorted(history, key=lambda e: (e.occurred_at, e.exposure_id))),
        delivery_history=tuple(sorted(delivery_history, key=lambda i: (
            i.delivery_generated_at, i.delivery_id, i.event_prediction_id))),
        unresolved_exposure_ids=tuple(sorted(e.exposure_id for e in history
                                             if e.event_prediction_id is None)))
    return context, tuple(candidates)


class _PersonaIndex(StrictModel):
    persona_id: NonEmpty
    persona_version_id: NonEmpty
    available_at: Instant
