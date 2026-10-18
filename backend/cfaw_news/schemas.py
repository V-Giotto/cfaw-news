from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GoalInput(StrictModel):
    name: str = Field(min_length=2, max_length=100)
    purpose: str = Field(min_length=4, max_length=800)
    scope: str = Field(default="", max_length=500)
    constraints: str = Field(default="", max_length=500)
    keywords: list[str] = Field(default_factory=list, max_length=16)
    trial_requested: bool = False

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values):
        if any(not value.strip() or len(value) > 60 for value in values):
            raise ValueError("关键词需为 1–60 字符")
        return list(dict.fromkeys(value.strip() for value in values))


class GoalUpdate(GoalInput):
    expected_version: int = Field(ge=1)
    status: Literal["active", "paused"] = "active"


class CheckInput(StrictModel):
    expected_version: int = Field(ge=1)


class Citation(StrictModel):
    article_id: str = Field(min_length=1, max_length=100)
    paragraph_id: str = Field(min_length=1, max_length=30)


class Proposal(StrictModel):
    title: str = Field(min_length=2, max_length=100)
    content: str = Field(min_length=4, max_length=600)
    duration_minutes: int = Field(ge=10, le=60)
    kind: Literal["verification", "trial"] = "verification"


class Judgment(StrictModel):
    outcome: Literal["update", "no_change", "insufficient_evidence", "needs_review"]
    change_kind: Literal["new", "updated", "withdrawn", "unchanged", "candidates_changed"]
    summary: str = Field(min_length=4, max_length=900)
    next_step: str = Field(min_length=2, max_length=400)
    material_change: str = Field(default="", max_length=400)
    uncertainties: list[str] = Field(default_factory=list, max_length=6)
    citations: list[Citation] = Field(default_factory=list, max_length=12)
    proposal: Proposal | None = None

    @field_validator("uncertainties")
    @classmethod
    def bounded_uncertainties(cls, values):
        if any(not value or len(value) > 300 for value in values):
            raise ValueError("待核实条件需为 1–300 字符")
        return values


class DecisionInput(StrictModel):
    choice: Literal["watch", "handled", "dismissed"]
    reason: str = Field(default="", max_length=300)


class ApprovalInput(StrictModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def valid_interval(self):
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("时间必须包含时区")
        seconds = (self.end - self.start).total_seconds()
        if seconds <= 0 or seconds > 3600:
            raise ValueError("核实/试用安排需为不超过 60 分钟的有效时段")
        return self


class RefreshInput(StrictModel):
    source_ids: list[str] = Field(min_length=1, max_length=32)
