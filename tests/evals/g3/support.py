"""Only tests rehash deliberately mutated temporary copies; runtime never repairs pins."""

from uuid import uuid4

from evals.intelligence_g2.contracts import json_bytes, read_json
from evals.intelligence_g3.contracts import PACKAGE, ROOT
from evals.intelligence_g3.replay import load_input
from evals.intelligence_v1.hashing import sha256_bytes

PINS = {
    "E04-positive": "c7a97e64cf13d74251df0223def8be2095d5a79d3a4da54bd8a34a3a628497d6",
    "E06-correction": "d037b501299e941ced69a614cc669a2323cea4d0ccd0c43b37ccb6b85b1ee380",
    "E10-negative": "a9a53c69d005a8c0eba2eabdff07274b934cc16b0adc19ff6fa5c1af9703620a",
}


class Scenario:
    def __init__(self, case="E06-correction"):
        self.root = ROOT / ".tmp/evals/g3/tests" / uuid4().hex
        self.root.mkdir(parents=True)
        self.manifest = read_json((PACKAGE / "manifests" / f"pr1-{case}.json").read_bytes())
        self.payloads = {key: read_json((ROOT / self.manifest[key]["path"]).read_bytes())
                         for key in ("fixture", "personas", "history", "deliveries")}
        self.path = self.root / "input.json"

    def save(self):
        for key, value in self.payloads.items():
            p = self.root / (key + ".json")
            p.write_bytes(json_bytes(value))
            self.manifest[key] = dict(path=p.relative_to(ROOT).as_posix(),
                                      sha256=sha256_bytes(p.read_bytes()))
        self.path.write_bytes(json_bytes(self.manifest))
        return sha256_bytes(self.path.read_bytes())

    def load(self):
        return load_input(self.path, manifest_sha256=self.save())


def interaction(scenario):
    record = scenario.payloads["fixture"]["steps"][0]["record"]
    event, item, snap = record["grouping"]["events"][0], record["rule"]["items"][0], record["rule"]["snapshots"][0]
    stamp = snap["as_of"]
    result = dict(schema_revision="g3-pr1-1", interaction_id="synthetic:opened:1",
        persona_id=scenario.payloads["personas"][0]["persona"]["persona_id"],
        delivery_id="synthetic:delivery:1", target=dict(event_key=event["event_key"],
            event_revision=event["event_revision"], item_id=item["item_id"],
            snapshot_id=snap["snapshot_id"], as_of=stamp), kind="opened",
        occurred_at=stamp, available_at=stamp, source="synthetic_fixture",
        record_origin="synthetic", provenance_uri="tests/evals/g3/support.py")
    scenario.payloads["deliveries"] = [dict(schema_revision="g3-pr1-1",
        delivery=dict(delivery_id=result["delivery_id"], as_of=stamp, generated_at=stamp),
        persona_id=result["persona_id"], available_at=stamp, items=[result["target"]],
        record_origin="synthetic", provenance_uri="tests/evals/g3/support.py")]
    return result
