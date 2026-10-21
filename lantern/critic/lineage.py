"""Which retrieved papers are 'lineage': the ones a rule under test was derived from.

The policy counts lineage evidence at a fraction of an external source's weight (see policy.py), so the critic cannot
confirm a rule just by retrieving the papers it came from. This module decides which DOIs are lineage.

Two sources. First, DOIs mentioned in the repo's own provenance documents (ROADMAP.md, IMPLEMENTATION_PLAN.md, README.md,
docs/SCIENTIFIC_CONTRACT.md), since those cite the papers the project's rules were built on. Second, an explicit list in
`data/critic_lineage.json`, a plain JSON array of DOI strings. The DOIs of the papers the CN>=9 and loop-spacing rules
were derived from belong in that file; it ships empty. Missing files are not an error: they simply contribute nothing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# A DOI is "10." + registrant + "/" + suffix; the suffix runs to whitespace or a markup delimiter.
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s<>\"'`\[\]*]+", re.IGNORECASE)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVENANCE_DOCS = ("ROADMAP.md", "IMPLEMENTATION_PLAN.md", "README.md", "docs/SCIENTIFIC_CONTRACT.md")
LINEAGE_JSON = "data/critic_lineage.json"
_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:")


def _clean(doi: str) -> str:
    doi = doi.strip()
    while doi:
        last = doi[-1]
        if last in ".,;:!?'\"":
            doi = doi[:-1]
        elif last == ")" and doi.count(")") > doi.count("("):   # keep balanced parens, e.g. 10.1016/S0092-8674(00)81-5
            doi = doi[:-1]
        elif last in "}>" :
            doi = doi[:-1]
        else:
            break
    return doi.lower()


def lineage_from_text(text: str) -> set[str]:
    return {d for d in (_clean(m) for m in DOI_RE.findall(text or "")) if d}


def lineage_from_files(paths) -> set[str]:
    out: set[str] = set()
    for p in paths:
        try:
            out |= lineage_from_text(Path(p).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return out


def load_lineage(extra_file=None, root=None) -> set[str]:
    """DOIs from the provenance docs plus data/critic_lineage.json plus an optional extra JSON list file."""
    root = Path(root) if root is not None else REPO_ROOT
    out = lineage_from_files(root / d for d in PROVENANCE_DOCS)
    for f in (root / LINEAGE_JSON, extra_file):
        if f is None:
            continue
        try:
            items = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str):
                    out |= lineage_from_text(item) or {_clean(item)} if item.strip() else set()
    return out


def is_lineage(paper_doi: str, lineage) -> bool:
    d = (paper_doi or "").strip().lower()
    for pre in _PREFIXES:
        if d.startswith(pre):
            d = d[len(pre):]
            break
    d = _clean(d)
    return bool(d) and d in {_clean(x) for x in lineage}
