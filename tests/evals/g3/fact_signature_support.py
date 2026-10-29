"""Authored synthetic native G2 scenarios; never imported by prediction code."""

from functools import lru_cache

from evals.intelligence_g2.contracts import data, json_bytes
from evals.intelligence_g3.history_contracts import HistoryInput

from .history_support import with_history
from .ranking_support import native_replay

CASES = {
    "symbol-ack": ("latency < 50 ms", "latency > 50 ms", "ack", "version", True),
    "symbol-persona": ("latency < 50 ms", "latency > 50 ms", "old_persona", "version", True),
    "symbol-ack-persona": ("latency < 50 ms", "latency > 50 ms", "both", "version", True),
    "inclusive": ("latency <= 50 ms", "latency >= 50 ms", "ack", "version", True),
    "equality": ("latency = 50 ms", "latency != 50 ms", "ack", "version", True),
    "numeric": ("latency < 50 ms", "latency < 60 ms", "ack", "version", True),
    "decimal": ("latency < 0.5 ms", "latency < 0.05 ms", "ack", "version", True),
    "unit": ("latency < 50 ms", "latency < 50 s", "ack", "version", True),
    "unit-case": ("memory < 50 MB", "memory < 50 mB", "ack", "version", True),
    "word-control": ("latency < 50 ms", "latency above 50 ms", "ack", "version", True),
    "unchanged-version": ("latency < 50 ms", "latency < 50 ms", "ack", "version", False),
    "unchanged-reprint": ("latency < 50 ms", "latency < 50 ms", "ack", "reprint", False),
    "current-persona": ("latency < 50 ms", "latency > 50 ms", "current_persona", "version", False),
}


def statement(condition):
    return ("Atlas Tool v1.0 claims a speed gain of 40%. Task: summarization; Dataset: ToySet; "
            "Baseline: Base v1.0; Protocol: P1; Hardware: CPU; Conditions: " + condition + ";")


@lru_cache
def scenario(name):
    old, new, knowledge, mode, _ = CASES[name]
    first = dict(id="official", title="Atlas Tool v1.0 release", body=statement(old),
                 url="synthetic://atlas/releases/v1")
    if mode == "reprint":
        second = [first, dict(id="copy", title=first["title"], body=statement(new),
                              upstream="official", url=first["url"])]
    else:
        second = [{**first, "version": 2, "body": statement(new)}]
        if old == new:
            # A native document version cannot repeat the exact content hash.
            # Change editorial metadata while preserving the attributed fact.
            second[0]["title"] = "Atlas Tool v1.0 release metadata update"
    for product in ("Boreal", "Ember", "Fjord", "Cedar", "Delta"):
        second.append(dict(id=product.lower(), title=f"{product} Kit v1.0 release",
            body=f"{product} Kit provides local evaluation and tooling for agents."))
    source = with_history(native_replay([(0, [first]), (3, second)]),
                          ("acknowledged",) if knowledge in {"ack", "both"} else ())
    raw = data(source)
    raw["replay"]["attention_budget_seconds"] = 180
    raw["replay"]["persona"]["persona"]["knowledge_known"] = (
        [statement(old)] if knowledge in {"old_persona", "both"} else
        [statement(new)] if knowledge == "current_persona" else [])
    # Roundtrip through the real public wire validator, including all native G2
    # event/evidence/view bindings. No copied or edited G2 outputs are fabricated.
    return HistoryInput.model_validate_json(json_bytes(raw))


def target(value):
    return value.replay.deliveries[0].items[0].event_key
