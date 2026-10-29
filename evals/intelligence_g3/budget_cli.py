"""One pinned offline planning job. No ranking, evaluation matrix or integration."""

import argparse

from evals.intelligence_g2.contracts import data, read_json
from evals.intelligence_g2.replay import safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .budget import derive
from .budget_contracts import BriefingPlan, BudgetInput, check_schemas, schema_payloads
from .contracts import PACKAGE, ROOT, fail, json_bytes
from .history_contracts import parse_history as parse

OUTPUT_BASE = ROOT / ".tmp/evals/g3"


def export_plan(input_path, *, input_sha256, out):
    path = safe_path(input_path, areas=(OUTPUT_BASE, PACKAGE / "fixtures"), code="G3_PATH_INVALID")
    raw = path.read_bytes()
    if sha256_bytes(raw) != input_sha256:
        fail("G3_SHA_MISMATCH", "budget_input_file")
    value = parse(BudgetInput, read_json(raw))
    result = parse(BriefingPlan, dict(input=data(value), **derive(value)))
    output = safe_path(out, areas=(OUTPUT_BASE,), code="G3_PATH_INVALID")
    output.mkdir(parents=True, exist_ok=False)
    for name, payload in (("input.json", raw), ("briefing_plan.json", json_bytes(result))):
        with (output / name).open("xb") as stream:
            stream.write(payload)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input")
    parser.add_argument("--input-sha256")
    parser.add_argument("--out")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-schemas", action="store_true")
    mode.add_argument("--write-schemas", action="store_true")
    args = parser.parse_args(argv)
    if args.check_schemas or args.write_schemas:
        if args.write_schemas:
            folder = PACKAGE / "schema/v4_1"
            folder.mkdir(parents=True, exist_ok=True)
            for name, raw in schema_payloads().items():
                path = folder / name
                if path.exists() and path.read_bytes() != raw:
                    fail("G3_SCHEMA_INVALID", "existing_pr4_schema")
                if not path.exists():
                    with path.open("xb") as stream:
                        stream.write(raw)
        if not check_schemas():
            fail("G3_SCHEMA_INVALID", "schema/v4_1")
        print("g3-pr4-plan-v2")
        return 0
    if not all((args.input, args.input_sha256, args.out)):
        parser.error("--input, --input-sha256 and --out are required")
    export_plan(args.input, input_sha256=args.input_sha256, out=args.out)
    print("g3-pr4-plan-v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
