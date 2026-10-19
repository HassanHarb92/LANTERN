"""Offline tests for geometry-v1, the M3.1 structural call. No network access.

The first group pins the behaviour that makes the score honest -- what it
refuses to score, and what it refuses to let influence the score. The second
group re-derives ROADMAP 3.17's separation from the committed corpus, so that
a change to the thresholds that quietly breaks the result it was built on
fails here rather than in a figure six months later.
"""
import json
from pathlib import Path

import pytest

from reefinder.geometry import (CRITERIA, MAX_RESOLUTION_A, SCORE_VERSION,
                                rank_key, score_site, score_sites)
from reefinder.structure import (ALL_METAL_CODES, binding_neighborhood,
                                 cached_structure, resolution_from_coordinates)

ROOT = Path(__file__).resolve().parent.parent
LN_TABLE = ROOT / "data" / "lanthanide_sites.parquet"
CA_TABLE = ROOT / "data" / "calcium_sites.parquet"
COUNTERPARTS = ROOT / "data" / "calcium_counterparts.json"

SCORED = [name for name, _, _ in CRITERIA]


def site(coordination=9, bidentate=2, **extra):
    """A flat site row, the shape the corpus tables use."""
    return {"coordination_number": coordination, "bidentate_carboxylates": bidentate,
            "other_ligand_donor_count": 0, **extra}


def assembly(s, resolution=2.0):
    return score_site(s, resolution_A=resolution, coordinate_source="assembly1")


def test_a_lanthanide_like_site_meets_both_criteria():
    call = assembly(site(coordination=10, bidentate=3))
    assert call["call"] == "lanthanide-like"
    assert call["criteria_met"] == 2 and call["score"] == 100.0
    assert call["score_version"] == SCORE_VERSION


def test_a_calcium_like_site_meets_neither():
    call = assembly(site(coordination=7, bidentate=1))
    assert call["call"] == "calcium-like"
    assert call["criteria_met"] == 0 and call["score"] == 0.0


def test_net_charge_and_sasa_are_reported_but_never_scored():
    """The fourth and fifth time these failed is recorded in ROADMAP 3.17.

    Net charge is significant and is the published Dudev prediction, so the
    pressure to let it into the score is real and recurring. This test is the
    thing that makes letting it in loud.
    """
    weak = site(coordination=7, bidentate=1, net_charge=-6, metal_sasa_A2=0.0)
    strong = site(coordination=7, bidentate=1, net_charge=0, metal_sasa_A2=90.0)
    assert assembly(weak)["score"] == assembly(strong)["score"]
    assert assembly(weak)["triage_only"] == {"net_charge": -6, "metal_sasa_A2": 0.0}
    assert all(c["descriptor"] in SCORED for c in assembly(weak)["criteria"])
    assert len(SCORED) == 2, "geometry-v1 scores coordination number and bidentate only"


def test_a_failing_call_from_an_asymmetric_unit_is_not_reliable():
    """The 3.17 bug, encoded as a refusal.

    Both criteria are counts that a truncated parse can only understate, so an
    ASU can turn a real site into a negative but never into a false positive.
    9C8X reads CN 5 in the deposited coordinates and CN 10 in the assembly.
    """
    truncated = score_site(site(coordination=5, bidentate=1), resolution_A=2.0,
                           coordinate_source="asu")
    assert truncated["call"] == "calcium-like"
    assert truncated["call_reliable"] is False
    assert any("symmetry axis" in c for c in truncated["caveats"])

    passing = score_site(site(coordination=10, bidentate=3), resolution_A=2.0,
                         coordinate_source="asu")
    assert passing["call"] == "lanthanide-like"
    assert passing["call_reliable"] is True, "a pass cannot be an artefact of truncation"


def test_unstated_provenance_is_treated_as_an_asymmetric_unit():
    """Not knowing where the coordinates came from is the case the bug hides
    in, so it gets the same treatment rather than the benefit of the doubt."""
    call = score_site(site(coordination=6, bidentate=0), resolution_A=2.0)
    assert call["call_reliable"] is False
    assert call["coordinate_source"] == "unstated"


def test_a_chelated_site_is_not_callable():
    """Half the first shell non-protein means the geometry describes the
    ligand. The corpus excludes these; so does the score."""
    call = assembly(site(coordination=8, bidentate=2, other_ligand_donor_count=4))
    assert call["call"] == "not callable"
    assert call["score"] is None and call["criteria_met"] == 0


def test_resolution_worse_than_the_contrast_cutoff_is_not_callable():
    call = score_site(site(coordination=10, bidentate=3), resolution_A=3.4,
                      coordinate_source="assembly1")
    assert call["call"] == "not callable"
    assert str(MAX_RESOLUTION_A) in " ".join(call["caveats"])


def test_unknown_resolution_is_scored_but_says_so():
    call = score_site(site(coordination=10, bidentate=3), coordinate_source="assembly1")
    assert call["call"] == "lanthanide-like"
    assert any("Resolution unknown" in c for c in call["caveats"])


def test_every_call_carries_the_n_equals_three_caveat():
    """No path through the scorer may return a bare number."""
    for s in (site(10, 3), site(7, 1), site(8, 2, other_ligand_donor_count=8)):
        caveats = " ".join(assembly(s)["caveats"])
        assert "n = 3 families" in caveats
        assert "not a probability" in caveats
        assert "not a validated classifier" in caveats


