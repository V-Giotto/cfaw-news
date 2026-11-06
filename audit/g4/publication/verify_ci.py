"""Verify the explicitly amended G4 CI profile without changing frozen G3 assets."""

import argparse
import json
from pathlib import Path

from audit.g4.h09_review.test_control import verify_execution, verify_inventory
from audit.g4.pr6.freeze import sha
from evals.intelligence_g3.junit_inventory import verify_junit


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def execution(path, **kwargs):
    record = read(path)
    base = Path(path).with_suffix(".frozen-runner.json")
    assert sha(base) == record["frozen_runner_receipt_sha256"]
    assert read(base) == record["frozen_runner"]
    verify_execution(record, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--collect-control", type=Path, required=True)
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--full-control", type=Path)
    parser.add_argument("--basetemp", type=Path)
    args = parser.parse_args()
    if any((args.junit, args.full_control, args.basetemp)) and not all((args.junit, args.full_control, args.basetemp)):
        parser.error("full verification requires junit, full-control and basetemp together")
    inventory = args.inventory.resolve()
    required = verify_inventory(read(inventory))
    execution(args.collect_control, mode="collect", inventory=str(inventory))
    result = dict(status="PASS", profile="g4-exact-retry-amendment-v1", nodes=len(required["nodes"]),
                  original_unamended_g3_profile_claimed=False)
    if args.junit:
        execution(args.full_control, mode="full", junit=str(args.junit.resolve()), basetemp=str(args.basetemp.resolve()))
        result["junit"] = verify_junit(required, args.junit)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
