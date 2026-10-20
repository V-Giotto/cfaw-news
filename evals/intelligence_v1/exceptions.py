"""Transport-independent errors. Diagnostics contain identifiers, never evidence text."""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Issue:
    code: str
    path: str = ""
    line: int | None = None
    record_id: str = ""
    field: str = ""


class ContractError(ValueError):
    def __init__(self, code: str, *, field: str = "", record_id: str = ""):
        super().__init__(code)
        self.code = code
        self.field = field
        self.record_id = record_id


@dataclass
class ValidationReport:
    manifest_sha256: str = ""
    counts: dict[str, int] = field(default_factory=dict)
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    filtered: list[Issue] = field(default_factory=list)
    pending: tuple[str, ...] = (
        "claim_semantic_support", "real_provenance_and_license_review",
        "independent_annotation", "replay_rankers_metrics", "undeclared_semantic_lineage",
    )

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        def ordered(items):
            return [asdict(item) for item in sorted(
                items, key=lambda x: (x.path, x.line or 0, x.code, x.record_id, x.field)
            )]
        return {
            "ok": self.ok, "manifest_sha256": self.manifest_sha256,
            "counts": dict(sorted(self.counts.items())), "errors": ordered(self.errors),
            "warnings": ordered(self.warnings), "filtered": ordered(self.filtered),
            "pending": list(self.pending),
        }


class DatasetValidationError(ValueError):
    def __init__(self, report: ValidationReport):
        super().__init__("DATASET_INVALID")
        self.report = report
