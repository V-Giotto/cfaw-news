"""Export/check PR2 wire schemas without changing frozen PR1/G1/G2/G3 artifacts."""

import argparse
from pathlib import Path

from .contracts import CoverageWindow, G4DocumentVersion, SourcePolicy, canonical

MODELS = (SourcePolicy, G4DocumentVersion, CoverageWindow)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = {m.__name__ + ".schema.json": canonical(m.model_json_schema()) + b"\n" for m in MODELS}
    if args.check:
        actual = {p.name: p.read_bytes() for p in args.directory.iterdir() if p.is_file()}
        if actual != expected:
            raise SystemExit("G4_PR2_SCHEMA_MISMATCH")
    else:
        args.directory.mkdir(parents=True, exist_ok=True)
        for name, payload in expected.items():
            with (args.directory / name).open("xb") as stream:
                stream.write(payload)
    print("g4-document-ledger-v1: 3 schemas PASS")


if __name__ == "__main__":
    main()
