"""Target-ion chemistry: the small part of "which lanthanide?" that is real.

The UI offers a target-ion dropdown. `chemistry.score_sequence()` does not take
an ion argument and never has, so every entry in that dropdown produces the
same bytes. This module exists to make the choice mean something where it
genuinely can, and -- the larger half of the job -- to say in code where it
cannot, so the dropdown stops implying a discrimination the pipeline does not
perform.

**Where it cannot mean anything.** A sequence-only score counts acidic
residues and EF-hand-like motifs. Those counts do not know what ion you had in
mind; La3+ and Lu3+ are the same letters. `SEQUENCE_SCORE_IS_ION_INDEPENDENT`
is that sentence in a form the UI can display, and it should be displayed
rather than paraphrased.

**Where it can.** Lanthanides contract across the series: 4f electrons shield
the nuclear charge poorly, so the trivalent radius falls monotonically from
La3+ to Lu3+ -- 1.032 A to 0.861 A at CN 6, about 17% -- while the charge stays
at 3+. Ionic radius, the coordination number the ion prefers, and charge
density therefore genuinely differ along the series. A *resolved* site with a
measured coordination number and a measured mean donor distance is a geometric
object of a particular size, and some Ln3+ fit it better than others.
`size_match()` is that comparison and nothing more.

**What size_match is not.** It is a size propensity. It is not an affinity, not
a binding constant, and not a selectivity prediction. Selectivity between
adjacent lanthanides in a protein is set by desolvation, pocket rigidity,
protonation and cooperativity -- none of which a radius knows about. Two facts
in this module bound how much the propensity can ever be worth:

  * The entire La3+ -> Lu3+ contraction is ~0.18 A at CN 8-9. Adjacent
    lanthanides differ by ~0.01-0.02 A, which is at or below the coordinate
    error of a 2.0-2.5 A crystal structure. `size_match()` is scaled by that
    full series width precisely so that an adjacent-pair difference comes out
    looking as small as it is.
  * Ca2+ at CN 7-8 sits *inside* the Ln3+ range at the same coordination
    number, within ~0.01-0.02 A of its nearest lanthanide neighbour. That is
    the structural reason calcium-binding proteins bind lanthanides at all,
    and the reason this project is hard. A size criterion cannot separate the
    two ions; see tests/test_ions.py.

**Provenance of the numbers.** All radii are Shannon's *effective* ionic radii
(SHANNON_SOURCE), the scale anchored to r(O2-) = 1.40 A so that
r(cation) + 1.40 reproduces observed metal-oxygen distances. Every CN 6 and
CN 8 entry below was re-verified in a second, independent publication of the
same data on Shannon's *crystal* scale (WebElements per-element "atom sizes"
pages, which list crystal radii in pm); crystal = effective + 0.14 A exactly,
by construction of the two scales, and all twenty re-checked values agreed to
the last published digit. That check is executed, not asserted, in
`test_cn6_and_cn8_radii_match_independently_published_crystal_radii`.

The CN 7, 9 and 10 columns were not available in that second source and rest
instead on two weaker checks. The first is monotonic contraction across the
series. The second is agreement with observed protein sites in this project's
own corpus -- but be precise about how much agreement that is, because the
honest number is small. The corpus holds 3375 sites; the check
(`test_predicted_distance_tracks_observed_protein_sites_at_cn_8_and_9`) runs
over the resolution <= 2.5 A, non-chelator-flagged subset, which is 1802 rows,
of which 641 have both a tabulated radius and a measured donor distance. Those
641 split CN 6: 157, CN 7: 184, CN 8: 144, CN 9: 135, CN 10: 21. The check
also pools them into >= CN 8 and < CN 8 and tests the two medians, so it never
isolates CN 7, 9 or 10 individually, and the CN 10 column in particular rests
on 21 sites inside a pooled statistic. Treat the CN 10 row as the weakest in
the table.

This module is pure: no I/O, no network, no dependencies outside the standard
library. It holds reference data and arithmetic over it, so that a caller that
cannot reach a network still gets either a correct answer or an honest
"unknown".
"""
from __future__ import annotations

import re

SHANNON_SOURCE = ("Shannon, R. D. (1976) Acta Crystallographica A32, 751-767, "
                  "doi:10.1107/S0567739476001551")

# The statement the UI must show next to any sequence-derived ranking. Kept as
# a constant rather than left to each caller's prose, because the failure mode
# here is a caller writing something softer and the softer version being the
# only thing a reader ever sees.
SEQUENCE_SCORE_IS_ION_INDEPENDENT = (
    "A sequence-only score cannot tell one trivalent lanthanide from another. "
    "chemistry.score_sequence() counts acidic residues and EF-hand-like motifs, "
    "and those counts are identical for every one of the fifteen trivalent "
    "lanthanides -- the residues are the same residues. Selecting a target "
    "ion does not "
    "change this ranking by one digit and must not be presented as if it did. "
    "Ion identity can only enter through a structure: an observed coordination "
    "number and mean donor distance can be compared against the ion's Shannon "
    "radius (ions.size_match), and that comparison is a size propensity, not an "
    "affinity and not a selectivity prediction."
)

