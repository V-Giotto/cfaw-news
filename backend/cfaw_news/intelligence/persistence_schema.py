"""Explicit PR4 Schema/OpenAPI export using an isolated configuration, without lifespan/DB writes."""

import argparse
import json
from pathlib import Path

from .boundary import DisabledStatus
from .contracts import canonical
from .corpus_trust import CorpusPrefix, DocumentWatermark
from .history_store import MIGRATION
from .persistence_contracts import MODELS
from .runtime_contracts import FACT_PIN, RANK_PIN


def payloads(scratch):
    from ..config import Settings
    from ..main import create_app
    scratch = Path(scratch).resolve()
    (scratch / "data").mkdir(parents=True, exist_ok=True)
    catalog = scratch / "data/sources.json"
    if not catalog.exists():
        catalog.write_bytes(canonical(dict(sources=[])))
    config = Settings(_env_file=None, root=scratch, database_url="sqlite:///" + (scratch / "schema-only.db").as_posix(),
        llm_mode="baseline", news_auto_refresh=False, news_media_fetch=False, news_reading_fetch=False,
        intelligence_enabled=True, intelligence_anchor=scratch / "schema-only-anchor.json")
    app = create_app(config)
    try:
        result = {m.__name__ + ".schema.json": canonical(m.model_json_schema()) + b"\n"
                  for m in (*MODELS, DisabledStatus, CorpusPrefix, DocumentWatermark)}
        result["OpenAPI.json"] = canonical(app.openapi()) + b"\n"
        result["Version.json"] = canonical(dict(revision="g4-pr4-contracts-v2", migration=MIGRATION.REVISION,
            checkpoint_revision="g4-checkpoint-v2", corpus_revision="g4-corpus-prefix-v1",
            request_namespaces=("client", "system"),
            migration_source_sha256=MIGRATION.source_sha256(), schema_sha256=MIGRATION.schema_sha256(),
            runtime_policy_sha256=RANK_PIN, fact_signature_policy_sha256=FACT_PIN)) + b"\n"
        assert not (scratch / "schema-only.db").exists()
        return result
    finally:
        app.state.database.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = payloads(args.scratch)
    if args.check:
        actual = {p.name: p.read_bytes() for p in args.directory.iterdir() if p.is_file()}
        if actual != expected:
            raise SystemExit("G4_PR4_SCHEMA_MISMATCH")
    else:
        args.directory.mkdir(parents=True, exist_ok=False)
        for name, raw in expected.items():
            with (args.directory / name).open("xb") as stream:
                stream.write(raw)
    print(json.dumps(dict(status="PASS", revision="g4-pr4-contracts-v2", artifacts=len(expected), database_created=False)))


if __name__ == "__main__":
    main()
