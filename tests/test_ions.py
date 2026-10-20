"""Tests for lantern/ions.py.

Two jobs, in this order of importance. The second one first: pin the claims
this module makes about what it CANNOT do, because those are the claims the
rest of the platform is built on and the ones a future "improvement" will
quietly delete. The first: check the published numbers are the published
numbers, against a source outside this repository.
"""
import inspect
from pathlib import Path

import pytest

from lantern import ions
from lantern.chemistry import METALS, score_sequence, screen

ROOT = Path(__file__).resolve().parent.parent
SITE_TABLE = ROOT / "data" / "lanthanide_sites.parquet"


# --- the contraction is real ------------------------------------------------

def test_radii_decrease_monotonically_from_la_to_lu_at_every_coordination_number():
    """The lanthanide contraction, which is the only reason a target ion can
    mean anything at all here.

    4f electrons shield the growing nuclear charge poorly, so the trivalent
    radius falls steadily across the series rather than staying flat. If this
    ever fails, a radius has been mistyped and every size_match() number in
    the platform is wrong -- the ordering of the series is the one property
    the whole module rests on.
    """
    for cn in (6, 8, 9):
        tabulated = [(ion, ions.SHANNON_EFFECTIVE_RADII_A[ion][cn])
                     for ion in ions.LANTHANIDES_III
                     if cn in ions.SHANNON_EFFECTIVE_RADII_A[ion]]
        assert len(tabulated) == 15, f"CN {cn} should cover the whole series"
        radii = [r for _, r in tabulated]
        assert all(a > b for a, b in zip(radii, radii[1:])), (cn, tabulated)

    # And the size of it: about 17% from La3+ to Lu3+ at CN 6.
    shrinkage = 1 - ions.radius("Lu3+", 6) / ions.radius("La3+", 6)
    assert 0.16 < shrinkage < 0.18


def test_radius_grows_with_coordination_number_for_every_tabulated_ion():
    """More donors crowding an ion push them further out, so the radius
    assigned at CN 9 must exceed the one at CN 8, and CN 8 the one at CN 6.

    Independent of the monotonicity check above: that one walks the series at
    fixed CN, this one walks CN at fixed ion, so between them a single
    transposed digit cannot survive in either direction.
    """
    for ion, by_cn in ions.SHANNON_EFFECTIVE_RADII_A.items():
        cns = sorted(by_cn)
        radii = [by_cn[cn] for cn in cns]
        assert all(a < b for a, b in zip(radii, radii[1:])), (ion, by_cn)


def test_cn6_and_cn8_radii_match_independently_published_crystal_radii():
    """Check the table against a second publication of the same data.

    Shannon reports two scales: *effective* radii anchored to r(O2-) = 1.40 A,
    which is what this module stores, and *crystal* radii anchored to
    r(O2-) = 1.26 A. They differ by exactly 0.14 A for every cation, by
    construction of the two anchors. WebElements publishes the crystal set, in
    picometres, on its per-element "atom sizes" pages
    (e.g. https://www.webelements.com/cerium/atom_sizes.html).

    So converting their numbers and comparing is a genuine external check, not
    a restatement: the values below were read off that second source and would
    not agree with a transcription error here. CN 7, 9 and 10 are absent from
    it and are covered instead by the monotonicity tests above and by the
    corpus comparison at the bottom of this file.
    """
    crystal_radii_pm = {
        ("La3+", 6): 117.2, ("La3+", 8): 130.0,
        ("Ce3+", 6): 115.0, ("Ce3+", 8): 128.3,
        ("Eu3+", 6): 108.7, ("Eu3+", 8): 120.6,
        ("Dy3+", 6): 105.2, ("Dy3+", 8): 116.7,
        ("Yb3+", 6): 100.8, ("Yb3+", 8): 112.5,
        ("Lu3+", 6): 100.1, ("Lu3+", 8): 111.7,
        ("Ca2+", 6): 114.0, ("Ca2+", 8): 126.0,
        ("Ce4+", 6): 101.0, ("Ce4+", 8): 111.0,
        ("Eu2+", 6): 131.0, ("Eu2+", 8): 139.0,
        ("Yb2+", 6): 116.0, ("Yb2+", 8): 128.0,
    }
    crystal_minus_effective_A = 0.14
    for (ion, cn), crystal_pm in crystal_radii_pm.items():
        expected = crystal_pm / 100.0 - crystal_minus_effective_A
        assert ions.radius(ion, cn) == pytest.approx(expected, abs=0.0005), (ion, cn)


