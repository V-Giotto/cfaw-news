"""Reuse the explicit authored PR4 walkthrough in a fresh repair-only output directory."""

import argparse
import gc
import hashlib
import json
from pathlib import Path

from cfaw_news.intelligence.contracts import digest
from cfaw_news.intelligence.runtime_contracts import FACT_PIN, RANK_PIN

from audit.g4.pr4 import local_probe

ROOT = Path(__file__).resolve().parents[3]
AREA = ROOT / ".tmp/evals/g3/g4-pr4-fix-20261102-001"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    folder = (ROOT / args.out).resolve()
    if not folder.is_relative_to(AREA):
        raise ValueError("fresh repair artifacts required")
    folder.mkdir(exist_ok=False)
    local_probe.AREA = folder
    local_probe.maintenance()
    local_probe.api()
    gc.collect()
    files = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in folder.rglob("*") if p.is_file()}
    result = dict(status="PASS", fixture_scope="AI-authored mock only; not live RSS or genuine rights proof",
        checkpoint_revision="g4-checkpoint-v2", files=files, aggregate_sha256=digest(files),
        runtime_policy_sha256=RANK_PIN, fact_signature_policy_sha256=FACT_PIN,
        external_network_calls=0, user_database_writes=0, external_model_calls=0)
    with (folder / "proof.json").open("xb") as stream:
        stream.write(local_probe.json_bytes(result))
    print(json.dumps(dict(status="PASS", files=len(files), aggregate_sha256=result["aggregate_sha256"])))


if __name__ == "__main__":
    main()