# Attached to every size_match() result rather than documented once, because
# the result dict travels and the docstring does not.
SIZE_MATCH_IS_NOT_AFFINITY = (
    "Size propensity only: how well this ion's Shannon radius fits the observed "
    "donor distance at the observed coordination number. Not an affinity, not a "
    "binding constant, not a selectivity prediction. The whole La3+ -> Lu3+ "
    "contraction is ~0.18 A and adjacent lanthanides differ by ~0.01-0.02 A, "
    "which is at or below the coordinate error of a 2.0-2.5 A structure, so "
    "adjacent-pair differences in this number are not resolvable."
)

# Shannon's effective ionic radii, in Angstrom, keyed by canonical ion and
# coordination number.
#
# Scope decisions, each deliberate:
#
#   CN 6-10 only. Shannon also tabulates CN 12 (and CN 2-5 for some ions).
#   Those are omitted because CN 6-10 is where the data is: 99.6% of the 3375
#   sites in this project's corpus sit at CN 10 or below. Only 14 sites exceed
#   it -- 5 at CN 11, 7 at CN 12, 2 at CN 14 -- so a CN 12 column would be
#   exercised by 7 sites and a CN 11 or CN 14 one could not be filled from
#   Shannon at all.
#
#   Note what this is NOT: it is not a claim that higher coordination numbers
#   cannot occur. They do occur, 14 times, and CN 12 is among them. Those sites
#   get an explicit "unknown" from size_match() rather than a score, which is
#   the correct answer for a geometry this table has no row for -- but a reader
#   should not be told they are impossible. (An earlier version of this comment
#   said the corpus maximum was CN 11 and that CN 12 "cannot occur". Both were
#   false; the CN <= 11 figure is true only of the resolution-filtered subset.)
#
#   Gaps are real gaps. Where Shannon does not tabulate a (ion, CN) pair --
#   Pr3+ at CN 7, Lu3+ at CN 7, most of the CN 10 column -- the entry is absent
#   and radius() returns None. Interpolating across the series would produce a
#   number indistinguishable from a measured one, which is the exact failure
#   this project's contract forbids.
#
#   Pm3+ is included although no one will ever put promethium in a protein: it
#   is radioactive with no stable isotope. It is here so that "the radii fall
#   monotonically across the series" is a statement about the whole series
#   rather than about the series with a hole in it.
#
#   The secondary oxidation states at the bottom carry CN 6 and CN 8 only.
#   Shannon tabulates more; those two are the ones that were independently
#   re-verified for this file, and an unverified row is worth less here than a
#   missing one. They are included at all because Ce(IV) and Eu(II) are not
#   curiosities -- oxidising Ce3+ and reducing Eu3+ are the two places where
#   industrial rare-earth separation actually works, so a user typing "Ce4+"
#   means it, and must not be silently handed the Ce3+ radius.
SHANNON_EFFECTIVE_RADII_A: dict[str, dict[int, float]] = {
    "La3+": {6: 1.032, 7: 1.10, 8: 1.160, 9: 1.216, 10: 1.27},
    "Ce3+": {6: 1.01, 7: 1.07, 8: 1.143, 9: 1.196, 10: 1.25},
    "Pr3+": {6: 0.99, 8: 1.126, 9: 1.179},
    "Nd3+": {6: 0.983, 8: 1.109, 9: 1.163},
    "Pm3+": {6: 0.97, 8: 1.093, 9: 1.144},
    "Sm3+": {6: 0.958, 7: 1.02, 8: 1.079, 9: 1.132},
    "Eu3+": {6: 0.947, 7: 1.01, 8: 1.066, 9: 1.120},
    "Gd3+": {6: 0.938, 7: 1.00, 8: 1.053, 9: 1.107},
    "Tb3+": {6: 0.923, 7: 0.98, 8: 1.040, 9: 1.095},
    "Dy3+": {6: 0.912, 7: 0.97, 8: 1.027, 9: 1.083},
    "Ho3+": {6: 0.901, 8: 1.015, 9: 1.072, 10: 1.12},
    "Er3+": {6: 0.890, 7: 0.945, 8: 1.004, 9: 1.062},
    "Tm3+": {6: 0.880, 8: 0.994, 9: 1.052},
    "Yb3+": {6: 0.868, 7: 0.925, 8: 0.985, 9: 1.042},
    "Lu3+": {6: 0.861, 8: 0.977, 9: 1.032},
    # Y3+ and Sc3+ are rare earths but not lanthanides (IUPAC: rare earths =
    # the 15 lanthanides plus Sc and Y). Y3+ is here because it sits between
    # Ho3+ and Er3+ in size and is consequently the commonest lanthanide mimic
    # in the PDB -- structure.REE_LIGAND_CODES carries two separate component
    # codes for it. Sc3+ is far smaller than any lanthanide and is here mainly
    # so that is_lanthanide("Sc3+") returning False is backed by a radius a
    # reader can check.
    "Y3+": {6: 0.900, 7: 0.96, 8: 1.019, 9: 1.075},
    "Sc3+": {6: 0.745, 8: 0.870},
    # The competitor. Not a rare earth; the ion every site in this project is
    # already occupied by.
    "Ca2+": {6: 1.00, 7: 1.06, 8: 1.12, 9: 1.18, 10: 1.23},
    "Ce4+": {6: 0.87, 8: 0.97},
    "Eu2+": {6: 1.17, 8: 1.25},
    "Yb2+": {6: 1.02, 8: 1.14},
}

