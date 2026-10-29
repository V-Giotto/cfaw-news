"""PR5 score-only ablations. PR2/PR3 rankers and PR4 policy remain unchanged."""

from typing import Literal

from pydantic import model_validator

from evals.intelligence_g2.contracts import data, digest
from evals.intelligence_v1.contracts import Sha256, StrictModel

from .budget import derive, plan_briefing
from .budget_contracts import BudgetConfig, BudgetInput
from .contracts import fail
from .history_contracts import HistoryInput, parse_history
from .pr5_contracts import DISABLED, Job
from .revisit import RevisitEvent, RevisitResult, rank_revisit


class ScoreProjection(StrictModel):
    revision: Literal["g3-pr5-score-ablation-v1"] = "g3-pr5-score-ablation-v1"
    variant: Literal["no_history", "no_material", "no_novelty_material", "no_exploration", "no_duplicate"]
    base_ranking_sha256: Sha256
    disabled_score_features: tuple[str, ...]
    events: tuple[RevisitEvent, ...]


def project(base, variant):
    if variant not in DISABLED or base.algorithm_id != "p1":
        fail("G3_CONFIG_INVALID", "registered_score_ablation")
    disabled = DISABLED[variant]
    rows = []
    for row in base.events:
        terms = tuple(t.model_copy(update={"weight": 0.0, "contribution": 0.0})
                      if t.feature in disabled else t for t in row.components)
        rows.append(row.model_copy(update={"components": terms,
                    "score": round(sum(t.contribution for t in terms), base.base_config.score_decimals),
                    "reason_codes": (*row.reason_codes, "score_ablation:" + variant)}))
    rows.sort(key=lambda r: (not r.eligible, not r.protected, -r.score,
                             r.event_key, r.event_revision, r.item_id))
    return ScoreProjection(variant=variant, base_ranking_sha256=digest(base),
        disabled_score_features=disabled,
        events=tuple(r.model_copy(update={"rank": i}) for i, r in enumerate(rows, 1)))


class ExperimentInput(StrictModel):
    history_input: HistoryInput
    base_ranking: RevisitResult
    ranking: ScoreProjection
    config: BudgetConfig = BudgetConfig()

    @model_validator(mode="after")
    def bound(self):
        # Existing hard gates, identity/context, history and ordering validation
        # all run on the untouched base. The projection is fully recomputed.
        BudgetInput(history_input=self.history_input, ranking=self.base_ranking, config=self.config)
        if self.ranking != project(self.base_ranking, self.ranking.variant):
            fail("G3_EXPERIMENT_INVALID", "score_projection")
        return self


def predict(source, job: Job):
    source = source.model_copy(update={"replay": source.replay.model_copy(
        update={"attention_budget_seconds": job.budget})})
    source = parse_history(HistoryInput, data(source))
    base = rank_revisit(source, "p1" if job.variant in DISABLED else job.variant)
    if job.variant in DISABLED:
        ranking = project(base, job.variant)
        experiment = ExperimentInput(history_input=source, base_ranking=base, ranking=ranking)
        plan = derive(experiment)
    else:
        ranking = base
        plan = data(plan_briefing(source, base))
        plan.pop("input")
    raw = data(source)
    return dict(job=data(job), job_id=job.job_id, input_sha256=digest(source),
                candidate_pool_sha256=base.candidate_pool_sha256,
                context_sha256=digest(dict(as_of=raw["replay"]["as_of"],
                    persona=raw["replay"]["persona"], journal=raw["journal"],
                    deliveries=raw["replay"]["deliveries"], mappings=raw["mappings"],
                    budget=job.budget)),
                ranking=data(ranking), plan=plan)
