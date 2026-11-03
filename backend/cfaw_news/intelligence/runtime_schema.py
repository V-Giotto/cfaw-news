"""Versioned PR3 schemas; no modifications to native or prior G4 schemas."""

import argparse
from pathlib import Path

from evals.intelligence_g2.contracts import json_bytes

from .runtime_contracts import (
    RuntimeConfig,
    RuntimeEnvelope,
    RuntimePlan,
    RuntimeRanking,
    RuntimeResult,
)

MODELS = (RuntimeConfig, RuntimeEnvelope, RuntimeRanking, RuntimePlan, RuntimeResult)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = {m.__name__ + ".schema.json": json_bytes(m.model_json_schema()) for m in MODELS}
    if args.check:
        actual = {p.name: p.read_bytes() for p in args.directory.iterdir() if p.is_file()}
        if actual != expected:
            raise SystemExit("G4_PR3_SCHEMA_MISMATCH")
    else:
        args.directory.mkdir(parents=True, exist_ok=False)
        for name, body in expected.items():
            (args.directory / name).write_bytes(body)
    print("g4-pr3-runtime-envelope-v1: 5 schemas PASS")


if __name__ == "__main__":
    main()
