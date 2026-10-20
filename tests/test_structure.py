"""Offline tests for coordination-shell measurement. No network access."""
import statistics

import pytest
from lantern.structure import (REE_LIGAND_CODES, ALL_METAL_CODES, DONOR_ELEMENTS,
                                 CHELATED_REE_CODES, binding_neighborhood,
                                 donor_chemistry, cached_structure,
                                 fetch_structure, resolution_from_coordinates,
                                 site_net_charge, _valid_id)


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

    def test_yttrium_has_two_bare_ion_codes_and_both_are_present(self):
        # Y1 is a second bare yttrium ion code, chemically identical to YT3.
        # It was absent until 2026-10-19, which made binding_neighborhood
        # silently return zero sites for the 19 entries that use it.
        assert REE_LIGAND_CODES["Y1"] == REE_LIGAND_CODES["YT3"] == "Y"

    def test_nonexistent_thulium_code_absent(self):
        assert "TM" not in REE_LIGAND_CODES

    def test_every_rare_earth_component_is_either_claimed_or_excluded(self):
        """No rare-earth component may be unaccounted for.

        The PDB holds exactly 27 components whose formula contains a
        lanthanide, Y or Sc (enumerated 2026-10-19). Each one is either a bare
        ion we measure or a pre-chelated reagent we refuse on stated grounds.
        A new code appearing in neither set is the failure this pins: that is
        how Y1 went missing, by the list being written from memory rather than
        from an enumeration.
        """
        assert not (set(REE_LIGAND_CODES) & set(CHELATED_REE_CODES))
        assert len(REE_LIGAND_CODES) + len(CHELATED_REE_CODES) == 27
        assert all(reason for reason in CHELATED_REE_CODES.values())

    def test_excluded_components_are_chelates_not_bare_ions(self):
        # The exclusion rule is chemical, not cosmetic: every excluded code is
        # a metal already wrapped in a cage, polyoxometalate, buffer or
        # fluoride, so its first shell belongs to the reagent. Bare ions are
        # one atom and can never qualify.
        assert "YT3" not in CHELATED_REE_CODES
        assert "YBT" in CHELATED_REE_CODES  # buffer, not biology
        assert "7MT" in CHELATED_REE_CODES  # crystallophore, not biology

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


def test_calcium_is_only_scanned_when_asked_for():
    # The default must stay rare-earth-only: callers that ask for REE sites
    # and silently get calcium back would report competitor sites as hits.
    assert "CA" not in REE_LIGAND_CODES
    assert ALL_METAL_CODES["CA"] == "Ca"


@pytest.mark.skipif(cached_structure("9PI2") is None,
                    reason="run scripts/prefetch_structures.py first")
def test_9pi2_sorts_two_ions_by_loop_chemistry_in_one_crystal():
    """The cleanest control available: Nd3+ and Ca2+ in the same protein,
    same crystal, 0.99 A. Any Ln-vs-Ca descriptor that cannot separate these
    four sites is not measuring selectivity, because every confounder --
    construct, conditions, refinement, resolution -- is held fixed.
    """
    text, fmt = cached_structure("9PI2")
    chain_a = [s for s in binding_neighborhood(text, fmt, metals=ALL_METAL_CODES)
               if s["chain"] == "A"]
    nd = [s for s in chain_a if s["element"] == "Nd"]
    ca = [s for s in chain_a if s["element"] == "Ca"]
    assert len(nd) == 3 and len(ca) == 1

    for site in nd:
        assert site["coordination_number"] == 10
        assert site["chemistry"]["bidentate_carboxylates"] == 4
        assert site["chemistry"]["water"] == 0

    # The one loop that reverts to calcium geometry is the one that took the
    # calcium: CN 7, a single bidentate carboxylate, and a water back at -X.
    assert ca[0]["coordination_number"] == 7
    assert ca[0]["chemistry"]["bidentate_carboxylates"] == 1
    assert ca[0]["chemistry"]["water"] == 1


