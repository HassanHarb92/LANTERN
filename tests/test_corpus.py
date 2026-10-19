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
