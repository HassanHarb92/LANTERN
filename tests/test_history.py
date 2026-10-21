"""The Saved runs page: its tables, and that a reopened run still draws.

The page itself is thin -- the work is in the pure functions it builds its
tables from, and in whether a run read back off disk can still produce the
3D view the live page produced. Both are checked here without a browser.

The last class drives the real page headlessly to confirm the section
exists, is reachable, and says something true when the archive is empty.
"""
import json
import pathlib

import pytest

from lantern.history import (CAVEAT_ARCHIVE_IS_NOT_A_SURVEY,
                             CAVEAT_SHORTLIST_IS_ION_INDEPENDENT, protein_rows,
                             run_table, site_rows, structures_in,
                             structures_measured)
from lantern.runs import DEFAULT_RUNS_DIR, RUNS_ENV, index, rehydrate
from lantern.viewer import overview_html, site_viewer_html

COMMITTED = sorted(p for p in DEFAULT_RUNS_DIR.glob("*.json")
                   if p.stem != "index")


def _record(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())["record"]


@pytest.fixture(scope="module")
def record():
    """Eu3+ again: the one seeded run carrying both kinds of structure."""
    for path in COMMITTED:
        run = json.loads(path.read_text())
        if (run["record"].get("plan") or {}).get("target") == "Eu3+":
            return run["record"]
    pytest.fail("the committed archive no longer holds the Eu3+ run")


@pytest.fixture(scope="module")
def summaries():
    """The committed archive's own index, read directly off disk.

    Not `index()` -- conftest points that at a temporary directory -- so
    this reads the files the repository actually ships.
    """
    return [json.loads(p.read_text()) for p in COMMITTED]


class TestTheRunList:

    def test_one_row_per_run_with_the_columns_the_list_shows(self, summaries):
        from lantern.runs import _summary
        table = run_table([_summary(run) for run in summaries])
        assert len(table) == len(summaries)
        assert list(table.columns) == [
            "Question", "Ion", "Holds the ion", "Candidates", "Structures",
            "Asked", "Last answered", "Live search"]

    def test_the_ion_column_says_which_ion_was_asked_about(self, summaries):
        from lantern.runs import _summary
        table = run_table([_summary(run) for run in summaries])
        assert set(table["Ion"]) == {
            (run["record"]["plan"] or {}).get("target") for run in summaries}

    def test_a_run_that_found_nothing_holding_the_ion_says_so(self):
        """An em dash, not a blank and not a structure that holds something
        else. Pm3+ has no deposited structure anywhere, and the row has to
        read as an answer rather than as missing data."""
        row = run_table([{
            "question": "what about Pm3+", "target": "Pm3+",
            "ion_structure": None, "structures": ["8FNR", "8FNS"],
            "sites_holding_the_target": 0, "candidates": 2,
            "times_answered": 1, "last_answered": "2026-01-01T00:00:00Z",
            "settings": {"live": False}}]).iloc[0]
        assert row["Holds the ion"] == "—"
        assert row["Structures"] == 2, (
            "structures were still measured; none held the ion")


class TestTheCountAboveTheTable:

    def test_the_ion_s_own_structures_are_counted_as_measured(self,
                                                              summaries):
        """They were measured the same way a candidate's was, and they are
        the entries named in most rows of the table underneath the count."""
        from lantern.runs import _summary
        rows = [_summary(run) for run in summaries]
        counted = structures_measured(rows)
        named = {s["ion_structure"] for s in rows if s["ion_structure"]}
        assert named and named <= counted
        assert counted > {pdb for s in rows for pdb in s["structures"]}

    def test_a_run_with_no_ion_structure_contributes_no_blank(self):
        assert structures_measured([
            {"structures": ["8FNR"], "ion_structure": None}]) == {"8FNR"}

    def test_an_entry_measured_in_two_runs_is_counted_once(self):
        """The count is of structures, not of times one was looked at."""
        assert structures_measured([
            {"structures": ["8FNR", "8FNS"], "ion_structure": "6FKW"},
            {"structures": ["8FNR", "8FNS"], "ion_structure": "6FKW"},
        ]) == {"8FNR", "8FNS", "6FKW"}


class TestTheStructureList:

    def test_the_ion_s_own_structure_comes_first_and_is_not_a_candidate(
            self, record):
        """Somebody who asked about Eu3+ came to see europium, and this is
        the only block guaranteed to hold it."""
        drawn = structures_in(record)
        assert drawn[0]["pdb_id"] == record["ion_structure"]["pdb_id"]
        assert drawn[0]["is_candidate"] is False
        assert "the ion itself" in drawn[0]["label"]
        assert all(item["is_candidate"] for item in drawn[1:])

    def test_every_measured_deposited_structure_is_offered(self, record):
        assert [item["pdb_id"] for item in structures_in(record)[1:]] == [
            ev["pdb_id"] for ev in record["evidence"]]

    def test_a_predicted_structure_is_not_offered_as_one_to_look_at(self,
                                                                    record):
        """There are no deposited coordinates to draw, and a prediction shown
        beside measured entries would read as one of them."""
        guessed = {"pdb_id": None, "structure_kind": "predicted",
                   "accession": "P0DQJ0", "sites": []}
        assert structures_in({**record, "evidence": [guessed]}) == [
            item for item in structures_in(record) if not item["is_candidate"]]

    def test_a_run_with_no_structures_offers_none(self):
        assert structures_in({"evidence": []}) == []


