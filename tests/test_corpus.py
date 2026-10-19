"""Offline tests for the M2 corpus pipeline. No network access.

These cover the parts that are pure logic -- title classification, the
chelator columns, the enumeration's own integrity. Parsing 636 structures is
not a unit test; `scripts/build_site_table.py` reports its own failures and
the parquet it writes is checked here only if it has been built.
"""
import json
from pathlib import Path

import pytest

from scripts.build_site_table import KNOWN_CHELATORS, title_first_pass

ROOT = Path(__file__).resolve().parent.parent
ENUMERATION = ROOT / "data" / "ree_pdb_entries.json"
TABLE = ROOT / "data" / "lanthanide_sites.parquet"


def test_title_first_pass_records_why_it_fired():
    """A label with no recorded basis cannot be audited later."""
    label, basis = title_first_pass(
        "NMR SOLUTION STRUCTURE OF CERIUM-LOADED CALMODULIN")
    assert label == "ln_substituted_ca"
    assert basis == "title:calmodulin", "the matching keyword must be recorded"


def test_title_first_pass_prefers_the_more_specific_rule():
    """An LBT fused to calmodulin is an engineered construct, not a
    Ln-substituted calcium site. Rule order is what decides that, so it is
    pinned rather than left to dict ordering.
    """
    label, _ = title_first_pass(
        "CRYSTAL STRUCTURE OF A LANTHANIDE-BINDING TAG FUSED TO CALMODULIN")
    assert label == "engineered_lbt"


def test_title_first_pass_admits_when_it_knows_nothing():
    """The commonest title in the corpus says nothing at all.

    Returning a confident class for "STRUCTURE OF X" would quietly turn
    2663 unlabelled sites into whichever class happened to be the default.
    """
    label, basis = title_first_pass("CRYSTAL STRUCTURE OF A HYPOTHETICAL PROTEIN")
    assert label == "unclassified"
    assert basis == "title:none"
    assert title_first_pass("")[0] == "unclassified"
    assert title_first_pass(None)[0] == "unclassified"


def test_no_chelator_name_contains_the_join_separator():
    """A regression test for a real bug.

    `first_shell_known_chelators` joins names into one string.
    "pyridine-2,6-dicarboxylate" contains a comma, so joining on a comma and
    splitting back produced two fictitious chelators, "pyridine-2" and
    "6-dicarboxylate", in the summary. The column now joins on ";", so no
    name may contain one.
    """
    for code, name in KNOWN_CHELATORS.items():
        assert ";" not in name, f"{code} would be split by the join separator"


def test_enumeration_is_complete_and_marked_uncurated():
    payload = json.loads(ENUMERATION.read_text())
    assert len(payload["entries"]) == 636
    assert "curation_status" in json.dumps(payload["_provenance"]).lower() \
        or "not yet curated" in payload["_provenance"]["description"].lower()
    assert all(entry.get("elements") for entry in payload["entries"].values())


@pytest.mark.skipif(not TABLE.exists(), reason="site table not built")
def test_site_table_schema_and_scale():
    """If the parquet has been built, it must carry the descriptors M3.1
    added -- a table missing them would silently un-do that work."""
    import pandas as pd
    frame = pd.read_parquet(TABLE)
    for column in ("pdb_id", "family", "coordination_number", "net_charge",
                   "metal_sasa_A2", "chelator_flagged", "class_first_pass",
                   "class_basis", "first_shell_known_chelators"):
        assert column in frame.columns, column
    assert frame["pdb_id"].nunique() == 636
    assert set(frame["family"]) <= {"lanthanide", "calcium"}
    assert (frame["family"] == "lanthanide").sum() > 2000


@pytest.mark.skipif(not TABLE.exists(), reason="site table not built")
def test_charge_varies_outside_the_ef_hand_fold():
    """The measured answer to the question §3.12 left open.

    Inside the EF-hand fold 97.6% of sites carry -3 or -4, which is why net
    charge could not rank within it. §3.12 attributed that to the fold rather
    than to the descriptor. Across the corpus the same figure must be far
    lower, or that explanation was wrong.
    """
    import pandas as pd
    frame = pd.read_parquet(TABLE)
    lanthanide = frame[frame["family"] == "lanthanide"]
    in_class = lanthanide["net_charge"].isin([-3, -4]).mean()
    assert in_class < 0.5, (
        f"{in_class:.1%} of corpus Ln sites are -3/-4; if this approaches the "
        "EF-hand figure of 97.6% then charge is constant everywhere and "
        "§3.12's explanation needs rewriting")
    assert lanthanide["net_charge"].nunique() >= 4


def test_title_pass_catches_the_abbreviated_lanmodulin():
    """9PI2 is titled "Ancylobacter lacus LanM", not "lanmodulin".

    The longer keyword dropped a structurally confirmed lanthanide binder
    into the unclassified pile -- the same failure mode as §3.11's HMM miss,
    reached by a different route. Pinned because the keyword list is the
    kind of thing that gets "tidied".
    """
    label, basis = title_first_pass(
        "X-ray crystal structure of Ancylobacter lacus LanM bound to "
        "Nd(III) and Ca(II)")
    assert label == "natural_ln_biology", basis
    assert title_first_pass("lanmodulin (LanM) with La")[0] == "natural_ln_biology"


