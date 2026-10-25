import json

from evals.intelligence_g2.contracts import PACKAGE, ROOT
from evals.intelligence_g2.pr6.contracts import PredictionJob
from evals.intelligence_g2.pr6.manifest import load_campaign, sha256_bytes
from evals.intelligence_g2.pr6.reproduce import make_jobs

CONFIG = PACKAGE / "manifests/pr6_ci_campaign.json"


def campaign():
    return load_campaign(CONFIG, sha256_bytes(CONFIG.read_bytes()))


def job(case, *, mode="mock", profile="standard", strategy="r1", order="canonical"):
    original = next(
        j for j in make_jobs(campaign()) if j.case_id == case and j.mode == mode and not j.prefix
    )
    from evals.intelligence_g2.pr6.contracts import digest

    args = original.model_dump(mode="json", exclude={"job_id", "schema_revision"})
    args.update(profile=profile, strategy=strategy, order=order)
    return PredictionJob(job_id=digest(args), **args)


def reference(case):
    # Tests/evaluation only. This file is not imported by any runtime worker.
    path = ROOT / "evals/intelligence_g2/fixtures/pr6/v1/reference/expected_v5.json"
    return next(c for c in json.loads(path.read_bytes())["cases"] if c["case_id"] == case)
