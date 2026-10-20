"""geometry-v2: one descriptor, because a fourth family killed the other one.

This is the M3.1 geometric score. It is deliberately the smallest thing the
measurements support, and most of this module is the reasons for what it
leaves out.

**What changed from v1, and why it matters more than what it scores.** v1 had
two criteria: coordination number >= 9 and bidentate carboxylates >= 2. At
n = 3 families those two were indistinguishable -- both separated the natural
lanthanide families from all 55 calcium accessions with *zero* overlap, at the
same exact p. Adding a fourth family (ROADMAP 3.19: a wild-type tandem-PepSY
protein from *Methylobacillus flagellatus*, UniProt Q1H2G7, crystallised with
seven different lanthanides) separated them completely:

    coordination number      Ln medians 9, 9, 9, 10    0 of 55 Ca reach 9
    bidentate carboxylates   Ln medians 1, 2, 2, 3.5  30 of 55 Ca reach 1

The fourth family reaches CN 9 through five *monodentate* carboxylates rather
than two bidentate ones. Same coordination number, different route to it. So
the bidentate threshold had to drop to 1 to keep the family, and at 1 it lets
through 30 of the 55 calcium accessions: the criterion is not a lanthanide
signal, it is a description of how three particular folds happen to chelate.

**The trap this is the third instance of.** Ranked by p-value, bidentate
carboxylates is still the *second best* descriptor of the nine at n = 4
(p=0.000068). Ranked by overlap it is seventh, at 30 of 55. ROADMAP 3.17
established the rule -- overlap count beats p-value at small n -- and this is
the first time it has been applied against something already shipped. The
p-value stays small because three of four families sit high; it cannot see
that the fourth one is in the calcium bulk.

**What dropping it cost, measured both ways.** The second criterion was never
buying specificity: CN >= 9 alone already passed 0 of 55 calcium accessions
before the fourth family existed. It was costing sensitivity.

                            Ln families   Ca accessions   site sens   site spec
    CN>=9 AND bidentate>=2      3 of 4         0 of 55       52.9%      99.55%
    CN>=9 alone                 4 of 4         0 of 55       65.4%      99.25%

Twelve points of sensitivity and a whole family, for 0.3 points of site-level
specificity -- two additional false-positive sites out of 664. Those four
numbers are printed by `scripts/selectivity_contrast.py` rather than copied
in by hand, which is how the first version of them came to be computed over
a denominator containing three calcium ions.

**A second negative control, orthogonal to calcium.** 3.19 also curated the
Tb-Xo4 "crystallophore" entries: 12 structures where a lanthanide complex was
added purely as a nucleating and phasing agent, so the element is right and
the site is certainly not biology. 98 of their 126 sites are removed by the
resolution and chelator filters; of the 28 that survive, *none* reaches CN 9
(they run CN 0-4, bare surface ions). The calcium contrast tests the wrong
metal in a real site; this tests the right metal in a non-site.

**What is reported and not scored.** Net charge is the published Dudev
prediction and is exactly as tempting as that makes it, but 17 of 55 calcium
accessions are as anionic as the lanthanide families -- it has now failed on
overlap five times. Solvent accessibility fails too (25 of 55). Bidentate
carboxylates now joins them. All three are in `triage_only`: visible, so a
reader can see they were measured and rejected rather than forgotten.

**There are no weights.** The score is whether the one criterion is met. The
threshold is the minimum of the positive class's family medians, fitted and
scored on the same points; that makes this a descriptive separation, not a
validated classifier, and `caveats` says so on every single call.

**Why a negative call is weaker than a positive one.** Coordination number is
a count that a truncated parse can only *understate*. A metal on a
crystallographic symmetry axis is coordinated by two protomers while the
deposited asymmetric unit holds one, so a CN read off an ASU is a lower bound:
9C8X reads CN 5 from the deposited coordinates and CN 10 from the biological
assembly, which is the difference between discarding a lanthanide chaperone
and finding one. This affects 119 of the 808 entries in the corpus. So when
the coordinates are an asymmetric unit a *passing* call is safe and a
*failing* call is not trustworthy -- `call_reliable` is False and the caveat
names the fix. Collapsing to a single criterion makes this cleaner than it was
in v1, because the one thing scored is exactly the thing truncation hides.
"""
from __future__ import annotations

# (descriptor, minimum to count as met, what that threshold is)
#
# The threshold is the weakest of the four lanthanide families, not a midpoint
# between the classes. A midpoint would be tuned to the calcium set's upper
# tail, which is 55 accessions of whatever happened to be deposited; the family
# minimum is a statement about the positive class, which is the thing being
# generalised from.
CRITERIA: tuple[tuple[str, int, str], ...] = (
    ("coordination_number", 9,
     "weakest of 4 Ln families; 0 of 55 Ca accessions and 0 of 28 crystallophore "
     "sites reach it (ROADMAP 3.19, exact one-sided p=0.000002)"),
)

SCORE_VERSION = "geometry-v2"

# The resolution both arms of the contrast were held to. Beyond it the donor
# distances that set the coordination number are not reliably placed, and --
# the lesson of 3.15 -- a resolution cut applied to one side of a comparison
# and not the other manufactures geometric differences on its own.
MAX_RESOLUTION_A = 2.5

ALWAYS = (
    "Threshold is the minimum family median of 4 natural Ln families, fitted and "
    "scored on the same points: a descriptive separation, not a validated classifier.",
    "n = 4 families. The claim is the overlap count -- 0 of 55 Ca accessions reach "
    "the threshold -- not the p-value, which at this n is mostly a statement about n.",
    "A fifth family may do to coordination number what the fourth did to bidentate "
    "carboxylates (ROADMAP 3.19). One descriptor surviving four families is the "
    "current state of the evidence, not a result.",
    "Describes an observed coordination geometry. Not an affinity, not a selectivity "
    "constant, and not a probability.",
)