# --- why this project is hard ----------------------------------------------

def test_calcium_is_size_indistinguishable_from_a_light_lanthanide():
    """The structural reason calcium proteins bind lanthanides, as numbers.

    Every site this platform looks at is a calcium site that a lanthanide has
    displaced, and the obvious question is why a protein evolved for Ca2+ has
    any affinity for Ln3+ at all. Part of the answer is here: at the
    coordination numbers proteins actually use, Ca2+ is not merely near the
    lanthanide range, it is *inside* it, and closer to its nearest lanthanide
    neighbour than adjacent lanthanides are to each other.

    Worth stating precisely, because the loose version of this claim puts
    Ca2+ next to the mid-series. It does not. Its nearest neighbour is Ce3+ at
    CN 7 (0.010 A) and Pr3+ at CN 8 (0.006 A) -- the early, large end.

    The consequence for this module: a size criterion cannot separate Ca2+
    from Ln3+, so size_match() must never be presented as a selectivity
    argument. Selectivity comes from charge and desolvation, which is why
    structure.py counts pocket charge and geometry.py counts donors.
    """
    for cn in (7, 8):
        calcium = ions.radius("Ca2+", cn)
        series = {ion: ions.SHANNON_EFFECTIVE_RADII_A[ion][cn]
                  for ion in ions.LANTHANIDES_III
                  if cn in ions.SHANNON_EFFECTIVE_RADII_A[ion]}

        # Inside the lanthanide range, not merely adjacent to it.
        assert min(series.values()) < calcium < max(series.values())

        nearest, gap = min(((ion, abs(calcium - r)) for ion, r in series.items()),
                           key=lambda pair: pair[1])
        assert gap < 0.015, (cn, nearest, gap)
        assert nearest in ("Ce3+", "Pr3+"), (cn, nearest)

        # The sharper form: Ca2+ is closer to *every* lanthanide than the two
        # ends of the lanthanide series are to each other. Any size window
        # wide enough to admit the whole series admits calcium too.
        worst = max(abs(calcium - r) for r in series.values())
        assert worst < ions.contraction_span_A(cn), (cn, worst)


def test_size_match_cannot_separate_adjacent_lanthanides():
    """The honest limit on the one ion-dependent number this module produces.

    Neighbouring lanthanides differ by at most 0.020 A at CN 9. The
    oxide-anchored donor radius this module uses is itself biased by 0.045 A
    against real protein sites (see the corpus test below). The systematic
    error is therefore more than twice the signal needed to tell Nd3+ from
    Pr3+, before crystallographic coordinate error -- of order 0.2 A at the
    2.0-2.5 A resolutions in this corpus -- is considered at all.

    So a fit difference between adjacent lanthanides is noise. This test
    exists so that nobody later reads a 0.10 gap in `fit` as a result.
    """
    cn = 9
    radii = [ions.radius(ion, cn) for ion in ions.LANTHANIDES_III]
    widest_adjacent_gap = max(a - b for a, b in zip(radii, radii[1:]))
    assert widest_adjacent_gap == pytest.approx(0.020, abs=1e-6)
    assert widest_adjacent_gap < 0.045, "signal is smaller than the method's own bias"

    fits = [ions.size_match(ion, cn, 2.56)["fit"] for ion in ions.LANTHANIDES_III]
    assert max(abs(a - b) for a, b in zip(fits, fits[1:])) < 0.12


def test_size_match_cannot_separate_calcium_from_lanthanides_at_a_real_ef_hand():
    """The same limit, run on the geometry that actually matters.

    CN 7 with a 2.43 A mean donor distance is the median calcium site in this
    project's corpus -- the canonical pentagonal-bipyramidal EF-hand. Ca2+ is
    not the top-scoring ion there (Sm3+ is, narrowly), but it lands in the
    middle of the lanthanide band, outscoring most of the series.

    The quantitative form of "cannot separate": the gap from Ca2+ to the best
    lanthanide is smaller than the module's own systematic bias. The
    oxide-anchored donor radius is off by 0.045 A against real protein sites,
    which at CN 7 is 0.26 in fit units; the Ca2+-to-best gap is about 0.11. A
    ranking whose spread is under half its own bias is not a discrimination,
    and nothing downstream may present it as one.
    """
    calcium = ions.size_match("Ca2+", 7, 2.43)["fit"]
    lanthanides = ions.rank_by_size_match(7, 2.43)
    fits = [m["fit"] for m in lanthanides]

    assert min(fits) < calcium < max(fits), "Ca2+ should sit inside the Ln band"
    assert sum(1 for f in fits if f < calcium) >= len(fits) // 2

    corpus_bias_in_fit_units = 0.045 / ions.contraction_span_A(7)
    assert max(fits) - calcium < corpus_bias_in_fit_units