class TestTheTables:

    def test_the_site_table_shows_what_was_measured(self, record):
        sites = record["evidence"][0]["sites"]
        table = site_rows(sites)
        assert len(table) == len(sites)
        assert "Element" in table.columns and "CN" in table.columns
        assert any("call" in column for column in table.columns), (
            "the geometry call has to carry the version that made it")
        assert table["Element"].tolist() == [
            s["deposited_element"] for s in sites]

    def test_the_protein_table_says_how_far_each_candidate_got(self, record):
        table = protein_rows(record["shortlist"])
        assert len(table) == len(record["shortlist"]["candidates"])
        assert list(table.columns) == ["Protein", "Accession", "Rules passed",
                                       "Selected"]
        assert all("/" in passed for passed in table["Rules passed"])

    def test_a_shortlist_with_no_candidates_is_an_empty_table_not_a_crash(
            self):
        assert protein_rows({}).empty


class TestTheCaveats:

    def test_the_archive_does_not_claim_to_be_a_sample(self):
        for caveat in (CAVEAT_ARCHIVE_IS_NOT_A_SURVEY,
                       CAVEAT_SHORTLIST_IS_ION_INDEPENDENT):
            assert "—" not in caveat, "house style is --"
            assert " you " not in f" {caveat} ", "caveats are declarative"
        assert "not a sample" in CAVEAT_ARCHIVE_IS_NOT_A_SURVEY

    def test_the_page_repeats_that_the_shortlist_ignores_the_ion(self):
        """This page can be reached without ever seeing the live one, where
        the same point is made."""
        assert "identically for every" in CAVEAT_SHORTLIST_IS_ION_INDEPENDENT


class TestEveryCommittedRunStillDraws:
    """The archive is only worth shipping if its runs reopen.

    Re-measuring a cached coordinate file is the one thing the page does at
    view time, so it is the one thing that can be stale in a way nothing else
    catches: a parser change renumbers sites, every saved run silently loses
    its viewer, and the committed archive becomes fifteen pages of numbers
    with no picture.
    """

    @pytest.mark.parametrize("path", COMMITTED, ids=lambda p: p.stem)
    def test_it_rehydrates_without_withholding_the_viewer(self, path):
        for item in structures_in(rehydrate(_record(path))):
            assert "viewer_unavailable" not in item, item["viewer_unavailable"]
            assert item["coordinates"], f"{item['pdb_id']} has no coordinates"

    def test_the_viewer_html_is_actually_produced(self, record):
        """Both views the page offers, on the structure with the most sites."""
        widest = max(structures_in(rehydrate(record)),
                     key=lambda item: len(item["sites"]))
        raw = [site["raw"] for site in widest["sites"]]
        text, fmt = widest["coordinates"]
        overview = overview_html(text, fmt, raw)
        assert "<script" in overview and len(overview) > 1000
        one = site_viewer_html(text, fmt, raw[0],
                               call={"call": widest["sites"][0]["call"],
                                     "call_reliable": True,
                                     "score_version": widest["score_version"]})
        assert "<script" in one and len(one) > 1000


class TestThePageItself:

    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")

    @pytest.fixture
    def page(self, tmp_path, monkeypatch):
        """The app opened on an archive of its own, with no gateway."""
        import streamlit as st

        monkeypatch.setenv(RUNS_ENV, str(tmp_path))
        for variable in ("ARGO_USER", "ARGO_API_KEY", "OPENAI_API_KEY",
                         "ANTHROPIC_API_KEY"):
            monkeypatch.setenv(variable, "")
        # The run list is cached with a short ttl, and the cache outlives an
        # AppTest, so without this the page would be shown the archive from
        # whichever test ran before.
        st.cache_data.clear()
        return self.AppTest.from_file(self.APP, default_timeout=300).run()

    def test_the_section_can_be_reached(self, page):
        page.segmented_control(key="section").set_value("Saved runs").run()
        assert not page.exception, [str(e.value) for e in page.exception]
        assert any("Saved runs" in str(h.value) for h in page.subheader)

    def test_an_empty_archive_says_how_runs_get_there(self, page):
        page.segmented_control(key="section").set_value("Saved runs").run()
        assert any("No runs are saved yet" in str(i.value) for i in page.info)

    def test_an_archived_run_is_listed_with_its_question(self, page, record,
                                                         tmp_path):
        import streamlit as st

        from lantern.runs import save
        save(record, "what proteins should I try for capturing Eu3+",
             {"live": False, "allow_predictions": False, "max_structures": 3})
        st.cache_data.clear()
        page.segmented_control(key="section").set_value("Saved runs").run()
        assert not page.exception, [str(e.value) for e in page.exception]
        assert len(index()) == 1
        listed = page.dataframe[0].value
        assert listed["Question"].tolist() == [
            "what proteins should I try for capturing Eu3+"]
        assert listed["Ion"].tolist() == ["Eu3+"]
        assert any("Select a run above" in str(i.value) for i in page.info)
