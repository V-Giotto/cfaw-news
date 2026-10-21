"""Read-only offline validation. No repair, database, environment or network access."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from pydantic import ValidationError

from .contracts import (
    SCHEMA_MODELS,
    SCHEMA_REVISION,
    Adjudication,
    Annotation,
    BaselineConfig,
    Claim,
    CoverageWindow,
    Delivery,
    DocumentObservation,
    DocumentVersion,
    EventGroup,
    EventRelation,
    Exposure,
    FamilySplit,
    GoldLabel,
    Manifest,
    PersonaVersion,
    ReplayStep,
    SourceRegistry,
    schema_text,
)
from .exceptions import ContractError, DatasetValidationError, Issue, ValidationReport
from .hashing import canonical_json, sha256_bytes
from .pilot import annotation_packet, citation_status
from .provenance import (
    SENSITIVE,
    check_document,
    check_provenance,
    check_source,
    controlled_path,
)
from .split_metadata import split_metadata_issues
from .temporal import (
    previous_delivery,
    require_visible_version,
    version_chains,
    visible_exposures,
    visible_persona,
    visible_versions,
)

RECORD_MODELS = {
    "documents": DocumentVersion, "personas": PersonaVersion, "steps": ReplayStep,
    "deliveries": Delivery, "exposures": Exposure, "coverage": CoverageWindow,
    "events": EventGroup, "claims": Claim, "gold": GoldLabel, "families": FamilySplit,
    "observations": DocumentObservation, "event_relations": EventRelation,
    "annotations": Annotation, "adjudications": Adjudication,
}
REQUIRED_RECORD_ROLES = frozenset(RECORD_MODELS) - {
    "observations", "event_relations", "annotations", "adjudications",
}
ID_FIELDS = {
    "documents": ("doc_version_id",), "personas": ("persona_version_id",),
    "steps": ("timeline_id", "step_id"), "deliveries": ("delivery_id",),
    "exposures": ("exposure_id",), "coverage": ("coverage_window_id",),
    "events": ("event_id",), "claims": ("claim_id", "valid_as_of"),
    "gold": ("timeline_id", "step_id", "persona_version_id", "event_id", "annotation_version"),
    "families": ("family_id",),
    "observations": ("observation_id",),
    "event_relations": ("left_doc_version_id", "right_doc_version_id", "evidence_at"),
    "annotations": ("annotation_id",), "adjudications": ("adjudication_id",),
}
REQUIRED_SCHEMAS = {f"schema/{name}.schema.json": model for name, model in SCHEMA_MODELS.items()}


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("INVALID_JSON")
        result[key] = value
    return result


def _json(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError):
        raise ContractError("INVALID_JSON") from None


def _parse(model, raw: bytes):
    _json(raw)
    try:
        return model.model_validate_json(raw)
    except ValidationError as exc:
        error = exc.errors(include_input=False)[0]
        cause = error.get("ctx", {}).get("error")
        if isinstance(cause, ContractError):
            raise ContractError(cause.code, field=cause.field or ".".join(
                str(part) for part in error["loc"]
            ), record_id=cause.record_id) from None
        raise ContractError("SCHEMA_INVALID", field=".".join(
            str(part) for part in error["loc"]
        )) from None


def _need(index, key):
    if key not in index:
        raise ContractError("REFERENCE_NOT_FOUND", record_id=str(key))
    return index[key]


class _Validator:
    def __init__(self, report, root):
        self.report = report
        self.root = root
        self.locations = {}
        self.records = defaultdict(list)

    def issue(self, error, *, path="", line=None, record_id=""):
        self.report.errors.append(Issue(error.code, path, line,
                                        error.record_id or record_id, error.field))

    def run(self, function, row=None):
        try:
            return function()
        except ContractError as error:
            path, line, record_id = self.locations.get(id(row), ("", None, ""))
            self.issue(error, path=path, line=line, record_id=record_id)

    def files(self, manifest, manifest_path):
        payloads, entries, physical_paths = {}, {}, set()
        for entry in manifest.file_hashes:
            path = self.run(lambda: controlled_path(self.root, entry.path))
            if path is None:
                continue
            if path == manifest_path:
                self.issue(ContractError("MANIFEST_SELF_HASH"), path=entry.path)
                continue
            if entry.path in entries or path in physical_paths:
                self.issue(ContractError("DUPLICATE_ID"), path=entry.path)
                continue
            entries[entry.path] = entry
            physical_paths.add(path)
            try:
                raw = path.read_bytes()
            except OSError:
                self.issue(ContractError("FILE_MISSING"), path=entry.path)
                continue
            if sha256_bytes(raw) != entry.sha256:
                self.issue(ContractError("SHA_MISMATCH"), path=entry.path)
                continue
            payloads[entry.path] = raw  # Parse exactly these verified bytes, never reopen data.
            if entry.path in REQUIRED_SCHEMAS and entry.role != "schema":
                self.issue(ContractError("SCHEMA_INVALID", field="role"), path=entry.path)
            if entry.path.endswith(".jsonl") != (entry.role in RECORD_MODELS):
                self.issue(ContractError("MANIFEST_PATH_INVALID"), path=entry.path)
            if entry.role == "code" and not entry.path.endswith(".py"):
                self.issue(ContractError("MANIFEST_PATH_INVALID"), path=entry.path)
            if entry.role == "schema" and not entry.path.endswith(".schema.json"):
                self.issue(ContractError("MANIFEST_PATH_INVALID"), path=entry.path)
        required = {p.relative_to(self.root).as_posix() for p in self.root.glob("*.py")}
        required.update(p.relative_to(self.root).as_posix()
                        for p in (self.root / "schema").glob("*.schema.json"))
        required.update(REQUIRED_SCHEMAS)
        required.update(p.relative_to(self.root).as_posix() for p in self.root.rglob("*.jsonl"))
        required.update(p.relative_to(self.root).as_posix()
                        for p in (self.root / "manifests").glob("*.json") if p != manifest_path)
        for relative in sorted(required - entries.keys()):
            self.issue(ContractError("UNLISTED_INPUT"), path=relative)
        roles = Counter(entry.role for entry in entries.values())
        for role in {*REQUIRED_RECORD_ROLES, "source_registry"}:
            if not roles[role] or (role == "source_registry" and roles[role] != 1):
                self.issue(ContractError("UNLISTED_INPUT"), path=role)
        if self.report.errors:
            return None
        return entries, payloads

    def decode(self, entries, payloads):
        registry = None
        seen = defaultdict(dict)
        for relative, entry in sorted(entries.items()):
            raw = payloads[relative]
            if entry.role in RECORD_MODELS:
                if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or (raw and not raw.endswith(b"\n")):
                    self.issue(ContractError("INVALID_JSON"), path=relative)
                    continue
                lines = raw.splitlines()
                if entry.record_count != len(lines):
                    self.issue(ContractError("RECORD_COUNT_MISMATCH"), path=relative)
                    continue
                for line_number, line in enumerate(lines, 1):
                    try:
                        row = _parse(RECORD_MODELS[entry.role], line)
                    except ContractError as error:
                        self.issue(error, path=relative, line=line_number)
                        continue
                    key = tuple(getattr(row, f) for f in ID_FIELDS[entry.role])
                    if key in seen[entry.role]:
                        code = "DUPLICATE_ID"
                        if entry.role == "families" and seen[entry.role][key].split != row.split:
                            code = "CROSS_FAMILY_SPLIT"
                        self.issue(ContractError(code), path=relative, line=line_number,
                                   record_id=str(key[0]))
                    seen[entry.role][key] = row
                    self.records[entry.role].append(row)
                    self.locations[id(row)] = (relative, line_number, str(key[0]))
            elif entry.role == "source_registry":
                try:
                    registry = _parse(SourceRegistry, raw)
                    if registry.schema_revision != SCHEMA_REVISION:
                        raise ContractError("UNSUPPORTED_REVISION")
                    if entry.record_count != len(registry.sources):
                        raise ContractError("RECORD_COUNT_MISMATCH")
                except ContractError as error:
                    self.issue(error, path=relative)
            elif entry.role == "baseline_config":
                try:
                    _parse(BaselineConfig, raw)
                except ContractError as error:
                    self.issue(error, path=relative)
            elif relative in REQUIRED_SCHEMAS or entry.role == "schema":
                model = REQUIRED_SCHEMAS.get(relative)
                if model is None or raw != schema_text(model).encode():
                    self.issue(ContractError("SCHEMA_INVALID"), path=relative)
            if entry.role not in {*RECORD_MODELS, "source_registry"} and entry.record_count is not None:
                self.issue(ContractError("RECORD_COUNT_MISMATCH"), path=relative)
        self.report.counts = {role: len(self.records[role]) for role in RECORD_MODELS}
        return registry

    def references(self, manifest, registry, controlled):
        r = self.records
        sources = {}
        for source in registry.sources:
            if source.source_id in sources:
                self.issue(ContractError("DUPLICATE_ID", record_id=source.source_id))
            sources[source.source_id] = source
            self.run(lambda: check_source(source, self.root, controlled))
        documents = {row.doc_version_id: row for row in r["documents"]}
        events = {row.event_id: row for row in r["events"]}
        families = {row.family_id: row.split for row in r["families"]}
        personas = {row.persona_version_id: row for row in r["personas"]}
        deliveries = {row.delivery_id: row for row in r["deliveries"]}
        coverage = {row.coverage_window_id: row for row in r["coverage"]}
        steps = {(row.timeline_id, row.step_id): row for row in r["steps"]}
        origins = Counter(row.record_origin for row in r["documents"])
        if any(getattr(manifest.record_origin_breakdown, k) != origins[k]
               for k in ("real", "synthetic")):
            self.issue(ContractError("RECORD_COUNT_MISMATCH", field="record_origin_breakdown"))
        splits = Counter(families.values())
        if any(getattr(manifest.family_split_counts, k) != splits[k] for k in ("train", "dev", "test")):
            self.issue(ContractError("RECORD_COUNT_MISMATCH", field="family_split_counts"))
        self.run(lambda: version_chains(r["documents"]))
        for row, error in split_metadata_issues(r["documents"], families, r["personas"], r["steps"]):
            path, line, record_id = self.locations.get(id(row), ("", None, ""))
            self.issue(error, path=path, line=line, record_id=record_id)
        for observation in r["observations"]:
            def check_observation():
                document = _need(documents, observation.doc_version_id)
                check_provenance(observation.record_origin, observation.provenance_uri,
                                 self.root, controlled)
                if observation.record_origin != document.record_origin:
                    raise ContractError("ORIGIN_MISMATCH")
                if observation.observed_at < document.observed_at:
                    raise ContractError("FUTURE_EVIDENCE")
                if observation.content_sha256 != document.content_sha256:
                    raise ContractError("SHA_MISMATCH", field="content_sha256")
            self.run(check_observation, observation)
        relation_keys = set()
        for relation in r["event_relations"]:
            def check_relation():
                left = _need(documents, relation.left_doc_version_id)
                right = _need(documents, relation.right_doc_version_id)
                check_provenance(relation.record_origin, relation.provenance_uri,
                                 self.root, controlled)
                if left.doc_version_id == right.doc_version_id:
                    raise ContractError("SCHEMA_INVALID", field="right_doc_version_id")
                if any(d.record_origin != relation.record_origin for d in (left, right)):
                    raise ContractError("ORIGIN_MISMATCH")
                if _need(families, left.family_id) != _need(families, right.family_id):
                    raise ContractError("CROSS_FAMILY_SPLIT")
                if max(left.available_at, right.available_at) > relation.evidence_at:
                    raise ContractError("FUTURE_EVIDENCE")
                key = (*sorted((left.doc_version_id, right.doc_version_id)), relation.evidence_at)
                if key in relation_keys:
                    raise ContractError("DUPLICATE_ID")
                relation_keys.add(key)
            self.run(check_relation, relation)
        for document in r["documents"]:
            self.run(lambda: check_document(document, sources, self.root, controlled), document)
        for event in r["events"]:
            def check_event():
                if event.family_id not in families:
                    raise ContractError("FAMILY_NOT_FOUND")
                check_provenance(event.record_origin, event.provenance_uri, self.root, controlled)
                for version_id in event.document_version_ids:
                    document = _need(documents, version_id)
                    if document.family_id != event.family_id:
                        raise ContractError("CROSS_FAMILY_SPLIT")
                    if document.record_origin != event.record_origin:
                        raise ContractError("ORIGIN_MISMATCH")
                for related in event.related_event_ids:
                    _need(events, related)
            self.run(check_event, event)
        for window in r["coverage"]:
            self.run(lambda: _need(sources, window.source_id), window)
        for exposure in r["exposures"]:
            def check_exposure():
                delivery = _need(deliveries, exposure.delivery_id)
                if exposure.occurred_at < delivery.generated_at:
                    raise ContractError("INVALID_INTERVAL")
                if exposure.reference_event_id_for_fixture:
                    event = _need(events, exposure.reference_event_id_for_fixture)
                    if event.record_origin != "synthetic":
                        raise ContractError("ORIGIN_MISMATCH")
                    if event.first_observed_at > exposure.occurred_at:
                        raise ContractError("FUTURE_EVIDENCE")
            self.run(check_exposure, exposure)
        for persona in r["personas"]:
            self.run(lambda: visible_persona(r["personas"], persona_id=persona.persona_id,
                                             as_of=persona.available_at), persona)
        for step in r["steps"]:
            def check_step():
                persona = _need(personas, step.persona_version_id)
                if persona.available_at > step.as_of:
                    raise ContractError("FUTURE_PERSONA")
                selected = visible_persona(r["personas"], persona_id=persona.persona_id,
                                           as_of=step.as_of)
                if selected.persona_version_id != persona.persona_version_id:
                    raise ContractError("VERSION_CONFLICT")
                for version_id in step.visible_doc_version_ids:
                    require_visible_version(_need(documents, version_id), as_of=step.as_of)
                scoped = [x for x in r["documents"] if x.family_id in step.family_scope_ids]
                actual = tuple(x.doc_version_id for x in visible_versions(scoped, as_of=step.as_of))
                if actual != step.visible_doc_version_ids:
                    raise ContractError("VISIBLE_SET_MISMATCH")
                previous_delivery(r["deliveries"], step.previous_delivery_id, as_of=step.as_of)
                for window_id in step.coverage_window_ids:
                    window = _need(coverage, window_id)
                    if window.end_at > step.as_of or window.observed_at > step.as_of:
                        raise ContractError("FUTURE_COVERAGE")
                _, filtered = visible_exposures(r["exposures"], as_of=step.as_of, strict=False)
                self.report.filtered.extend(Issue(x.code, record_id=x.record_id,
                                                  field=step.timeline_id + "/" + step.step_id)
                                            for x in filtered)
                for document in scoped:
                    if document.available_at > step.as_of:
                        self.report.filtered.append(Issue("FUTURE_VERSION",
                            record_id=document.doc_version_id,
                            field=step.timeline_id + "/" + step.step_id))
            self.run(check_step, step)
        claim_texts = {}
        for claim in r["claims"]:
            def check_claim():
                event = _need(events, claim.event_id)
                check_provenance(claim.record_origin, claim.provenance_uri, self.root, controlled)
                if claim.record_origin != event.record_origin:
                    raise ContractError("ORIGIN_MISMATCH")
                if event.first_observed_at > claim.valid_as_of:
                    raise ContractError("FUTURE_EVIDENCE")
                if claim.claim_id in claim_texts and claim_texts[claim.claim_id] != claim.claim_text:
                    raise ContractError("VERSION_CONFLICT")
                claim_texts[claim.claim_id] = claim.claim_text
                for ref in claim.evidence_refs:
                    document = _need(documents, ref.doc_version_id)
                    if _need(families, document.family_id) != _need(families, event.family_id):
                        raise ContractError("CROSS_FAMILY_SPLIT", field="evidence_refs")
                    if document.record_origin != claim.record_origin:
                        raise ContractError("ORIGIN_MISMATCH", field="evidence_refs")
                    if document.available_at > claim.valid_as_of:
                        raise ContractError("FUTURE_EVIDENCE")
                    if ref.paragraph_id is not None and ref.paragraph_id not in {
                        p.paragraph_id for p in document.paragraphs
                    }:
                        raise ContractError("CITATION_NOT_FOUND")
            self.run(check_claim, claim)
        for gold in r["gold"]:
            def check_gold():
                step = _need(steps, (gold.timeline_id, gold.step_id))
                event = _need(events, gold.event_id)
                check_provenance(gold.record_origin, gold.provenance_uri, self.root, controlled)
                if gold.record_origin != event.record_origin:
                    raise ContractError("ORIGIN_MISMATCH")
                if (gold.persona_version_id != step.persona_version_id
                        or gold.annotation_version != manifest.annotation_version):
                    raise ContractError("REFERENCE_NOT_FOUND")
                if event.family_id not in step.family_scope_ids:
                    raise ContractError("CROSS_FAMILY_SPLIT")
                if event.first_observed_at > step.as_of:
                    raise ContractError("FUTURE_EVIDENCE")
                for version_id in gold.supporting_doc_version_ids:
                    document = _need(documents, version_id)
                    if _need(families, document.family_id) != step.split:
                        raise ContractError("CROSS_FAMILY_SPLIT", field="supporting_doc_version_ids")
                    if document.record_origin != gold.record_origin:
                        raise ContractError("ORIGIN_MISMATCH", field="supporting_doc_version_ids")
                    if document.available_at > step.as_of:
                        raise ContractError("FUTURE_EVIDENCE")
            self.run(check_gold, gold)
        # Raw human records are optional. Structural validity is not human confirmation.
        annotations = {a.annotation_id: a for a in r["annotations"]}
        annotation_targets = set()
        for annotation in r["annotations"]:
            def check_annotation():
                step = _need(steps, (annotation.timeline_id, annotation.step_id))
                if (annotation.persona_version_id != step.persona_version_id
                        or annotation.annotation_version != manifest.annotation_version):
                    raise ContractError("REFERENCE_NOT_FOUND")
                if annotation.guide_revision != "dev01-guide-v1":
                    raise ContractError("UNSUPPORTED_REVISION", field="guide_revision")
                if "ANNOTATION_GUIDE.md" not in controlled:
                    raise ContractError("UNLISTED_INPUT", field="guide_revision")
                if annotation.submitted_at < step.as_of:
                    raise ContractError("INVALID_INTERVAL", field="submitted_at")
                packet = annotation_packet(r["documents"], r["personas"], r["coverage"], step=step)
                if sha256_bytes(packet) != annotation.packet_sha256:
                    raise ContractError("SHA_MISMATCH", field="packet_sha256")
                label = annotation.initial_label
                target = (annotation.annotator_id, annotation.timeline_id, annotation.step_id,
                          label.local_event_id, annotation.annotation_version)
                if target in annotation_targets:
                    raise ContractError("DUPLICATE_ID")
                annotation_targets.add(target)
                for version_id in label.document_version_ids:
                    if version_id not in step.visible_doc_version_ids:
                        raise ContractError("FUTURE_EVIDENCE", field="document_version_ids")
                relation_keys = set()
                for relation in label.document_relations:
                    pair = (*sorted((relation.left_doc_version_id, relation.right_doc_version_id)),
                            relation.evidence_at)
                    if pair in relation_keys:
                        raise ContractError("DUPLICATE_ID", field="document_relations")
                    relation_keys.add(pair)
                    check_provenance(relation.record_origin, relation.provenance_uri,
                                     self.root, controlled)
                    for version_id in (relation.left_doc_version_id, relation.right_doc_version_id):
                        if version_id not in step.visible_doc_version_ids:
                            raise ContractError("FUTURE_EVIDENCE", field="document_relations")
                        if _need(documents, version_id).record_origin != relation.record_origin:
                            raise ContractError("ORIGIN_MISMATCH", field="document_relations")
                    if relation.left_doc_version_id == relation.right_doc_version_id:
                        raise ContractError("SCHEMA_INVALID", field="document_relations")
                    if max(documents[v].available_at for v in (
                        relation.left_doc_version_id, relation.right_doc_version_id
                    )) > relation.evidence_at:
                        raise ContractError("FUTURE_EVIDENCE", field="document_relations")
                    if relation.evidence_at > step.as_of:
                        raise ContractError("FUTURE_EVIDENCE", field="document_relations")
                for review in label.claim_reviews:
                    for ref in review.evidence_refs:
                        document = _need(documents, ref.doc_version_id)
                        if document.family_id not in step.family_scope_ids:
                            raise ContractError("CROSS_FAMILY_SPLIT", field="evidence_refs")
                        citation_status(r["documents"], ref, as_of=step.as_of)
            self.run(check_annotation, annotation)
        for adjudication in r["adjudications"]:
            def check_adjudication():
                prior = [_need(annotations, key) for key in adjudication.prior_annotation_ids]
                if len(set(adjudication.prior_annotation_ids)) != len(prior):
                    raise ContractError("DUPLICATE_ID", field="prior_annotation_ids")
                if len({a.annotator_id for a in prior}) < 2:
                    raise ContractError("SCHEMA_INVALID", field="prior_annotation_ids")
                label = adjudication.final_label
                for annotation in prior:
                    if (annotation.timeline_id, annotation.step_id, annotation.persona_version_id,
                        annotation.annotation_version) != (label.timeline_id, label.step_id,
                        label.persona_version_id, label.annotation_version):
                        raise ContractError("REFERENCE_NOT_FOUND", field="final_label")
                    if annotation.submitted_at > adjudication.adjudicated_at:
                        raise ContractError("INVALID_INTERVAL", field="adjudicated_at")
                key = tuple(getattr(label, name) for name in ID_FIELDS["gold"])
                final = [g for g in r["gold"] if tuple(getattr(g, n) for n in ID_FIELDS["gold"]) == key]
                if len(final) != 1 or final[0] != label:
                    raise ContractError("REFERENCE_NOT_FOUND", field="final_label")
                if label.adjudication_status not in {"adjudicated", "unresolved"}:
                    raise ContractError("SCHEMA_INVALID", field="final_label.adjudication_status")
                if (label.adjudication_status == "unresolved"
                        and "unresolved_adjudication" not in self.report.pending):
                    self.report.pending += ("unresolved_adjudication",)
            self.run(check_adjudication, adjudication)


def validate_dataset(manifest_path: str | Path, *, strict: bool = True) -> ValidationReport:
    report = ValidationReport()
    try:
        try:
            path = Path(manifest_path).absolute()
        except (ValueError, RuntimeError):
            raise ContractError("MANIFEST_PATH_INVALID") from None
        if (path.name != "dataset_manifest.json" or path.parent.name != "manifests"
                or any(p.casefold() in SENSITIVE or p.casefold().startswith(".env")
                       for p in path.parts)):
            raise ContractError("MANIFEST_PATH_INVALID")
        try:
            root = path.parent.parent.resolve()
        except (ValueError, RuntimeError):
            raise ContractError("MANIFEST_PATH_INVALID") from None
        path = controlled_path(root, "manifests/dataset_manifest.json")
        raw = path.read_bytes()
        report.manifest_sha256 = sha256_bytes(raw)
        manifest = _parse(Manifest, raw)
        if manifest.schema_revision != SCHEMA_REVISION:
            raise ContractError("UNSUPPORTED_REVISION")
        validator = _Validator(report, root)
        verified = validator.files(manifest, path)
        if verified is not None:
            entries, payloads = verified
            registry = validator.decode(entries, payloads)
            registry_files = [e for e in entries.values() if e.role == "source_registry"]
            if registry_files[0].sha256 != manifest.source_registry_sha256:
                validator.issue(ContractError("SHA_MISMATCH", field="source_registry_sha256"))
            configs = [e for e in entries.values() if e.role == "baseline_config"]
            if (len(configs) > 1 or (configs[0].sha256 if configs else None)
                    != manifest.baseline_config_sha256):
                validator.issue(ContractError("SHA_MISMATCH", field="baseline_config_sha256"))
            if not report.errors:
                validator.references(manifest, registry, set(entries))
    except ContractError as error:
        report.errors.append(Issue(error.code, "manifests/dataset_manifest.json",
                                   field=error.field))
    except OSError:
        report.errors.append(Issue("FILE_MISSING", "manifests/dataset_manifest.json"))
    if strict and not report.ok:
        raise DatasetValidationError(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = validate_dataset(args.manifest, strict=args.strict)
    except DatasetValidationError as error:
        report = error.report
    print(canonical_json(report.to_dict()))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