def _descriptors(site: dict) -> dict:
    """Pull the scored and triage descriptors out of a `binding_neighborhood`
    site, tolerating the flatter row shape the corpus tables use.

    The two dict shapes exist for a reason -- the site dict nests `chemistry`,
    `charge` and `burial`, while the parquet rows are flat -- and a scorer that
    only read one of them could not be checked against the corpus it was
    derived from.
    """
    chemistry = site.get("chemistry") or {}
    charge = site.get("charge") or {}
    burial = site.get("burial") or {}

    def pick(key, *sources):
        for source in sources:
            if key in source and source[key] is not None:
                return source[key]
        return None

    return {
        "coordination_number": pick("coordination_number", site),
        "bidentate_carboxylates": pick("bidentate_carboxylates", chemistry, site),
        "other_ligand_donor_count": pick("other_ligand_donor_count", site) or 0,
        "net_charge": pick("net_charge", charge, site),
        "metal_sasa_A2": pick("metal_sasa_A2", burial, site),
    }


def score_site(site: dict, *, resolution_A: float | None = None,
               coordinate_source: str | None = None) -> dict:
    """Apply geometry-v2 to one site.

    `coordinate_source` is "assembly1" when the coordinates came from the
    biological assembly and "asu" when they came from the deposition as
    deposited. It is not cosmetic and it is not optional in spirit: leaving it
    unset is treated the same as "asu", because an unknown provenance is
    exactly the case where the coordination number may be half of one.
    """
    d = _descriptors(site)
    coordination = d["coordination_number"]
    criteria, met = [], 0
    for name, minimum, basis in CRITERIA:
        value = d[name]
        passed = value is not None and value >= minimum
        met += bool(passed)
        criteria.append({"descriptor": name, "value": value, "threshold": minimum,
                         "met": bool(passed), "basis": basis})

    caveats = list(ALWAYS)
    callable_site = coordination is not None

    # Half the first shell being non-protein, non-water is the corpus's
    # chelator flag. Such a site is measuring the chelator's denticity, so the
    # score is withheld rather than reported with a warning next to it.
    if callable_site and coordination and d["other_ligand_donor_count"] >= coordination / 2:
        callable_site = False
        caveats.append(
            "At least half the first shell is non-protein, non-water: this is a chelated "
            "or soaked complex and its geometry describes the ligand, not the protein.")

    if resolution_A is None:
        caveats.append(
            f"Resolution unknown. The contrast behind this threshold was held to "
            f"{MAX_RESOLUTION_A} A on both sides.")
    elif resolution_A > MAX_RESOLUTION_A:
        callable_site = False
        caveats.append(
            f"Resolution {resolution_A:.2f} A is worse than the {MAX_RESOLUTION_A} A cutoff "
            "both arms of the contrast were held to; donor placement is not reliable here.")

    from_asu = coordinate_source != "assembly1"
    if from_asu:
        caveats.append(
            "Scored from the asymmetric unit" + ("" if coordinate_source else " (provenance not stated)")
            + ". A metal on a crystallographic symmetry axis is coordinated by two protomers "
            "while the deposition holds one, so the coordination number is a lower bound -- "
            "9C8X reads CN 5 here and CN 10 in the biological assembly. Re-score the assembly "
            "before acting on anything short of a pass.")

    if not callable_site:
        call, reliable = "not callable", False
    elif met == len(CRITERIA):
        # A pass cannot be manufactured by a truncated parse, only hidden by
        # one, so a passing call is trustworthy whatever the provenance.
        call, reliable = "lanthanide-like", True
    else:
        call, reliable = "calcium-like", not from_asu

    return {
        "score_version": SCORE_VERSION,
        "call": call,
        "call_reliable": reliable,
        "criteria_met": met if callable_site else 0,
        "criteria_total": len(CRITERIA),
        "score": round(100.0 * met / len(CRITERIA), 1) if callable_site else None,
        "criteria": criteria,
        "triage_only": {
            # Measured, reported, and deliberately not scored. Bidentate count
            # was scored in v1 and was removed by the fourth family, which
            # reaches CN 9 monodentate; net charge is the Dudev prediction and
            # fails on overlap for the fifth time; SASA fails for the sixth.
            "bidentate_carboxylates": d["bidentate_carboxylates"],
            "net_charge": d["net_charge"],
            "metal_sasa_A2": d["metal_sasa_A2"],
        },
        "coordinate_source": coordinate_source or "unstated",
        "caveats": caveats,
    }


def rank_key(call: dict) -> tuple:
    """Sort key for ranking sites, highest first.

    Criterion met is the primary key, then the raw coordination number, and
    then nothing. Sites tied on CN are left in input order rather than
    separated by a descriptor that failed: bidentate count would be the
    obvious tiebreak and using it would silently rank the monodentate family
    of 3.19 below the bidentate ones, which is the weighted-score mistake in
    miniature. Sites that cannot be called sort last whatever their geometry.
    """
    values = {c["descriptor"]: (c["value"] or 0) for c in call["criteria"]}
    return (call["call"] != "not callable", call["criteria_met"],
            values.get("coordination_number", 0))


def score_sites(sites: list[dict], *, resolution_A: float | None = None,
                coordinate_source: str | None = None) -> list[dict]:
    """geometry-v2 over every site in one structure, best first."""
    calls = [score_site(s, resolution_A=resolution_A, coordinate_source=coordinate_source)
             for s in sites]
    return sorted(calls, key=rank_key, reverse=True)
