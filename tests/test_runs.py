"""Archiving a run, and opening it again later. No network access.

The archive is the only part of this platform that outlives the browser tab,
so the things worth pinning are the ones that are silent when they break: a
question that quietly files itself as a second run, a reopened run that draws
a viewer built from coordinates its numbers were never measured from, and an
index that keeps claiming a run that is no longer on disk.

Every test points the archive at a temporary directory of its own. The
committed archive is the subject of test_export_results.py instead.
"""
import json

import pytest

from lantern.runs import (COORDINATES_ARE_NOT_IN_THE_RUN, DEFAULT_RUNS_DIR,
                          RUNS_ENV, index, load, rehydrate, run_id, runs_dir,
                          save)
from scripts.export_results import QUESTION, SETTINGS

EU = QUESTION.format(ion="Eu3+")


@pytest.fixture
def archive(tmp_path, monkeypatch):
    """An empty archive, private to one test."""
    monkeypatch.setenv(RUNS_ENV, str(tmp_path))
    return tmp_path


@pytest.fixture(scope="module")
def record():
    """A real answer to work on: Eu3+, which carries both kinds of structure.

    Read from the committed archive rather than recomputed, so these tests
    stay about the archive and not about discover.py. `exportable()` has
    already run on it, which is the shape `save` stores anyway.
    """
    path = DEFAULT_RUNS_DIR / f"{run_id(EU, SETTINGS)}.json"
    return json.loads(path.read_text())["record"]


class TestWhatCountsAsTheSameRun:

    def test_the_same_question_and_settings_name_the_same_run(self):
        assert run_id(EU, SETTINGS) == run_id(EU, dict(SETTINGS))

    def test_spacing_and_capitals_do_not_make_a_second_run(self):
        assert run_id("  What Proteins   For EU3+ ", SETTINGS) == run_id(
            "what proteins for eu3+", SETTINGS)

    def test_a_setting_that_changes_the_answer_makes_a_different_run(self):
        """Otherwise a live-search answer silently overwrites the offline one
        it disagrees with, which is the comparison most worth keeping."""
        for key, value in (("live", True), ("allow_predictions", True),
                           ("max_structures", 9)):
            assert run_id(EU, {**SETTINGS, key: value}) != run_id(EU, SETTINGS)

    def test_a_setting_that_does_not_change_the_answer_is_ignored(self):
        assert run_id(EU, {**SETTINGS, "viewer_theme": "dark"}) == run_id(
            EU, SETTINGS)


class TestSavingAndReopening:

    def test_a_saved_run_comes_back_whole(self, archive, record):
        save(record, EU, SETTINGS)
        reopened = load(run_id(EU, SETTINGS))
        assert reopened["record"] == record
        assert reopened["question"] == EU
        assert reopened["settings"] == SETTINGS
        assert reopened["headline"]

    def test_it_lands_in_the_archive_the_environment_points_at(self, archive,
                                                               record):
        save(record, EU, SETTINGS)
        assert runs_dir() == archive
        assert (archive / f"{run_id(EU, SETTINGS)}.json").exists()

    def test_coordinates_are_not_written_to_disk(self, archive, record):
        """A megabyte of coordinate file per run, for a picture that is
        already on disk under data/structures/."""
        bulky = {**record, "evidence": [
            {**ev, "coordinates": ("ATOM" * 1000, "pdb"),
             "sites": [{**s, "raw": {"donors": ["everything"]}}
                       for s in ev["sites"]]}
            for ev in record["evidence"]]}
        save(bulky, EU, SETTINGS)
        written = (archive / f"{run_id(EU, SETTINGS)}.json").read_text()
        # The keys, not the word: a caveat on every run explains what
        # coordinates are, and matching on that would pass whatever is stored.
        assert '"coordinates":' not in written
        assert '"raw":' not in written
        assert "ATOMATOM" not in written

    def test_asking_again_bumps_the_count_and_keeps_the_first_time(
            self, archive, record):
        first = save(record, EU, SETTINGS)
        again = save(record, EU, SETTINGS)
        assert (first["times_answered"], again["times_answered"]) == (1, 2)
        assert again["first_answered"] == first["first_answered"]
        assert len(list(archive.glob("*.json"))) == 2, (
            "one run file and one index -- a second asking is not a new run")

    def test_a_narration_belongs_to_the_run_that_produced_it(self, archive,
                                                             record):
        """Carrying it forward would caption new measurements with a model's
        reading of the previous ones."""
        save(record, EU, SETTINGS, narration="the model's reading")
        assert load(run_id(EU, SETTINGS))["narration"] == "the model's reading"
        save(record, EU, SETTINGS)
        assert load(run_id(EU, SETTINGS))["narration"] is None

    def test_a_refusal_is_archived_like_any_other_run(self, archive):
        """What the platform declined to answer is part of its record."""
        refused = {"answered": False, "evidence": [], "notes": ["no target"],
                   "plan": {"target": None}, "shortlist": {}}
        summary = save(refused, "what about iron", SETTINGS)
        assert summary["answered"] is False
        assert load(run_id("what about iron", SETTINGS))["headline"]

    def test_an_id_that_was_never_saved_opens_as_nothing(self, archive):
        assert load("0123456789ab") is None

    def test_a_file_that_is_not_a_run_is_not_served_as_one(self, archive):
        (archive / "broken.json").write_text("{not json")
        (archive / "notarun.json").write_text('{"id": "notarun"}')
        assert load("broken") is None
        assert load("notarun") is None


