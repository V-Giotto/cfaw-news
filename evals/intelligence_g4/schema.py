"""Explicit schema export/check for PR1; imports never create files."""

import argparse
from pathlib import Path

from evals.intelligence_g2.contracts import json_bytes

from .contracts import MODELS, RESULT_REVISION, REVISION

DIRECTORY = Path(__file__).parent / "schema/v2"


def payloads():
    return {m.__name__ + ".schema.json": json_bytes(m.model_json_schema()) for m in MODELS}


def check_schemas(folder=DIRECTORY):
    expected = payloads()
    return (set(p.name for p in folder.glob("*.schema.json")) == set(expected)
            and all((folder / name).read_bytes() == raw for name, raw in expected.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-schemas", action="store_true")
    group.add_argument("--export-schemas", action="store_true")
    args = parser.parse_args(argv)
    if args.export_schemas:
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        for name, raw in payloads().items():
            with (DIRECTORY / name).open("xb") as stream:
                stream.write(raw)
    ok = check_schemas()
    print(json_bytes(dict(ok=ok, revision=RESULT_REVISION, input_revision=REVISION)).decode(), end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
