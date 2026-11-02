"""Explicit local rights registry; feed existence grants no redistribution rights."""

import json
from pathlib import Path

from .contracts import LedgerError, SourcePolicy, canonical, safe_url


def policy_for(source, registry: Path | None = None) -> SourcePolicy:
    value = None
    if registry is not None and registry.exists():
        raw = json.loads(registry.read_bytes())
        if set(raw) != {"schema_revision", "sources"} or raw["schema_revision"] != (
                "g4-source-registry-v1") or not isinstance(raw["sources"], list):
            raise LedgerError("G4_POLICY_REGISTRY_INVALID")
        policies = [SourcePolicy.model_validate_json(canonical(p)) for p in raw["sources"]]
        if len({p.source_id for p in policies}) != len(policies):
            raise LedgerError("G4_POLICY_REGISTRY_INVALID")
        value = next((p for p in policies if p.source_id == source["id"]), None)
    url = safe_url(source["url"], https=True)
    if value is not None:
        if value.source_url != url or value.record_origin != "real":
            raise LedgerError("G4_POLICY_SOURCE_MISMATCH")
        return value
    return SourcePolicy(source_id=source["id"], source_url=url,
                        source_label=source["label"][:512],
                        source_role="community" if source.get("kind", "").startswith("hn")
                        else "media")
