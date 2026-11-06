"""Explain the retained real pilot's rejected whole-document paragraph without publishing."""

import json

from cfaw_news.database import Database
from cfaw_news.intelligence.persistence_models import BriefingRun
from cfaw_news.intelligence.runtime import run
from sqlalchemy import select

from audit.g4.pr6.freeze import ROOT, write
from evals.intelligence_g2.contracts import json_bytes


def main():
    base = ROOT / ".tmp/evals/g3/g4-pr6-20261105-001"
    database = Database("sqlite:///" + (base / "pilot-accepted/pilot.db").as_posix())
    try:
        with database.session() as session:
            row = session.scalar(select(BriefingRun))
            raw, pin = json_bytes(row.input), row.input_sha256
        result = run(raw, expected_sha256=pin)
        gaps = [g.code for stage in result.stages for g in stage.evidence.validation.coverage_gaps]
        assert "whole_paragraph_quote_limit" in gaps
        assert not result.stages[-1].evidence.next_state.claims
        out = base / "long-paragraph-proof"
        write(out / "result.json", dict(status="PASS_SAFE_REJECTION", input_sha256=pin,
            record_origin="real", source="unmodified MIT README in one overlong paragraph",
            gaps=gaps, extracted_claims=0, fabricated_claims=0, output_state=result.state,
            publication_performed=False, external_network_calls=0))
        print(json.dumps(dict(status="PASS_SAFE_REJECTION", gaps=gaps)))
    finally:
        database.engine.dispose()


if __name__ == "__main__":
    main()
