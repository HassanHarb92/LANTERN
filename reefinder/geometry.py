"""geometry-v1: the structural call, built on the two descriptors that survived.

This is the M3.1 geometric score. It is deliberately the smallest thing that
the measurements support, and most of this module is the reasons for what it
leaves out.

**What it scores, and why only two things.** ROADMAP 3.17 compared three
natural lanthanide families -- lanmodulin, the XoxF/MDH dehydrogenases, and
the LanD lanthanide chaperone -- against 55 calcium accessions, both sides at
2.5 A or better and chelator-free, with an exact one-sided rank test. Nine
descriptors were measured. Exactly two separate with *no overlap at all*:

    coordination number      Ln 9.00  Ca 7.00   0 of 55 Ca accessions reach 9
    bidentate carboxylates   Ln 2.00  Ca 1.00   0 of 55 Ca accessions reach 2

Those two are the score. Net charge is significant (p=0.0024) and it is the
published Dudev prediction, which is exactly why it is tempting -- but 17 of
55 calcium accessions are as anionic as the lanthanide families, so it is a
triage filter and not a selectivity term. It is reported here, under
`triage_only`, and it does not move the score. Solvent accessibility is not
significant at all (p=0.063, 25 of 55 overlapping) and is reported for the
same reason: so that a reader can see it was measured and rejected rather than
forgotten.

**There are no weights.** A weighted sum of two descriptors fitted on three
families would be three numbers fitted to three points. The score is the count
of criteria met, and ties break on the raw descriptors through `rank_key`. The
thresholds are the family medians of the positive class, fitted and scored on
the same points; that makes this a descriptive separation, not a validated
classifier, and `caveats` says so on every single call.

**Why a negative call is weaker than a positive one.** Both criteria are
counts that a truncated parse can only *understate*. A metal on a
crystallographic symmetry axis is coordinated by two protomers while the
deposited asymmetric unit holds one, so the coordination number read off an
ASU is a lower bound: 9C8X reads CN 5 and net charge -3 from the deposited
coordinates and CN 10, net charge -6 from the biological assembly, which is
the difference between discarding a lanthanide chaperone and finding one.
This affects 119 of the 808 entries in the corpus. So when the coordinates are
an asymmetric unit, a *passing* call is safe and a *failing* call is not
trustworthy -- `call_reliable` is False and the caveat names the fix.
"""
from __future__ import annotations

# (descriptor, minimum to count as met, what that threshold is)
#
# Both thresholds are the weakest of the three lanthanide families, not a
# midpoint between the classes. A midpoint would be tuned to the calcium set's
# upper tail, which is 55 accessions of whatever happened to be deposited; the
# family minimum is a statement about the positive class, which is the thing
# being generalised from.
CRITERIA: tuple[tuple[str, int, str], ...] = (
    ("coordination_number", 9,
     "weakest of 3 Ln families; 0 of 55 Ca accessions reach it (ROADMAP 3.17, exact p=0.00003)"),
    ("bidentate_carboxylates", 2,
     "weakest of 3 Ln families; 0 of 55 Ca accessions reach it (ROADMAP 3.17, exact p=0.00003)"),
)

SCORE_VERSION = "geometry-v1"

# The resolution both arms of the 3.17 contrast were held to. Beyond it the
# donor distances that set the coordination number are not reliably placed,
# and -- the lesson of 3.15 -- a resolution cut applied to one side of a
# comparison and not the other manufactures geometric differences on its own.
MAX_RESOLUTION_A = 2.5

ALWAYS = (
    "Thresholds are the family medians of 3 natural Ln families and are fitted and "
    "scored on the same points: a descriptive separation, not a validated classifier.",
    "n = 3 families. The claim is the overlap count -- 0 of 55 Ca accessions reach "
    "either threshold -- not the p-value, which at this n is mostly a statement about n.",
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
    """Apply geometry-v1 to one site.

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
            f"Resolution unknown. The contrast behind these thresholds was held to "
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
            "while the deposition holds one, so both criteria are lower bounds -- 9C8X reads "
            "CN 5 here and CN 10 in the biological assembly. Re-score the assembly before "
            "acting on anything short of a pass.")

    if not callable_site:
        call, reliable = "not callable", False
    elif met == len(CRITERIA):
        call, reliable = "lanthanide-like", True
    elif met:
        # A pass can only be understated by a truncated parse, never
        # overstated, so a partial or failing call from an ASU is the one that
        # may be an artefact of the coordinates rather than of the protein.
        call, reliable = "partial", not from_asu
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
            # Measured, reported, and deliberately not scored. See the module
            # docstring: net charge is the Dudev prediction and it fails on
            # overlap for the fourth time; SASA fails for the fifth.
            "net_charge": d["net_charge"],
            "metal_sasa_A2": d["metal_sasa_A2"],
        },
        "coordinate_source": coordinate_source or "unstated",
        "caveats": caveats,
    }


def rank_key(call: dict) -> tuple:
    """Sort key for ranking sites, highest first.

    Criteria met is the primary key because it is the part that was measured.
    The raw descriptors break ties instead of being folded into a weighted
    score, so the ordering within a band is transparently "more donors, more
    bidentate carboxylates" rather than a fitted combination pretending to be
    one number. Sites that cannot be called sort last whatever their geometry.
    """
    values = {c["descriptor"]: (c["value"] or 0) for c in call["criteria"]}
    return (call["call"] != "not callable", call["criteria_met"],
            values.get("coordination_number", 0), values.get("bidentate_carboxylates", 0))


def score_sites(sites: list[dict], *, resolution_A: float | None = None,
                coordinate_source: str | None = None) -> list[dict]:
    """geometry-v1 over every site in one structure, best first."""
    calls = [score_site(s, resolution_A=resolution_A, coordinate_source=coordinate_source)
             for s in sites]
    return sorted(calls, key=rank_key, reverse=True)
