"""T23 must hold before prediction, including when reference files are absent."""

import json

import pytest
from conftest import append_evidence_document, read_rows, refresh, write_rows
from test_loader import loaded

from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.validate import validate_dataset


def holdout(root, defect=None, split="test"):
    families = read_rows(root, "families.jsonl")
    families.append(dict(family_id="family:holdout", split=split))
    write_rows(root, "families.jsonl", families)
    independent = append_evidence_document(root, origin="synthetic", family_id="family:holdout")
    documents = read_rows(root, "documents.jsonl")
    original, copy = documents[0], documents[-1]
    if defect == "sha":
        copy.update({k: original[k] for k in ("title", "text_excerpt", "paragraphs",
                                             "content_sha256")})
    elif defect == "url":
        copy["canonical_url"] = original["canonical_url"]
    elif defect == "family":
        copy.update(document_id=original["document_id"],
                    available_at="2026-01-01T12:00:00Z",
                    supersedes_version_id=original["doc_version_id"])
    elif defect in {"upstream", "upstream_same_split"}:
        copy["upstream_document_id"] = original["document_id"]
    elif defect == "upstream_missing":
        copy["upstream_document_id"] = "missing:document"
    elif defect == "upstream_future":
        copy["upstream_document_id"] = "syn:future"
        copy["family_id"] = original["family_id"]
    write_rows(root, "documents.jsonl", documents)

    personas = read_rows(root, "personas.jsonl")
    persona = {**personas[0], "persona_id": "persona:holdout",
               "persona_version_id": "persona:holdout:1"}
    if defect == "persona":
        persona = personas[0]
    else:
        if defect == "persona_history":
            persona.update(persona_id=personas[0]["persona_id"],
                           available_at="2026-01-01T12:00:00Z")
        personas.append(persona)
    write_rows(root, "personas.jsonl", personas)
    steps = read_rows(root, "steps.jsonl")
    steps.append({**steps[0], "timeline_id": "HOLDOUT", "split": split,
                  "family_scope_ids": ["family:holdout"],
                  "persona_version_id": persona["persona_version_id"],
                  "visible_doc_version_ids": [independent["doc_version_id"]]})
    if defect == "timeline":
        steps[-1]["timeline_id"] = steps[0]["timeline_id"]
        steps[-1]["step_id"] = "holdout"
    if defect == "scope":
        steps[-1]["family_scope_ids"] = [families[0]["family_id"]]
    if defect == "upstream_same_split":
        families[-1]["split"] = "dev"
        steps[-1]["split"] = "dev"
        write_rows(root, "families.jsonl", families)
    if defect == "upstream_future":
        steps.pop()  # Only derivation metadata is invalid, independent of replay scope.
    write_rows(root, "steps.jsonl", steps)
    return refresh(root)


@pytest.mark.parametrize("defect", ["sha", "url", "family", "upstream",
                                   "upstream_same_split", "persona", "persona_history",
                                   "timeline", "scope"])
def test_T23_prediction_and_full_validation_reject_split_leakage(bundle, defect):
    manifest = holdout(bundle, defect)
    assert "CROSS_FAMILY_SPLIT" in {e.code for e in validate_dataset(manifest, strict=False).errors}
    # Fail at bundle loading, before a caller can request any step or ranking.
    with pytest.raises(ContractError, match="^CROSS_FAMILY_SPLIT$"):
        loaded(bundle)


@pytest.mark.parametrize("defect,code", [("upstream_missing", "REFERENCE_NOT_FOUND"),
                                       ("upstream_future", "FUTURE_EVIDENCE")])
def test_prediction_validates_derivation_metadata(bundle, defect, code):
    manifest = holdout(bundle, defect)
    assert code in {e.code for e in validate_dataset(manifest, strict=False).errors}
    with pytest.raises(ContractError, match=f"^{code}$"):
        loaded(bundle)


@pytest.mark.parametrize("split", ["train", "test"])
def test_T23_independent_holdout_ranks_without_reference_files(bundle, split):
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.loader import load_step

    manifest = holdout(bundle, split=split)
    assert validate_dataset(manifest).ok
    entries = json.loads(manifest.read_bytes())["file_hashes"]
    for entry in entries:
        if entry["role"] in {"gold", "events", "claims", "annotations", "adjudications",
                             "event_relations"}:
            (bundle/entry["path"]).unlink()
    data = loaded(bundle)
    context, candidates = load_step(data, timeline_id="HOLDOUT", step_id="D1", config=data.config)
    ranked = get_ranker("b1", data.config).rank(context, candidates)
    assert len(ranked) == 1 and context.persona.persona_id == "persona:holdout"
    assert context.candidate_doc_version_ids == ("evidence:synthetic:v1",)


@pytest.mark.parametrize("defect", ["sha", "persona_history"])
def test_T23_step_and_cli_reject_before_output_without_reference_files(bundle, tmp_path, defect):
    from evals.intelligence_v1.hashing import sha256_bytes
    from evals.intelligence_v1.loader import load_step
    from evals.intelligence_v1.replay import main

    manifest = holdout(bundle, defect)
    for entry in json.loads(manifest.read_bytes())["file_hashes"]:
        if entry["role"] in {"gold", "events", "claims", "annotations", "adjudications",
                             "event_relations"}:
            (bundle/entry["path"]).unlink()
    with pytest.raises(ContractError, match="^CROSS_FAMILY_SPLIT$"):
        data = loaded(bundle)
        load_step(data, timeline_id="HOLDOUT", step_id="D1", config=data.config)
    out = tmp_path/"rejected"
    assert main(["--manifest", str(manifest), "--manifest-sha256", sha256_bytes(manifest.read_bytes()),
                 "--algo", "b1", "--split", "test", "--out", str(out)]) == 1
    assert not out.exists()