# The 15 lanthanides in atomic-number order. The contraction is a statement
# about this sequence, so the order is load-bearing and not alphabetical.
LANTHANIDES_III: tuple[str, ...] = (
    "La3+", "Ce3+", "Pr3+", "Nd3+", "Pm3+", "Sm3+", "Eu3+", "Gd3+",
    "Tb3+", "Dy3+", "Ho3+", "Er3+", "Tm3+", "Yb3+", "Lu3+",
)

_LANTHANIDE_SYMBOLS = frozenset(ion[:-2] for ion in LANTHANIDES_III)

# Shannon's effective-radius scale is defined so that r(O2-) = 1.40 A and
# r(cation) + 1.40 reproduces observed metal-oxygen distances in oxides. Using
# that anchor as the donor radius is therefore not a fitted parameter -- it is
# the constant the cation radii were derived against, and picking anything else
# would mean using the radii outside the scale they belong to.
#
# It is nonetheless the wrong oxygen. A protein donor is a carboxylate or
# carbonyl O, not an oxide ion, and the sum runs slightly long against real
# protein sites. Measured over this project's own corpus (data/
# lanthanide_sites.parquet, sites at <= 2.5 A resolution and not chelator-
# flagged), the median of observed-minus-predicted is:
#
#     CN 8-9   n = 279   -0.045 A      the regime geometry.py actually scores
#     CN 6-7   n = 341   +0.070 A      wrong sign, and larger
#
# The CN 8-9 bias is about a quarter of the full series width, so it shifts
# every ion's fit by the same small amount and leaves the ranking between ions
# intact. The CN 6-7 figure is not a worse fit of the same kind: a coordination
# number read off an asymmetric unit is a lower bound (geometry.py), so a
# truncated CN 9 site is filed as CN 6 with its CN 9 donor distances, which
# drives the residual positive. Treat a low-CN size match as describing the
# parse, not the chemistry.
DONOR_OXYGEN_RADIUS_A = 1.40

# Plausibility window for a mean first-shell donor distance, in Angstrom. The
# upper bound is structure.FIRST_SHELL_ANGSTROM: that module only admits donors
# within 3.2 A, so a mean above it cannot have come from a first shell and is
# a unit error or a second-shell average. The lower bound is generous -- the
# shortest metal-oxygen bonds here are Yb-O near 2.2 A -- and exists to catch
# the same mistake from the other side. Outside this window size_match()
# returns "unknown" rather than a number.
MIN_PLAUSIBLE_DONOR_DISTANCE_A = 2.0
MAX_PLAUSIBLE_DONOR_DISTANCE_A = 3.2

# Observed coordination-number ranges, as (minimum, typical, maximum).
#
# The split is the standard textbook one (Greenwood & Earnshaw, Chemistry of
# the Elements): in aqueous solution the larger lanthanides are 9-coordinate,
# [Ln(H2O)9]3+, and the smaller ones 8-coordinate, with the changeover in the
# middle of the series. Because 4f orbitals overlap ligands poorly, Ln3+
# bonding is essentially electrostatic and non-directional, so geometry is set
# by the ligands rather than the metal and the observed range is wide.
#
# This is deliberately NOT derived from this project's corpus, although the
# corpus is right there. Corpus coordination numbers are dominated by surface
# and symmetry-truncated sites: over the 1517 non-calcium sites that survive
# the 2.5 A resolution and chelator filters the median CN is 5, far below any
# solution value, because a metal on a crystallographic symmetry axis is read
# from one protomer (geometry.py). Fitting a "typical" range to those numbers
# would describe the deposition and parsing pipeline, not the ion.
#
# The range is descriptive. It is not a filter, not a constraint, and a site
# outside it is unusual rather than wrong.
_COORDINATION_RANGES: dict[str, tuple[int, int, int]] = {
    # Large, early lanthanides: 9-coordinate aqua ions.
    "La3+": (8, 9, 10), "Ce3+": (8, 9, 10), "Pr3+": (8, 9, 10),
    "Nd3+": (8, 9, 10), "Pm3+": (8, 9, 10),
    # Mid-series, spanning the 9 -> 8 changeover. The changeover is placed
    # between Gd3+ and Tb3+ to follow the textbook split, but where exactly it
    # falls -- and whether it is a step or a gradual mixture of CN 9 and CN 8
    # species -- is the live question in the EXAFS literature on the so-called
    # gadolinium break. The `typical` value for these five ions is therefore
    # the weakest number in this table and should not be leaned on; the
    # `minimum`-to-`maximum` range is the part that is not in dispute.
    "Sm3+": (7, 9, 10), "Eu3+": (7, 9, 10), "Gd3+": (7, 9, 10),
    "Tb3+": (7, 8, 9), "Dy3+": (7, 8, 9),
    # Small, late lanthanides and Y3+: 8-coordinate aqua ions.
    "Ho3+": (7, 8, 9), "Er3+": (7, 8, 9), "Tm3+": (7, 8, 9),
    "Yb3+": (6, 8, 9), "Lu3+": (6, 8, 9), "Y3+": (6, 8, 9),
    # Sc3+ is much smaller and behaves like a first-row transition cation.
    "Sc3+": (6, 6, 8),
    # Ca2+ in proteins. CN 7 pentagonal bipyramidal is the canonical EF-hand
    # geometry; the EF4 loops in 9PI2 and 8FNS are CN 7 with one water.
    "Ca2+": (6, 7, 8),
}

