"""The Explorer tab: the selection logic as pure functions, then the page.

Row selection from a chart or a table is a click in a browser, which AppTest
cannot make. So the part that decides *which rows a selection means* lives in
lantern/explorer.py as functions of DataFrames, and is tested here directly;
the AppTest layer proves the tab renders, offline, and degrades when the
optional retrieval-hits file is absent.
"""
import json
import pathlib

import pandas as pd
import pytest

from lantern import explorer as ex
from lantern.chemistry import screen
from lantern.catalog import load_reference

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")
CREDENTIALS = ("ARGO_USER", "ARGO_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")


@pytest.fixture(scope="module")
def tables():
    ln = ex.curated_sites(ex.load_sites(ex.LN_SITES), ex.GROUP_LN)
    ca = ex.curated_sites(ex.load_sites(ex.CA_SITES), ex.GROUP_CA)
    return ln, ca


class TestFiltering:

    def test_curated_counts_match_the_validated_recount(self, tables):
        """136 natural Ln and 664 Ca sites, 89 and 5 at CN >= 9: the numbers
        the report's section 9 recomputed from the raw files."""
        ln, ca = tables
        assert (len(ln), len(ca)) == (136, 664)
        assert ex.threshold_summary(ln)["above"] == 89
        assert ex.threshold_summary(ca)["above"] == 5

    def test_every_filter_is_applied(self, tables):
        ln, ca = tables
        for frame in tables:
            assert (frame["resolution_A"] <= 2.5).all()
            assert not frame["chelator_flagged"].any()
        assert set(ln["class_first_pass"]) == {"natural_ln_biology"}
        assert set(ln["family"]) == {"lanthanide"}

    def test_threshold_is_read_from_the_scoring_rule(self):
        from lantern.geometry import CRITERIA
        assert ex.CN_THRESHOLD == dict((n, m) for n, m, _ in CRITERIA)["coordination_number"]

    def test_unknown_group_is_rejected(self, tables):
        with pytest.raises(ValueError):
            ex.curated_sites(ex.load_sites(ex.LN_SITES), "Mg")


class TestBinning:

    def test_percentages_sum_to_100_within_each_group(self, tables):
        dist = ex.cn_distribution(*tables)
        for group, part in dist.groupby("group"):
            assert part["percent"].sum() == pytest.approx(100.0, abs=0.2)
            assert part["n"].sum() == part["total"].iloc[0]

    def test_both_groups_share_one_axis(self, tables):
        dist = ex.cn_distribution(*tables)
        axes = [set(p["cn"]) for _, p in dist.groupby("group")]
        assert axes[0] == axes[1]

    def test_small_example_by_hand(self):
        ln = pd.DataFrame({"coordination_number": [9, 9, 10, 8]})
        ca = pd.DataFrame({"coordination_number": [6, 7]})
        dist = ex.cn_distribution(ln, ca).set_index(["group", "cn"])
        assert dist.loc[(ex.GROUP_LN, 9), "percent"] == 50.0
        assert dist.loc[(ex.GROUP_CA, 7), "percent"] == 50.0
        assert dist.loc[(ex.GROUP_CA, 9), "n"] == 0
        assert ex.threshold_summary(ln) == {"above": 3, "total": 4, "percent": 75.0}

    def test_empty_input_does_not_raise(self):
        empty = pd.DataFrame({"coordination_number": pd.Series([], dtype=int)})
        assert ex.cn_distribution(empty, empty).empty
        assert ex.threshold_summary(empty)["percent"] is None