@pytest.mark.skipif(cached_structure("8DQ2") is None,
                    reason="run scripts/prefetch_structures.py first")
def test_8dq2_lanthanum_sites_expel_water_entirely():
    # Same protein as 8FNR with La3+ instead of Dy3+. CN 10 with four
    # bidentate carboxylates and no water is the signature of Glu at loop
    # position 9 acting as a first-shell bidentate ligand.
    text, fmt = cached_structure("8DQ2")
    la = [s for s in binding_neighborhood(text, fmt) if s["chain"] == "A"]
    assert len(la) == 3
    assert all(s["element"] == "La" for s in la)
    assert all(s["coordination_number"] == 10 for s in la)
    assert all(s["chemistry"]["water"] == 0 for s in la)


@CACHED
def test_bidentate_count_separates_lanthanide_from_calcium_ef_hands():
    """Across every cached EF-hand site, bidentate carboxylate count separates
    the two ions where coordination number alone would be ambiguous.

    8FNR's EF4 is the interesting case: it holds a lanthanide but is
    chemically a calcium site, and it groups with the calcium sites here.
    That is the behaviour we want -- the descriptor follows the chemistry,
    not the element label.
    """
    lanthanide_like, calcium_like = [], []
    for code in ("8FNS", "8FNR", "8DQ2", "9PI2", "1CLL"):
        cached = cached_structure(code)
        if cached is None:
            continue
        for site in binding_neighborhood(*cached, metals=ALL_METAL_CODES):
            if site["chain"] != "A":
                continue
            bucket = calcium_like if site["coordination_number"] <= 7 else lanthanide_like
            bucket.append(site["chemistry"]["bidentate_carboxylates"])

    assert lanthanide_like and calcium_like
    assert min(lanthanide_like) >= 2
    assert max(calcium_like) <= 1


@CACHED
def test_backbone_carbonyl_does_not_discriminate_inside_the_ef_hand_family():
    """A documented limit on the strongest published population-level feature.

    Across the PDB, backbone carbonyl count is the single best Ln-vs-Ca
    discriminator (0.39 vs 1.87 per site). Inside the EF-hand family it is
    worth nothing, because the loop grammar puts a backbone carbonyl at
    position 7 of every loop regardless of which ion binds. This test exists
    so nobody reaches for that feature here expecting it to work.
    """
    carbonyls, sites = set(), 0
    for code in ("8FNS", "8FNR", "8DQ2", "9PI2", "1CLL"):
        cached = cached_structure(code)
        if cached is None:
            continue
        for site in binding_neighborhood(*cached, metals=ALL_METAL_CODES):
            carbonyls.add(site["chemistry"]["backbone_carbonyl"])
            sites += 1
    # Every chain, not a sample: four elements, CN 4 to 10, zero variance.
    assert sites >= 40, f"only {sites} sites -- is the structure cache complete?"
    assert carbonyls == {1}, "EF-hand sites each contribute exactly one backbone carbonyl"


def test_donor_chemistry_classifies_atoms_by_residue_and_name():
    donors = [
        {"kind": "protein", "chain": "A", "residue_number": 5, "residue": "GLU",
         "atom": "OE1", "element": "O", "distance_A": 2.4},
        {"kind": "protein", "chain": "A", "residue_number": 5, "residue": "GLU",
         "atom": "OE2", "element": "O", "distance_A": 2.5},
        {"kind": "protein", "chain": "A", "residue_number": 9, "residue": "ASP",
         "atom": "OD1", "element": "O", "distance_A": 2.4},
        {"kind": "protein", "chain": "A", "residue_number": 12, "residue": "LYS",
         "atom": "O", "element": "O", "distance_A": 2.4},
        {"kind": "water", "chain": "A", "residue_number": 301, "residue": "HOH",
         "atom": "O", "element": "O", "distance_A": 2.5},
    ]
    chem = donor_chemistry(donors)
    assert chem["carboxylate"] == 3           # two Glu O, one Asp O
    assert chem["bidentate_carboxylates"] == 1   # only Glu5 gives both
    assert chem["monodentate_carboxylates"] == 1
    assert chem["backbone_carbonyl"] == 1     # Lys12 main-chain O
    assert chem["water"] == 1
    assert chem["glu_carboxylate_O"] == 2 and chem["asp_carboxylate_O"] == 1