# --- the ion-independence statement must be true, not just written ----------

def test_sequence_scorer_really_does_ignore_the_target_ion():
    """Pins SEQUENCE_SCORE_IS_ION_INDEPENDENT to the code it describes.

    The constant is a claim about chemistry.score_sequence(). Asserting the
    prose alone would let the two drift apart silently: somebody adds an ion
    argument, the sequence score becomes ion-dependent, and the UI keeps
    displaying a sentence saying it cannot be. Checked structurally, because
    the thing being guarded is a signature.

    If this fails, the fix is to update the constant and the UI copy, not to
    delete the test.
    """
    for function in (score_sequence, screen):
        parameters = inspect.signature(function).parameters
        assert not any(word in name.lower()
                       for name in parameters
                       for word in ("ion", "metal", "target", "element")), \
            f"{function.__name__} grew an ion argument; the constant is now false"

    assert "cannot" in ions.SEQUENCE_SCORE_IS_ION_INDEPENDENT
    assert "size propensity" in ions.SEQUENCE_SCORE_IS_ION_INDEPENDENT


def test_chemistry_metals_table_carries_no_number_that_could_enter_a_score():
    """METALS is a display lookup, and must stay one.

    The dropdown is fed from chemistry.METALS. As long as every value in it is
    prose, no code path can accidentally multiply a score by something
    ion-specific and make the dropdown look functional. A number appearing
    there is the first step of exactly that mistake.
    """
    for key, entry in METALS.items():
        assert all(isinstance(value, str) for value in entry.values()), key


# --- parsing ----------------------------------------------------------------

def test_parser_accepts_every_key_of_the_chemistry_metals_dropdown():
    """The dropdown's own strings must round-trip, or the ion the user picked
    arrives at this module as an unknown."""
    for key in METALS:
        assert ions.canonical_ion(key) == key


@pytest.mark.parametrize("spelling", [
    "Ce3+", "ce3+", "CE3+", "Ce 3+", "CE 3+", "Ce+3", "Ce(3+)",
    "Ce(III)", "ce(iii)", "Ce III", "cerium", "Cerium", "CERIUM",
    "cerium(III)", " Ce3+ ", "Ce",
])
def test_parser_is_tolerant_of_the_spellings_people_actually_type(spelling):
    assert ions.canonical_ion(spelling) == "Ce3+"


def test_bare_element_takes_the_oxidation_state_it_actually_has():
    assert ions.canonical_ion("Dy") == "Dy3+"
    assert ions.canonical_ion("yttrium") == "Y3+"
    # Not 3+: calcium is the one ion here that is not trivalent, and defaulting
    # it to Ca3+ would produce an ion with no radius and no referent.
    assert ions.canonical_ion("Ca") == "Ca2+"
    assert ions.canonical_ion("calcium") == "Ca2+"


def test_parser_refuses_pdb_component_codes_that_look_like_charge_strings():
    """A bare trailing digit is not a charge, and must not be read as one.

    structure.REE_LIGAND_CODES contains ER3, EU3, GD3, HO3, YB2 and Y1. Four
    would happen to parse correctly as charges, YB2 is genuinely ytterbium(II)
    so it would too -- and Y1 is simply a second RCSB code for the yttrium ion
    and would parse as a non-existent Y+. One silent wrong answer is worse
    than six refusals, so the parser requires an explicit sign and component
    codes stay structure.py's business.
    """
    for code in ("ER3", "EU3", "GD3", "HO3", "YB2", "Y1", "YT3", "LA"):
        if code == "LA":
            assert ions.canonical_ion(code) == "La3+"   # a bare symbol, not a code
        else:
            assert ions.canonical_ion(code) is None, code


@pytest.mark.parametrize("rubbish", [
    "", "   ", "unobtainium", "Ti", "Fe3+", "Zn2+", "Ce3-", "3+", "Ce3",
    None, 3, [], "Ce3++",
])
def test_parser_returns_none_rather_than_a_plausible_guess(rubbish):
    assert ions.canonical_ion(rubbish) is None


