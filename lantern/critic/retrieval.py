"""Turn a claim into numbered Evidence from a local scholarbud index.

Retrieval is lexical and local on purpose: the judge may only cite what is in this list, so the list has to be auditable and
reproducible. Records the rule under test was derived from are tagged `lineage`, never dropped, so the policy can discount them.
"""
from __future__ import annotations

from ..scholarbud import BM25Index, Library, search_chemrxiv
from ..scholarbud.types import Paper
from .lineage import is_lineage
from .types import Claim, Evidence

# Wide enough for a whole abstract. BM25 ranks on the full title and abstract, so a 600-char window used to rank a paper
# on text it then hid from the judge. The abstract that says LanM EF-hands "contain a higher number of coordination
# numbers (8-9) compared to only 7 in Calmodulin" puts that sentence at character 1450 of 1663, and every claim about a
# coordination number came back "no_evidence" while the one passage that answered them was cut off mid-abstract. A
# scientific abstract states its results last, which is exactly the half a short window drops. Keep this <=
# judge.SNIPPET_MAX_CHARS, or the judge's own cap silently re-truncates and the window here means nothing.
SNIPPET_CHARS = 2400
MIN_ABSTRACT_CHARS = 80
# PDB depositions are the measured data under test, not commentary on it. The first live run ranked the deposition of
# 8FNR itself as the best "evidence" for a claim about 8FNR; citing the data in support of itself is circular.
DATA_DEPOSIT_PREFIXES = ("10.2210/",)


def is_citable(paper: Paper) -> bool:
    """A record the judge may cite: literature with an abstract, not a data deposition."""
    doi = (paper.doi or "").lower()
    return len(paper.abstract or "") >= MIN_ABSTRACT_CHARS and not doi.startswith(DATA_DEPOSIT_PREFIXES)


def snippet_of(paper: Paper, limit: int = SNIPPET_CHARS) -> str:
    text = (paper.abstract or paper.title).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."


def retrieve(claim: Claim, index: BM25Index, lineage: set[str], k: int = 4, start: int = 1) -> list[Evidence]:
    """Top-k records for one claim, numbered from `start` in rank order.

    The pipeline passes a running `start` so evidence numbers are unique across a whole record; the policy matches a
    verdict's citations to evidence by that number and would otherwise mix up claims."""
    hits = [h for h in index.search(claim.query or claim.text, k=max(k * 5, 20)) if is_citable(h[0])][:k]
    return [Evidence(n=i, cid=p.cid, doi=p.doi, title=p.title, year=p.year, source=p.source, url=p.url,
                     snippet=snippet_of(p), score=float(s), preprint=p.preprint,
                     lineage=is_lineage(p.doi, lineage))
            for i, (p, s) in enumerate(hits, start)]


def build_index(queries: list[str], *, library: Library | None = None, rows: int = 20, live: bool = False,
                search=search_chemrxiv) -> BM25Index:
    """Index the library, optionally topped up from Crossref first. `live=False` never touches the network."""
    lib = library if library is not None else Library()
    if live:
        for q in queries:
            for paper in search(q, rows=rows):
                lib.upsert(paper)
    return BM25Index(lib.all())
