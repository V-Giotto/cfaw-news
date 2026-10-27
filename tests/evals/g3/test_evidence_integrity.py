"""Wire-level evidence, native content, historical revision and coverage regressions."""

import copy

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.contracts import G3ReplayInput
from evals.intelligence_g3.replay import export_input
from evals.intelligence_v1.exceptions import ContractError

from .support import Scenario, interaction


@pytest.fixture(scope="module")
def replay():
    return data(Scenario().load())


@pytest.mark.parametrize("entry", ["load", "export", "json"])
@pytest.mark.parametrize("fault", ["current_support", "current_link", "membership_event"])
def test_current_evidence_cannot_claim_support_or_dangle(entry, fault):
    s = Scenario()
    if entry == "json":
        raw = data(s.load())
        evidence = raw["evidence"]
    else:
        evidence = s.payloads["fixture"]["steps"][-1]["record"]["evidence"]
    if fault == "current_support":
        evidence["assessments"][0]["verification_state"] = "independently_supported"
    elif fault == "current_link":
        evidence["assessments"][0]["evidence_link_ids"] = ["missing:link"]
    else:
        evidence["memberships"][0]["event_key"] = "missing:event"
    if entry == "json" and "observations" in raw:
        raw["observations"][-1]["evidence"] = copy.deepcopy(evidence)
    with pytest.raises((ContractError, ValidationError)):
        if entry == "json":
            G3ReplayInput.model_validate_json(json_bytes(raw))
        elif entry == "load":
            s.load()
        else:
            export_input(s.path, manifest_sha256=s.save(), out=s.root / "rejected")
    assert not (s.root / "rejected").exists()


@pytest.mark.parametrize("fault", ["fact", "uncertainty", "view_digest", "claim_archive"])
def test_formal_native_identity_rejects_rewritten_facts(replay, fault):
    raw = copy.deepcopy(replay)
    c = raw["candidates"][0]
    if fault == "fact":
        c["rule_item"]["what_happened"]["text"] = "Forged source fact."
        c["presentation"]["base_item"] = copy.deepcopy(c["rule_item"])
    elif fault == "uncertainty":
        assert c["rule_item"]["uncertainties"]
        c["rule_item"]["uncertainties"] = []
        c["presentation"]["base_item"] = copy.deepcopy(c["rule_item"])
    elif fault == "view_digest":
        c["g2_view_sha256"] = "0" * 64
    else:
        raw["evidence"]["next_state"]["claims"] = []
    if "observations" in raw:
        raw["observations"][-1]["candidates"] = copy.deepcopy(raw["candidates"])
        raw["observations"][-1]["evidence"] = copy.deepcopy(raw["evidence"])
    with pytest.raises((ContractError, ValidationError)):
        G3ReplayInput.model_validate_json(json_bytes(raw))


def test_historical_reference_revision_is_bound_to_original_observation():
    s = Scenario()
    s.payloads["history"] = [interaction(s)]
    raw = data(s.load())
    old_id = raw["history"][0]["target"]["snapshot_id"]
    assert old_id != raw["candidates"][0]["snapshot"]["snapshot_id"]
    next(r for r in raw["published_refs"] if r["snapshot_id"] == old_id)["event_revision"] = "f" * 64
    raw["history"][0]["target"]["event_revision"] = "f" * 64
    raw["deliveries"][0]["items"][0]["event_revision"] = "f" * 64
    with pytest.raises((ContractError, ValidationError)):
        G3ReplayInput.model_validate_json(json_bytes(raw))


def empty_coverage_scenario():
    """Native G2 APIs create an empty pool with two real-shaped synthetic windows."""
    from evals.intelligence_g2.contracts import G2ReplayInput
    from evals.intelligence_g2.pr2.contracts import PR2Config
    from evals.intelligence_g2.pr2.replay import run_sequence as group
    from evals.intelligence_g2.pr3.contracts import EvidenceInput, PR3Config
    from evals.intelligence_g2.pr3.pipeline import run_evidence_step
    from evals.intelligence_g2.pr4.contracts import PR4Config
    from evals.intelligence_g2.pr4.replay import run_sequence as rule
    from tests.evals.g2.support import input_at

    s = Scenario("E10-negative")
    step = s.payloads["fixture"]["steps"][0]
    raw = step["replay_input"]
    stamp = raw["context"]["as_of"]
    template = data(input_at().sources[0])
    raw["sources"] = [{**template, "source_id": "synthetic:source:" + str(i)} for i in range(2)]
    raw["context"]["source_coverage"] = [dict(coverage_window_id="synthetic:coverage:" + str(i),
        source_id="synthetic:source:" + str(i), start_at=stamp, end_at=stamp, observed_at=stamp,
        status=status, reason="explicit synthetic coverage fixture") for i, status in enumerate(("covered", "failed"))]
    raw["source_coverage_digest"] = digest(raw["context"]["source_coverage"])
    value = G2ReplayInput.model_validate_json(json_bytes(raw))
    inputs, results = group([value], strategy="r1", config=PR2Config())
    evidence_input = EvidenceInput(grouping_input=inputs[0], grouping_result=results[0],
        grouping_config=PR2Config(), config_sha256=digest(PR3Config()))
    evidence = run_evidence_step(evidence_input=evidence_input, config=PR3Config())
    _, items = rule([evidence_input], [evidence], config=PR4Config())
    step["record"].update(grouping=data(results[0]), evidence=data(evidence), rule=data(items[0]),
        pool_sha256=digest(dict(context=data(value.context), documents=[], sources=[data(p) for p in value.sources],
                                manifest=value.input_manifest_sha256)))
    return s


