"""The one record shared by every scholarbud module and by the critic."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Paper:
    """A literature record as retrieved. Only what the source states; nothing model-written.

    `abstract` is plain text (JATS markup stripped). `source` names where it came from ("chemrxiv", "crossref",
    "arxiv"). `preprint` is True for ChemRxiv and arXiv items, which are not peer reviewed.
    """
    doi: str = ""
    title: str = ""
    abstract: str = ""
    year: int | None = None
    source: str = ""
    url: str = ""
    license: str = ""
    preprint: bool = False
    arxiv_id: str = ""

    @property
    def cid(self) -> str:
        """Canonical id used for dedup and citation: DOI, else arXiv id, else a title hash."""
        import hashlib
        import re
        if self.doi:
            return "doi:" + self.doi.strip().lower()
        if self.arxiv_id:
            return "arxiv:" + self.arxiv_id.strip().lower()
        t = re.sub(r"\W+", " ", self.title.lower()).strip()
        return "title:" + hashlib.sha1(t.encode()).hexdigest()[:16]

    def as_dict(self) -> dict:
        d = asdict(self)
        d["cid"] = self.cid
        return d
