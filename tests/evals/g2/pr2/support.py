"""Authored synthetic scenarios; expected outcomes never enter prediction."""

from datetime import timedelta
from functools import lru_cache

from evals.intelligence_g2.contracts import G2VisibleDocument, IdentitySeed, VersionIdentity, digest
from evals.intelligence_g2.pr2.contracts import PACKAGE, PR2Config
from evals.intelligence_g2.pr2.replay import run_sequence
from evals.intelligence_v1.contracts import Paragraph
from evals.intelligence_v1.hashing import content_sha256, sha256_bytes

from ..support import input_at

FIXTURES = PACKAGE / "fixtures/pr2/v1"
CONFIG = PACKAGE / "manifests/pr2_config.json"


@lru_cache
def base():
    return input_at()


def make_input(specs, *, timeline="SYN-PR2", day=0, previous=None):
    sample = base()
    template = sample.visible_documents[0]
    cutoff = sample.context.as_of + timedelta(days=day)
    old = {d.candidate.document_id: d for d in previous.visible_documents} if previous else {}
    wrapped, seeds, sources = [], [], []
    for spec in specs:
        document_id = spec["id"]
        version_id = document_id + ":" + str(spec.get("version", 1))
        prior = old.get(document_id)
        available = (prior.candidate.available_at if prior and prior.candidate.doc_version_id == version_id
                     else cutoff)
        title = spec.get("title", "Atlas Tool v1.0 release")
        body = spec.get("body", "The Atlas Tool release provides local execution for a fixed toy workflow.")
        paragraphs = (Paragraph(paragraph_id="p1", text=body),) if body else ()
        source_id = "pr2-source:" + document_id
        candidate = template.candidate.model_copy(update={"doc_version_id": version_id,
            "document_id": document_id, "title": title, "text_excerpt": None,
            "paragraphs": paragraphs, "canonical_url": spec.get("url", "synthetic://pr2/" + document_id),
            "source_id": source_id, "upstream_document_id": spec.get("upstream"),
            "available_at": available, "observed_at": available, "published_at": available,
            "content_sha256": content_sha256(title, None, paragraphs)})
        lineage = prior.visible_lineage if prior else ()
        if not prior or prior.candidate.doc_version_id != version_id:
            lineage += (VersionIdentity(doc_version_id=version_id, document_id=document_id,
                available_at=available, supersedes_version_id=prior.candidate.doc_version_id if prior else None,
                content_sha256=candidate.content_sha256),)
        elif candidate != prior.candidate:
            raise AssertionError("a changed synthetic payload must use a new document version")
        wrapped.append(G2VisibleDocument(candidate=candidate, record_origin="synthetic",
            redistribution_rights="synthetic", provenance_uri="fixtures/pr2/v1/prediction/inputs.jsonl",
            visible_lineage=lineage))
        seeds.append(IdentitySeed(document_id=document_id, anchor_doc_version_id=lineage[0].doc_version_id,
                                  first_visible_at=lineage[0].available_at))
        sources.append(sample.sources[0].model_copy(update={"source_id": source_id,
            "source_type": candidate.source_type, "record_origin": "synthetic",
            "redistribution_rights": "synthetic", "allowed_use": ("metadata", "excerpt", "fulltext")}))
    context = sample.context.model_copy(update={"timeline_id": timeline, "step_id": "D" + str(day),
        "as_of": cutoff, "time_window_start": sample.context.as_of, "time_window_end": cutoff,
        "candidate_doc_version_ids": tuple(sorted(d.candidate.doc_version_id for d in wrapped)),
        "source_coverage": (), "exposure_history": (), "delivery_history": ()})
    return sample.model_copy(update={"dataset_id": "g2-pr2-synthetic", "dataset_revision": "g2-pr2-fixtures-v1",
        "context": context, "visible_documents": tuple(sorted(wrapped, key=lambda d: d.candidate.doc_version_id)),
        "identity_seeds": tuple(seeds), "sources": tuple(sources), "source_coverage_digest": digest([])})


def sequence(steps, *, timeline="SYN-PR2"):
    values = []
    for day, specs in steps:
        values.append(make_input(specs, timeline=timeline, day=day, previous=values[-1] if values else None))
    return tuple(values)


def run(values, strategy="r1"):
    return run_sequence(values, strategy=strategy, config=PR2Config())


def pin(path):
    return sha256_bytes(path.read_bytes())


def duplicate_specs():
    return [{"id": f"copy-{i:02}", "url": "synthetic://atlas/releases/tag/v1.0"} for i in range(10)]


def evidence_steps():
    a = {"id": "official", "url": "synthetic://atlas/releases/tag/v1.0"}
    b = {"id": "test", "title": "Atlas Tool v1.0 test", "body":
         "Target: synthetic://atlas/releases/tag/v1.0\nWe tested one toy setup; this is an unverified source report."}
    return [(0, [a]), (8, [a, b])]


def merge_split_steps():
    a = {"id": "a", "title": "Atlas Tool release"}
    b = {"id": "b", "title": "Atlas Tool release", "body": "A second announcement with an unresolved release identifier."}
    a2 = {**a, "version": 2, "title": "Atlas Tool v1.0 release", "body": "Target: synthetic://atlas/main\nRelease metadata now identifies the target."}
    b2 = {**b, "version": 2, "title": "Atlas Tool v1.0 release", "body": "Target: synthetic://atlas/main\nThis note identifies the same target."}
    b3 = {**b2, "version": 3, "title": "Atlas Tool v2.0 release", "body":
          "CORRECTION: Target: synthetic://atlas/second\nThe earlier target identifier was incorrect; this is version v2.0."}
    return [(0, [a, b]), (1, [a2, b2]), (2, [a2, b3])]


def bridge_specs():
    common = [f"common{i}" for i in range(15)]
    left, right = [f"left{i}" for i in range(5)], [f"right{i}" for i in range(5)]
    return [{"id": name, "title": "Atlas Tool release", "body":
             "Event date: 2026-01-01\n" + " ".join(words)}
            for name, words in (("a", common + left), ("b", common + left + right), ("c", common + right))]
