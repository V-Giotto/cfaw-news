"""Registered PR5 development campaign, independent of prediction/reference data."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from evals.intelligence_g2.contracts import digest, json_bytes
from evals.intelligence_v1.contracts import NonEmpty, Sha256, StrictModel

from .budget_contracts import BudgetConfig
from .contracts import PACKAGE, fail
from .history_contracts import HistoryConfig
from .ranking_contracts import RankingConfig

VARIANTS = ("b0", "b1", "b2", "b3", "b4", "p1", "no_history",
            "no_material", "no_novelty_material", "no_exploration", "no_duplicate")
DISABLED = {
    "no_history": ("novelty", "material_change", "exploration", "duplicate"),
    "no_material": ("material_change",),
    "no_novelty_material": ("novelty", "material_change"),
    "no_exploration": ("exploration",), "no_duplicate": ("duplicate",),
}


def configuration():
    return dict(revision="g3-pr5-score-ablation-v1", ranking=RankingConfig().model_dump(mode="json"),
                history=HistoryConfig().model_dump(mode="json"),
                budget=BudgetConfig().model_dump(mode="json"),
                disabled={name: list(features) for name, features in DISABLED.items()},
                safety="eligibility_and_mandatory_update_protection_always_preserved",
                ndcg_k=10, budgets=[180, 420, 900], horizons=[1, 3, 7], seeds=[1, 719])


class FilePin(StrictModel):
    path: NonEmpty
    sha256: Sha256


class Case(StrictModel):
    case_id: NonEmpty
    input: FilePin
    revisit_days: Literal[1, 3, 7] | None
    cohort: Literal["revisit", "stress"]
    data_source: Literal["synthetic_ai_development_reused_nonblind"] = (
        "synthetic_ai_development_reused_nonblind")


class Campaign(StrictModel):
    schema_revision: Literal["g3-pr5-campaign-v1"] = "g3-pr5-campaign-v1"
    profile: Literal["ai_development"] = "ai_development"
    config_sha256: Sha256
    references: FilePin
    cases: tuple[Case, ...]
    independent_test_set: Literal[False] = False
    human_gold: Literal[False] = False

    @model_validator(mode="after")
    def registered(self):
        if (self.config_sha256 != digest(configuration()) or not self.cases
                or len({c.case_id for c in self.cases}) != len(self.cases)
                or {c.revisit_days for c in self.cases if c.cohort == "revisit"} != {1, 3, 7}):
            fail("G3_CAMPAIGN_INVALID", "config_or_cases")
        return self


class Job(StrictModel):
    case_id: NonEmpty
    budget: Literal[180, 420, 900]
    variant: Literal["b0", "b1", "b2", "b3", "b4", "p1", "no_history", "no_material",
                     "no_novelty_material", "no_exploration", "no_duplicate"]

    @property
    def job_id(self):
        return f"{self.case_id}--{self.budget}--{self.variant}"


class Metric(StrictModel):
    numerator: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    denominator: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    value: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    sample_count: Annotated[int, Field(ge=0)]
    event_family_count: Annotated[int, Field(ge=0)]
    data_source: NonEmpty = "synthetic_ai_development_reused_nonblind"
    undefined_reason: NonEmpty | None

    @model_validator(mode="after")
    def ratio(self):
        if (min(self.numerator, self.denominator, self.sample_count, self.event_family_count) < 0
                or (self.denominator == 0 and (self.numerator != 0 or self.value is not None
                                              or not self.undefined_reason))
                or (self.denominator > 0 and (self.value != self.numerator / self.denominator
                                             or self.undefined_reason is not None))):
            fail("G3_METRIC_INVALID", "ratio")
        return self


def schema_payloads():
    from .experiments import ExperimentInput, ScoreProjection

    return {m.__name__ + ".schema.json": json_bytes(m.model_json_schema())
            for m in (Campaign, Job, Metric, ExperimentInput, ScoreProjection)}


def check_schemas():
    folder = PACKAGE / "schema/v5"
    return ({p.name for p in folder.glob("*.schema.json")} == set(schema_payloads())
            and all((folder / p).read_bytes() == raw for p, raw in schema_payloads().items()))


if __name__ == "__main__":
    if not check_schemas():
        fail("G3_SCHEMA_INVALID", "schema/v5")
    print("g3-pr5-campaign-v1")
