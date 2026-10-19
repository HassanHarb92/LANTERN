"""Offline tests for coordination-shell measurement. No network access."""
import pytest
from reefinder.structure import (REE_LIGAND_CODES, DONOR_ELEMENTS, binding_neighborhood,
                                 cached_structure, fetch_structure, _valid_id)


def _atom(serial, name, resname, chain, resseq, x, y, z, element, hetatm=False):
    """One fixed-column PDB coordinate record."""
    record = "HETATM" if hetatm else "ATOM  "
    return (f"{record}{serial:>5} {name:<4}{'':1}{resname:>3} {chain}{resseq:>4}"
            f"{'':4}{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.00:>6.2f}{20.00:>6.2f}{'':10}{element:>2}")


# A neodymium ion with one carboxylate oxygen at 2.4 A, that oxygen's own
# carbon at 2.9 A, one water oxygen at 2.5 A, and a nitrogen out at 5.0 A.
# A correct first shell is the two oxygens: the carbon is not a donor, the
# water is, and the distant nitrogen is in the second shell.
SYNTHETIC_SITE = "\n".join([
    _atom(1, "ND", "ND", "A", 201, 0.0, 0.0, 0.0, "ND", hetatm=True),
    _atom(2, "OD1", "ASP", "A", 35, 2.4, 0.0, 0.0, "O"),
    _atom(3, "CG", "ASP", "A", 35, 2.9, 0.0, 0.0, "C"),
    _atom(4, "O", "HOH", "A", 301, 0.0, 2.5, 0.0, "O", hetatm=True),
    _atom(5, "NZ", "LYS", "A", 40, 0.0, 0.0, 5.0, "N"),
    "END",
])


@pytest.fixture(scope="module")
def site():
    sites = binding_neighborhood(SYNTHETIC_SITE, "pdb")
    assert len(sites) == 1, "the single Nd ion should yield exactly one site"
    return sites[0]


def test_ion_identified_with_element(site):
    assert site["element"] == "Nd"


def test_carbon_is_not_counted_as_a_donor(site):
    # The carboxylate carbon sits 2.9 A away, inside the radius but not a donor.
    assert all(d["element"] != "C" for d in site["donors"])


def test_water_is_counted_as_a_donor(site):
    assert site["water_donor_count"] == 1


def test_coordination_number_splits_protein_and_water(site):
    assert site["coordination_number"] == 2
    assert site["protein_donor_count"] == 1


def test_second_shell_atom_excluded(site):
    assert all(d["distance_A"] <= 3.2 for d in site["donors"])
    assert all(d["residue"] != "LYS" for d in site["donors"])


def test_donors_sorted_by_distance(site):
    distances = [d["distance_A"] for d in site["donors"]]
    assert distances == sorted(distances)


def test_structure_without_rare_earth_yields_no_sites():
    calcium_only = "\n".join([
        _atom(1, "CA", "CA", "A", 149, 0.0, 0.0, 0.0, "CA", hetatm=True),
        _atom(2, "OD1", "ASP", "A", 20, 2.4, 0.0, 0.0, "O"),
        "END",
    ])
    assert binding_neighborhood(calcium_only, "pdb") == []


class TestLigandCodes:
    """The chemical-component codes that actually exist in the PDB."""

    def test_erbium_and_yttrium_use_suffixed_codes(self):
        # Plain ER and Y are not rare-earth ion components; omitting ER3/YT3
        # made the previous implementation blind to every erbium and yttrium site.
        assert "ER3" in REE_LIGAND_CODES and "YT3" in REE_LIGAND_CODES
        assert "ER" not in REE_LIGAND_CODES and "Y" not in REE_LIGAND_CODES

    def test_nonexistent_thulium_code_absent(self):
        assert "TM" not in REE_LIGAND_CODES

    @pytest.mark.parametrize("pair", [("EU", "EU3"), ("GD", "GD3"), ("HO", "HO3"), ("YB", "YB2")])
    def test_dual_coded_elements_merge_to_one_element(self, pair):
        first, second = pair
        assert REE_LIGAND_CODES[first] == REE_LIGAND_CODES[second]

    def test_donor_elements_are_hard_base_atoms(self):
        assert DONOR_ELEMENTS == {"O", "N", "S"}


@pytest.mark.parametrize("bad", ["", "8FN", "8FNSS", "8FN!"])
def test_invalid_accessions_rejected(bad):
    with pytest.raises(ValueError):
        _valid_id(bad)


def test_fetch_structure_rejects_bad_id_before_any_request():
    # Validation must happen before the network call, so this stays offline.
    with pytest.raises(ValueError):
        fetch_structure("nope!")


# --- Regression tests over the prefetched real structures (M1) --------------
# These use data/structures/, populated by scripts/prefetch_structures.py, so
# they stay offline while testing against authentic deposited coordinates
# rather than a hand-written fixture.

CACHED = pytest.mark.skipif(cached_structure("8FNR") is None,
                            reason="run scripts/prefetch_structures.py first")


@CACHED
def test_8fns_neodymium_sites_match_documented_coordination():
    # ROADMAP 3.1: three Nd sites at CN 9 (7 protein O + 2 water), one at 10.
    text, fmt = cached_structure("8FNS")
    sites = binding_neighborhood(text, fmt)
    assert {s["element"] for s in sites} == {"Nd"}
    counts = sorted(s["coordination_number"] for s in sites)
    assert counts == [9, 9, 9, 10]
    for site in sites:
        assert site["water_donor_count"] == 2
        assert 2.4 <= site["mean_donor_distance_A"] <= 2.7


@CACHED
def test_8fnr_dysprosium_sites_separate_by_coordination_number():
    # ROADMAP 3.6: EF1-3 are CN 9 with no water; EF4 is CN 7 with one water,
    # i.e. calcium-like, and is the only loop PROSITE PS00018 detects.
    text, fmt = cached_structure("8FNR")
    chain_a = [s for s in binding_neighborhood(text, fmt) if s["chain"] == "A"]
    assert len(chain_a) == 4

    by_site = {s["site"]: s for s in chain_a}
    for site_id in ("201", "202", "203"):
        site = by_site[site_id]
        assert site["coordination_number"] == 9
        assert site["water_donor_count"] == 0

    ef4 = by_site["204"]
    assert ef4["coordination_number"] == 7
    assert ef4["water_donor_count"] == 1
    # EF4's donors start at 107 -- the single position PS00018 matches.
    assert min(d["residue_number"] for d in ef4["donors"]
               if d["kind"] == "protein") == 107


@CACHED
def test_calmodulin_has_no_rare_earth_sites():
    # 1CLL is the calcium contrast set; finding a lanthanide in it would mean
    # the ion table had started matching unrelated components.
    text, fmt = cached_structure("1CLL")
    assert binding_neighborhood(text, fmt) == []
