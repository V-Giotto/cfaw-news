import json
from datetime import datetime

import pytest

from evals.intelligence_v1.contracts import Delivery, DocumentVersion, Exposure, PersonaVersion
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.temporal import (
    parse_instant,
    previous_delivery,
    project_candidate,
    require_visible_version,
    visible_exposures,
    visible_persona,
    visible_versions,
)


def records(bundle, name, model):
    return [model.model_validate_json(line)
            for line in next(bundle.rglob(name)).read_bytes().splitlines()]


def test_T01_future_corpus_is_valid_but_not_a_candidate(bundle):
    docs = records(bundle, "documents.jsonl", DocumentVersion)
    cutoff = parse_instant("2026-10-20T00:00:00Z")
    future = docs[-1]
    assert future not in visible_versions(docs, as_of=cutoff)
    for function in (require_visible_version, project_candidate):
        with pytest.raises(ContractError, match="FUTURE_VERSION"):
            function(future, as_of=cutoff)
    projected = [project_candidate(x, as_of=cutoff).model_dump_json()
                 for x in visible_versions(docs, as_of=cutoff)]
    assert "FAR_FUTURE_SECRET" not in "".join(projected)


def test_T02_late_observation_and_inclusive_boundary(bundle):
    docs = records(bundle, "documents.jsonl", DocumentVersion)
    late = docs[2]
    assert late.published_at < late.observed_at == late.available_at
    assert late not in visible_versions(docs, as_of=parse_instant("2026-01-02T00:00:00Z"))
    assert late in visible_versions(docs, as_of=late.available_at)


def test_T20_future_feedback_rejected_without_mutating_knowledge(bundle):
    rows = records(bundle, "exposures.jsonl", Exposure)
    personas = records(bundle, "personas.jsonl", PersonaVersion)
    before = tuple(p.model_dump_json() for p in personas)
    cutoff = parse_instant("2026-01-09T00:00:00Z")
    with pytest.raises(ContractError, match="FUTURE_EXPOSURE"):
        visible_exposures(rows, as_of=cutoff)
    visible, filtered = visible_exposures(rows, as_of=cutoff, strict=False)
    assert [x.kind for x in visible] == ["included", "opened"]
    assert [(x.code, x.record_id) for x in filtered] == [("FUTURE_EXPOSURE", "exposure:ack")]
    assert tuple(p.model_dump_json() for p in personas) == before


def test_persona_and_previous_delivery_gates(bundle):
    personas = records(bundle, "personas.jsonl", PersonaVersion)
    deliveries = records(bundle, "deliveries.jsonl", Delivery)
    assert visible_persona(personas, persona_id="persona:developer",
                           as_of=personas[1].available_at) == personas[1]
    with pytest.raises(ContractError, match="FUTURE_PERSONA"):
        visible_persona(personas, persona_id="persona:developer",
                        as_of=parse_instant("2025-01-01T00:00:00Z"))
    with pytest.raises(ContractError, match="FUTURE_DELIVERY"):
        previous_delivery(deliveries, "delivery:d3", as_of=deliveries[0].generated_at)
    assert previous_delivery(deliveries, None, as_of=deliveries[0].generated_at) is None


def test_TZ01_equal_instants_and_offset_string_misordering():
    a, b = "2026-10-20T08:00:00+08:00", "2026-10-20T00:00:00Z"
    assert parse_instant(a) == parse_instant(b)
    earlier, later = "2026-10-20T08:00:00+08:00", "2026-10-20T01:00:00Z"
    assert earlier > later and parse_instant(earlier) < parse_instant(later)


@pytest.mark.parametrize("value,code", [
    ("2026-10-20T00:00:00", "NAIVE_DATETIME"), ("2026-10-20", "INVALID_DATETIME"),
    ("2026-02-30T00:00:00Z", "INVALID_DATETIME"), ("2026-01-01T00:00:00+24:00", "INVALID_DATETIME"),
    ("2026-01-01T00:00:00+00:60", "INVALID_DATETIME"),
    ("2026-01-01T00:00:00-00:00", "INVALID_DATETIME"),
    ("2026-01-01T00:00:00.1234567Z", "INVALID_DATETIME"), (0, "INVALID_DATETIME"),
])
def test_TZ02_rejects_ambiguous_or_invalid_time(value, code):
    with pytest.raises(ContractError, match=code):
        parse_instant(value)


def test_naive_cutoff_is_rejected(bundle):
    with pytest.raises(ContractError, match="NAIVE_DATETIME"):
        visible_versions([], as_of=datetime(2026, 1, 1))


def test_all_shipped_negative_cases(bundle, edit):
    from evals.intelligence_v1.validate import validate_dataset

    cases = json.loads((bundle / "fixtures/invalid/cases.json").read_bytes())
    # Each parameter gets an independent copy, including its manifest.
    import shutil
    from pathlib import Path

    from conftest import BASE, refresh, write_rows

    for index, case in enumerate(cases):
        root = bundle.parent / f"case-{index}"
        shutil.copytree(bundle, root)
        if case["entry"] == "instant":
            with pytest.raises(ContractError, match=case["expected_code"]):
                parse_instant(case["value"])
            continue
        if case["entry"] == "exposure":
            rows = records(root, "exposures.jsonl", Exposure)
            with pytest.raises(ContractError, match=case["expected_code"]):
                visible_exposures([rows[case["index"]]], as_of=parse_instant(case["as_of"]))
            continue
        manifest_path = root / "manifests/dataset_manifest.json"
        if case["entry"] == "manifest":
            manifest = json.loads(manifest_path.read_bytes())
            manifest["file_hashes"][0].update(case["changes"])
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        else:
            rows = [json.loads(x) for x in (root / BASE / case["target"]).read_bytes().splitlines()]
            rows[case["index"]].update(case["changes"])
            write_rows(root, case["target"], rows)
            manifest_path = refresh(root)
        report = validate_dataset(Path(manifest_path), strict=False)
        assert not report.ok and case["expected_code"] in {x.code for x in report.errors}, case
