"""Offline, explicit administration for the authored PR5 development package.

Never run on import. Existing story records are not overwritten. Freeze is a
separate explicit operation after code, data and test evidence are final.
"""

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .contracts import SCHEMA_MODELS, SCHEMA_REVISION, DocumentVersion, Paragraph, schema_text
from .exceptions import ContractError
from .hashing import canonical_json, content_sha256, sha256_bytes
from .temporal import parse_instant, visible_versions

PRIMARY_TIMELINES = tuple(f"DEV-{n:02}" for n in range(1, 6))
ANNOTATION_VERSION = "g1a-annotation-v2"
GUIDE_REVISION = "g1a-guide-v3"
GUIDE_FILE = "ANNOTATION_GUIDE_V3.md"


def json_bytes(value):
    return (canonical_json(value) + "\n").encode()


def rows(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(json_bytes(value) for value in values))


STORIES = {
    2: ("Juniper Framework", [0, 1, 2, 3, 8], 2,
        "The release claims compatibility with both ABI 1 and ABI 2; no compatibility test is supplied.",
        "CORRECTION: Juniper Framework supports ABI 2 only. The earlier ABI 1 claim was incorrect.",
        "We tested Juniper Framework on Linux with ABI 2 in three toy integration tasks. ABI 1 was not supported in this limited test.",
        "Track framework compatibility and deployment ABI constraints"),
    3: ("Aurora Tool", [0, 1, 3, 4, 8], 3,
        "The publisher claims large speed gains on every task without a protocol or independent measurements.",
        "The performance claim is limited to a toy workload; universal speed gains have not been established.",
        "We ran Aurora Tool on one Linux GPU with two toy prompts; results did not establish universal gains. No production system was measured.",
        "Follow AI tools while separating publicity from reproducible measurements"),
    4: ("Willow Runtime", [0, 3, 5, 6, 8], 6,
        "Willow Runtime offers plugin loading for local AI workflows. The publisher initially described plugin isolation as complete.",
        "SECURITY CORRECTION: plugin isolation in Willow Runtime is incomplete. Disable untrusted plugins until a fix is independently verified.",
        "We reproduced a plugin boundary failure in Willow Runtime version 1 on a local Linux toy setup. No other version or deployment was tested.",
        "Track security limitations of AI runtimes and untrusted plugins"),
    5: ("Mosaic Sketch", [0, 1, 2, 3, 8], 3,
        "Mosaic Sketch is a data compression method outside Agent tooling. The release makes no claim about retrieval applications.",
        "A technical note describes how Mosaic Sketch might compact retrieval cache keys, with no proof of end to end retrieval quality.",
        "We tested Mosaic Sketch on three small retrieval cache traces on a CPU. Space decreased in this setup; general retrieval quality was not evaluated.",
        "Explore cross domain ideas for retrieval cache efficiency"),
}


