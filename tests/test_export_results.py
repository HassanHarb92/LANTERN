"""The committed run archive has to still be true. No network access.

A generated file committed to a repository is a claim that outlives the run
that made it, and the failure mode is silent: someone changes discover.py,
nobody reseeds, and results/ keeps telling GitHub visitors an answer the
code no longer gives. These tests are the tripwire for that -- they read
what is committed and check it against the code as it is now.

They deliberately read `DEFAULT_RUNS_DIR` rather than `runs_dir()`, because
conftest.py points the latter at a temporary directory for the session. The
subject here is the archive in the repository, not wherever the app happens
to be writing.
"""
import json

import pytest

from lantern.discover import answer, exportable
from lantern.ions import LANTHANIDES_III
from lantern.runs import DEFAULT_RUNS_DIR, run_id
from scripts.export_results import (QUESTION, RESULTS, SETTINGS, _ion_row,
                                    _nothing_found, _readme)

SEEDED = {ion: DEFAULT_RUNS_DIR / f"{run_id(QUESTION.format(ion=ion), SETTINGS)}.json"
          for ion in LANTHANIDES_III}


def _run(ion: str) -> dict:
    return json.loads(SEEDED[ion].read_text())


def test_every_lanthanide_is_seeded_into_the_archive():
    """A missing run is an ion whose answer nobody can open."""
    missing = [ion for ion, path in SEEDED.items() if not path.exists()]
    assert not missing, f"not seeded: {missing}"


def test_the_archive_holds_nothing_but_its_runs_and_its_index():
    """A stray file here would be served to the browser as a run."""
    unexpected = [p.name for p in DEFAULT_RUNS_DIR.glob("*")
                  if p.suffix != ".json"]
    assert not unexpected


@pytest.mark.parametrize("ion", list(LANTHANIDES_III))
def test_a_seeded_run_answers_the_ion_it_is_filed_under(ion):
    run = _run(ion)
    record = run["record"]
    assert record["plan"]["target"] == ion
    assert record["ion_report"]["target"] == ion
    assert ion in run["question"], "the question has to name the ion"
    assert run["origin"] == "seed"
    assert run["settings"] == SETTINGS


@pytest.mark.parametrize("ion", list(LANTHANIDES_III))
def test_a_seeded_run_keeps_its_caveats(ion):
    """Stripping a record for the archive must never strip what qualifies it."""
    record = _run(ion)["record"]
    assert record["caveats"], "an answer with no caveats is not this platform's"
    assert record["ion_report"]["caveat"]


@pytest.mark.parametrize("ion", list(LANTHANIDES_III))
def test_a_seeded_run_carries_no_coordinates(ion):
    """Coordinates are for the viewer; archiving them would bloat every diff."""
    record = _run(ion)["record"]
    for item in record["evidence"] + [record.get("ion_structure") or {}]:
        assert "coordinates" not in item
        assert all("raw" not in site for site in item.get("sites", []))


def test_the_readme_says_what_the_archive_says():
    """The summary and the runs cannot disagree; most readers see only one.

    Built from the committed runs rather than from a fresh answer, so this
    fails when the README is stale even if the runs are current.
    """
    rows = [_ion_row(ion, _run(ion)["record"]) for ion in LANTHANIDES_III]
    blank = {"commit": "", "branch": "", "score_version": "",
             "generated_at_utc": ""}
    want = _readme(rows, blank)
    have = (RESULTS / "README.md").read_text()
    for row in rows:
        line = (f"| **{row['ion']}** | {row['structure_shown']} | "
                f"{row['how']} | {row['sites_holding_the_ion']} |")
        assert line in have, f"README disagrees with {row['ion']}'s run"
    assert want.count("|") == have.count("|"), "the tables differ in shape"


def test_a_named_structure_is_one_that_holds_the_ion():
    """Naming a structure in the table is a measurement claim, not a label."""
    named = 0
    for ion in LANTHANIDES_III:
        record = _run(ion)["record"]
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


def test_reanswering_one_ion_reproduces_what_is_archived():
    """The whole point of committing generated files: they stay reproducible.

    One ion, not fifteen, because this calls the real pipeline. Eu3+ is the
    one to pin -- it is the ion that drove the ion-structure work, and its
    answer comes from the element lookup rather than from the corpus.
    """
    fresh = exportable(answer(QUESTION.format(ion="Eu3+"), live=False))
    through_json = json.loads(json.dumps(fresh, default=str))
    assert through_json == _run("Eu3+")["record"], (
        "the archive is stale -- run scripts/export_results.py")