# Element names accepted by the parser, lowercase.
_ELEMENT_NAMES: dict[str, str] = {
    "lanthanum": "La", "cerium": "Ce", "praseodymium": "Pr",
    "neodymium": "Nd", "promethium": "Pm", "samarium": "Sm",
    "europium": "Eu", "gadolinium": "Gd", "terbium": "Tb",
    "dysprosium": "Dy", "holmium": "Ho", "erbium": "Er",
    "thulium": "Tm", "ytterbium": "Yb", "lutetium": "Lu",
    "yttrium": "Y", "scandium": "Sc", "calcium": "Ca",
}

_NAME_BY_SYMBOL: dict[str, str] = {sym: name.capitalize() for name, sym in _ELEMENT_NAMES.items()}


def element_name(symbol: str) -> str:
    """"Ce" -> "Cerium". The symbol itself for anything not in the table.

    Exists so a caller building display text does not have to reach into
    _ELEMENT_NAMES and invert it, or keep a second copy of the names that can
    drift out of step with the one the parser accepts.
    """
    return _NAME_BY_SYMBOL.get(symbol.strip().capitalize(), symbol)


# Oxidation state assumed when a bare element or name is given with no charge.
# Every rare earth is 3+; calcium is 2+. Stated as data rather than inferred,
# so that adding an element without deciding its default charge is impossible.
_DEFAULT_CHARGE: dict[str, int] = {sym: 3 for sym in _ELEMENT_NAMES.values()}
_DEFAULT_CHARGE["Ca"] = 2

_ROMAN_CHARGES = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5}

# "Ce3+", "ce 3+", "Ce+3", "Ce(3+)" -- a sign is REQUIRED.
#
# Refusing a bare trailing digit is the point, not an oversight. PDB chemical
# component codes look exactly like charge strings and do not mean that:
# structure.REE_LIGAND_CODES contains ER3, EU3, GD3, HO3, YB2 and Y1. Three of
# those would parse correctly by accident, YB2 happens to be ytterbium(II) and
# would also parse correctly, and Y1 is simply a second code for the yttrium
# ion and would parse as the non-existent Y+. One wrong answer out of six is
# worse than six refusals, so component codes are not this parser's job -- use
# structure.REE_LIGAND_CODES for those.
_CHARGED = re.compile(r"^([a-z]+)\s*\(?\s*(?:([0-9])\s*([+-])|([+-])\s*([0-9]))\s*\)?$")
# "Ce(III)", "cerium(iii)", "Ce III"
_ROMAN = re.compile(r"^([a-z]+?)\s*\(?\s*(i{1,3}|iv|v)\s*\)?$")
# "Ce", "cerium"
_BARE = re.compile(r"^([a-z]+)$")

_SYMBOL_BY_LOWER = {sym.lower(): sym for sym in _ELEMENT_NAMES.values()}


def _resolve_symbol(token: str) -> str | None:
    """Element symbol for a lowercase symbol-or-name token, or None."""
    if token in _ELEMENT_NAMES:
        return _ELEMENT_NAMES[token]
    return _SYMBOL_BY_LOWER.get(token)


# Oxidation states each element forms in water, which is the only condition
# this platform looks at. +3 for every rare earth, +2 for calcium, plus the
# four aqueous-accessible exceptions: Ce4+ is the stable oxidised cerium in
# acid, and Sm2+, Eu2+ and Yb2+ are the three lanthanides with a reachable
# divalent state in solution.
#
# This is a SCOPE statement, not a claim about what exists. Tb4+ and Pr4+ are
# real in solid oxides, and essentially every lanthanide has been made
# divalent in an organometallic complex -- none of them in water, none of them
# in a protein, so none of them is an input this module can say anything
# useful about. Refusing them is narrower than denying them.
#
# Without this guard, "Ce0+" and "Ce9+" and "Ca(III)" canonicalised cleanly.
# Every numeric path then failed closed -- radius() returns None because the
# key is absent from the table -- but the *classifiers* did not:
# is_lanthanide("Ce0+") was True and ion_charge("Ce0+") returned 0. A caller
# that filters a user's ion list with is_lanthanide() before scoring would
# carry a nonexistent species through to the UI and only find out it was
# nonsense when the score came back blank.
_AQUEOUS_CHARGES: dict[str, frozenset[int]] = {
    **{sym: frozenset({3}) for sym in _ELEMENT_NAMES.values()},
    "Ca": frozenset({2}),
    "Ce": frozenset({3, 4}),
    "Sm": frozenset({2, 3}),
    "Eu": frozenset({2, 3}),
    "Yb": frozenset({2, 3}),
}


def _plausible(symbol: str | None, charge: int) -> bool:
    """True if this element forms this oxidation state in water."""
    return symbol is not None and charge in _AQUEOUS_CHARGES.get(symbol, frozenset())