# --- burial and net charge: the Dudev descriptors (M3.1) -------------------

def test_net_charge_counts_residues_not_oxygens():
    """A bidentate carboxylate donates two oxygens and carries one charge.

    Counting donor atoms instead of donor residues would read the synthetic
    site's Glu as -2 and push every bidentate-rich lanthanide site a full
    charge class too negative -- straight into the -4 bucket the Dudev rule
    treats as the Ln-selective one, by an arithmetic error rather than by
    chemistry.
    """
    donors = [
        {"kind": "protein", "chain": "A", "residue_number": 5, "residue": "GLU",
         "atom": "OE1", "element": "O", "distance_A": 2.4},
        {"kind": "protein", "chain": "A", "residue_number": 5, "residue": "GLU",
         "atom": "OE2", "element": "O", "distance_A": 2.5},
        {"kind": "protein", "chain": "A", "residue_number": 9, "residue": "ASP",
         "atom": "OD1", "element": "O", "distance_A": 2.4},
        {"kind": "water", "chain": "A", "residue_number": 301, "residue": "HOH",
         "atom": "O", "element": "O", "distance_A": 2.5},
    ]
    charge = site_net_charge(donor_chemistry(donors))
    assert charge["anionic_groups"] == 2        # one Glu, one Asp
    assert charge["net_charge"] == -2           # not -3, which atom-counting gives
    assert charge["neutral_donors"] == 1        # the water
    assert charge["unassigned_donors"] == 0


def test_unassigned_donors_flags_charge_the_model_does_not_cover():
    """His and non-water heteroatom ligands are not in the charge model.

    Reporting -1 for a site whose shell is half unmodelled would be a number
    with no error bar attached. The count is what tells a caller the figure
    is partial.
    """
    donors = [
        {"kind": "protein", "chain": "A", "residue_number": 5, "residue": "ASP",
         "atom": "OD1", "element": "O", "distance_A": 2.4},
        {"kind": "protein", "chain": "A", "residue_number": 7, "residue": "HIS",
         "atom": "NE2", "element": "N", "distance_A": 2.5},
        {"kind": "ligand", "chain": "A", "residue_number": 400, "residue": "EDO",
         "atom": "O1", "element": "O", "distance_A": 2.6},
    ]
    charge = site_net_charge(donor_chemistry(donors))
    assert charge["net_charge"] == -1
    assert charge["unassigned_donors"] == 2, "His N and the ligand O are unmodelled"


def test_burial_is_measured_with_waters_removed():
    """Ordered waters must not be allowed to shield the ion.

    An exposed site attracts more ordered water, so counting waters as
    occluders inverts the descriptor: the most solvent-exposed sites would
    report the smallest SASA. Checked on real coordinates, where the four
    Nd sites of 8FNS each carry two first-shell waters.
    """
    cached = cached_structure("8FNS")
    if cached is None:
        pytest.skip("8FNS not in the structure cache")
    sites = binding_neighborhood(*cached)
    assert sites, "no Nd sites found in 8FNS"
    for site in sites:
        assert site["chemistry"]["water"] >= 1, "expected first-shell waters here"
        assert site["burial"]["metal_sasa_A2"] is not None
        # Buried or nearly so despite those waters, which is only possible
        # because they were stripped before the probe was rolled.
        assert site["burial"]["metal_sasa_A2"] < 10.0


