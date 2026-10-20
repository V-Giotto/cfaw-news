import json
import subprocess
import sys

import pytest
from conftest import BASE, SOURCE, read_rows, refresh, write_rows

from evals.intelligence_v1.exceptions import DatasetValidationError
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes
from evals.intelligence_v1.validate import validate_dataset


def save_manifest(path, value):
    path.write_bytes((canonical_json(value) + "\n").encode())


def codes(report):
    return {x.code for x in report.errors}


def test_shipped_bundle_and_complete_three_steps():
    report = validate_dataset(SOURCE / "manifests/dataset_manifest.json")
    assert report.ok
    # PR1's three-step fixture remains intact; DEV-01 adds seven versions/six steps.
    assert len(read_rows(SOURCE, "documents.jsonl")) == 4
    assert len(read_rows(SOURCE, "steps.jsonl")) == 3
    assert report.counts["documents"] == 11 and report.counts["steps"] == 9
    assert report.counts["gold"] == 3
    assert report.manifest_sha256 == sha256_bytes(
        (SOURCE / "manifests/dataset_manifest.json").read_bytes())
    assert report.pending and {x.code for x in report.filtered} == {"FUTURE_VERSION", "FUTURE_EXPOSURE"}


def test_T22_one_byte_gold_tamper_stops_before_parsing_and_does_not_repair(bundle):
    path = refresh(bundle, frozen=True)
    gold = bundle / BASE / "gold.jsonl"
    gold.write_bytes(gold.read_bytes() + b" ")
    before = gold.read_bytes(), path.read_bytes()
    report = validate_dataset(path, strict=False)
    assert codes(report) == {"SHA_MISMATCH"} and report.counts == {}
    with pytest.raises(DatasetValidationError) as caught:
        validate_dataset(path)
    assert caught.value.report.to_dict() == report.to_dict()
    assert before == (gold.read_bytes(), path.read_bytes())


def test_manifest_self_hash_and_path_sensitivity(bundle):
    path = refresh(bundle)
    manifest = json.loads(path.read_bytes())
    manifest["file_hashes"].append(dict(path="manifests/dataset_manifest.json", role="support",
                                         sha256=sha256_bytes(path.read_bytes()), record_count=None))
    save_manifest(path, manifest)
    assert "MANIFEST_SELF_HASH" in codes(validate_dataset(path, strict=False))


def test_unlisted_input_and_missing_file_are_not_silently_ignored(bundle):
    path = refresh(bundle)
    extra = bundle / "fixtures/valid/unlisted.jsonl"
    extra.write_bytes(b"{}\n")
    assert "UNLISTED_INPUT" in codes(validate_dataset(path, strict=False))
    extra.unlink()
    (bundle / BASE / "gold.jsonl").unlink()
    assert "FILE_MISSING" in codes(validate_dataset(path, strict=False))


def test_record_counts_registry_hash_and_revision(bundle):
    path = refresh(bundle)
    manifest = json.loads(path.read_bytes())
    entry = next(e for e in manifest["file_hashes"] if e["role"] == "gold")
    entry["record_count"] += 1
    manifest["source_registry_sha256"] = "0" * 64
    save_manifest(path, manifest)
    assert {"RECORD_COUNT_MISMATCH", "SHA_MISMATCH"} <= codes(validate_dataset(path, strict=False))
    manifest["schema_revision"] = "unsupported"
    save_manifest(path, manifest)
    assert codes(validate_dataset(path, strict=False)) == {"UNSUPPORTED_REVISION"}


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}\n', b'{"a":NaN}\n', b'not json\n',
                                  b'\xef\xbb\xbf{}\n', b'{}\r\n', b'{}'])
def test_bad_jsonl_encoding_duplicates_and_nonfinite(bundle, raw):
    (bundle / BASE / "gold.jsonl").write_bytes(raw)
    path = refresh(bundle)
    assert "INVALID_JSON" in codes(validate_dataset(path, strict=False))


def test_GOLD01_future_support_and_missing_paragraph(edit):
    path = edit("gold.jsonl", 0, supporting_doc_version_ids=["syn:agent-x:v2"])
    assert "FUTURE_EVIDENCE" in codes(validate_dataset(path, strict=False))
    path = edit("claims.jsonl", 0, evidence_refs=[
        dict(doc_version_id="syn:agent-x:v1", paragraph_id="p999", direction="supports")
    ])
    assert "CITATION_NOT_FOUND" in codes(validate_dataset(path, strict=False))


