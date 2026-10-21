"""Shared records for the critic. Plain dataclasses, JSON-serialisable through as_dict().

THE CONTRACT. The critic reads numbers the deterministic pipeline already produced and comments on them against
literature. It never writes, edits or re-scores a number. A Verdict is commentary; the Policy turns commentary into at most
a flag ("badge") or a demotion to human review, never a promotion.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

LABELS = ("supports", "contradicts", "no_evidence")


@dataclass(frozen=True)
class Claim:
    """One checkable statement derived from a discovery record.

    `kind` is "number" when it states a measured value (a coordination number, a distance) and "qualitative" otherwise.
    `query` is the text used to retrieve literature. `source_field` says where in the record it came from, so a verdict can
    be traced back to the number it comments on.
    """
    id: str
    text: str
    kind: str = "qualitative"
    query: str = ""
    source_field: str = ""
    value: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Evidence:
    """A retrieved passage the judge may cite. `n` is the 1-based number shown to the judge and cited back."""
    n: int
    cid: str
    doi: str = ""
    title: str = ""
    year: int | None = None
    source: str = ""
    url: str = ""
    snippet: str = ""
    score: float = 0.0
    preprint: bool = False
    lineage: bool = False   # True when this record is one the rule under test was derived from

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Verdict:
    """The judge's reading of one claim. `cited` holds Evidence numbers that survived the post-check."""
    claim_id: str
    label: str = "no_evidence"
    cited: tuple = ()
    confidence: float = 0.0
    rationale: str = ""
    downgraded: str = ""    # non-empty when the post-check changed the judge's answer, and why

    def __post_init__(self):
        if self.label not in LABELS:
            raise ValueError(f"label must be one of {LABELS}, got {self.label!r}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")

    def as_dict(self) -> dict:
        d = asdict(self)
        d["cited"] = list(self.cited)
        return d