def canonical_ion(name: str) -> str | None:
    """Canonical "<Symbol><charge>+" form, or None if the input is not an ion
    this module tabulates data about.

    Accepts the spellings a user or a dropdown actually produces: "Ce3+",
    "ce3+", "CE 3+", "Ce+3", "Ce(3+)", "Ce(III)", "cerium", "Cerium(III)".
    Every key of chemistry.METALS round-trips unchanged.

    Returns None rather than a best guess, in three situations that are worth
    telling apart:

      - not an element this module knows ("unobtainium") -> None;
      - an element, in an oxidation state it does not form in water ("Ce0+",
        "Ce9+", "Ca(III)", "Tb4+") -> None, because canonicalising it would
        let it reach is_lanthanide() and ion_charge() as if it were a species
        this platform could meet. See _AQUEOUS_CHARGES for the scope;
      - an element, in an aqueous oxidation state, with no radius tabulated
        here ("Sm2+") -> the canonical string. This one is deliberately NOT
        None: radius() returns None for it, so the caller can tell "not an
        ion" from "an ion, no data".

    An unrecognised ion string reaching a scoring function as a silent default
    would produce a result that reads exactly like a real one, which is the
    failure this project's contract is written against.
    """
    if not isinstance(name, str):
        return None
    token = name.strip().lower().replace("–", "-")
    if not token:
        return None

    # Each pattern is tried in turn, and one that matches the *shape* but not
    # a real element -- or a real element in a state it does not form -- falls
    # through to the next rather than returning.
    #
    # No input currently needs that fall-through, and the comment that used to
    # live here claimed one did: it said "Sm" would otherwise be eaten by the
    # roman pattern as S + M. It would not; _ROMAN does not match "sm", and in
    # fact it matches no element symbol or name in _ELEMENT_NAMES at all
    # (checked in test_canonical_ion_tries_every_pattern_before_giving_up).
    # The ordering is kept as cheap insurance against a future element or
    # spelling that does collide, not because something today relies on it.
    match = _CHARGED.match(token)
    if match:
        symbol = _resolve_symbol(match.group(1))
        digit, sign = (match.group(2), match.group(3)) if match.group(2) else \
                      (match.group(5), match.group(4))
        # No rare earth or alkaline earth forms an anion, so a minus sign is a
        # typo or a different chemistry; either way it is not ours to guess at.
        if sign == "+" and _plausible(symbol, int(digit)):
            return f"{symbol}{digit}+"

    match = _ROMAN.match(token)
    if match:
        symbol = _resolve_symbol(match.group(1))
        charge = _ROMAN_CHARGES[match.group(2)]
        if _plausible(symbol, charge):
            return f"{symbol}{charge}+"

    match = _BARE.match(token)
    if match:
        symbol = _resolve_symbol(match.group(1))
        if symbol is not None:
            return f"{symbol}{_DEFAULT_CHARGE[symbol]}+"

    return None


def ion_charge(ion: str) -> int | None:
    """Formal charge of a canonical or near-canonical ion string, or None."""
    canonical = canonical_ion(ion)
    if canonical is None:
        return None
    return int(canonical[-2])


def is_lanthanide(ion: str) -> bool:
    """True for the 15 elements La-Lu, in any oxidation state.

    Y3+ and Sc3+ are rare earths and are tabulated here, but they are not
    lanthanides and this returns False for them. The distinction matters
    because the contraction argument -- the only genuinely ion-dependent thing
    this module offers -- is a statement about the 4f series. Y3+ borrows a
    lanthanide-sized radius without having the 4f electrons that produce it,
    and Sc3+ does not even borrow the radius.
    """
    canonical = canonical_ion(ion)
    if canonical is None:
        return False
    return canonical[:-2] in _LANTHANIDE_SYMBOLS


def is_rare_earth(ion: str) -> bool:
    """True for the 15 lanthanides plus Y and Sc, the IUPAC rare earths."""
    canonical = canonical_ion(ion)
    if canonical is None:
        return False
    return canonical[:-2] in _ELEMENT_NAMES.values() and canonical[:-2] != "Ca"


def tabulated_coordination_numbers(ion: str) -> tuple[int, ...]:
    """Coordination numbers Shannon tabulates for this ion here, ascending.

    Empty for an unknown ion or an oxidation state with no data, which is the
    same signal radius() gives and lets a caller enumerate what is answerable
    before asking.
    """
    canonical = canonical_ion(ion)
    if canonical is None:
        return ()
    return tuple(sorted(SHANNON_EFFECTIVE_RADII_A.get(canonical, {})))


def whole_cn(cn) -> int | None:
    """A coordination number as an int, or None if it is not a whole count.

    Coordination numbers arrive from JSON and from parquet as "9" or as
    numpy.int64 often enough to be worth coercing. What must NOT happen is
    int(9.7) -> 9: a mean coordination number averaged across protomers, or a
    fractional occupancy, would then be answered with the CN 9 row and the
    answer would be indistinguishable from a real lookup. A count that is not
    whole is a count this table cannot be asked about.

    bool is rejected for the same reason size_match() rejects it as a distance:
    True is not a coordination number.
    """
    if isinstance(cn, bool):
        return None
    try:
        whole = int(cn)
        if float(cn) != whole:
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    return whole


def radius(ion: str, cn: int) -> float | None:
    """Shannon effective ionic radius in Angstrom, or None if not tabulated.

    None covers four distinct cases on purpose -- unrecognised ion,
    untabulated oxidation state, untabulated coordination number, and a
    coordination number that is not a whole count -- because a caller's correct
    response to all four is identical: do not report a size match. Use
    tabulated_coordination_numbers() and canonical_ion() to tell them apart
    when the distinction matters for a message to the user.

    There is no interpolation between coordination numbers, and no truncation
    to one. Shannon's gaps are where the underlying crystal structures were too
    few to fit a radius to, and filling them -- whether by interpolating or by
    rounding 9.7 down to the CN 9 row -- would manufacture a number with the
    same shape as a measured one.
    """
    canonical = canonical_ion(ion)
    if canonical is None:
        return None
    whole = whole_cn(cn)
    if whole is None:
        return None
    return SHANNON_EFFECTIVE_RADII_A.get(canonical, {}).get(whole)