class TestSelection:

    def test_a_bar_selects_exactly_its_sites(self, tables):
        ln, ca = tables
        got = ex.sites_for_selection(ln, ca, [{"group": ex.GROUP_LN, "cn": 9}])
        assert len(got) == int((ln["coordination_number"] == 9).sum())
        assert set(got["group"]) == {ex.GROUP_LN}
        assert (got["coordination_number"] == 9).all()

    def test_two_groups_at_one_cn(self, tables):
        ln, ca = tables
        got = ex.sites_for_selection(ln, ca, [{"group": ex.GROUP_LN, "cn": 9},
                                              {"group": ex.GROUP_CA, "cn": 9}])
        assert set(got["group"]) == {ex.GROUP_LN, ex.GROUP_CA}

    @pytest.mark.parametrize("bad", [None, [], [{}], [{"group": "Ca"}], [{"group": "Ca", "cn": "x"}],
                                     [{"group": "Mg", "cn": 9}]])
    def test_nothing_or_nonsense_selects_nothing(self, tables, bad):
        """No click must never read as 'every site'."""
        assert ex.sites_for_selection(*tables, bad).empty

    def test_brush_filters_inclusively(self):
        frame = pd.DataFrame({"x": [1, 2, 3, 4], "y": [0, 1, 2, 3]})
        got = ex.filter_by_brush(frame, {"x": [4, 2], "y": [0, 2]}, "x", "y")
        assert list(got["x"]) == [2, 3]

    @pytest.mark.parametrize("bad", [None, {}, {"x": [1, 2]}, {"x": "a", "y": "b"}])
    def test_no_brush_keeps_every_row(self, bad):
        frame = pd.DataFrame({"x": [1, 2], "y": [0, 1]})
        assert len(ex.filter_by_brush(frame, bad, "x", "y")) == 2


class TestSiteView:
    """The click-through never raises; each failure has its own message."""

    ROW = {"pdb_id": "8FNS", "chain": "A", "site": "1", "element": "Nd",
           "coordination_number": 9, "coordinate_source": "asu"}

    def test_a_cached_site_is_found(self, tables):
        ln, _ = tables
        row = ln[ln["pdb_id"] == "8FNS"].iloc[0].to_dict()
        from lantern.structure import cached_structure
        view = ex.site_view(row, fetch=lambda i: cached_structure(i) or (_ for _ in ()).throw(
            ValueError("no")))
        assert view["status"] == "ok"
        assert view["site"]["chain"] == row["chain"]
        assert view["site"]["xyz"], "viewer needs the deposited ion position"

    def test_fetch_failure_is_a_message_not_an_exception(self):
        def refuse(_):
            raise ValueError("offline")
        view = ex.site_view(self.ROW, fetch=refuse)
        assert view["status"] == "unavailable"
        assert "could not be fetched" in view["message"]

    def test_symmetry_copy_chain_is_explained(self):
        view = ex.site_view({**self.ROW, "chain": "A-2"}, fetch=lambda i: ("", "pdb"))
        assert view["status"] == "unavailable" and "symmetry copy" in view["message"]

    def test_site_not_in_file_is_reported(self):
        view = ex.site_view(self.ROW, fetch=lambda i: ("", "pdb"), measure=lambda *a, **k: [])
        assert view["status"] == "unavailable" and "not found" in view["message"]

    def test_cn_disagreement_is_noted(self):
        site = {"chain": "A", "site": "1", "element": "Nd", "coordination_number": 7}
        view = ex.site_view({**self.ROW, "coordination_number": 9, "coordinate_source": "assembly1"},
                            fetch=lambda i: ("", "pdb"), measure=lambda *a, **k: [site])
        assert view["status"] == "ok" and "CN 9" in view["note"] and "CN 7" in view["note"]

    def test_the_viewer_html_is_built_for_a_found_site(self, tables):
        from lantern.structure import cached_structure
        from lantern.viewer import site_viewer_html
        ln, _ = tables
        row = ln[ln["pdb_id"] == "8FNS"].iloc[0].to_dict()
        view = ex.site_view(row, fetch=lambda i: cached_structure(i))
        html = site_viewer_html(view["text"], view["fmt"], view["site"])
        assert "lantern-site" in html