def test_an_unusual_oxidation_state_is_parsed_but_not_silently_coerced():
    """Ce4+ and Eu2+ are how rare-earth separation is actually done
    industrially, so a user typing them means them.

    The contract: they canonicalise (they are real ions) but they resolve to
    their own radii, never to the trivalent ones. Handing back the Ce3+ radius
    for a Ce4+ query would be a plausible-looking wrong answer, which is the
    specific failure this project's style forbids.
    """
    assert ions.canonical_ion("Ce(IV)") == "Ce4+"
    assert ions.canonical_ion("Eu2+") == "Eu2+"
    assert ions.radius("Ce4+", 6) == 0.87
    assert ions.radius("Ce4+", 6) != ions.radius("Ce3+", 6)
    # And where the table was not independently verified, there is no number.
    assert ions.radius("Ce4+", 9) is None


def test_is_lanthanide_excludes_the_rare_earths_that_are_not_lanthanides():
    """Y3+ and Sc3+ are rare earths; neither is a lanthanide.

    Y3+ borrows a late-lanthanide radius without the 4f electrons that cause
    the contraction, so it belongs in the radius table but not in any claim
    about the series. Sc3+ does not even borrow the radius.
    """
    assert all(ions.is_lanthanide(ion) for ion in ions.LANTHANIDES_III)
    for ion in ("Y3+", "Sc3+", "Ca2+", "Fe3+", "nonsense"):
        assert not ions.is_lanthanide(ion), ion
    for ion in ("Y3+", "Sc3+", "La3+", "Lu3+"):
        assert ions.is_rare_earth(ion), ion
    assert not ions.is_rare_earth("Ca2+")
    # Oxidation state does not change which element it is.
    assert ions.is_lanthanide("Ce4+") and ions.is_lanthanide("Eu2+")


# --- charge density ---------------------------------------------------------

def test_charge_density_separates_trivalent_lanthanides_from_calcium():
    """The hard-acid proxy, and the electrostatic half of why Ln3+ displaces
    Ca2+ from an oxygen-rich pocket: same size, half again the charge
    density."""
    calcium = ions.charge_density("Ca2+", 7)
    assert calcium == pytest.approx(2 / 1.06, abs=1e-6)
    for ion in ions.LANTHANIDES_III:
        if 9 in ions.SHANNON_EFFECTIVE_RADII_A[ion]:
            assert ions.charge_density(ion, 9) > 1.3 * calcium, ion


def test_charge_density_rises_monotonically_and_so_ranks_every_site_alike():
    """Why charge density is exported but is not a site descriptor.

    It is a function of the ion alone. Across the series it rises smoothly, so
    using it to choose between ions would return the same answer -- Lu3+ --
    for every site in the corpus. A descriptor that cannot change its mind
    with the data is not reading the data.
    """
    densities = [ions.charge_density(ion, 9) for ion in ions.LANTHANIDES_III]
    assert all(a < b for a, b in zip(densities, densities[1:]))
    assert ions.charge_density("Lu3+", 9) == max(densities)


def test_charge_density_is_none_wherever_the_radius_is():
    assert ions.charge_density("Lu3+", 7) is None     # not tabulated by Shannon
    assert ions.charge_density("unobtainium", 8) is None


# --- fail closed ------------------------------------------------------------

def test_radius_returns_none_rather_than_interpolating_a_missing_coordination_number():
    """Shannon's gaps are gaps. Filling Lu3+ at CN 7 by interpolation would
    produce a number shaped exactly like a measured one."""
    assert ions.radius("Lu3+", 7) is None
    assert ions.radius("Pr3+", 7) is None
    assert 7 not in ions.tabulated_coordination_numbers("Lu3+")
    assert ions.tabulated_coordination_numbers("Lu3+") == (6, 8, 9)
    assert ions.tabulated_coordination_numbers("unobtainium") == ()