def build_stories(root):
    registry_path = root / "manifests/source_registry.json"
    registry = json.loads(registry_path.read_bytes())
    for number, (subject, days, changed_day, initial, changed, measured, goal) in STORIES.items():
        folder = root / f"DEV-{number:02}"
        folder.mkdir(exist_ok=False)
        timeline, prefix = folder.name, f"d{number:02}"
        provenance = f"{timeline}/README.md"
        family = f"family:dev{number:02}"
        epoch = datetime(2026, number + 1, 1, 12, tzinfo=timezone.utc)

        def at(day):
            return (epoch + timedelta(days=day)).isoformat().replace("+00:00", "Z")

        folder.joinpath("README.md").write_text(
            f"# {timeline} — synthetic development story\n\n{subject} is fictional. All text, "
            "sources, dates and test observations are authored fixtures, not collected history or "
            "human annotation. Original repository test text may be redistributed as synthetic.\n\n"
            "The administrator references and authored expectations are withheld from annotators. "
            "A reviewer receives only their current single-step packet and the v2 guide. "
            "No real A/B submissions exist. No-change and important older evidence are deliberate "
            "test challenges, not guaranteed ranking results.\n", encoding="utf-8")
        source_ids = {}
        for suffix, kind in (("official", "official"), ("media", "media"),
                             ("test", "independent_test"), ("community", "community")):
            source_ids[kind] = f"dev{number:02}-{suffix}"
            registry["sources"].append({
                "source_id": source_ids[kind], "record_origin": "synthetic", "domain": None,
                "source_type": kind, "publisher_or_upstream": f"Fictional {subject} {suffix}",
                "independence_relation": "Authored scenario only; media repeats official upstream.",
                "allowed_use": ["metadata", "excerpt", "fulltext"],
                "redistribution_rights": "synthetic", "license_url_or_note": "Original repository synthetic text.",
                "observed_scope": f"{timeline} only, no online collection", "checked_at": None,
                "restrictions": {"max_excerpt_chars": None, "note": "Not real evidence or human labels."},
                "provenance_uri": provenance})

        def document(key, day, text, kind="official", *, version=1, upstream=None):
            paragraphs = (Paragraph(paragraph_id="p1", text=text),)
            title = f"{subject} {key}"
            return {"doc_version_id": f"{prefix}:{key}:{version}", "document_id": f"{prefix}:{key}",
                "canonical_url": f"synthetic://dev{number:02}/{key}", "source_id": source_ids[kind],
                "source_type": kind, "content_kind": "synthetic_text", "record_origin": "synthetic",
                "provenance_uri": provenance, "redistribution_rights": "synthetic", "title": title,
                "language": "en", "text_excerpt": None, "paragraphs": [p.model_dump() for p in paragraphs],
                "content_sha256": content_sha256(title, None, paragraphs),
                "cleaner_revision": "pr5-authored-nfc-lf-v1", "published_at": at(day),
                "published_time_confidence": "source_reported", "observed_at": at(day),
                "available_at": at(day), "supersedes_version_id": f"{prefix}:{key}:1" if version == 2 else None,
                "family_id": family, "upstream_document_id": upstream}

        repost_day = days[1]
        docs = [document("release", 0, initial), document("release", changed_day, changed, version=2),
                document("repost", repost_day, f"Reprint of the {subject} announcement. {initial}",
                         "media", upstream=f"{prefix}:release"),
                document("discussion", repost_day, f"Community publicity repeats the {subject} "
                         "release. Popularity is not evidence of compatibility, safety or performance.",
                         "community", upstream=f"{prefix}:release"),
                document("test", max(changed_day, 3), measured, "independent_test"),
                document("license", repost_day, f"Separate {subject} license notice: example assets "
                         "are licensed for local educational use. This is a different announcement, "
                         "not a performance, compatibility or security result."),
                document("theme", 8, f"Separate {subject} documentation theme release changes "
                         "colours only. It adds no new evidence about earlier technical claims.")]
        parsed = [DocumentVersion.model_validate_json(canonical_json(d)) for d in docs]
        release_id = f"{prefix}:event:release"
        events = []
        for key, members, day in (("release", [d["doc_version_id"] for d in docs[:5]], 0),
                                  ("license", [docs[5]["doc_version_id"]], repost_day),
                                  ("theme", [docs[6]["doc_version_id"]], 8)):
            events.append({"event_id": f"{prefix}:event:{key}", "family_id": family,
                "canonical_subject": f"{subject} {key}", "event_type": "release" if key == "release" else "other",
                "first_observed_at": at(day), "document_version_ids": members, "related_event_ids": [],
                "status": "open", "identity_note": "Authored reference, not predicted grouping or human gold.",
                "record_origin": "synthetic", "provenance_uri": provenance})
        persona = {"persona_id": f"{prefix}:developer", "persona_version_id": f"{prefix}:developer:1",
            "available_at": at(0), "persona_origin": "constructed", "domain_interests": [subject, "AI", "retrieval"],
            "current_goals": [goal], "hard_constraints": ["Only scoped evidence; local CPU deployment preferred"],
            "knowledge_known": [], "attention_budget_seconds": 420,
            "exploration_preference": "broad_but_ranked", "locale": "en"}
        personas = [persona]
        if number == 5:
            personas.append({**persona, "persona_version_id": f"{prefix}:developer:2", "available_at": at(2),
                "current_goals": ["Find academic inspiration for retrieval cache compression"],
                "hard_constraints": ["Require clearly scoped measurements; production deployment is optional"]})
        delivery_id = f"{prefix}:delivery:D0"
        prediction_id = "predicted:" + sha256_bytes(canonical_json({"members": [docs[0]["doc_version_id"]],
                                                                  "revision": "conservative-v1"}).encode())
        delivery = {"delivery_id": delivery_id, "as_of": at(0),
                    "generated_at": (epoch+timedelta(seconds=1)).isoformat()}
        items = [{"delivery_id": delivery_id, "event_prediction_id": prediction_id,
                  "members": [{k: docs[0][k] for k in ("document_id", "doc_version_id", "content_sha256")}]}]
        exposures = [{"exposure_id": f"{prefix}:included", "delivery_id": delivery_id,
                      "event_prediction_id": prediction_id, "kind": "included",
                      "occurred_at": delivery["generated_at"], "source": "synthetic_history"},
                     {"exposure_id": f"{prefix}:future-ack", "delivery_id": delivery_id,
                      "event_prediction_id": prediction_id, "kind": "acknowledged", "occurred_at": at(9),
                      "source": "synthetic_future_negative"}]
        steps, coverage, expected = [], [], []
        for day in days:
            visible = visible_versions(parsed, as_of=parse_instant(at(day)))
            windows = []
            for kind in source_ids:
                wid = f"{prefix}:coverage:{kind}:D{day}"
                gap = number == 4 and day == 5 and kind == "official"
                coverage.append({"coverage_window_id": wid, "source_id": source_ids[kind],
                    "start_at": at(0), "end_at": at(day), "observed_at": at(day),
                    "status": "service_offline" if gap else "covered",
                    "reason": "Simulated service gap; world updates unknown." if gap else ""})
                windows.append(wid)
            pv = f"{prefix}:developer:{2 if number == 5 and day >= 2 else 1}"
            steps.append({"timeline_id": timeline, "step_id": f"D{day}", "family_scope_ids": [family],
                "as_of": at(day), "persona_version_id": pv, "previous_delivery_id": delivery_id if day else None,
                "attention_budget_seconds": 420, "time_window_start": at(0), "time_window_end": at(day),
                "visible_doc_version_ids": [d.doc_version_id for d in visible], "coverage_window_ids": windows,
                "split": "dev"})
            for event in events:
                members = sorted(set(event["document_version_ids"]) & {d.doc_version_id for d in visible})
                if not members:
                    continue
                change = ("new" if day == 0 or (event["event_id"] != release_id and day == (
                    8 if event["event_id"].endswith("theme") else repost_day)) else "no_change")
                if event["event_id"] == release_id and day == changed_day:
                    change = "correction" if number in {2, 4} else "meaningful_update"
                if change == "no_change" and any(w["status"] != "covered"
                        for w in coverage if w["coverage_window_id"] in windows):
                    change = "insufficient"
                expected.append({"basis": "synthetic_test_expectation", "record_origin": "synthetic",
                    "provenance_uri": provenance, "timeline_id": timeline, "step_id": f"D{day}",
                    "persona_version_id": pv, "event_id": event["event_id"],
                    "tier": "focus" if event["event_id"] == release_id and day >= changed_day else (
                        "radar" if event["event_id"] == release_id else "archive"),
                    "graded_relevance": 3 if event["event_id"] == release_id and day >= changed_day else (
                        2 if event["event_id"] == release_id else 0),
                    "material_change": change, "supporting_doc_version_ids": members})
        relations = [{"left_doc_version_id": docs[0]["doc_version_id"],
            "right_doc_version_id": d["doc_version_id"], "relation": relation,
            "rationale": "Authored relation; same upstream differs from independent scoped evidence.",
            "evidence_at": d["available_at"], "record_origin": "synthetic", "provenance_uri": provenance}
            for d, relation in ((docs[2], "syndicated"), (docs[3], "syndicated"),
                                (docs[4], "same_event_different_evidence"),
                                (docs[5], "related_distinct_event"))]
        claims = [{"claim_id": f"{prefix}:claim:{i}", "event_id": release_id,
            "claim_text": d["paragraphs"][0]["text"], "claim_type": "measured_result" if i == 4 else "capability_claim",
            "asserted_by": d["source_id"], "evidence_refs": [{"doc_version_id": d["doc_version_id"],
                "paragraph_id": "p1", "direction": "supports"}],
            "verification_state": "independently_supported" if i == 4 else "source_attributed",
            "valid_as_of": d["available_at"], "scope": "Authored local toy scenario only",
            "limitations": ["Synthetic material, not measured real-world evidence"],
            "record_origin": "synthetic", "provenance_uri": provenance} for i, d in enumerate(docs[:5])]
        data = {"documents": docs, "events": events, "personas": personas, "steps": steps,
                "coverage_windows": coverage, "deliveries": [delivery], "delivery_items": items,
                "exposures": exposures, "event_relations": relations, "claims": claims,
                "families": [{"family_id": family, "split": "dev"}], "expectations": expected}
        for name, records in data.items():
            write_rows(folder / f"{name}.jsonl", records)
        (folder / "visible_versions.json").write_bytes(json_bytes({s["step_id"]: s["visible_doc_version_ids"] for s in steps}))
        (folder / "annotation_template.json").write_bytes(json_bytes({"template_only": True,
            "annotation_version": ANNOTATION_VERSION, "guide_revision": GUIDE_REVISION,
            "annotation_id": None, "annotator_id": None, "submitted_at": None,
            "packet_sha256": None, "initial_label": None}))
        (folder / "semantic_probe.json").write_bytes(json_bytes({"administrator_only": True,
            "claim_text": "The cited announcement establishes a million-fold gain on every platform.",
            "doc_version_id": docs[0]["doc_version_id"], "paragraph_id": "p1",
            "expected_semantic_support": "unsupported", "human_measurement": "not_measured"}))
    registry["schema_revision"] = SCHEMA_REVISION
    registry_path.write_bytes(json_bytes(registry))
    # DEV-01 bytes remain unchanged; expectations are separate administrator records.
    write_rows(root / "labels/expectations.jsonl", dev01_expectations(root))
    for name in ("annotations", "adjudications", "gold", "event_alignments", "support_reviews"):
        write_rows(root / f"labels/g1a_v1/{name}.jsonl", [])
    (root / "labels/review_session.json").write_bytes(json_bytes({"revision": "g1a-review-v1",
        "annotation_version": ANNOTATION_VERSION, "guide_revision": GUIDE_REVISION,
        "guide_sha256": sha256_bytes((root / GUIDE_FILE).read_bytes()),
        "status": "not_started", "confirmed_by": None, "confirmed_at": None,
        "participants": [], "packet_receipts": []}))


