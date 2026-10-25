from datetime import timedelta

import pytest

from evals.intelligence_g2.contracts import G2Error
from evals.intelligence_g2.pr3.contracts import PR3Config
from evals.intelligence_g2.pr3.extract import extract_claims
from evals.intelligence_g2.pr3.lineage import build_source_lineage

from .support import run


@pytest.mark.parametrize("stage", ["extract", "lineage"])
def test_direct_paragraph_stage_rejects_future_candidate_before_body_access(stage):
    values, _ = run("T19")
    value = values[0]
    replay = value.grouping_input.replay_input
    wrapped = replay.visible_documents[0]
    candidate = wrapped.candidate.model_copy(update={"available_at": replay.context.as_of + timedelta(days=1)})
    replay = replay.model_copy(update={"visible_documents": (wrapped.model_copy(update={"candidate": candidate}),)})
    with pytest.raises(G2Error) as error:
        if stage == "extract":
            extract_claims(replay_input=replay, events=value.grouping_result.events, config=PR3Config())
        else:
            build_source_lineage(replay_input=replay, grouping_result=value.grouping_result, config=PR3Config())
    assert (error.value.code, error.value.stage, error.value.field, error.value.record_id) == (
        "FUTURE_VERSION", "bridge", "candidate.available_at", candidate.doc_version_id)