def test_nested_site_dicts_from_binding_neighborhood_score_the_same():
    """`binding_neighborhood` nests chemistry/charge/burial; the corpus rows
    are flat. A scorer that read only one shape could not be checked against
    the corpus it came from."""
    nested = {"coordination_number": 10, "other_ligand_donor_count": 0,
              "chemistry": {"bidentate_carboxylates": 3},
              "charge": {"net_charge": -4}, "burial": {"metal_sasa_A2": 0.0}}
    assert assembly(nested)["call"] == "lanthanide-like"
    assert assembly(nested)["triage_only"]["net_charge"] == -4


def test_ranking_breaks_ties_on_raw_descriptors_not_on_a_fitted_weight():
    ranked = score_sites([site(7, 1), site(10, 3), site(9, 2), site(12, 1)],
                         resolution_A=2.0, coordinate_source="assembly1")
    assert [c["criteria_met"] for c in ranked] == [2, 2, 1, 0]
    assert ranked[0]["criteria"][0]["value"] == 10, "within a band, more donors ranks first"
    assert rank_key(ranked[0]) > rank_key(ranked[-1])


def test_an_uncallable_site_sorts_below_everything_callable():
    ranked = score_sites([site(12, 4, other_ligand_donor_count=9), site(6, 0)],
                         resolution_A=2.0, coordinate_source="assembly1")
    assert ranked[0]["call"] == "calcium-like"
    assert ranked[-1]["call"] == "not callable"


# --- the separation this score exists to reproduce -------------------------

def _corpus_groups():
    """Family medians for the 3 Ln families and the 55 Ca accessions, under
    exactly ROADMAP 3.17's filters."""
    import pandas as pd

    from scripts.selectivity_contrast import FAMILIES, quality

    ln = pd.read_parquet(LN_TABLE)
    ln = quality(ln[ln["pdb_id"].isin(FAMILIES)], MAX_RESOLUTION_A)
    ln = ln[ln["element"] != "CA"]
    ln = ln.assign(group=ln["pdb_id"].map(FAMILIES))

    ca = quality(pd.read_parquet(CA_TABLE), MAX_RESOLUTION_A)
    accession = {}
    for pdb_id, record in json.loads(COUNTERPARTS.read_text())["entries"].items():
        got = record.get("accessions") or []
        accession[pdb_id] = got[0] if got else pdb_id
    ca = ca.assign(group=ca["pdb_id"].map(lambda p: accession.get(p, p)))

    def calls(frame):
        medians = frame.groupby("group")[SCORED].median().round().astype(int)
        return {g: assembly(site(**dict(row)))["call"] for g, row in medians.iterrows()}

    return calls(ln), calls(ca)


@pytest.mark.skipif(cached_structure("9PI2") is None, reason="9PI2 not cached")
def test_9pi2_is_called_correctly_ion_by_ion_in_a_single_crystal():
    """The strongest offline check there is: one 0.99 A crystal holding both
    Nd3+ and Ca2+ in the same fold.

    Resolution, fold, crystal form, refinement and depositor are identical
    across the two ions here, so nothing in the usual list of confounders can
    explain a split. Every Nd site must pass and every Ca site must fail; one
    misassignment here means the thresholds are measuring something other than
    the ion.
    """
    text, fmt = cached_structure("9PI2")
    resolution = resolution_from_coordinates(text, fmt)
    assert resolution is not None and resolution < 1.1

    calls = {"ND": set(), "CA": set()}
    for s in binding_neighborhood(text, fmt, metals=ALL_METAL_CODES):
        call = score_site(s, resolution_A=resolution, coordinate_source="asu")
        calls[s["element"].upper()].add(call["call"])
    assert calls["ND"] == {"lanthanide-like"}, calls["ND"]
    assert calls["CA"] == {"calcium-like"}, calls["CA"]


@pytest.mark.skipif(cached_structure("1CLL") is None, reason="1CLL not cached")
def test_calmodulin_is_not_called_lanthanide_like():
    """1CLL is the negative control the whole project is built against: four
    canonical Ca2+ EF-hands at CN 7."""
    text, fmt = cached_structure("1CLL")
    sites = binding_neighborhood(text, fmt, metals=ALL_METAL_CODES)
    assert sites, "1CLL has four calcium sites"
    for call in score_sites(sites, resolution_A=resolution_from_coordinates(text, fmt),
                            coordinate_source="asu"):
        assert call["call"] == "calcium-like"


@pytest.mark.skipif(not (LN_TABLE.exists() and CA_TABLE.exists() and COUNTERPARTS.exists()),
                    reason="corpus tables not built")
def test_geometry_v1_reproduces_the_separation_it_was_derived_from():
    """Every Ln family passes and no Ca accession does -- the 0 of 55 overlap
    that is the actual claim in ROADMAP 3.17, re-derived through the shipped
    scorer rather than through the analysis script."""
    lanthanide, calcium = _corpus_groups()
    assert len(lanthanide) == 3, "3.17 is a three-family result"
    assert set(lanthanide.values()) == {"lanthanide-like"}, lanthanide
    false_positives = [g for g, call in calcium.items() if call == "lanthanide-like"]
    assert not false_positives, f"Ca accessions reaching both thresholds: {false_positives}"
    assert len(calcium) >= 50, "the Ca comparison set should not have silently shrunk"