class TestPairs:

    def test_pair_table_has_two_rows_per_pair(self):
        pairs = pd.read_csv(ex.PAIRS)
        long = ex.pair_table(pairs)
        assert len(pairs) == 19 and len(long) == 38
        assert set(long["ion"]) == {"Ln", "Ca"}
        first = pairs.iloc[0]
        got = long[long["pair"] == 1].set_index("ion")["cn"]
        assert got["Ln"] == first["coordination_number_ln"]
        assert got["Ca"] == first["coordination_number_ca"]

    def test_sign_counts_match_the_validated_sign_test(self):
        """Report 9.1 #8: 6 up, 5 down, 8 ties."""
        assert ex.pair_signs(pd.read_csv(ex.PAIRS)) == {"up": 6, "down": 5, "tie": 8}


class TestHits:

    def write(self, tmp_path, rows):
        path = tmp_path / "hits.json"
        path.write_text(json.dumps(rows))
        return path

    def test_missing_file_is_a_message(self, tmp_path):
        hits, message = ex.load_hits(tmp_path / "absent.json")
        assert hits is None and ex.HITS_ENV in message

    def test_env_var_points_the_loader(self, tmp_path, monkeypatch):
        path = self.write(tmp_path, [{"acc": "X1", "len": 100, "gaps": [12, 13, 12],
                                      "strict": True, "hdr": ">sp|X1|X1_H Name OS=Org", "pro2": 2}])
        monkeypatch.setenv(ex.HITS_ENV, str(path))
        hits, _ = ex.load_hits()
        assert hits.iloc[0]["max_gap"] == 13 and hits.iloc[0]["name"] == "Name"

    @pytest.mark.parametrize("content", ["not json", "[{}]", '{"a": 1}', "[]"])
    def test_malformed_file_is_a_message(self, tmp_path, content):
        path = tmp_path / "bad.json"
        path.write_text(content)
        hits, message = ex.load_hits(path)
        assert hits is None and message

    def test_default_is_the_repo_local_file(self):
        assert pathlib.Path(ex.DEFAULT_HITS) == ex.DATA / "figures" / "retrieval_hits.json"
        assert "/work" not in ex.DEFAULT_HITS

    def test_default_path_missing_is_a_message_not_an_exception(self, monkeypatch, tmp_path):
        monkeypatch.delenv(ex.HITS_ENV, raising=False)
        monkeypatch.setattr(ex, "DEFAULT_HITS", str(tmp_path / "nope.json"))
        hits, message = ex.load_hits()
        assert hits is None and "not found" in message

    def test_in_family_absent_gives_no_split(self, tmp_path):
        rows = [{"acc": "A", "len": 90, "gaps": [12, 13, 12], "strict": True, "hdr": "", "pro2": 1}]
        hits, _ = ex.load_hits(self.write(tmp_path, rows))
        assert hits["in_family"].isna().all() and ex.family_split(hits) is None

    def test_in_family_present_is_split(self, tmp_path):
        base = {"len": 90, "gaps": [12, 13, 12], "strict": True, "hdr": "", "pro2": 1}
        rows = [dict(base, acc="A", in_family=True), dict(base, acc="B", in_family=False),
                dict(base, acc="C", in_family=False), dict(base, acc="D")]
        hits, _ = ex.load_hits(self.write(tmp_path, rows))
        assert ex.family_split(hits) == {"inside": 1, "outside": 2, "unknown": 1}

    def test_cells_keep_every_hit(self, tmp_path):
        rows = [{"acc": f"A{i}", "len": 90, "gaps": [12, 13, 12 + i % 2], "strict": True,
                 "hdr": "", "pro2": i % 3} for i in range(30)]
        hits, _ = ex.load_hits(self.write(tmp_path, rows))
        assert ex.hit_cells(hits)["hits"].sum() == 30


class TestCandidates:

    def test_table_is_the_existing_screen_unchanged(self):
        screened = screen(load_reference())
        table = ex.candidate_table(screened)
        assert list(table["score"]) == [c.score for c in screened]
        assert list(table["rank"]) == list(range(1, len(screened) + 1))
        assert list(table["score"]) == sorted(table["score"], reverse=True)


