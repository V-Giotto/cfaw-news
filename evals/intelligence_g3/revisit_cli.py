"""Pinned PR3 offline ranking export, one algorithm per invocation; no matrix/planner."""

import argparse

from evals.intelligence_g2.contracts import json_bytes, read_json
from evals.intelligence_g2.replay import safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import PACKAGE, ROOT, fail
from .history_contracts import HistoryInput, check_schemas, parse_history, schema_payloads
from .revisit import rank_revisit

OUTPUT_BASE = ROOT / ".tmp/evals/g3"


def export_revisit(input_path, *, input_sha256, out, algorithm="p1"):
    path = safe_path(input_path, areas=(OUTPUT_BASE, PACKAGE / "fixtures"), code="G3_PATH_INVALID")
    raw = path.read_bytes()
    if sha256_bytes(raw) != input_sha256:
        fail("G3_SHA_MISMATCH", "history_input_file")
    value = parse_history(HistoryInput, read_json(raw))
    result = rank_revisit(value, algorithm)
    output = safe_path(out, areas=(OUTPUT_BASE,), code="G3_PATH_INVALID")
    # Validate everything before creating artifacts; an existing output is never reused.
    output.mkdir(parents=True, exist_ok=False)
    with (output / "input.json").open("xb") as stream:
        stream.write(raw)
    with (output / "ranking.json").open("xb") as stream:
        stream.write(json_bytes(result))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input")
    parser.add_argument("--input-sha256")
    parser.add_argument("--out")
    parser.add_argument("--algorithm", choices=("b0", "b1", "b2", "b3", "b4", "p1"), default="p1")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-schemas", action="store_true")
    mode.add_argument("--write-schemas", action="store_true")
    args = parser.parse_args(argv)
    if args.check_schemas or args.write_schemas:
        if args.write_schemas:
            folder = PACKAGE / "schema/v3"
            folder.mkdir(parents=True, exist_ok=True)
            for name, raw in schema_payloads().items():
                path = folder / name
                if path.exists() and path.read_bytes() != raw:
                    fail("G3_SCHEMA_INVALID", "existing_pr3_schema")
                if not path.exists():
                    with path.open("xb") as stream:
                        stream.write(raw)
        if not check_schemas():
            fail("G3_SCHEMA_INVALID", "schema/v3")
        print("g3-pr3-history-v1")
        return 0
    if not all((args.input, args.input_sha256, args.out)):
        parser.error("--input, --input-sha256 and --out are required")
    export_revisit(args.input, input_sha256=args.input_sha256, out=args.out, algorithm=args.algorithm)
    print("g3-pr3-ranking-v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
