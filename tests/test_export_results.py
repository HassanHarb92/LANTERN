"""The committed results have to still be true. No network access.

A generated file committed to a repository is a claim that outlives the run
that made it, and the failure mode is silent: someone changes discover.py,
nobody reruns the exporter, and results/ keeps telling GitHub visitors an
answer the code no longer gives. These tests are the tripwire for that --
they read what is committed and check it against the code as it is now.

The README gets the same treatment as the JSON. It is the only part most
people will ever read, so a summary that has drifted from the records beside
it is worse than no summary.
"""
import json
from pathlib import Path

import pytest

from lantern.ions import LANTHANIDES_III
from scripts.export_results import (QUESTION, RESULTS, _ion_row, _nothing_found,
                                    _readme)
from lantern.discover import answer, exportable

COMMITTED = sorted(p for p in RESULTS.glob("*.json")
                   if not p.name.startswith("_"))


def _record(ion: str) -> dict:
    return json.loads((RESULTS / f"{ion.replace('+', '')}.json").read_text())


def test_every_lanthanide_has_a_committed_answer():
    """A missing file is an ion whose answer nobody can see."""
    assert {p.stem for p in COMMITTED} == {i.replace("+", "")
                                           for i in LANTHANIDES_III}


@pytest.mark.parametrize("ion", list(LANTHANIDES_III))
def test_a_committed_record_answers_the_ion_it_is_filed_under(ion):
    record = _record(ion)
    assert record["plan"]["target"] == ion
    assert record["ion_report"]["target"] == ion
    assert ion in record["question"], "the question has to name the ion"


@pytest.mark.parametrize("ion", list(LANTHANIDES_III))
def test_a_committed_record_keeps_its_caveats(ion):
    """Stripping the record for export must never strip what qualifies it."""
    record = _record(ion)
    assert record["caveats"], "an answer with no caveats is not this platform's"
    assert record["ion_report"]["caveat"]


@pytest.mark.parametrize("ion", list(LANTHANIDES_III))
def test_a_committed_record_carries_no_coordinates(ion):
    """Coordinates are for the viewer; committing them would bloat the diff."""
    record = _record(ion)
    for item in record["evidence"] + [record.get("ion_structure") or {}]:
        assert "coordinates" not in item
        assert all("raw" not in site for site in item.get("sites", []))


def test_the_readme_says_what_the_records_say():
    """The summary and the records cannot disagree; most readers see only one.

    Built from the committed JSON rather than from a fresh run, so this
    fails when the README is stale even if the records are current.
    """
    rows = [_ion_row(ion, _record(ion)) for ion in LANTHANIDES_III]
    blank = {"commit": "", "branch": "", "score_version": "", "generated_at_utc": ""}
    want = _readme(rows, blank)
    have = (RESULTS / "README.md").read_text()
    for row in rows:
        line = (f"| **{row['ion']}** | {row['structure_shown']} | "
                f"{row['how']} | {row['sites_holding_the_ion']} |")
        assert line in have, f"README disagrees with {row['ion']}'s record"
    assert want.count("|") == have.count("|"), "the tables differ in shape"


def test_a_named_structure_is_one_that_holds_the_ion():
    """Naming a structure in the table is a measurement claim, not a label."""
    named = 0
    for ion in LANTHANIDES_III:
        record = _record(ion)
        row = _ion_row(ion, record)
        if row["structure_shown"] == "--":
            assert row["sites_holding_the_ion"] == 0
            continue
        named += 1
        element = record["ion_report"]["element"]
        source = (record.get("ion_structure")
                  or next(ev for ev in record["evidence"]
                          if ev["pdb_id"] in row["structure_shown"]))
        held = [s for s in source["sites"]
                if (s["deposited_element"] or "").capitalize() == element
                and not s["size_match_is_counterfactual"]]
        assert held, f"{row['structure_shown']} holds no {element}"
        assert row["sites_holding_the_ion"] >= len(held)
    assert named >= 11, "the count of answerable ions must not quietly drop"


def test_the_summary_distinguishes_the_three_kinds_of_nothing(monkeypatch):
    """"Nothing is deposited" and "we stopped looking" are different answers.

    No ion currently hits the cap -- the one element with more entries than
    the walk allows found a structure early -- so the branch that would
    overstate the search is pinned here rather than left untested until the
    index grows.
    """
    import scripts.export_results as export

    def fake(ion, tried, indexed):
        monkeypatch.setattr(export, "structure_search",
                            lambda _: {"entries_tried": tried,
                                       "entries_in_index": indexed,
                                       "limit": 30})
        return _nothing_found(ion)

    assert fake("Pm3+", 0, 0) == "nothing holding it is deposited"
    assert fake("Ho3+", 16, 16).startswith("all 16 deposited entries measured")
    capped = fake("Gd3+", 30, 179)
    assert "30 of 179" in capped, "a capped walk must not read as exhaustive"
    assert "all" not in capped


def test_regenerating_one_ion_reproduces_what_is_committed():
    """The whole point of committing generated files: they stay reproducible.

    One ion, not fifteen, because this calls the real pipeline. Eu3+ is the
    one to pin -- it is the ion that drove the ion-structure work, and its
    answer comes from the element lookup rather than the corpus.
    """
    fresh = exportable(answer(QUESTION.format(ion="Eu3+"), live=False))
    text = json.dumps(fresh, indent=2, default=str, sort_keys=True) + "\n"
    assert text == (RESULTS / "Eu3.json").read_text(), (
        "results/ is stale -- run scripts/export_results.py")
