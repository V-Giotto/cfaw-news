import pytest

from evals.intelligence_g2.contracts import G1_PIN, ROOT, digest
from evals.intelligence_g2.pr2.contracts import PR2Config
from evals.intelligence_g2.pr2.replay import load_sequence
from evals.intelligence_g2.pr2.replay import run_sequence as group_sequence
from evals.intelligence_g2.pr3.contracts import PR3Config
from evals.intelligence_g2.pr3.replay import run_sequence


@pytest.mark.parametrize("strategy", ["r0", "r1", "r2"])
def test_all_35_frozen_g1_steps_inherit_exact_parent_identity_and_partition(strategy):
    tasks = [(f"DEV-{n:02}", "D8") for n in range(1, 6)] + [("REVISIT-7D", "D8"), ("SYN-PR1", "D6")]
    count = 0
    for timeline, last in tasks:
        values, _ = load_sequence(ROOT / "evals/intelligence_v1/manifests/dataset_manifest.json",
            pin=G1_PIN, timeline_id=timeline, through_step=last)
        inputs, groups = group_sequence(values, strategy=strategy, config=PR2Config())
        fingerprints = [digest(g) for g in groups]
        outputs = run_sequence(inputs, groups, grouping_config=PR2Config(), config=PR3Config())
        for group, result in zip(groups, outputs, strict=True):
            assert {(e.event_key, e.event_revision, e.member_doc_version_ids) for e in group.events} == {
                (b.event_key, b.event_revision, b.current_doc_version_ids) for b in result.bundles}
            assert result.validation.ok
            assert not any(a.verification_state == "independently_supported" for a in result.assessments)
            count += 1
        assert [digest(g) for g in groups] == fingerprints
    assert count == 35
