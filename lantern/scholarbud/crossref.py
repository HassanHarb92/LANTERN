"""Crossref search for literature records, including ChemRxiv (a Crossref prefix).

chemrxiv.org itself sits behind Cloudflare and refuses scripted clients, so ChemRxiv abstracts come from Crossref filtered to
ChemRxiv's DOI prefix. Everything returned is what the registrant deposited; nothing is generated or summarised here.
"""
from __future__ import annotations

import html
import os
import re
import time

from .types import Paper

CROSSREF_URL = "https://api.crossref.org/works"
CHEMRXIV_PREFIX = "10.26434"
SELECT = "DOI,title,abstract,issued,created,license,URL,subtype"
RETRY_DELAY = 1.5  # seconds before the single retry; module-level so tests can zero it
_TAG = re.compile(r"<[^>]+>")


class LiteratureError(RuntimeError):
    """A literature lookup failed. Raised rather than returning [] so an outage is not read as 'no papers exist'."""


def clean_abstract(jats: str | None) -> str:
    """Strip JATS/HTML tags, unescape entities and collapse whitespace; None or empty gives ''."""
    if not jats:
        return ""
    text = _TAG.sub(" ", jats)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _year(item: dict) -> int | None:
    for key in ("issued", "created", "published", "published-online", "published-print"):
        parts = (item.get(key) or {}).get("date-parts") or [[]]
        first = parts[0] if parts else []
        if first and first[0]:
            try:
                return int(first[0])
            except (TypeError, ValueError):
                continue
    return None


def parse_item(item: dict, source: str = "crossref") -> Paper | None:
    """Turn one Crossref work into a Paper; None when it has no title (nothing citable)."""
    titles = item.get("title") or []
    title = clean_abstract(titles[0]) if titles else ""
    if not title:
        return None
    doi = (item.get("DOI") or "").strip()
    chem = doi.lower().startswith(CHEMRXIV_PREFIX + "/")
    licenses = item.get("license") or []
    lic = (licenses[0].get("URL") or "") if licenses else ""
    return Paper(
        doi=doi,
        title=title,
        abstract=clean_abstract(item.get("abstract")),
        year=_year(item),
        source="chemrxiv" if chem else source,
        url=item.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
        license=lic,
        preprint=chem,
    )


def _user_agent(mailto: str | None) -> str:
    mailto = mailto if mailto is not None else os.environ.get("LANTERN_MAILTO", "")
    base = "LANTERN-scholarbud/0.1"
    return f"{base} (mailto:{mailto})" if mailto else base


def search(query: str, rows: int = 20, *, prefix: str | None = None, mailto: str | None = None,
           session=None, timeout: int = 25) -> list[Paper]:
    """Query Crossref works. `session` is anything with .get(url, params=, headers=, timeout=), so tests need no network."""
    if session is None:
        import requests
        session = requests
    params = {"query": query, "rows": rows, "select": SELECT}
    if prefix:
        params["filter"] = f"prefix:{prefix}"
    headers = {"User-Agent": _user_agent(mailto)}

    resp = None
    for attempt in (0, 1):
        try:
            resp = session.get(CROSSREF_URL, params=params, headers=headers, timeout=timeout)
        except Exception as e:  # network errors differ by session type
            if attempt == 1:
                raise LiteratureError(f"Crossref request failed: {e}") from e
        else:
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == 1:
                    raise LiteratureError(f"Crossref returned HTTP {resp.status_code} after retry")
            elif resp.status_code != 200:
                raise LiteratureError(f"Crossref returned HTTP {resp.status_code}")
            else:
                break
        time.sleep(RETRY_DELAY)

    try:
        items = resp.json()["message"]["items"]
    except (ValueError, KeyError, TypeError) as e:
        raise LiteratureError(f"Crossref response was not the expected JSON: {e}") from e
    papers = (parse_item(it) for it in items)
    return [p for p in papers if p is not None]


def search_chemrxiv(query: str, rows: int = 20, **kw) -> list[Paper]:
    """ChemRxiv preprints only (Crossref filtered to ChemRxiv's DOI prefix)."""
    return search(query, rows, prefix=CHEMRXIV_PREFIX, **kw)