def dev01_expectations(root):
    original_docs = rows(root / "versions/documents.jsonl")
    original_events = rows(root / "events/events.jsonl")
    original_steps = rows(root / "timelines/steps.jsonl")
    original_coverage = rows(root / "timelines/coverage_windows.jsonl")
    expected = []
    for step in original_steps:
        for event in original_events:
            members = sorted(set(event["document_version_ids"]) & set(step["visible_doc_version_ids"]))
            if not members:
                continue
            release = event["event_id"].endswith("release")
            day = int(step["step_id"][1:])
            first_visible_at = min(parse_instant(s["as_of"]) for s in original_steps
                if set(event["document_version_ids"]) & set(s["visible_doc_version_ids"]))
            change = ("new" if parse_instant(step["as_of"]) == first_visible_at else
                      {4: "meaningful_update", 5: "correction"}.get(day, "no_change"))
            gap = any(w["coverage_window_id"] in step["coverage_window_ids"] and w["status"] != "covered"
                and max(parse_instant(w["start_at"]), parse_instant(step["time_window_start"])) <
                    min(parse_instant(w["end_at"]), parse_instant(step["time_window_end"]))
                for w in original_coverage)
            if change == "no_change" and gap:
                change = "insufficient"
            expected.append({"basis": "synthetic_test_expectation", "record_origin": "synthetic",
                "provenance_uri": "DEV-01/README.md", "timeline_id": "DEV-01", "step_id": step["step_id"],
                "persona_version_id": step["persona_version_id"], "event_id": event["event_id"],
                "tier": "focus" if release and day >= 4 else "radar" if release else "archive",
                "graded_relevance": 3 if release and day >= 4 else 2 if release else 0,
                "material_change": change,
                "supporting_doc_version_ids": members})
    assert len(original_docs) == 7
    return expected


