"""Offline tests for lantern.scholarbud: no network, fake sessions, inline Crossref-shaped fixtures."""
import re
from pathlib import Path

import pytest

from lantern.scholarbud import BM25Index, Library, Paper, search, search_chemrxiv
from lantern.scholarbud import crossref
from lantern.scholarbud.crossref import CHEMRXIV_PREFIX, LiteratureError, clean_abstract, parse_item

LAN_ITEM = {
    "DOI": "10.26434/chemrxiv.15005421/v1",
    "title": ["Quantum-Guided Binding-Site Engineering of Lanmodulin for Ce3+ Selectivity"],
    "abstract": "<jats:p>Lanmodulin is an EF-hand protein that binds lanthanides &amp; actinides with picomolar affinity.</jats:p>",
    "issued": {"date-parts": [[2025, 3, 1]]},
    "license": [{"URL": "https://creativecommons.org/licenses/by-nc-nd/4.0/"}],
    "URL": "http://dx.doi.org/10.26434/chemrxiv.15005421/v1",
}
CAM_ITEM = {
    "DOI": "10.1000/cam.1",
    "title": ["Calmodulin conformational dynamics"],
    "abstract": "Calmodulin binds calcium through four EF-hand motifs.",
    "created": {"date-parts": [[2019]]},
}


class FakeResp:
    def __init__(self, status=200, items=None):
        self.status_code = status
        self._items = items or []

    def json(self):
        return {"message": {"items": self._items}}


class FakeSession:
    def __init__(self, *resps):
        self.resps = list(resps)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return self.resps.pop(0)


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(crossref, "RETRY_DELAY", 0)
    monkeypatch.delenv("LANTERN_MAILTO", raising=False)


# ---- abstract cleaning / parsing

def test_clean_abstract_strips_jats_and_entities():
    out = clean_abstract("<jats:p>A &amp; B<jats:italic>x</jats:italic>\n  <jats:sub>2</jats:sub></jats:p>")
    assert "<" not in out and "A & B" in out
    assert "  " not in out and "\n" not in out


def test_clean_abstract_empty():
    assert clean_abstract(None) == ""
    assert clean_abstract("") == ""
    assert clean_abstract("<jats:p> </jats:p>") == ""


def test_parse_item_chemrxiv():
    p = parse_item(LAN_ITEM)
    assert p.source == "chemrxiv" and p.preprint is True
    assert p.year == 2025 and p.license.endswith("4.0/")
    assert p.abstract.startswith("Lanmodulin is an EF-hand") and "&amp;" not in p.abstract
    assert p.cid == "doi:10.26434/chemrxiv.15005421/v1"


def test_parse_item_missing_title_is_none():
    assert parse_item({"DOI": "10.1/x"}) is None
    assert parse_item({"DOI": "10.1/x", "title": []}) is None


def test_parse_item_missing_abstract_and_defaults():
    p = parse_item({"DOI": "10.1000/x", "title": ["T"]})
    assert p.abstract == "" and p.year is None and p.preprint is False and p.source == "crossref"
    assert p.url == "https://doi.org/10.1000/x" and p.license == ""


def test_parse_item_year_fallbacks():
    assert parse_item(CAM_ITEM).year == 2019  # created when issued absent
    both = dict(CAM_ITEM, issued={"date-parts": [[2021, 5]]})
    assert parse_item(both).year == 2021
    empty_issued = dict(CAM_ITEM, issued={"date-parts": [[None]]})
    assert parse_item(empty_issued).year == 2019


def test_parse_item_custom_source():
    assert parse_item(CAM_ITEM, source="x").source == "x"


# ---- search request construction

def test_search_params_and_parse():
    s = FakeSession(FakeResp(items=[LAN_ITEM, {"DOI": "10.1/notitle"}]))
    out = search("lanmodulin", rows=7, session=s)
    assert [p.doi for p in out] == [LAN_ITEM["DOI"]]
    c = s.calls[0]
    assert c["url"] == "https://api.crossref.org/works"
    assert c["params"]["query"] == "lanmodulin" and c["params"]["rows"] == 7
    assert c["params"]["select"] == "DOI,title,abstract,issued,created,license,URL,subtype"
    assert "filter" not in c["params"]


def test_search_chemrxiv_prefix_filter():
    s = FakeSession(FakeResp(items=[LAN_ITEM]))
    search_chemrxiv("lanmodulin", session=s)
    assert s.calls[0]["params"]["filter"] == f"prefix:{CHEMRXIV_PREFIX}"


def test_user_agent_mailto_from_env(monkeypatch):
    monkeypatch.setenv("LANTERN_MAILTO", "a@example.org")
    s = FakeSession(FakeResp())
    search("q", session=s)
    assert "mailto:a@example.org" in s.calls[0]["headers"]["User-Agent"]


def test_user_agent_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("LANTERN_MAILTO", "env@example.org")
    s = FakeSession(FakeResp())
    search("q", session=s, mailto="arg@example.org")
    ua = s.calls[0]["headers"]["User-Agent"]
    assert "arg@example.org" in ua and "env@example.org" not in ua