@pytest.mark.skipif(not TABLE.exists(), reason="site table not built")
def test_site_signature_strips_chain_but_keeps_identity():
    """The signature is what makes a matched Ln/Ca pair findable.

    It must drop the chain -- otherwise two NCS copies of one site never
    compare equal and the within-entry tier is empty by construction -- while
    keeping residue name and number, which is what stops two unrelated sites
    from matching on shape alone.
    """
    import pandas as pd
    frame = pd.read_parquet(TABLE)
    for column in ("first_shell_protein_residues", "site_signature"):
        assert column in frame.columns, column

    with_donors = frame[frame["protein_donor_count"] > 0]
    assert len(with_donors), "no site has a protein donor; parser is broken"
    assert (with_donors["site_signature"].str.len() > 0).all()
    # A chain id would survive as a colon; the signature uses none.
    assert not with_donors["site_signature"].str.contains(":").any()
    # The per-residue column keeps the chain, and must still carry it.
    assert with_donors["first_shell_protein_residues"].str.contains(":").all()

    # A site with no protein donors must produce an empty signature rather
    # than a token that would match every other such site.
    bare = frame[frame["protein_donor_count"] == 0]
    if len(bare):
        assert (bare["site_signature"].str.len() == 0).all()


@pytest.mark.skipif(not TABLE.exists(), reason="site table not built")
def test_signature_residue_count_never_exceeds_donor_count():
    """One residue can donate two atoms -- a bidentate carboxylate -- so
    residues <= donors. The reverse would mean the signature invented a
    residue, which is the failure that would silently corrupt every pair.
    """
    import pandas as pd
    frame = pd.read_parquet(TABLE)
    sized = frame[frame["site_signature"].str.len() > 0]
    residues = sized["site_signature"].str.count(";") + 1
    assert (residues <= sized["protein_donor_count"]).all()


@pytest.mark.skipif(not TABLE.exists(), reason="site table not built")
def test_table_carries_resolution_for_the_paired_contrast():
    """Every geometric column is resolution-dependent, so the cutoff has to
    be appliable from the table itself rather than re-fetched per analysis.
    """
    import pandas as pd
    frame = pd.read_parquet(TABLE)
    assert "resolution_A" in frame.columns
    assert "method" in frame.columns
    xray = frame[frame["method"] == "X-RAY DIFFRACTION"]
    assert xray["resolution_A"].notna().all(), (
        "an X-ray entry with no resolution would silently survive the "
        "quality cut that the matched contrast depends on")
    # NMR has no resolution in this sense; it must be absent, not zero.
    nmr = frame[frame["method"] == "SOLUTION NMR"]
    if len(nmr):
        assert nmr["resolution_A"].isna().all()


def test_resolution_filter_is_not_optional_once_asked_for():
    """Regression: the matched contrast's first run filtered one side only.

    Capping the Ca set at 2.5 A while leaving Corpus A uncapped left the Ln
    sides 0.17 A worse-resolved than their partners and produced a +0.08 A
    donor-distance "effect" that vanished at a symmetric cutoff. The guard
    is that a filter request against a table with no resolution column must
    fail loudly rather than silently return everything.
    """
    import pandas as pd
    from scripts.paired_sites import load
    frame = pd.DataFrame({
        "site_signature": ["ASP1;ASP2;ASP3"] * 3,
        "protein_donor_count": [4, 4, 4],
        "family": ["lanthanide", "calcium", "calcium"],
    })
    path = ROOT / "tests" / "_tmp_no_resolution.parquet"
    frame.to_parquet(path, index=False)
    try:
        assert len(load(path, 2, 3)) == 3, "unfiltered load should pass all"
        with pytest.raises(SystemExit, match="resolution"):
            load(path, 2, 3, 2.5)
    finally:
        path.unlink(missing_ok=True)


def test_land_is_natural_biology_without_matching_islandicus():
    """Regression: the obvious keyword for landiscernin is a trap.

    LanD is a third natural family -- a lanthanide chaperone whose published
    function is separating light lanthanides -- and the first keyword set
    missed all four of its entries. The obvious fix, the substring "land",
    also matches "Ignicoccus islandicus" (6QSS), a malate dehydrogenase
    co-crystallised with Tb-Xo4, which is a phasing experiment. Both halves
    are pinned here because fixing the miss by reintroducing the trap is the
    likely regression.
    """
    label, basis = title_first_pass(
        "X-ray crystal structure of Methylorubrum extorquens La(III)-bound LanD")
    assert label == "natural_ln_biology", basis

    label, _ = title_first_pass(
        "Crystal Structure of Ignicoccus islandicus malate dehydrogenase "
        "co-crystallized with 10 mM Tb-Xo4")
    assert label != "natural_ln_biology", (
        "'islandicus' contains 'land'; a soaked archaeal dehydrogenase is "
        "not lanthanide biology")


def test_table_records_which_coordinates_each_site_came_from():
    """A site parsed from the asymmetric unit when its partner protomer is
    missing is wrong in every geometric column at once -- 9C8X read CN 5,
    charge -3, SASA 47.9 from the ASU against CN 10, charge -6, SASA 0.0
    from the dimer. Which source was used therefore has to be recoverable
    from the table, or a contrast that mixes the two unevenly between its
    arms is confounded with no way to notice.
    """
    import pandas as pd
    frame = pd.read_parquet(TABLE)
    assert "coordinate_source" in frame.columns
    assert set(frame["coordinate_source"]) <= {"asu", "assembly1"}
    # One entry is one deposition, so it cannot have been parsed both ways.
    per_entry = frame.groupby("pdb_id")["coordinate_source"].nunique()
    assert (per_entry == 1).all(), "an entry parsed from two sources at once"
