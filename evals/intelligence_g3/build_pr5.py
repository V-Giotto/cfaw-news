"""Author a NEW synthetic regression revision; never imported by prediction.

This explicitly reuses nonblind PR2/PR3/PR4 builders. Labels are authored from
scenario intent, not predictions. It is neither a holdout set nor human gold.
Existing inputs, source/config/required-test manifests and reports are read-only.
"""

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import PACKAGE
from .history_contracts import parse_history
from .pr5_contracts import Campaign, Case, FilePin, configuration, schema_payloads


def build():
    # Authoring-only imports. Runtime reproduction consumes the frozen JSON.
    from tests.evals.g3.budget_support import coverage_case, long_case, pool_case, protected_case
    from tests.evals.g3.history_support import revisit_case, with_history
    from tests.evals.g3.ranking_support import pool
    from tests.evals.g3.test_budget_diagnostics import native_interval_case

    folder = PACKAGE / "fixtures/pr5/v1"
    folder.mkdir(parents=True, exist_ok=False)
    cases, refs = [], {}

    def add(name, source, days=None, mode="ordinary"):
        raw = json_bytes(source)
        (folder / (name + ".json")).write_bytes(raw)
        cases.append(Case(case_id=name, input=FilePin(path=f"fixtures/pr5/v1/{name}.json",
            sha256=sha256_bytes(raw)), revisit_days=days, cohort="revisit" if days else "stress"))
        labels = []
        for c in source.replay.candidates:
            # Same synthetic product across modes/horizons is ONE family.
            family = "synthetic-product:" + c.event.canonical_subject.split()[0].lower()
            important = mode not in {"repeat", "reprint", "hold"}
            if mode == "hold":
                important = c.rule_item.tier_candidate != "hold"
            kind = mode
            if mode == "protected":
                # PR4 author's alternating correction/withdrawal products.
                from tests.evals.g3.budget_support import NAMES

                product = family.split(":")[-1]
                names = [n.lower() for n in NAMES]
                kind = ("correction" if names.index(product) % 2 == 0 else "withdrawal"
                        ) if product in names[:6] else "ordinary"
            labels.append(dict(event_key=c.event.event_key, event_revision=c.event.event_revision,
                snapshot_id=c.snapshot.snapshot_id, family_id=family, important=important,
                gain=3 if important else 0, change_kind=kind,
                duplicate=mode in {"repeat", "reprint"}, evaluable=True))
        refs[name] = labels

    for days in (1, 3, 7):
        for mode in ("repeat", "reprint", "material", "correction", "withdrawal"):
            add(f"{mode}-ack-{days}d", with_history(revisit_case(days, mode), ("acknowledged",)),
                days, mode)
        add(f"repeat-open-{days}d", with_history(revisit_case(days), ("opened",)), days, "repeat")
    add("crowded14", pool_case())
    add("protected6", protected_case(6), mode="protected")
    add("oversize", long_case(160))
    add("hold-control", with_history(pool(), ("opened",)), mode="hold")
    for status in ("unknown", "partial", "failed"):
        add("coverage-" + status, coverage_case(status))
    add("past-covered-gap", native_interval_case(((-48, -24, "covered"),)))
    reference = dict(schema_revision="g3-pr5-references-v1", origin="ai_development",
        synthetic=True, non_blind=True, independent_validation=False, human_gold=False,
        held_out=False, semantic_truth="not_evaluated", author="Codex AI",
        method="Authored scenario intent; no ranking outputs used to choose labels or weights",
        source="PR2/PR3/PR4 reused builders; correlated horizons and stress cases", cases=refs)
    ref_raw = json_bytes(reference)
    (folder / "references.json").write_bytes(ref_raw)
    value = Campaign(config_sha256=digest(configuration()), cases=tuple(cases),
        references=FilePin(path="fixtures/pr5/v1/references.json", sha256=sha256_bytes(ref_raw)))
    manifest = PACKAGE / "manifests/pr5_campaign.json"
    with manifest.open("xb") as stream:
        stream.write(json_bytes(value))
    schema_folder = PACKAGE / "schema/v5"
    schema_folder.mkdir(parents=True, exist_ok=False)
    for name, raw in schema_payloads().items():
        (schema_folder / name).write_bytes(raw)
    print("campaign_sha256=" + sha256_bytes(json_bytes(value)))
    print("cases=" + str(len(cases)))
    # Validate the authoring output through the formal schema too.
    parse_history(Campaign, data(value))


if __name__ == "__main__":
    build()