class TestChartSpecs:
    """Specs validate and carry the rows they were given."""

    def test_cn_chart(self, tables):
        dist = ex.cn_distribution(*tables)
        spec = ex.cn_chart(dist).to_dict()
        assert any("cn_pick" in p.get("name", "") for p in _params(spec))
        assert len(next(iter(spec["datasets"].values()))) in (len(dist), 1)
        assert "rule" in json.dumps(spec)

    def test_other_charts_validate(self, tables):
        pairs = ex.pair_table(pd.read_csv(ex.PAIRS))
        ex.pair_chart(pairs).to_dict()
        ex.candidate_chart(ex.candidate_table(screen(load_reference()))).to_dict()
        cells = ex.hit_cells(pd.DataFrame({"max_gap": [13], "pro2": [1], "strict": [True]}))
        ex.loop_chart(cells).to_dict()


def _params(spec):
    found = list(spec.get("params", []))
    for layer in spec.get("layer", []):
        found += layer.get("params", [])
    return found


@pytest.fixture
def offline(monkeypatch):
    for variable in CREDENTIALS:
        monkeypatch.setenv(variable, "")


def open_explorer(monkeypatch_env=None):
    app = AppTest.from_file(APP, default_timeout=120).run()
    app.segmented_control(key="section").set_value("Explorer").run()
    return app


class TestTheTabRenders:

    def test_it_renders_without_exceptions(self, offline, monkeypatch, tmp_path):
        monkeypatch.setenv(ex.HITS_ENV, str(tmp_path / "absent.json"))
        app = open_explorer()
        assert not app.exception, [str(e.value) for e in app.exception]
        text = " ".join(c.value for c in app.caption)
        # The caveats are part of the view, not decoration.
        assert "in-sample" in text and "pseudo-replicates" in text
        assert "sequence leads only" in text

    def test_v4_degrades_when_the_hits_file_is_absent(self, offline, monkeypatch, tmp_path):
        monkeypatch.setenv(ex.HITS_ENV, str(tmp_path / "absent.json"))
        app = open_explorer()
        assert not app.exception
        assert any("retrieval-hits file was not found" in i.value for i in app.info)

    def test_v4_draws_when_the_hits_file_exists(self, offline, monkeypatch, tmp_path):
        path = tmp_path / "hits.json"
        path.write_text(json.dumps([{"acc": "X1", "len": 100, "gaps": [12, 13, 12],
                                     "strict": True, "hdr": ">sp|X1|X1_H N OS=O", "pro2": 2}]))
        monkeypatch.setenv(ex.HITS_ENV, str(path))
        app = open_explorer()
        assert not app.exception
        assert not any("retrieval-hits file was not found" in i.value for i in app.info)
        # No in_family column: nothing is said about family membership.
        assert not any("reference family" in c.value for c in app.caption)
        assert any("candidates only, unchecked" in c.value for c in app.caption)

    def test_v4_shows_the_family_split_with_the_honest_caption(self, offline, monkeypatch, tmp_path):
        base = {"len": 100, "gaps": [12, 13, 12], "strict": True,
                "hdr": ">sp|X|X_H N OS=O", "pro2": 2}
        path = tmp_path / "hits.json"
        path.write_text(json.dumps([dict(base, acc="X1", in_family=True),
                                    dict(base, acc="X2", in_family=False)]))
        monkeypatch.setenv(ex.HITS_ENV, str(path))
        app = open_explorer()
        assert not app.exception, [str(e.value) for e in app.exception]
        text = " ".join(c.value for c in app.caption)
        assert "1 of these hits are in the reference family and 1 are outside it" in text
        assert "candidates only, unchecked" in text

    def test_the_ask_page_is_still_the_default(self, offline):
        app = AppTest.from_file(APP, default_timeout=60).run()
        assert not app.exception
        assert not any("Explorer" == s.value for s in app.subheader)