def test_radius_table_stops_at_cn_10_where_all_but_0_4_percent_of_sites_are():
    """Shannon tabulates CN 12; this module stops at 10, and the reason is
    coverage rather than impossibility.

    An earlier version of this test asserted the corpus's largest first shell
    was CN 11 and never read the corpus to check. It is 14. So read it: the
    scope claim the module makes is that CN 6-10 is where essentially all the
    data is, and that is the claim pinned here.
    """
    import pandas as pd

    frame = pd.read_parquet(SITE_TABLE)
    counts = frame.coordination_number
    assert counts.max() == 14, "module comment names the sites above CN 10 explicitly"
    assert (counts > 10).sum() == 14
    assert (counts <= 10).mean() > 0.99

    for by_cn in ions.SHANNON_EFFECTIVE_RADII_A.values():
        assert max(by_cn) <= 10

    # The 14 sites outside the table get an explicit unknown, not a score.
    for cn in sorted(set(counts[counts > 10])):
        assert ions.size_match("Nd3+", int(cn), 2.5)["status"] == "unknown"


@pytest.mark.parametrize("ion,cn,distance,why", [
    ("unobtainium", 9, 2.5, "unknown ion"),
    ("Lu3+", 7, 2.4, "coordination number not tabulated for this ion"),
    ("Nd3+", 9, None, "missing distance"),
    ("Nd3+", 9, "2.5", "distance given as text"),
    ("Nd3+", None, 2.5, "missing coordination number"),
    ("Nd3+", 9, 25.0, "distance in the wrong unit"),
    ("Nd3+", 9, 1.1, "distance too short to be a metal-oxygen bond"),
    ("Nd3+", 9, 3.9, "beyond the 3.2 A first shell structure.py admits"),
])
def test_size_match_returns_unknown_rather_than_a_number_it_cannot_justify(
        ion, cn, distance, why):
    """An input the table does not support is an unknown, never a low score.

    The distinction is the whole point: a low fit says "this ion is the wrong
    size for this site", which is a result. An unknown says "this was not
    evaluated". Collapsing the second into the first would quietly reject
    candidates that were never tested.
    """
    result = ions.size_match(ion, cn, distance)
    assert result["status"] == "unknown", why
    assert result["fit"] is None
    assert result["basis"].startswith("unknown:")


@pytest.mark.parametrize("cn", [9.7, 8.5, 9.0001, "9.7", True, False, float("nan")])
def test_no_entry_point_truncates_a_fractional_coordination_number(cn):
    """A coordination number that is not a whole count must not be answered.

    This is the failure that motivated whole_cn(). radius("La3+", 9.7) used to
    return 1.216 -- the CN 9 value, indistinguishable from a real lookup -- and
    charge_density() and contraction_span_A() each reproduced it by their own
    route. A mean coordination number across protomers is a plausible input in
    this codebase, so the wrong answer was reachable, not theoretical.

    9.0001 is in the list on purpose: it is a hair from a whole number and
    must still be refused, because "close enough to round" is the reasoning
    that put the bug there.
    """
    assert ions.whole_cn(cn) is None
    assert ions.radius("La3+", cn) is None
    assert ions.charge_density("La3+", cn) is None
    assert ions.contraction_span_A(cn) is None
    result = ions.size_match("La3+", cn, 2.55)
    assert result["status"] == "unknown"
    assert result["fit"] is None


@pytest.mark.parametrize("cn,expected", [(9, 9), ("9", 9), (9.0, 9), (6, 6)])
def test_a_whole_coordination_number_still_goes_through_however_it_is_spelled(cn, expected):
    """The guard must not cost the coercion it was added around. 9.0 is whole."""
    assert ions.whole_cn(cn) == expected
    assert ions.radius("La3+", cn) == ions.radius("La3+", expected)


@pytest.mark.parametrize("text", [
    "Ce0+", "Ce9+", "Ce1+", "Ca(III)", "Ca3+", "YI", "Y1+", "Ce V", "Ce5+",
    "Tb4+", "Pr4+", "Nd2+", "scv",
])
def test_an_oxidation_state_these_elements_do_not_form_in_water_is_refused(text):
    """None, not a canonical string.

    Every numeric path already failed closed on these -- no radius is
    tabulated, so size_match() returned "unknown". The classifiers did not:
    is_lanthanide("Ce0+") was True and ion_charge("Ce0+") was 0, so a caller
    filtering a user's ion list with is_lanthanide() before scoring would
    carry a species that does not exist all the way to the UI.

    Tb4+, Pr4+ and Nd2+ are here deliberately. They are real in oxides and in
    organometallic chemistry, and refusing them is a scope statement about
    water and proteins, not a claim they do not exist -- see _AQUEOUS_CHARGES.
    """
    assert ions.canonical_ion(text) is None
    assert ions.is_lanthanide(text) is False
    assert ions.is_rare_earth(text) is False
    assert ions.ion_charge(text) is None
    assert ions.size_match(text, 9, 2.5)["status"] == "unknown"


