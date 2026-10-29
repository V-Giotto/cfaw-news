"""Author a new nonblind regression campaign; never rewrite the PR5 v1 inputs."""

from evals.intelligence_g2.contracts import data, digest, json_bytes, read_json
from evals.intelligence_v1.hashing import sha256_bytes

from .artifacts import load_campaign, write
from .contracts import PACKAGE
from .fact_signature import policy
from .pr5_contracts import Campaign, Case, FilePin

BASE_PIN = "56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf"


def build():
    from tests.evals.g3.fact_signature_support import CASES, scenario, target

    base = load_campaign(PACKAGE / "manifests/pr5_campaign.json", BASE_PIN)
    references = read_json((PACKAGE / base.references.path).read_bytes())
    assert sha256_bytes(json_bytes(references)) == base.references.sha256
    folder = PACKAGE / "fixtures/pr5/fact_signature_v2"
    folder.mkdir(parents=True, exist_ok=False)
    cases = list(base.cases)
    for name, spec in CASES.items():
        value = scenario(name)
        raw = json_bytes(value)
        case_id = "fact-" + name
        write(folder, name + ".json", raw)
        cases.append(Case(case_id=case_id, input=FilePin(
            path=f"fixtures/pr5/fact_signature_v2/{name}.json", sha256=sha256_bytes(raw)),
            revisit_days=3, cohort="revisit"))
        labels = []
        for candidate in value.replay.candidates:
            selected = candidate.event.event_key == target(value)
            important = selected and spec[-1]
            labels.append(dict(event_key=candidate.event.event_key,
                event_revision=candidate.event.event_revision, snapshot_id=candidate.snapshot.snapshot_id,
                family_id="synthetic-product:" + candidate.event.canonical_subject.split()[0].lower(),
                important=important, gain=3 if important else 0,
                change_kind="material" if important else "repeat" if selected else "ordinary",
                duplicate=selected and name in {"unchanged-version", "unchanged-reprint"}, evaluable=True))
        references["cases"][case_id] = labels
    references.update(author="Codex AI", method="Existing PR5 labels preserved; added labels from authored case intent, not rankings",
        source="PR5 v1 reused nonblind development plus authored native G2 symbol/quantity/unit/reprint regression cases")
    raw_refs = json_bytes(references)
    write(folder, "references.json", raw_refs)
    campaign = Campaign.model_validate_json(json_bytes({**data(base),
        "cases": [data(c) for c in cases], "references": dict(
        path="fixtures/pr5/fact_signature_v2/references.json", sha256=sha256_bytes(raw_refs))}))
    manifest = PACKAGE / "manifests/pr5_fact_signature_campaign.json"
    with manifest.open("xb") as stream:
        stream.write(json_bytes(campaign))
    write(folder, "provenance.json", dict(base_campaign_pin=BASE_PIN, fact_signature_policy=policy(),
        source="tests/evals/g3/fact_signature_support.py", added_cases=len(CASES),
        profile="ai_development", synthetic=True, non_blind=True, held_out=False,
        independent_validation=False, human_gold=False, external_requests=0, model_calls=0,
        scoring_configuration_sha256=campaign.config_sha256,
        signature_policy_sha256=digest(policy())))
    print("campaign_sha256=" + sha256_bytes(json_bytes(campaign)))
    print("cases=" + str(len(cases)))


if __name__ == "__main__":
    build()