def charge_density(ion: str, cn: int) -> float | None:
    """Formal charge divided by Shannon radius, in e/Angstrom. None if the
    radius is not tabulated.

    The standard hard-acid proxy, and the one-line reason lanthanides displace
    calcium from oxygen-rich sites: Ln3+ at CN 9 runs 2.47 e/A (La3+) to
    2.91 e/A (Lu3+), while Ca2+ at its canonical protein CN 7 is 1.89 e/A, so
    a Ln3+ brings 1.3-1.5x the charge density into the same pocket. That is
    electrostatic and it is the mechanism behind the pocket-charge selectivity
    result this project already leans on (Nikolova & Dudev, Int J Mol Sci 2023,
    24, 6297; cited in structure.py).

    It is a ratio of two numbers, not a thermodynamic quantity. It says nothing
    about desolvation penalty, which is the term that actually decides whether
    the displacement happens, and nothing about discrimination *within* the
    lanthanide series -- charge density rises monotonically from La3+ to Lu3+
    and would rank every site the same way, which is a signature of a
    descriptor carrying no site-specific information.
    """
    r = radius(ion, cn)
    charge = ion_charge(ion)
    if r is None or charge is None or r <= 0:
        return None
    return charge / r


def typical_coordination(ion: str) -> dict | None:
    """Observed coordination-number range for an ion, or None if unknown.

    Returns {"minimum", "typical", "maximum", "basis", "caveat"}. See
    _COORDINATION_RANGES for where the numbers come from and why they are not
    taken from this project's corpus.
    """
    canonical = canonical_ion(ion)
    if canonical is None or canonical not in _COORDINATION_RANGES:
        return None
    low, typical, high = _COORDINATION_RANGES[canonical]
    return {
        "ion": canonical,
        "minimum": low,
        "typical": typical,
        "maximum": high,
        "basis": ("Aqueous and solid-state coordination numbers for the trivalent "
                  "rare earths (Greenwood & Earnshaw, Chemistry of the Elements): "
                  "the larger ions are 9-coordinate as [Ln(H2O)9]3+ and the smaller "
                  "ones 8-coordinate. Ca2+ is given its canonical protein geometry, "
                  "CN 7 pentagonal bipyramidal."),
        "caveat": ("Descriptive, not a constraint. Ln3+ bonding is essentially "
                   "electrostatic and non-directional, so coordination geometry is "
                   "set by the ligands and a site outside this range is unusual "
                   "rather than wrong. A coordination number read from an "
                   "asymmetric unit is also a lower bound (see geometry.py), so a "
                   "site reading below the minimum may simply be truncated."),
    }


# The one statement this platform can make about the ion a user actually named,
# as opposed to the ion that happens to be in the crystal.
#
# Every other per-ion number here is comparative: size_match ranks the series at
# one site, and SIZE_RANK_SELF_CHECK records that the ranking does not even
# recover the ion known to bind there, so it cannot be read as "this ion binds".
# A coordination number is different in kind. It is read off the deposited
# coordinates, and _COORDINATION_RANGES gives each ion a range that was not
# derived from this corpus, so asking whether one falls inside the other is a
# question about the named ion that does not route through the ranking at all.
#
# It is still only geometry. A site can sit dead-centre in an ion's range and
# bind it weakly or not at all, which is why the verdict words below describe
# the coordination number and never the binding.
COORDINATION_FIT_IS_NOT_BINDING = (
    "Whether a coordination number falls in an ion's usual range is a statement "
    "about geometry and nothing else. It is not an affinity, not a selectivity "
    "prediction, and not evidence that the ion was observed in this site. "
    "Neighbouring lanthanides share almost identical ranges, so a site "
    "compatible with one is compatible with several; this can rule a site in, "
    "never rule a competitor out."
)

_FIT_WORDS = {
    "typical": "is exactly the coordination number {ion} most often adopts",
    "within_range": "falls inside the range {ion} is normally found in ({low}-{high})",
    "above_range": "is higher than {ion} is normally found in ({low}-{high})",
    "below_range": "is lower than {ion} is normally found in ({low}-{high})",
}


