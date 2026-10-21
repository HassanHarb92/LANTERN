"""SQLite store of Paper records, deduplicated by canonical id.

Adapted from ScholarMap's library_db.py. The same paper arrives from several queries and sources, often with a shorter
abstract the second time, so upsert merges instead of overwriting and is safe to call repeatedly.
"""
from __future__ import annotations

import sqlite3

from .types import Paper

_COLS = ("cid", "doi", "title", "abstract", "year", "source", "url", "license", "preprint", "arxiv_id")


class Library:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS papers (cid TEXT PRIMARY KEY, doi TEXT, title TEXT, abstract TEXT, year INTEGER,"
            " source TEXT, url TEXT, license TEXT, preprint INTEGER, arxiv_id TEXT)")
        self._db.execute("CREATE INDEX IF NOT EXISTS papers_doi ON papers (lower(doi))")
        self._db.commit()

    @staticmethod
    def _row_paper(row: tuple) -> Paper:
        d = dict(zip(_COLS, row))
        d.pop("cid")
        d["preprint"] = bool(d["preprint"])
        return Paper(**d)

    def _find(self, paper: Paper) -> tuple | None:
        row = self._db.execute(f"SELECT {','.join(_COLS)} FROM papers WHERE cid=?", (paper.cid,)).fetchone()
        if row is None and paper.doi:
            row = self._db.execute(f"SELECT {','.join(_COLS)} FROM papers WHERE lower(doi)=?",
                                   (paper.doi.strip().lower(),)).fetchone()
        return row

    def upsert(self, paper: Paper) -> str:
        """Insert or merge. Returns "inserted", "merged" (something was added) or "unchanged"."""
        row = self._find(paper)
        if row is None:
            self._db.execute(f"INSERT INTO papers VALUES ({','.join('?' * len(_COLS))})",
                             (paper.cid, paper.doi, paper.title, paper.abstract, paper.year, paper.source, paper.url,
                              paper.license, int(paper.preprint), paper.arxiv_id))
            self._db.commit()
            return "inserted"
        cid, old = row[0], self._row_paper(row)
        merged = Paper(
            doi=old.doi or paper.doi,
            title=old.title or paper.title,
            abstract=paper.abstract if len(paper.abstract) > len(old.abstract) else old.abstract,
            year=old.year if old.year is not None else paper.year,
            source=old.source or paper.source,
            url=old.url or paper.url,
            license=old.license or paper.license,
            preprint=old.preprint or paper.preprint,
            arxiv_id=old.arxiv_id or paper.arxiv_id,
        )
        if merged == old:
            return "unchanged"
        # The row keeps the cid it was first stored under so earlier citations of it stay valid; get() resolves by DOI too.
        self._db.execute(
            "UPDATE papers SET doi=?, title=?, abstract=?, year=?, source=?, url=?, license=?, preprint=?, arxiv_id=?"
            " WHERE cid=?",
            (merged.doi, merged.title, merged.abstract, merged.year, merged.source, merged.url, merged.license,
             int(merged.preprint), merged.arxiv_id, cid))
        self._db.commit()
        return "merged"

    def get(self, cid: str) -> Paper | None:
        row = self._db.execute(f"SELECT {','.join(_COLS)} FROM papers WHERE cid=?", (cid,)).fetchone()
        if row is None and cid.startswith("doi:"):
            row = self._db.execute(f"SELECT {','.join(_COLS)} FROM papers WHERE lower(doi)=?", (cid[4:],)).fetchone()
        return self._row_paper(row) if row else None

    def all(self) -> list[Paper]:
        rows = self._db.execute(f"SELECT {','.join(_COLS)} FROM papers ORDER BY rowid").fetchall()
        return [self._row_paper(r) for r in rows]

    def search_text(self, substr: str) -> list[Paper]:
        """Case-insensitive substring match on title or abstract (plain scan; use BM25Index for ranking)."""
        s = substr.lower()
        return [p for p in self.all() if s in p.title.lower() or s in p.abstract.lower()]

    def __len__(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