@pytest.mark.parametrize("text,expected", [
    ("Ce3+", "Ce3+"), ("Ce4+", "Ce4+"), ("Eu2+", "Eu2+"), ("Yb2+", "Yb2+"),
    ("Sm2+", "Sm2+"), ("Ca2+", "Ca2+"), ("Ce(IV)", "Ce4+"), ("Eu(II)", "Eu2+"),
    ("cerium", "Ce3+"), ("calcium", "Ca2+"), ("Sm", "Sm3+"),
])
def test_an_aqueous_oxidation_state_still_canonicalises(text, expected):
    """The guard must not narrow the parser's real job.

    Sm2+ is the case worth naming: a real aqueous ion with no radius in this
    table, so it canonicalises and radius() then returns None. That is the
    "an ion, no data" branch, distinct from "not an ion".
    """
    assert ions.canonical_ion(text) == expected


def test_canonical_ion_tries_every_pattern_before_giving_up():
    """The pattern ordering is insurance, and the comment says so honestly.

    An earlier comment justified the fall-through with "Sm would otherwise be
    consumed by the roman-numeral pattern as S + M". It would not. Pin the
    real state of affairs -- no element token collides with the roman pattern
    today -- so that if one ever does, this test is where it shows up.
    """
    assert ions._ROMAN.match("sm") is None
    collisions = [tok for tok in
                  list(ions._ELEMENT_NAMES) + [s.lower() for s in ions._ELEMENT_NAMES.values()]
                  if ions._ROMAN.match(tok)]
    assert collisions == [], collisions

    # A token that does match the roman shape, resolves to a real element, and
    # is still refused -- the path the ordering exists for.
    assert ions._ROMAN.match("scv") is not None
    assert ions.canonical_ion("scv") is None


def test_every_metal_this_platform_offers_survives_the_oxidation_state_guard():
    """chemistry.METALS is what the UI puts in a dropdown. If the guard
    rejected one of those, the guard is wrong, not the dropdown."""
    for key in METALS:
        assert ions.canonical_ion(key) == key, key


def test_size_match_accepts_a_numeric_string_coordination_number_but_not_a_text_distance():
    """Deliberately asymmetric. A coordination number is a count and arrives
    from JSON as "9" often enough to be worth coercing; a donor distance is a
    measurement whose text form is usually a unit or a placeholder, so
    coercing it would be the first step of accepting "2.5 A" as 2.5."""
    assert ions.size_match("Nd3+", "9", 2.5)["status"] == "scored"
    assert ions.size_match("Nd3+", 9, "2.5")["status"] == "unknown"


def test_an_unknown_result_has_every_key_a_scored_one_has():
    """Compared as whole key SETS, not against a list written out here.

    The listed-keys version of this test passed while _unknown() was missing
    ionic_radius_A and series_width_A -- both documented public keys -- so a
    caller reading one by name got a KeyError on exactly the inputs that could
    not be scored. Comparing the sets makes the test fail when the two shapes
    drift apart, whichever one of them moves.
    """
    unknown = ions.size_match("unobtainium", 9, 2.5)
    scored = ions.size_match("Nd3+", 9, 2.5)
    assert unknown["status"] == "unknown" and scored["status"] == "scored"
    assert set(unknown) == set(scored)

    # The failure the key-set comparison is standing in for: a real sweep of
    # every lanthanide at a coordination number only some of them tabulate.
    for ion in ions.LANTHANIDES_III:
        result = ions.size_match(ion, 7, 2.43)
        assert result["ionic_radius_A"] is not None or result["status"] == "unknown"
        assert result["series_width_A"] is not None or result["status"] == "unknown"


def test_every_result_states_it_is_not_an_affinity_in_words_not_by_identity():
    """Pin the SUBSTANCE of the disclaimer, not the constant against itself.

    `SIZE_MATCH_IS_NOT_AFFINITY in result["caveat"]` is true no matter what
    the constant says -- rewriting it to "Predicted binding affinity:" left
    the whole suite green. So assert the phrases that carry the meaning, and
    assert the words that would contradict them are absent.
    """
    required = ("Not an affinity", "not a binding constant",
                "not a selectivity prediction")
    forbidden = ("predicted affinity", "binding affinity", "Kd", "selectivity for")

    for phrase in required:
        assert phrase in ions.SIZE_MATCH_IS_NOT_AFFINITY, phrase

    checked = 0
    for cn in (6, 7, 8, 9, 10, 12):
        for ion in ions.LANTHANIDES_III + ("Ca2+", "unobtainium"):
            caveat = ions.size_match(ion, cn, 2.45)["caveat"]
            for phrase in required:
                assert phrase in caveat, (ion, cn, phrase)
            for phrase in forbidden:
                assert phrase not in caveat, (ion, cn, phrase)
            checked += 1
    assert checked > 90