def coordination_fit(ion: str, observed_cn: int) -> dict | None:
    """Where one observed coordination number sits in one ion's own range.

    Returns the range, a `verdict` of typical / within_range / above_range /
    below_range, and a `statement` saying it in words. None when the ion is
    unrecognised or untabulated, or the coordination number is not a whole
    number -- never a verdict of "no", which would read as a negative finding
    where there is simply no table entry.

    `below_range` is the weakest of the four and is reported with that stated:
    a coordination number measured on an asymmetric unit is a lower bound, so a
    site can read low because the symmetry mate holding the rest of the shell
    was not in the file. `above_range` has no such excuse.
    """
    span = typical_coordination(ion)
    cn = whole_cn(observed_cn)
    if span is None or cn is None:
        return None
    low, typical, high = span["minimum"], span["typical"], span["maximum"]
    if cn == typical:
        verdict = "typical"
    elif low <= cn <= high:
        verdict = "within_range"
    elif cn > high:
        verdict = "above_range"
    else:
        verdict = "below_range"
    statement = (f"CN {cn} " + _FIT_WORDS[verdict].format(
        ion=span["ion"], low=low, high=high) + ".")
    if verdict == "below_range":
        statement += (" A coordination number read from an asymmetric unit is a "
                      "lower bound, so this may be a truncated shell rather than "
                      "a mismatch.")
    return {
        "ion": span["ion"],
        "observed_cn": cn,
        "minimum": low, "typical": typical, "maximum": high,
        "verdict": verdict,
        "compatible": verdict in ("typical", "within_range"),
        "statement": statement,
        "basis": span["basis"],
        "caveat": COORDINATION_FIT_IS_NOT_BINDING + " " + span["caveat"],
    }


def contraction_span_A(cn: int) -> float | None:
    """Width of the trivalent lanthanide series at one coordination number:
    the largest tabulated Ln3+ radius minus the smallest.

    This is the natural unit for "how far off is this site", which is why
    size_match() divides by it. A residual of one span means the site is
    mismatched by the entire lanthanide contraction, at which point no Ln3+ is
    a size match and the fit is zero.

    Computed from the table rather than hardcoded, so that correcting a radius
    cannot leave a stale denominator behind. At CN 7 and CN 10 Shannon
    tabulates only part of the series, so the span there is a lower bound on
    the true width and size_match() says so.
    """
    cn = whole_cn(cn)
    if cn is None:
        return None
    radii = [SHANNON_EFFECTIVE_RADII_A[ion][cn]
             for ion in LANTHANIDES_III
             if cn in SHANNON_EFFECTIVE_RADII_A[ion]]
    if len(radii) < 2:
        return None
    return max(radii) - min(radii)


def _unknown(ion: str | None, cn, distance, reason: str) -> dict:
    """An explicitly-labelled non-answer.

    Shaped like a scored result -- every key a scored result carries, present
    and None -- so that a caller which forgets to check `status` renders a
    blank rather than silently picking up a neighbouring field as if it were a
    score, and so that one which reads a documented key by name gets None
    rather than a KeyError. Both halves matter: a dict that is only *mostly*
    the same shape turns a missing answer into a crash on the unlucky input,
    which is how an honest "unknown" becomes an outage.

    Pinned by test_an_unknown_result_has_every_key_a_scored_one_has, which
    compares the two key sets directly rather than listing either.
    """
    return {
        "ion": ion,
        "coordination_number": cn,
        "observed_mean_donor_distance_A": distance,
        "status": "unknown",
        "fit": None,
        "predicted_distance_A": None,
        "residual_A": None,
        "ionic_radius_A": None,
        "series_width_A": None,
        "basis": f"unknown: {reason}",
        "caveat": SIZE_MATCH_IS_NOT_AFFINITY,
    }


