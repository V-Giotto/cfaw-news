"""Temporary copies only. Rehashing is test preparation, never validator behavior."""

import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from evals.intelligence_v1.hashing import canonical_json, sha256_bytes

SOURCE = Path(__file__).resolve().parents[2] / "evals/intelligence_v1"
BASE = "fixtures/valid/minimal_three_step/"


def read_rows(root, name):
    return [json.loads(line) for line in (root / BASE / name).read_text("utf-8").splitlines()]


def write_rows(root, name, rows):
    (root / BASE / name).write_bytes(
        "".join(canonical_json(row) + "\n" for row in rows).encode()
    )


def append_evidence_document(root, *, origin, family_id):
    """Add an independent test document; never edit the checked-in corpus or labels."""
    from evals.intelligence_v1.contracts import DocumentVersion, Paragraph
    from evals.intelligence_v1.hashing import content_sha256
    from evals.intelligence_v1.temporal import parse_instant, visible_versions

    documents = read_rows(root, "documents.jsonl")
    document = {
        **documents[0], "doc_version_id": f"evidence:{origin}:v1",
        "document_id": f"evidence:{origin}", "family_id": family_id,
        "title": f"Independent {origin} evidence boundary probe",
    }
    if origin == "synthetic":
        paragraph = Paragraph(paragraph_id="p1", text="Independent synthetic evidence probe.")
        document.update(canonical_url="synthetic://fixture/evidence-probe",
                        text_excerpt=paragraph.text, paragraphs=[paragraph.model_dump()],
                        content_sha256=content_sha256(document["title"], paragraph.text,
                                                     (paragraph,)))
    else:
        document.update(record_origin="real", source_id="github-blog", content_kind="feed_summary",
                        canonical_url="https://github.blog/feed/",
                        provenance_uri="https://github.blog/feed/", redistribution_rights="unknown",
                        text_excerpt=None, paragraphs=[], content_sha256=None)
    documents.append(document)
    write_rows(root, "documents.jsonl", documents)
    # Keep the control scenario valid when a same-scope document becomes visible.
    parsed = [DocumentVersion.model_validate_json(canonical_json(row)) for row in documents]
    steps = read_rows(root, "steps.jsonl")
    for step in steps:
        scoped = [row for row in parsed if row.family_id in step["family_scope_ids"]]
        step["visible_doc_version_ids"] = [row.doc_version_id for row in visible_versions(
            scoped, as_of=parse_instant(step["as_of"])
        )]
    write_rows(root, "steps.jsonl", steps)
    return document


def refresh(root, *, frozen=False):
    path = root / "manifests/dataset_manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest["dataset_revision"] = "independent-test-copy"
    manifest["status"] = "frozen" if frozen else "draft"
    manifest["frozen_at"] = manifest["created_at"] if frozen else None
    for entry in manifest["file_hashes"]:
        file = root / entry["path"]
        if not file.is_file():
            continue
        raw = file.read_bytes()
        entry["sha256"] = sha256_bytes(raw)
        if entry["path"].endswith(".jsonl"):
            entry["record_count"] = len(raw.splitlines())
        if entry["role"] == "source_registry":
            entry["record_count"] = len(json.loads(raw)["sources"])
            manifest["source_registry_sha256"] = entry["sha256"]
    def role_rows(role):
        return [json.loads(line) for entry in manifest["file_hashes"] if entry["role"] == role
                and (root / entry["path"]).is_file()
                for line in (root / entry["path"]).read_bytes().splitlines()]

    docs = role_rows("documents")
    origins = Counter(row["record_origin"] for row in docs)
    manifest["record_origin_breakdown"] = {k: origins[k] for k in ("real", "synthetic")}
    families = {r["family_id"]: r["split"] for r in role_rows("families")}
    splits = Counter(families.values())
    manifest["family_split_counts"] = {k: splits[k] for k in ("train", "dev", "test")}
    path.write_bytes((canonical_json(manifest) + "\n").encode())
    return path


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "bundle"
    shutil.copytree(SOURCE, root, ignore=shutil.ignore_patterns("__pycache__"))
    refresh(root)
    return root


@pytest.fixture
def edit(bundle):
    def change(name, index, **changes):
        rows = read_rows(bundle, name)
        rows[index].update(changes)
        write_rows(bundle, name, rows)
        return refresh(bundle)
    return change