class TestSeedingLeavesNoDiff:
    """A diff under results/ has to mean the platform's answer changed.

    Seeded runs are regenerated in bulk by a script nobody asked a question
    of, so rewriting their timestamps would put fifteen meaningless lines in
    every diff and bury the one line where an answer actually moved.
    """

    def test_reseeding_an_unchanged_run_does_not_touch_the_file(self, archive,
                                                                record):
        path = archive / f"{run_id(EU, SETTINGS)}.json"
        save(record, EU, SETTINGS, origin="seed")
        before = path.read_bytes(), path.stat().st_mtime_ns
        save(record, EU, SETTINGS, origin="seed")
        assert (path.read_bytes(), path.stat().st_mtime_ns) == before

    def test_reseeding_a_changed_run_rewrites_it(self, archive, record):
        path = archive / f"{run_id(EU, SETTINGS)}.json"
        save(record, EU, SETTINGS, origin="seed")
        before = path.read_bytes()
        save({**record, "caveats": ["something new is true"]}, EU, SETTINGS,
             origin="seed")
        assert path.read_bytes() != before
        assert "something new is true" in path.read_text()

    def test_a_seed_is_not_counted_as_somebody_asking(self, archive, record):
        save(record, EU, SETTINGS, origin="seed")
        save(record, EU, SETTINGS, origin="seed")
        reopened = load(run_id(EU, SETTINGS))
        assert reopened["times_answered"] == 1
        assert reopened["origin"] == "seed"


class TestTheIndex:
    """A cache of the run files, and never the record of truth."""

    def test_it_lists_the_most_recently_answered_first(self, archive, record):
        for ion in ("La3+", "Nd3+", "Eu3+"):
            save(record, QUESTION.format(ion=ion), SETTINGS)
        listed = index()
        assert len(listed) == 3
        assert [s["last_answered"] for s in listed] == sorted(
            (s["last_answered"] for s in listed), reverse=True)

    def test_a_run_copied_in_by_hand_is_not_invisible(self, archive, record):
        """A colleague's run file dropped into the folder has to show up."""
        save(record, EU, SETTINGS)
        donated = json.loads((archive / f"{run_id(EU, SETTINGS)}.json")
                             .read_text())
        (archive / "aaaaaaaaaaaa.json").write_text(
            json.dumps({**donated, "id": "aaaaaaaaaaaa",
                        "question": "a colleague's question"}))
        assert {s["id"] for s in index()} == {run_id(EU, SETTINGS),
                                              "aaaaaaaaaaaa"}

    def test_a_run_deleted_by_hand_stops_being_listed(self, archive, record):
        save(record, EU, SETTINGS)
        save(record, QUESTION.format(ion="La3+"), SETTINGS)
        (archive / f"{run_id(EU, SETTINGS)}.json").unlink()
        assert [s["id"] for s in index()] == [
            run_id(QUESTION.format(ion="La3+"), SETTINGS)]

    def test_a_corrupt_index_is_rebuilt_rather_than_fatal(self, archive,
                                                          record):
        save(record, EU, SETTINGS)
        (archive / "index.json").write_text("{ truncated")
        assert [s["id"] for s in index()] == [run_id(EU, SETTINGS)]
        assert json.loads((archive / "index.json").read_text())["runs"]

    def test_an_archive_that_does_not_exist_yet_is_empty_not_an_error(
            self, tmp_path, monkeypatch):
        monkeypatch.setenv(RUNS_ENV, str(tmp_path / "never-written"))
        assert index() == []

    def test_a_summary_says_enough_to_fill_a_row_without_the_record(
            self, archive, record):
        summary, = [save(record, EU, SETTINGS)]
        for field in ("question", "target", "headline", "candidates",
                      "structures", "times_answered", "settings"):
            assert field in summary
        assert summary["target"] == "Eu3+"
        assert summary["ion_structure"] == "6FKW"
        assert "record" not in summary, "the index is a list, not a copy"