def size_match(ion: str, observed_cn: int, mean_donor_distance_A: float) -> dict:
    """How well one ion's size fits one observed coordination sphere.

    The comparison is deliberately the simplest defensible one:

        predicted = Shannon radius(ion, observed_cn) + DONOR_OXYGEN_RADIUS_A
        residual  = observed mean donor distance - predicted
        fit       = max(0, 1 - |residual| / contraction_span_A(observed_cn))

    Both constants are the scale's own, not fitted to anything: 1.40 A is the
    anchor Shannon's effective radii are defined against, and the denominator
    is the width of the lanthanide series at this coordination number, taken
    from the same table. Nothing here was tuned on protein data, so nothing
    here can have been overfitted to it.

    What the fit means. 1.0 is an exact size match and will not occur -- the
    oxide-anchored prediction runs about 0.045 A long at CN 8-9 against real
    protein sites, so a well-matched ion lands near 0.75. 0.0 means the site is
    off by more than the entire La3+-to-Lu3+ contraction, i.e. no lanthanide
    fits it. Because that systematic offset applies equally to every ion, the
    *ordering* of ions at one site is more trustworthy than any single number;
    rank_by_size_match() exists so callers can use the ordering directly.

    Returns "unknown" rather than a number when the ion is unrecognised, the
    coordination number is not tabulated for it, the series width at that
    coordination number is unknown, or the distance is outside the plausible
    first-shell window. A caller should render those as "unknown", not as a
    low score: a site this function cannot evaluate is not a site that fits
    badly.
    """
    canonical = canonical_ion(ion)
    if canonical is None:
        return _unknown(None, observed_cn, mean_donor_distance_A,
                        f"{ion!r} is not a recognised ion")

    # whole_cn() is the same guard radius() and contraction_span_A() apply, so
    # a fractional CN cannot reach the table by any of the three routes.
    cn = whole_cn(observed_cn)
    if cn is None:
        return _unknown(canonical, observed_cn, mean_donor_distance_A,
                        "coordination number is not a whole number")

    # A distance is a measurement, and is deliberately NOT coerced from text.
    # float("2.5") succeeding is how "2.5 A", "2,5" and a spreadsheet's
    # placeholder string start being treated as measurements; requiring a real
    # number pushes that failure back to whoever parsed the input and still
    # has the units. numpy floats subclass float and so are accepted; bool
    # does too and is rejected, because True is not a distance.
    if isinstance(mean_donor_distance_A, bool) or \
            not isinstance(mean_donor_distance_A, (int, float)):
        return _unknown(canonical, cn, mean_donor_distance_A,
                        "mean donor distance is missing or is not a number "
                        f"(got {type(mean_donor_distance_A).__name__})")
    distance = float(mean_donor_distance_A)
    if distance != distance:       # NaN, which pandas uses for a missing value
        return _unknown(canonical, cn, None,
                        "mean donor distance is missing (NaN)")

    r = radius(canonical, cn)
    if r is None:
        tabulated = tabulated_coordination_numbers(canonical)
        return _unknown(canonical, cn, distance,
                        f"Shannon 1976 tabulates no radius for {canonical} at CN {cn}"
                        + (f"; tabulated here at CN {list(tabulated)}" if tabulated
                           else "; no radii tabulated here for this oxidation state"))

    span = contraction_span_A(cn)
    if span is None:
        return _unknown(canonical, cn, distance,
                        f"fewer than two Ln3+ radii are tabulated at CN {cn}, so the "
                        "lanthanide series has no width to scale a residual against")

    if not (MIN_PLAUSIBLE_DONOR_DISTANCE_A <= distance <= MAX_PLAUSIBLE_DONOR_DISTANCE_A):
        return _unknown(canonical, cn, distance,
                        f"mean donor distance {distance:.2f} A is outside the plausible "
                        f"first shell ({MIN_PLAUSIBLE_DONOR_DISTANCE_A}-"
                        f"{MAX_PLAUSIBLE_DONOR_DISTANCE_A} A; structure.py admits no "
                        "donor beyond 3.2 A, so a mean above it is not a first shell)")

    predicted = r + DONOR_OXYGEN_RADIUS_A
    residual = distance - predicted
    fit = max(0.0, 1.0 - abs(residual) / span)

    basis = (f"{canonical} Shannon effective radius {r:.3f} A at CN {cn} "
             f"({SHANNON_SOURCE}) plus donor oxygen {DONOR_OXYGEN_RADIUS_A:.2f} A, the "
             f"r(O2-) anchor of that scale, predicts a {predicted:.3f} A mean donor "
             f"distance; observed {distance:.3f} A, residual {residual:+.3f} A. Scaled "
             f"by the {span:.3f} A width of the trivalent lanthanide series at CN {cn}.")

    caveats = [SIZE_MATCH_IS_NOT_AFFINITY]
    # An oxide-anchored prediction is systematically long against protein
    # carboxylate donors. Stated on every result because the number a reader
    # sees is the residual, and the residual carries this offset.
    caveats.append(
        "The r(O2-) = 1.40 A anchor describes oxides, not protein carboxylate and "
        "carbonyl donors: over 279 sites at CN 8-9 in this project's corpus the "
        "prediction runs 0.045 A long, so no ion reaches a fit of 1.0 and the "
        "ranking between ions is sounder than any single value.")
    if cn <= 7:
        caveats.append(
            f"CN {cn} is below the 8-10 range the trivalent lanthanides occupy, and a "
            "coordination number read from an asymmetric unit is a lower bound "
            "(geometry.py). In this project's corpus the same prediction runs 0.070 A "
            "SHORT at CN 6-7, the opposite sign, which is what a truncated parse of a "
            "higher-CN site looks like. Treat this as describing the parse.")
    tabulated_here = sum(1 for i in LANTHANIDES_III
                         if cn in SHANNON_EFFECTIVE_RADII_A[i])
    if tabulated_here < len(LANTHANIDES_III):
        caveats.append(
            f"Shannon tabulates only {tabulated_here} of {len(LANTHANIDES_III)} "
            f"trivalent lanthanides at CN {cn}, so the series width used as the "
            "denominator is a lower bound and this fit is correspondingly harsh.")

    return {
        "ion": canonical,
        "coordination_number": cn,
        "observed_mean_donor_distance_A": round(distance, 3),
        "status": "scored",
        "fit": round(fit, 3),
        "predicted_distance_A": round(predicted, 3),
        "residual_A": round(residual, 3),
        "ionic_radius_A": r,
        "series_width_A": round(span, 3),
        "basis": basis,
        "caveat": " ".join(caveats),
    }


def rank_by_size_match(observed_cn: int, mean_donor_distance_A: float,
                       ions: tuple[str, ...] = LANTHANIDES_III) -> list[dict]:
    """Every ion that can be scored at this site, best size match first.

    This is the form in which a size propensity is worth anything. The absolute
    fit carries a systematic offset from the oxide-anchored donor radius
    (size_match); the offset is the same for every ion at a given coordination
    number, so it cancels out of the ordering and leaves the comparison intact.

    Ions that cannot be scored are dropped rather than ranked last, because an
    unknown is not a poor fit and a list that mixes the two invites a reader to
    treat the bottom of it as rejected candidates. Call size_match() per ion
    when the distinction matters.

    The ordering is still a size ordering. It does not predict which ion the
    protein will actually prefer; adjacent lanthanides are separated here by
    ~0.01-0.02 A, well inside crystallographic coordinate error.
    """
    scored = [size_match(ion, observed_cn, mean_donor_distance_A) for ion in ions]
    return sorted((m for m in scored if m["status"] == "scored"),
                  key=lambda m: m["fit"], reverse=True)