def freeze(root, revision, *, frozen_at):
    path = root / "manifests/dataset_manifest.json"
    manifest = json.loads(path.read_bytes())
    if manifest["status"] == "frozen" and manifest["dataset_revision"] == revision:
        raise ContractError("FROZEN_REVISION_EXISTS")
    previous = {e["path"]: e for e in manifest["file_hashes"]}
    roles = {"documents": "documents", "events": "events", "personas": "personas", "steps": "steps",
        "coverage_windows": "coverage", "deliveries": "deliveries", "delivery_items": "delivery_items",
        "exposures": "exposures", "event_relations": "event_relations", "claims": "claims",
        "families": "families", "expectations": "fixture_expectations", "annotations": "annotations",
        "adjudications": "adjudications", "gold": "gold", "event_alignments": "event_alignments",
        "support_reviews": "support_reviews"}
    for name, model in SCHEMA_MODELS.items():
        (root / f"schema/{name}.schema.json").write_bytes(schema_text(model).encode())
    registry_path = root / "manifests/source_registry.json"
    registry = json.loads(registry_path.read_bytes())
    registry["schema_revision"] = SCHEMA_REVISION
    registry_path.write_bytes(json_bytes(registry))
    entries, documents, families = [], [], []
    for file in sorted(root.rglob("*")):
        if not file.is_file() or "__pycache__" in file.parts or file == path:
            continue
        relative = file.relative_to(root).as_posix()
        if relative.startswith("reports/") or file.name == "G1_ACCEPTANCE.md":
            continue  # External pins/reports cannot hash themselves through the Manifest.
        if file.suffix not in {".py", ".json", ".jsonl", ".md"}:
            continue
        role = previous.get(relative, {}).get("role", "support")
        count = None
        if file.suffix == ".py":
            role = "code"
        elif file.name.endswith(".schema.json"):
            role = "schema"
        elif file.suffix == ".jsonl":
            role = roles.get(file.stem, role)
            values = rows(file)
            count = len(values)
            if role == "documents":
                documents.extend(values)
            if role == "families":
                families.extend(values)
        elif relative == "manifests/source_registry.json":
            role, count = "source_registry", len(registry["sources"])
        entry = {"path": relative, "role": role, "sha256": sha256_bytes(file.read_bytes()), "record_count": count}
        if role in {"gold", "annotations", "adjudications", "event_alignments", "support_reviews"}:
            entry["annotation_version"] = (ANNOTATION_VERSION if relative.startswith("labels/g1a_v1/")
                                           else "synthetic-fixture-v1")
        entries.append(entry)
    origins = Counter(d["record_origin"] for d in documents)
    splits = Counter(f["split"] for f in families)
    hashes = {e["path"]: e["sha256"] for e in entries}
    draft = "draft" in revision
    manifest.update(dataset_revision=revision, schema_revision=SCHEMA_REVISION,
        annotation_version=ANNOTATION_VERSION, frozen_at=None if draft else frozen_at, status="draft" if draft else "frozen",
        file_hashes=entries, source_registry_sha256=hashes["manifests/source_registry.json"],
        record_origin_breakdown={k: origins[k] for k in ("real", "synthetic")},
        family_split_counts={k: splits[k] for k in ("train", "dev", "test")},
        limitations=["Five authored synthetic development stories, not independent evaluation users.",
                    "Human research is unconfirmed; AI development acceptance is a separate profile, not automatically passed.",
                    "Formal semantic change prediction and algorithm claim support unmeasured."])
    path.write_bytes(json_bytes(manifest))
    return sha256_bytes(path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--revision", default="pr5-five-trajectories-v9-ai-policy-r1")
    parser.add_argument("--frozen-at")
    args = parser.parse_args()
    if args.build:
        build_stories(args.root)
    if args.freeze:
        print(freeze(args.root, args.revision, frozen_at=args.frozen_at or datetime.now(timezone.utc).isoformat()))


if __name__ == "__main__":
    main()