def test_schema_drift_fails_after_file_hash_is_valid(bundle):
    (bundle / "schema/document_version.schema.json").write_bytes(b"{}\n")
    assert "SCHEMA_INVALID" in codes(validate_dataset(refresh(bundle), strict=False))


@pytest.mark.parametrize("contents", [None, b"{}\n"], ids=["valid-schema", "invalid-schema"])
def test_required_schema_cannot_be_disguised_as_support(bundle, contents):
    relative = "schema/document_version.schema.json"
    if contents is not None:
        (bundle / relative).write_bytes(contents)
    path = refresh(bundle)
    manifest = json.loads(path.read_bytes())
    next(e for e in manifest["file_hashes"] if e["path"] == relative)["role"] = "support"
    save_manifest(path, manifest)
    report = validate_dataset(path, strict=False)
    assert not report.ok, "a required schema was accepted under a different role"
    assert any(x.code == "SCHEMA_INVALID" and x.path == relative and x.field == "role"
               for x in report.errors)


@pytest.mark.parametrize("kind,expected", [
    ("synthetic-url", "PROVENANCE_INVALID"), ("manifest-path", "MANIFEST_PATH_INVALID"),
])
@pytest.mark.parametrize("interface", ["api", "cli"])
def test_malformed_input_keeps_json_report_contract(bundle, kind, expected, interface):
    path = refresh(bundle)
    if kind == "synthetic-url":
        rows = read_rows(bundle, "documents.jsonl")
        rows[0]["canonical_url"] = "synthetic://["
        write_rows(bundle, "documents.jsonl", rows)
        path = refresh(bundle)
    else:
        manifest = json.loads(path.read_bytes())
        manifest["file_hashes"][0]["path"] = "bad\u0000input.py"
        save_manifest(path, manifest)
    if interface == "api":
        report = validate_dataset(path, strict=False)
        assert not report.ok and expected in codes(report)
        with pytest.raises(DatasetValidationError) as caught:
            validate_dataset(path, strict=True)
        assert caught.value.report.to_dict() == report.to_dict()
    else:
        reports = []
        for flags in ([], ["--strict"]):
            result = subprocess.run(
                [sys.executable, "-B", "-m", "evals.intelligence_v1.validate",
                 "--manifest", str(path), *flags],
                capture_output=True, text=True, timeout=20,
            )
            assert result.returncode == 1, result.stderr
            report = json.loads(result.stdout)
            assert not report["ok"] and expected in {x["code"] for x in report["errors"]}
            assert "Traceback" not in result.stderr
            reports.append(report)
        assert reports[0] == reports[1]


def test_malformed_manifest_location_returns_domain_report(bundle):
    # Python callers can supply a NUL even though a shell cannot pass it in argv.
    location = str(bundle / "bad\u0000root/manifests/dataset_manifest.json")
    report = validate_dataset(location, strict=False)
    assert not report.ok and codes(report) == {"MANIFEST_PATH_INVALID"}
    with pytest.raises(DatasetValidationError) as caught:
        validate_dataset(location)
    assert caught.value.report.to_dict() == report.to_dict()


def test_T10_empty_candidates_and_unknown_coverage_are_legal(bundle):
    # A scenario before any observation is legal; no brief or global-no-change claim exists.
    steps = read_rows(bundle, "steps.jsonl")
    steps[0].update(as_of="2026-01-01T00:00:00Z", time_window_start="2025-12-31T00:00:00Z",
                    time_window_end="2026-01-01T00:00:00Z", coverage_window_ids=[])
    # At exactly D0 v1 is visible, so move observations later without inventing publication.
    documents = read_rows(bundle, "documents.jsonl")
    documents[0]["observed_at"] = documents[0]["available_at"] = "2026-01-01T01:00:00Z"
    steps[0]["visible_doc_version_ids"] = []
    write_rows(bundle, "documents.jsonl", documents)
    write_rows(bundle, "steps.jsonl", steps)
    write_rows(bundle, "gold.jsonl", [])
    claims = read_rows(bundle, "claims.jsonl")
    claims[0]["valid_as_of"] = "2026-01-01T01:00:00Z"
    write_rows(bundle, "claims.jsonl", claims)
    report = validate_dataset(refresh(bundle))
    assert report.ok