def test_low_coordination_results_say_they_may_be_describing_a_truncated_parse():
    """geometry.py's lesson, carried into this module.

    A coordination number read from an asymmetric unit is a lower bound, so a
    CN 6 reading of a real CN 9 site keeps the CN 9 donor distances. The
    corpus shows exactly that signature -- the prediction bias flips sign
    below CN 8 -- so a low-CN size match gets an explicit warning.
    """
    assert "truncated" not in ions.size_match("Nd3+", 9, 2.5)["caveat"]
    low = ions.size_match("Ca2+", 6, 2.45)
    assert low["status"] == "scored"
    assert "asymmetric unit" in low["caveat"]
    assert "truncated" in low["caveat"]


# --- the fit itself ---------------------------------------------------------

def test_size_match_prefers_the_ion_that_actually_fits_the_site():
    """The one genuinely ion-dependent behaviour in the platform.

    A tight CN 8 site at 2.37 A is a late-lanthanide pocket and a roomy CN 9
    site at 2.60 A is an early-lanthanide one. If these two sites returned the
    same ranking, the target-ion dropdown would still be cosmetic.
    """
    tight = [m["ion"] for m in ions.rank_by_size_match(8, 2.37)]
    roomy = [m["ion"] for m in ions.rank_by_size_match(9, 2.60)]
    assert tight[0] in ("Lu3+", "Yb3+"), tight
    assert roomy[0] in ("La3+", "Ce3+"), roomy
    assert tight[-1] == "La3+"
    assert roomy[-1] == "Lu3+"
    # A site off by more than the whole series is a fit of zero, not a
    # negative number and not a small positive one.
    assert ions.size_match("La3+", 8, 2.37)["fit"] == 0.0


def test_fit_is_bounded_and_the_denominator_is_the_series_width():
    for cn in (6, 8, 9):
        span = ions.contraction_span_A(cn)
        for distance in (2.0, 2.3, 2.45, 2.6, 3.2):
            for ion in ("La3+", "Gd3+", "Lu3+", "Ca2+"):
                result = ions.size_match(ion, cn, distance)
                if result["status"] != "scored":
                    continue
                assert 0.0 <= result["fit"] <= 1.0
                assert result["series_width_A"] == pytest.approx(span, abs=5e-4)


def test_contraction_span_is_derived_from_the_table_not_written_down_twice():
    """A hardcoded denominator would survive a corrected radius and silently
    rescale every fit."""
    for cn in (6, 7, 8, 9, 10):
        radii = [ions.SHANNON_EFFECTIVE_RADII_A[ion][cn]
                 for ion in ions.LANTHANIDES_III
                 if cn in ions.SHANNON_EFFECTIVE_RADII_A[ion]]
        assert ions.contraction_span_A(cn) == pytest.approx(max(radii) - min(radii))
    # Below two tabulated lanthanides the series has no width to scale against.
    assert ions.contraction_span_A(11) is None
    assert ions.contraction_span_A(3) is None


def test_ranking_drops_unscorable_ions_instead_of_putting_them_last():
    """At CN 7 Shannon tabulates only 9 of the 15 lanthanides. The six without
    a radius are absent from the ranking, because a reader scanning to the
    bottom of a list reads the bottom as rejected."""
    ranked = ions.rank_by_size_match(7, 2.43)
    assert len(ranked) == 9
    assert all(m["status"] == "scored" for m in ranked)
    assert "Lu3+" not in [m["ion"] for m in ranked]
    assert len(ions.rank_by_size_match(9, 2.5)) == 15
    # Sorted best first.
    fits = [m["fit"] for m in ranked]
    assert fits == sorted(fits, reverse=True)


def test_ranking_is_empty_rather_than_arbitrary_when_nothing_can_be_scored():
    assert ions.rank_by_size_match(9, 9.9) == []
    assert ions.rank_by_size_match(4, 2.4) == []


