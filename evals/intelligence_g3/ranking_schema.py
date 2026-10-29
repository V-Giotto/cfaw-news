"""Actual PR2 schema comparison, with strict CLI argument validation."""

import argparse

from evals.intelligence_g2.replay import safe_path

from .contracts import PACKAGE, ROOT, json_bytes
from .ranking_contracts import MODELS


def check_schemas(folder):
    payloads = {m.__name__ + ".schema.json": json_bytes(m.model_json_schema()) for m in MODELS}
    return ({p.name for p in folder.glob("*.schema.json")} == set(payloads)
            and all((folder / name).read_bytes() == raw for name, raw in payloads.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-schemas", action="store_true", required=True)
    parser.add_argument("--schema-dir", default=str(PACKAGE / "schema/v2"))
    args = parser.parse_args(argv)
    try:
        folder = safe_path(args.schema_dir, areas=(PACKAGE / "schema", ROOT / ".tmp/evals/g3"))
        if folder != PACKAGE / "schema/v2" and not folder.is_relative_to(ROOT / ".tmp/evals/g3"):
            raise ValueError("schema directory outside registered scope")
        if not check_schemas(folder):
            raise ValueError("schema mismatch")
    except (ValueError, OSError):
        print('{"ok":false,"code":"G3_SCHEMA_INVALID","field":"schema/v2"}')
        return 1
    print('{"ok":true,"schema":"v2"}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