def test_burial_reports_a_count_alongside_sasa():
    """Two measures that can be checked against each other.

    SASA depends on a per-element radius table that may not know an exotic
    lanthanide; a heavy-atom count does not. If the two ever disagree
    wildly, the radius table is the thing to suspect.
    """
    cached = cached_structure("8FNS")
    if cached is None:
        pytest.skip("8FNS not in the structure cache")
    for site in binding_neighborhood(*cached):
        burial = site["burial"]
        assert burial["protein_atoms_within_8A"] > 20, "an EF-hand site is enclosed"
        assert burial["shell_net_charge"] == (burial["shell_cationic_residues"]
                                              - burial["shell_anionic_residues"])


def test_site_dicts_are_json_serialisable():
    """numpy scalars from Bio.PDB must not reach a site dict.

    A numpy float passes every in-process assertion and then fails at
    json.dump() in whatever writes the corpus out, which is a long way from
    where it was introduced.
    """
    import json
    cached = cached_structure("8FNS")
    if cached is None:
        pytest.skip("8FNS not in the structure cache")
    json.dumps(binding_neighborhood(*cached, metals=ALL_METAL_CODES))


def test_net_charge_does_not_separate_lanthanide_from_calcium_ef_hands():
    """The measured M3.1 result, pinned so it cannot be quietly overturned.

    An EF-hand loop puts carboxylates at fixed loop positions, so first-shell
    charge is near-constant across the fold: 97.6% of cached sites are -3 or
    -4 whichever ion is bound. The Dudev rule needs charge to vary to have
    anything to say, so this descriptor cannot rank within the family -- and
    anyone who later sees it "working" should suspect their contrast set
    before believing it.
    """
    charges = {"lanthanide": [], "calcium": []}
    for code in ("8FNS", "8FNR", "8DQ2", "9PI2", "1CLL"):
        cached = cached_structure(code)
        if cached is None:
            continue
        for site in binding_neighborhood(*cached, metals=ALL_METAL_CODES):
            family = ("lanthanide" if site["metal"].strip().upper() in REE_LIGAND_CODES
                      else "calcium")
            charges[family].append(site["charge"]["net_charge"])

    assert len(charges["calcium"]) >= 6 and len(charges["lanthanide"]) >= 30
    pooled = charges["lanthanide"] + charges["calcium"]
    in_class = sum(1 for c in pooled if c in (-3, -4)) / len(pooled)
    assert in_class > 0.95, "charge stopped being near-constant across the fold"
    # Both families occupy the same classes; the medians differ by at most one.
    assert set(charges["calcium"]) <= {-3, -4}
    assert abs(statistics.median(charges["lanthanide"])
               - statistics.median(charges["calcium"])) <= 1


def test_resolution_is_read_from_both_coordinate_formats():
    """geometry-v2 gates on resolution, so a silent None would turn the gate
    into a caveat on every entry."""
    pdb = ("REMARK   2\n"
           "REMARK   2 RESOLUTION.    1.85 ANGSTROMS.\n")
    cif = "_refine.ls_d_res_high              1.85\n"
    assert resolution_from_coordinates(pdb, "pdb") == 1.85
    assert resolution_from_coordinates(cif, "cif") == 1.85
    # A mislabelled format must degrade to the right answer, not to None.
    assert resolution_from_coordinates(cif, "pdb") == 1.85
    assert resolution_from_coordinates(pdb, "cif") == 1.85


def test_an_entry_with_no_diffraction_resolution_returns_none():
    """NMR entries say so in words. None is the honest answer and geometry-v2
    turns it into a caveat; inventing a number would admit entries the
    contrast behind the thresholds excluded.
    """
    nmr = "REMARK   2 RESOLUTION. NOT APPLICABLE.\n"
    assert resolution_from_coordinates(nmr, "pdb") is None
    assert resolution_from_coordinates("", "cif") is None


@pytest.mark.skipif(cached_structure("9PI2") is None, reason="9PI2 not cached")
def test_cached_demo_structures_report_their_real_resolution():
    for code, expected in (("9PI2", 0.99), ("8FNS", 1.01), ("1CLL", 1.7)):
        cached = cached_structure(code)
        if cached is None:
            continue
        assert resolution_from_coordinates(*cached) == pytest.approx(expected)