class TestReopeningDrawsTheSameStructure:
    """Rehydration: the picture comes back, the numbers never move."""

    def test_the_coordinates_and_donor_atoms_come_back(self, record):
        restored = rehydrate(record)
        for item in restored["evidence"] + [restored["ion_structure"]]:
            assert "viewer_unavailable" not in item, item.get(
                "viewer_unavailable")
            text, fmt = item["coordinates"]
            assert fmt in ("pdb", "cif") and len(text) > 1000
            assert all(site["raw"] for site in item["sites"])

    def test_no_measurement_is_taken_from_the_re_measurement(self, record):
        """The archived numbers are the answer. Re-reading the coordinate
        file supplies the donor geometry the viewer needs and nothing else."""
        restored = rehydrate(record)
        for before, after in zip(record["evidence"], restored["evidence"]):
            assert {k: v for k, v in after.items() if k != "coordinates"} != {}
            for saved, drawn in zip(before["sites"], after["sites"]):
                assert {k: v for k, v in drawn.items() if k != "raw"} == saved

    def test_a_malformed_identifier_withholds_the_view(self, record):
        broken = {**record, "evidence": [
            {**record["evidence"][0], "pdb_id": "not-a-pdb-id"}]}
        item, = rehydrate(broken)["evidence"]
        assert "well-formed" in item["viewer_unavailable"]
        assert "coordinates" not in item

    def test_a_structure_missing_from_the_cache_withholds_the_view(self,
                                                                   record):
        absent = {**record, "evidence": [
            {**record["evidence"][0], "pdb_id": "9ZZZ"}]}
        item, = rehydrate(absent)["evidence"]
        assert "not in the local structure cache" in item["viewer_unavailable"]
        assert item["sites"] == record["evidence"][0]["sites"], (
            "the measurements are still the archive's; only the picture is "
            "missing")

    def test_a_structure_that_will_not_re_measure_withholds_the_view(
            self, record, monkeypatch):
        def explode(*_args, **_kwargs):
            raise RuntimeError("the parser moved on")

        monkeypatch.setattr("lantern.runs.binding_neighborhood", explode)
        item = rehydrate(record)["evidence"][0]
        assert "could not be re-measured (RuntimeError)" in item[
            "viewer_unavailable"]

    def test_a_site_that_no_longer_appears_withholds_the_view(self, record):
        """The pairing is by chain, label and element rather than by position,
        so a parser change that renumbered sites cannot quietly draw every
        saved measurement against the wrong shell."""
        first = record["evidence"][0]
        moved = {**record, "evidence": [
            {**first, "sites": [{**first["sites"][0], "chain": "ZZ"}]
                      + list(first["sites"][1:])}]}
        item, = rehydrate(moved)["evidence"]
        assert "no longer reproduces 1 of" in item["viewer_unavailable"]
        assert "coordinates" not in item

    def test_the_element_is_matched_whatever_its_capitalisation(self, record):
        """Saved sites spell it `Eu`, the coordinate file spells it `EU`."""
        first = record["evidence"][0]
        shouted = {**record, "evidence": [
            {**first, "sites": [{**s, "deposited_element":
                                 (s["deposited_element"] or "").lower()}
                                for s in first["sites"]]}]}
        assert "viewer_unavailable" not in rehydrate(shouted)["evidence"][0]

    def test_a_predicted_structure_is_left_exactly_as_it_was(self, record):
        """There is no deposited file to re-read, and nothing to say about
        one: a prediction was never measured from coordinates on disk."""
        predicted = {"pdb_id": None, "structure_kind": "predicted",
                     "accession": "P0DQJ0", "sites": []}
        out, = rehydrate({**record, "evidence": [predicted]})["evidence"]
        assert out == predicted

    def test_the_reason_the_view_can_be_missing_is_stated_in_full(self):
        assert "coordinate file on disk" in COORDINATES_ARE_NOT_IN_THE_RUN
        assert "—" not in COORDINATES_ARE_NOT_IN_THE_RUN, "house style is --"