# --- coordination ranges ----------------------------------------------------

def test_typical_coordination_follows_the_series_and_is_labelled_descriptive():
    """Large lanthanides are 9-coordinate aqua ions and small ones
    8-coordinate; Ca2+ in a protein is CN 7. The range must be labelled as an
    observation, since a reader who takes it as a constraint would discard the
    CN 10 sites this corpus contains."""
    assert ions.typical_coordination("La3+")["typical"] == 9
    assert ions.typical_coordination("Lu3+")["typical"] == 8
    assert ions.typical_coordination("Ca2+")["typical"] == 7
    for ion in ions.LANTHANIDES_III + ("Y3+", "Sc3+", "Ca2+"):
        entry = ions.typical_coordination(ion)
        assert entry["minimum"] <= entry["typical"] <= entry["maximum"]
        assert "not a constraint" in entry["caveat"]
        assert "lower bound" in entry["caveat"]
    assert ions.typical_coordination("unobtainium") is None


def test_typical_coordination_accepts_the_same_spellings_as_the_parser():
    assert ions.typical_coordination("cerium") == ions.typical_coordination("Ce3+")


# --- agreement with this project's own measurements -------------------------

def test_first_shell_window_agrees_with_the_structure_module():
    """Drift guard. The upper bound exists because structure.py admits no
    donor beyond 3.2 A, so a mean donor distance above it cannot be a first
    shell. If that cutoff moves, this one has to move with it."""
    from lantern.structure import FIRST_SHELL_ANGSTROM
    assert ions.MAX_PLAUSIBLE_DONOR_DISTANCE_A == FIRST_SHELL_ANGSTROM


@pytest.mark.skipif(not SITE_TABLE.exists(), reason="site table not built")
def test_predicted_distance_tracks_observed_protein_sites_at_cn_8_and_9():
    """Cross-check the CN 8 and CN 9 columns against real coordinates, and pin
    the bias the module advertises.

    Shannon's radii are fitted to oxides, and r(cation) + 1.40 A predicts a
    metal-oxygen distance in one. A protein donor is a carboxylate or carbonyl
    oxygen, so the prediction is expected to be close but not exact. Measured
    over sites at <= 2.5 A resolution that are not chelator-flagged, it runs
    about 0.045 A long at CN 8-9 -- a quarter of the width of the whole
    lanthanide series, which is the number size_match()'s caveat quotes.

    Below CN 8 the residual flips sign and grows. That is not a worse fit of
    the same kind: a coordination number read from an asymmetric unit is a
    lower bound, so a truncated CN 9 site is filed as CN 6 while keeping its
    CN 9 donor distances, which drives observed-minus-predicted positive. The
    two signs together are the evidence for that reading, so both are pinned.
    """
    import statistics

    import pandas as pd

    frame = pd.read_parquet(SITE_TABLE)
    clean = frame[(frame.resolution_A <= 2.5) & (~frame.chelator_flagged.astype(bool))]

    residuals = {"high": [], "low": []}
    for row in clean.itertuples():
        canonical = ions.canonical_ion(row.element)
        predicted = ions.radius(canonical, row.coordination_number) if canonical else None
        if predicted is None or pd.isna(row.mean_donor_distance_A):
            continue
        bucket = "high" if row.coordination_number >= 8 else "low"
        residuals[bucket].append(
            row.mean_donor_distance_A - (predicted + ions.DONOR_OXYGEN_RADIUS_A))

    assert len(residuals["high"]) > 200 and len(residuals["low"]) > 200
    high = statistics.median(residuals["high"])
    low = statistics.median(residuals["low"])

    # Small, negative, and well inside the series width at CN 8-9.
    assert -0.10 < high < 0.0, high
    assert abs(high) < 0.5 * ions.contraction_span_A(9), high
    # Opposite sign below CN 8: the truncation signature, not a fit problem.
    assert low > 0.0, low


@pytest.mark.skipif(not SITE_TABLE.exists(), reason="site table not built")
def test_every_element_in_the_corpus_is_recognised_by_the_parser():
    """If the corpus contains a metal this module cannot name, any ion-aware
    reporting over that corpus silently skips those sites."""
    import pandas as pd

    elements = set(pd.read_parquet(SITE_TABLE).element.dropna().unique())
    unparsed = {e for e in elements if ions.canonical_ion(e) is None}
    assert not unparsed, unparsed