def test_empty_pool_keeps_pinned_coverage_and_diagnostics():
    value = empty_coverage_scenario().load()
    assert not value.candidates and len(value.source_coverage) == 2
    assert any(g.code == "source_failed" for g in value.evidence.validation.coverage_gaps)
    assert G3ReplayInput.model_validate_json(json_bytes(value)) == value
    raw = data(value)
    raw["source_coverage"] = []
    with pytest.raises((ContractError, ValidationError)):
        G3ReplayInput.model_validate_json(json_bytes(raw))


@pytest.mark.parametrize("fault", ["current_support", "archive_support", "assessment_link", "membership_event",
                                   "bundle_assessment", "claim_archive", "citation_archive", "view_digest",
                                   "fact", "uncertainty", "coverage_digest", "future", "removed", "duplicate"])
def test_past_observations_cannot_be_rewritten_or_dropped(replay, fault):
    raw = copy.deepcopy(replay)
    observation = raw["observations"][0]
    evidence = observation["evidence"]
    candidate = observation["candidates"][0]
    if fault in {"current_support", "archive_support"}:
        collection = evidence if fault == "current_support" else evidence["next_state"]
        collection["assessments"][0]["verification_state"] = "independently_supported"
    elif fault == "assessment_link":
        evidence["assessments"][0]["evidence_link_ids"] = ["missing:link"]
    elif fault == "membership_event":
        evidence["memberships"][0]["event_key"] = "missing:event"
    elif fault == "bundle_assessment":
        evidence["bundles"][0]["assessments"] = []
    elif fault in {"claim_archive", "citation_archive"}:
        evidence["next_state"]["claims" if fault == "claim_archive" else "citations"] = []
    elif fault == "view_digest":
        candidate["g2_view_sha256"] = "0" * 64
    elif fault == "fact":
        candidate["rule_item"]["what_happened"]["text"] = "Forged old fact."
        candidate["presentation"]["base_item"] = copy.deepcopy(candidate["rule_item"])
    elif fault == "uncertainty":
        candidate["rule_item"]["uncertainties"] = []
        candidate["presentation"]["base_item"] = copy.deepcopy(candidate["rule_item"])
    elif fault == "coverage_digest":
        observation["source_coverage_digest"] = "0" * 64
    elif fault == "future":
        evidence["assessments"][0]["as_of"] = raw["as_of"]
    elif fault == "removed":
        raw["observations"].pop(0)
    else:
        raw["observations"].insert(0, copy.deepcopy(observation))
    with pytest.raises((ContractError, ValidationError)):
        G3ReplayInput.model_validate_json(json_bytes(raw))


def test_empty_coverage_cannot_be_dropped_from_both_copies_under_original_digest():
    raw = data(empty_coverage_scenario().load())
    assert raw["source_coverage"] == raw["observations"][-1]["source_coverage"]
    raw["source_coverage"] = raw["observations"][-1]["source_coverage"] = []
    with pytest.raises((ContractError, ValidationError), match="G3_REFERENCE_MISMATCH"):
        G3ReplayInput.model_validate_json(json_bytes(raw))


@pytest.mark.parametrize("fault", ["candidate", "coverage", "evidence", "identity"])
def test_final_projection_must_equal_last_observation(replay, fault):
    raw = copy.deepcopy(replay)
    if fault == "candidate":
        raw["observations"][-1]["candidates"] = []
    elif fault == "coverage":
        raw["source_coverage"] = [dict(coverage_window_id="foreign", source_id="foreign",
            start_at=raw["as_of"], end_at=raw["as_of"], observed_at=raw["as_of"], status="covered", reason="synthetic")]
    elif fault == "evidence":
        raw["evidence"]["validation"]["coverage_gaps"] = []
    else:
        raw["identity_state"]["registry"][0]["status"] = "dormant"
    with pytest.raises((ContractError, ValidationError)):
        G3ReplayInput.model_validate_json(json_bytes(raw))


