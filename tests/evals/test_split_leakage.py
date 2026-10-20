import pytest
from conftest import BASE, append_evidence_document, read_rows, refresh, write_rows

from evals.intelligence_v1.exceptions import DatasetValidationError
from evals.intelligence_v1.validate import validate_dataset


def codes(report):
    return {x.code for x in report.errors}


def test_T23_same_family_cannot_appear_in_dev_and_test(bundle):
    rows = read_rows(bundle, "families.jsonl")
    write_rows(bundle, "families.jsonl", rows + [{"family_id": rows[0]["family_id"], "split": "test"}])
    assert "CROSS_FAMILY_SPLIT" in codes(validate_dataset(refresh(bundle), strict=False))


def test_T23_counterfactual_step_retains_family(edit):
    report = validate_dataset(edit("steps.jsonl", 1, timeline_id="COUNTERFACTUAL", split="test"),
                              strict=False)
    assert "CROSS_FAMILY_SPLIT" in codes(report)


def test_T23_explicit_syndicated_upstream_cannot_hide_behind_new_family(bundle):
    families = read_rows(bundle, "families.jsonl")
    families.append(dict(family_id="family:disguised", split="test"))
    write_rows(bundle, "families.jsonl", families)
    documents = read_rows(bundle, "documents.jsonl")
    documents[2].update(family_id="family:disguised", upstream_document_id="syn:agent-x")
    write_rows(bundle, "documents.jsonl", documents)
    assert "CROSS_FAMILY_SPLIT" in codes(validate_dataset(refresh(bundle), strict=False))


def test_T23_exact_content_hash_cannot_cross_splits_with_a_different_family(bundle):
    families = read_rows(bundle, "families.jsonl")
    families.append(dict(family_id="family:copy", split="test"))
    write_rows(bundle, "families.jsonl", families)
    documents = read_rows(bundle, "documents.jsonl")
    documents.append({**documents[0], "doc_version_id": "copy:v1", "document_id": "copy",
                      "canonical_url": "synthetic://fixture/copy", "family_id": "family:copy"})
    write_rows(bundle, "documents.jsonl", documents)
    assert "CROSS_FAMILY_SPLIT" in codes(validate_dataset(refresh(bundle), strict=False))


@pytest.mark.parametrize("holder", ["claims", "gold"])
@pytest.mark.parametrize("owner_split", ["dev", "test"])
@pytest.mark.parametrize("cross_split", [False, True], ids=["same-split", "cross-split"])
def test_T23_evidence_references_respect_owner_split(bundle, holder, owner_split, cross_split):
    """A valid timestamp and locator must not permit held-out evidence in labels."""
    families = read_rows(bundle, "families.jsonl")
    families[0]["split"] = owner_split
    evidence_split = ("test" if owner_split == "dev" else "dev") if cross_split else owner_split
    families.append(dict(family_id="family:evidence-probe", split=evidence_split))
    write_rows(bundle, "families.jsonl", families)
    steps = read_rows(bundle, "steps.jsonl")
    for step in steps:
        step["split"] = owner_split
    write_rows(bundle, "steps.jsonl", steps)
    evidence = append_evidence_document(bundle, origin="synthetic",
                                        family_id="family:evidence-probe")
    # An unreferenced document in a different split is itself a legal corpus record.
    assert validate_dataset(refresh(bundle)).ok
    rows = read_rows(bundle, holder + ".jsonl")
    field = "evidence_refs" if holder == "claims" else "supporting_doc_version_ids"
    rows[0][field] = ([dict(doc_version_id=evidence["doc_version_id"], paragraph_id="p1",
                           direction="mentions")] if holder == "claims"
                      else [evidence["doc_version_id"]])
    write_rows(bundle, holder + ".jsonl", rows)
    manifest = refresh(bundle)
    report = validate_dataset(manifest, strict=False)
    if not cross_split:
        assert report.ok, report.to_dict()
        return
    assert not report.ok, "cross-split evidence was accepted"
    assert [(x.code, x.path, x.field) for x in report.errors] == [
        ("CROSS_FAMILY_SPLIT", BASE + holder + ".jsonl", field)
    ]
    with pytest.raises(DatasetValidationError) as caught:
        validate_dataset(manifest)
    assert caught.value.report.to_dict() == report.to_dict()