def test_no_mailto_leaked_when_unset():
    s = FakeSession(FakeResp())
    search("q", session=s)
    assert "@" not in s.calls[0]["headers"]["User-Agent"]
    assert "mailto" not in s.calls[0]["headers"]["User-Agent"]


def test_retry_on_429_then_success():
    s = FakeSession(FakeResp(429), FakeResp(items=[LAN_ITEM]))
    assert len(search("q", session=s)) == 1 and len(s.calls) == 2


def test_failure_after_retry_raises():
    s = FakeSession(FakeResp(503), FakeResp(503))
    with pytest.raises(LiteratureError):
        search("q", session=s)
    assert len(s.calls) == 2
    assert issubclass(LiteratureError, RuntimeError)


def test_client_error_not_retried():
    s = FakeSession(FakeResp(400))
    with pytest.raises(LiteratureError):
        search("q", session=s)
    assert len(s.calls) == 1


def test_network_exception_wrapped():
    class Boom:
        def get(self, *a, **k):
            raise OSError("down")
    with pytest.raises(LiteratureError):
        search("q", session=Boom())


# ---- library

def test_library_insert_merge_unchanged():
    lib = Library()
    short = Paper(doi="10.1/a", title="T", abstract="short")
    assert lib.upsert(short) == "inserted"
    assert lib.upsert(short) == "unchanged"
    rich = Paper(doi="10.1/a", title="T", abstract="a much longer abstract", year=2024, url="u", license="l")
    assert lib.upsert(rich) == "merged"
    got = lib.get("doi:10.1/a")
    assert got.abstract == "a much longer abstract" and got.year == 2024 and got.url == "u" and got.license == "l"
    assert lib.upsert(short) == "unchanged"  # shorter abstract never overwrites
    assert len(lib) == 1 and lib.all() == [got]


def test_library_cid_precedence_and_title_hash():
    assert Paper(doi="10.1/A", arxiv_id="1234.5", title="t").cid == "doi:10.1/a"
    assert Paper(arxiv_id="1234.5", title="t").cid == "arxiv:1234.5"
    assert Paper(title="Some  Title!").cid == Paper(title="some title").cid
    lib = Library()
    lib.upsert(Paper(title="Some Title"))
    assert lib.upsert(Paper(title="some  title")) == "unchanged"
    assert len(lib) == 1


def test_library_doi_case_insensitive():
    lib = Library()
    lib.upsert(Paper(doi="10.1/ABC", title="T"))
    assert lib.upsert(Paper(doi="10.1/abc", title="T", year=2020)) == "merged"
    assert len(lib) == 1
    assert lib.get("doi:10.1/abc").year == 2020


def test_library_search_text_and_persistence(tmp_path):
    path = str(tmp_path / "lib.db")
    lib = Library(path)
    lib.upsert(parse_item(LAN_ITEM))
    lib.upsert(parse_item(CAM_ITEM))
    assert [p.doi for p in lib.search_text("LANMODULIN")] == [LAN_ITEM["DOI"]]
    assert len(Library(path)) == 2
    assert lib.get("doi:nope") is None


# ---- bm25

def _papers():
    return [parse_item(LAN_ITEM), parse_item(CAM_ITEM)]


def test_bm25_ranks_lanmodulin_first():
    res = BM25Index(_papers()).search("lanmodulin lanthanide", k=5)
    assert res[0][0].doi == LAN_ITEM["DOI"] and res[0][1] > 0
    assert all(s > 0 for _, s in res)


def test_bm25_excludes_zero_scores_and_keeps_chem_tokens():
    idx = BM25Index(_papers())
    assert idx.search("zebrafish") == []
    assert [p.doi for p, _ in idx.search("Ce3+")] == [LAN_ITEM["DOI"]]
    assert {p.doi for p, _ in idx.search("EF-hand")} == {LAN_ITEM["DOI"], CAM_ITEM["DOI"]}


def test_bm25_tie_determinism():
    a = Paper(doi="10.1/b", title="same words")
    b = Paper(doi="10.1/a", title="same words")
    res = BM25Index([a, b]).search("same words")
    assert [p.doi for p, _ in res] == ["10.1/a", "10.1/b"]
    assert [p.doi for p, _ in BM25Index([b, a]).search("same words")] == ["10.1/a", "10.1/b"]


def test_bm25_empty_cases_and_k():
    assert BM25Index([]).search("x") == []
    assert BM25Index(_papers()).search("") == []
    assert BM25Index(_papers()).search("the of") == []
    assert len(BM25Index(_papers()).search("EF-hand", k=1)) == 1


# ---- isolation

def test_scholarbud_imports_nothing_else_from_lantern():
    pkg = Path(crossref.__file__).parent
    for f in pkg.glob("*.py"):
        src = f.read_text()
        for m in re.finditer(r"^\s*(?:from|import)\s+(\S+)", src, re.M):
            mod = m.group(1)
            if mod.startswith("lantern"):
                assert mod.startswith("lantern.scholarbud"), f"{f.name} imports {mod}"
            if mod.startswith(".."):
                pytest.fail(f"{f.name} imports from parent package: {mod}")