@pytest.mark.parametrize("revision", ["g3-pr1-1", "g3-pr1-2"])
def test_previous_formal_revisions_require_reexport(replay, revision):
    raw = copy.deepcopy(replay)
    raw["schema_revision"] = revision
    with pytest.raises(ValidationError):
        G3ReplayInput.model_validate_json(json_bytes(raw))


def test_observation_archive_is_required(replay):
    raw = copy.deepcopy(replay)
    del raw["observations"]
    with pytest.raises(ValidationError):
        G3ReplayInput.model_validate_json(json_bytes(raw))


def test_historical_links_resolve_in_original_observation_not_current_links(replay):
    old = {link["link_key"] for link in replay["observations"][0]["evidence"]["links"]}
    current = {link["link_key"] for link in replay["evidence"]["links"]}
    assert old - current
    assert G3ReplayInput.model_validate_json(json_bytes(replay))


@pytest.mark.parametrize("fault", ["fact", "uncertainty", "retained_view_digest"])
def test_even_reminted_native_ids_cannot_bypass_grounding_or_original_view(replay, fault):
    from evals.intelligence_g2.pr4.contracts import IntelligenceItem, ItemSnapshot
    from evals.intelligence_g2.pr4.snapshots import identify
    from evals.intelligence_g2.pr5.pipeline import identify as identify_presentation
    from evals.intelligence_g2.pr6.contracts import G3InputView

    raw = copy.deepcopy(replay)
    candidate = raw["candidates"][0]
    old_id = candidate["snapshot"]["snapshot_id"]
    if fault == "uncertainty":
        candidate["rule_item"]["uncertainties"] = []
    else:
        candidate["rule_item"]["what_happened"]["text"] = "Forged source fact with reminted IDs."
    item = identify(IntelligenceItem.model_validate_json(json_bytes(candidate["rule_item"])))
    p = candidate["presentation"]
    presentation = identify_presentation(item, p["headline"], p["body"], p["style_id"], tuple(p["claim_order"]), p["selection"])
    snapshot = ItemSnapshot.model_validate_json(json_bytes(candidate["snapshot"]))
    sha = digest(dict(item_id=item.item_id, as_of=snapshot.as_of.isoformat(), bundle_sha256=snapshot.bundle_sha256))
    snapshot = snapshot.model_copy(update=dict(item_id=item.item_id, snapshot_id="g2:snapshot:" + sha))
    candidate.update(rule_item=data(item), presentation=data(presentation), snapshot=data(snapshot))
    view = G3InputView(event_key=item.event_key, event_revision=item.event_revision, as_of=snapshot.as_of.isoformat(),
        bundle=candidate["bundle"], rule_item=data(item), presentation=data(presentation), snapshot=data(snapshot),
        source_coverage=tuple(data(w) for w in item.source_coverage), lineage_ids=snapshot.lineage_ids,
        trace_pointer=candidate["trace_pointer"])
    if fault != "retained_view_digest":
        candidate["g2_view_sha256"] = digest(view)
    raw["observations"][-1]["candidates"] = copy.deepcopy(raw["candidates"])
    raw["item_snapshots"] = [data(snapshot) if s["snapshot_id"] == old_id else s for s in raw["item_snapshots"]]
    for ref in raw["published_refs"]:
        if ref["snapshot_id"] == old_id:
            ref.update(item_id=item.item_id, snapshot_id=snapshot.snapshot_id)
    code = "G2_PR4_FACT_PROVENANCE_INVALID" if fault == "fact" else "G3_REFERENCE_MISMATCH"
    with pytest.raises((ContractError, ValidationError), match=code):
        G3ReplayInput.model_validate_json(json_bytes(raw))


@pytest.mark.parametrize("diagnostic", ["coverage_gaps", "independent_count"])
def test_empty_pool_cannot_drop_required_diagnostics_or_claim_independent_count(diagnostic):
    raw = data(empty_coverage_scenario().load())
    for result in (raw["evidence"], raw["observations"][-1]["evidence"]):
        if diagnostic == "coverage_gaps":
            result["validation"]["coverage_gaps"] = []
            result["validation"]["counts"]["coverage_gaps"] = 0
        else:
            result["validation"]["counts"]["confirmed_independent_support"] = 1
    with pytest.raises((ContractError, ValidationError)):
        G3ReplayInput.model_validate_json(json_bytes(raw))
