"""One typed question to a shortlist with structural evidence. The whole loop.

    ask -> plan -> select by design rules -> verify against structure -> show

This is the module the product is. Everything it calls already existed and was
already tested; what was missing was the join, and the join is where the
honesty has to live, because each step is careful on its own and the sentence
a user reads is built from all of them at once.

OFFLINE BY DEFAULT, AND THAT IS THE FULL LOOP. The reference set ships with
the deposited coordinates for both lanmodulins and for calmodulin, so a
question typed with no network and no model configured runs end to end: plan,
shortlist, real coordination numbers measured from real structures, a size
comparison against the user's ion, and a viewer. `live=True` widens the
protein search to UniProt and `allow_predictions=True` lets it fall back to an
AlphaFold model; neither is needed for the canonical question.

THREE PLACES THIS LOOP COULD LIE, AND WHAT STOPS IT.

1. The question. A model that reads "Ce3+" out of text that never mentioned an
   ion would hand the rest of the pipeline a confident target from nowhere.
   `plan.parse_question` corroborates the model's target against the ions the
   text actually names and flags what it cannot corroborate; this module
   refuses to proceed on a flagged plan rather than running it anyway.

2. The shortlist. `design.rank` selects on the lanmodulin architecture, which
   is identical for every lanthanide. It would be easy to present that list
   under the heading the user typed -- "proteins for Ce3+" -- and imply the
   ion was involved. `target_was_used` is False in the record and this module
   repeats it in `caveats`.

3. The structure. This is the subtle one. The deposited metal in 8FNS is
   neodymium; the user asked about cerium. Measuring the site and reporting a
   Ce3+ size fit is a *counterfactual*: it asks whether a Ce3+ ion would fit
   the sphere that an Nd3+ ion is actually sitting in. That is a legitimate
   and useful question and it is not the same as evidence that the protein
   binds Ce3+. Every size comparison in this record carries the element that
   was actually in the crystal, and `size_match_is_counterfactual` says so in
   words whenever those two differ.

WHAT AN ALPHAFOLD MODEL CAN AND CANNOT ADD. A prediction is apo: it contains
no metal ion, so it yields no coordination number, no donor distances and no
size comparison. What it gives is fold confidence, and the useful form of that
is pLDDT over the EF-hand loop residues -- "the binding loops are modelled
confidently" is a real statement and "AlphaFold confirms the site" is not one.
This module therefore reports a prediction as `structure_kind="predicted"`
with a pLDDT summary and no sites at all, rather than as a weaker version of
a deposited structure.
"""
from .alphafold import (EVIDENCE as PREDICTION_EVIDENCE, NotAPredictedModel,
                        confidence_gate, fetch_model, residue_plddt)
from .catalog import load_reference
from .chemistry import LOOP_LENGTH
from .design import SELECTION_IS_NOT_AFFINITY, ef_hand_layout, rank
from .geometry import SCORE_VERSION, score_site
from .ions import LANTHANIDES_III, rank_by_size_match, size_match
from .plan import parse_question
from .structure import (ALL_METAL_CODES, binding_neighborhood, cached_structure,
                        fetch_structure, resolution_from_coordinates)
from .uniprot import search_proteins

# Elements that are a lanthanide in a coordinate file. Yttrium is not one
# chemically but sits with them in every site table this project uses.
LANTHANIDE_ELEMENTS = frozenset(
    "LA CE PR ND PM SM EU GD TB DY HO ER TM YB LU Y".split())

SIZE_MATCH_IS_NOT_BINDING = (
    "A size match compares one ion's Shannon radius against the mean donor "
    "distance actually measured at this site. A good fit says the site is the "
    "right size; it is not an affinity, and it does not separate a lanthanide "
    "from calcium -- Ca2+ scores above Ce3+ at several real lanthanide sites."
)

# The self-check that makes a size number readable, and the reason it is shown
# on every site rather than kept for a methods note.
#
# Each site was crystallised with a particular lanthanide, so there is one ion
# per site that is known to bind it. Asking where the size score puts that ion
# is a free calibration, and the answer measured on this project's own cached
# structures is: not first. At 8FNS site A/201 (Nd, CN 9, 2.51 A) the score
# ranks Nd3+ ninth of fifteen and prefers Gd3+; at 8FNR site A/202 (Dy, CN 9,
# 2.42 A) it ranks Dy3+ sixth and prefers Lu3+. A score that cannot recover
# the ion sitting in the site cannot be used to choose between lanthanides for
# that site, and a user comparing targets on the fit alone would be reading
# noise. `deposited_rank` puts that check next to every number it qualifies.
#
# The rank varies between sites of one structure -- 8FNR ranks Dy3+ third at
# A/201 and sixth at A/202, on a 0.08 A difference in mean donor distance --
# which is the same point from the other direction: the ordering moves by
# several places on distance differences at the scale of coordinate error.
SIZE_RANK_SELF_CHECK = (
    "Each site carries `deposited_rank`: where this size score places the ion "
    "that was actually crystallised in it, out of the 15 trivalent "
    "lanthanides. On this project's own structures that rank is 6th and 9th, "
    "not 1st -- the score does not recover the ion known to bind the site. "
    "Read the fit as a rough size compatibility, never as a choice between "
    "one lanthanide and another."
)

# Why a poor counterfactual fit is not a prediction of non-binding.
SPHERE_CLOSED_AROUND_THE_DEPOSITED_ION = (
    "The donor distance measured here is a property of this complex, not of "
    "the empty protein. An EF-hand loop closes around whichever ion it has: "
    "comparing like with like at coordination number 9, the Nd sites of 8FNS "
    "average 2.52 A and the Dy sites of 8FNR average 2.43 A, tracking the "
    "ionic radii of the two metals. So a low fit for an ion that was not the "
    "one crystallised says the loop would have to move, which is what loops "
    "do; it is not evidence the protein will not bind that ion."
)

PREDICTION_HAS_NO_METAL = (
    "An AlphaFold model is apo: it contains no metal ion, so there is no "
    "coordination number, no donor distance and no size comparison to make "
    "from it. What it supports is that the binding loops are modelled "
    "confidently, which is a statement about the fold and not about binding."
)


def _structure_evidence(target: str, text: str, fmt: str, pdb_id: str) -> dict:
    """Measure every deposited metal site and compare the target ion to each."""
    resolution = resolution_from_coordinates(text, fmt)
    sites = binding_neighborhood(text, fmt, metals=ALL_METAL_CODES)
    # RCSB serves the asymmetric unit, not the biological assembly, so every
    # call made here is scored as "asu" and geometry-v2 downgrades negatives.
    measured = []
    for site in sites:
        call = score_site(site, resolution_A=resolution, coordinate_source="asu")
        deposited = (site.get("element") or "").upper()
        fit = size_match(target, site["coordination_number"],
                         site["mean_donor_distance_A"])
        measured.append({
            "chain": site["chain"], "site": site["site"],
            "deposited_element": site["element"],
            "coordination_number": site["coordination_number"],
            "mean_donor_distance_A": site["mean_donor_distance_A"],
            "protein_donors": site["protein_donor_count"],
            "water_donors": site["water_donor_count"],
            "call": call["call"], "call_reliable": call["call_reliable"],
            "caveats": call["caveats"],
            "size_match": fit,
            # True whenever the ion asked about is not the ion in the crystal.
            "size_match_is_counterfactual": deposited != _element_of(target),
            "ion_context": _ion_context(target, deposited,
                                        site["coordination_number"],
                                        site["mean_donor_distance_A"]),
            "site_id": call["site_id"],
        })
    return {
        "structure_kind": "deposited",
        "pdb_id": pdb_id,
        "format": fmt,
        "resolution_A": resolution,
        "sites": measured,
        "site_count": len(measured),
        "lanthanide_sites": sum(1 for m in measured
                                if (m["deposited_element"] or "").upper()
                                in LANTHANIDE_ELEMENTS),
        "score_version": SCORE_VERSION,
        "coordinates": (text, fmt),
    }


def _element_of(ion: str) -> str:
    """"Ce3+" -> "CE". Used only to ask whether two labels name one element."""
    return "".join(c for c in str(ion) if c.isalpha()).upper()


def _rank_of(element: str, ordering: list[dict]) -> int | None:
    """1-based position of an element symbol in a ranked ion list, or None.

    None is returned for calcium and for anything else outside the trivalent
    lanthanide series, and for an ion the series could not score at this
    coordination number. It means "not placed", never "placed last".
    """
    wanted = (element or "").upper()
    for position, entry in enumerate(ordering, start=1):
        if _element_of(entry["ion"]) == wanted:
            return position
    return None


def _ion_context(target: str, deposited: str, cn, distance) -> dict:
    """Where the target and the deposited ion sit in this site's size ordering.

    `deposited_rank` is the calibration described at SIZE_RANK_SELF_CHECK: the
    site is known to hold the deposited ion, so a size score worth using
    should put it near the top. Reporting the two ranks side by side lets a
    reader see how much the ordering is worth before reading anything into
    where their own target landed.
    """
    ordering = rank_by_size_match(cn, distance) if cn and distance else []
    deposited_rank = _rank_of(deposited, ordering)
    context = {
        "ordering": [{"ion": m["ion"], "fit": m["fit"]} for m in ordering],
        "ions_scored": len(ordering),
        "ions_in_series": len(LANTHANIDES_III),
        "target_rank": _rank_of(_element_of(target), ordering),
        "deposited_rank": deposited_rank,
        "best_fitting_ion": ordering[0]["ion"] if ordering else None,
        "self_check": SIZE_RANK_SELF_CHECK,
    }
    # An absent rank is not a bad rank, and rendered as an empty cell it reads
    # like one. Say which of the two reasons applies, so the table can print
    # the reason instead of a blank next to a list of ions that scored.
    if deposited_rank is None:
        in_series = any(_element_of(ion) == (deposited or "").upper()
                        for ion in LANTHANIDES_III)
        context["deposited_rank_unavailable"] = (
            f"Shannon 1976 tabulates no radius for {deposited} at coordination "
            f"number {cn}, so the ion known to bind this site cannot be placed "
            "in the ordering and the self-check is unavailable here."
            if in_series else
            f"{deposited} is not a trivalent lanthanide, so it is not in this "
            "ordering. The ordering ranks lanthanides only.")
    return context


def _prediction_evidence(accession: str, sequence: str, *, timeout: int) -> dict:
    """An AlphaFold model summarised as fold confidence, never as a site.

    pLDDT is reported over the EF-hand loop residues as well as overall,
    because the whole-chain mean is dominated by the helices and a confident
    mean can sit on top of disordered loops -- which are precisely the
    residues that would do the binding.

    The loop positions come from the UniProt sequence and the pLDDT values
    from the model file, which align because an AlphaFold DB model numbers its
    residues against that same canonical sequence. `ef_loop_residues_found`
    reports how many of the expected positions were actually present, so a
    truncated or fragmented model shows up as a small number instead of a
    confident score over the handful of residues that happened to match.
    """
    record = fetch_model(accession, timeout=timeout)
    per_residue = residue_plddt(record["model_path"])
    layout = ef_hand_layout(sequence or "")
    loop_residues = [n for start in layout["starts"]
                     for n in range(start, start + LOOP_LENGTH)]
    covered = [n for n in loop_residues if n in per_residue]
    gate = confidence_gate([per_residue[n] for n in covered]) if covered else None
    return {
        "structure_kind": "predicted",
        "accession": accession,
        "model_path": record["model_path"],
        # The API's own figure, cross-checked against the file by fetch_model.
        "mean_plddt": record.get("mean_plddt"),
        "ef_loop_residues": len(loop_residues),
        "ef_loop_residues_found": len(covered),
        "ef_loop_confidence": gate,
        "sites": [],
        "site_count": 0,
        "why_no_sites": PREDICTION_HAS_NO_METAL,
        "what_this_is": PREDICTION_EVIDENCE,
    }


def _evidence_for(candidate: dict, protein, target: str, *, live: bool,
                  allow_predictions: bool, timeout: int) -> dict:
    """Whatever structural evidence can be had for one candidate, or why none."""
    notes: list[str] = []
    pdb_id = getattr(protein, "pdb_id", None)

    if pdb_id:
        coords = cached_structure(pdb_id)
        if coords is None and live:
            try:
                coords = fetch_structure(pdb_id, timeout=timeout)
            except Exception as exc:
                notes.append(f"Could not fetch {pdb_id} ({type(exc).__name__}).")
                coords = None
        elif coords is None:
            notes.append(f"{pdb_id} is linked but not in the local cache; "
                         "enable live lookups to fetch it.")
        if coords is not None:
            text, fmt = coords
            evidence = _structure_evidence(target, text, fmt, pdb_id.upper())
            evidence["notes"] = notes
            return evidence

    if allow_predictions and getattr(protein, "accession", None):
        try:
            evidence = _prediction_evidence(protein.accession,
                                            getattr(protein, "sequence", ""),
                                            timeout=timeout)
            evidence["notes"] = notes
            return evidence
        except NotAPredictedModel as exc:
            notes.append(f"AlphaFold returned a file that is not a prediction: {exc}")
        except Exception as exc:
            notes.append(f"No AlphaFold model available "
                         f"({type(exc).__name__}).")

    notes.append("No deposited structure and no prediction, so the coordination "
                 "number is unknown. The design rules above are sequence-only.")
    return {"structure_kind": "none", "sites": [], "site_count": 0, "notes": notes}


def answer(question, *, client=None, proteins=None, live=False,
           allow_predictions=False, verify=True, max_structures: int = 3,
           timeout: int = 25) -> dict:
    """Run the whole loop on one question.

    Returns a record with `answered` False and the plan's own notes when the
    question could not be resolved to a validated target -- including when a
    language model offered one the question text does not support. Nothing
    downstream runs in that case: a shortlist printed under an unvalidated
    target is worse than no shortlist, because it looks like an answer.
    """
    plan = parse_question(question, client)
    record = {
        "question": plan.question,
        "plan": plan.as_dict(),
        "answered": False,
        "shortlist": None,
        "evidence": [],
        "caveats": [SELECTION_IS_NOT_AFFINITY],
        "notes": list(plan.notes),
    }
    if plan.needs_clarification or plan.target is None:
        return record

    target = plan.target
    if proteins is None:
        if live:
            proteins = search_proteins(plan.corpus, limit=plan.limit)
            record["notes"].append(
                f"Searched UniProt for {plan.corpus!r}, up to {plan.limit} records.")
        else:
            proteins = load_reference()
            record["notes"].append(
                f"Screened the bundled reference set ({len(proteins)} authentic "
                "UniProt sequences). Switch on live lookups to search more.")

    shortlist = rank(proteins, target=target)
    record["shortlist"] = shortlist
    record["answered"] = True
    record["caveats"].append(
        f"The shortlist does not depend on {target}: every design rule is a "
        "lanmodulin-architecture rule and fires identically for all four "
        "supported lanthanides. The ion enters only at the structure step.")

    if not verify:
        return record

    by_accession = {getattr(p, "accession", None): p for p in proteins}
    selected = [c for c in shortlist["candidates"] if c["selected"]][:max_structures]
    for candidate in selected:
        protein = by_accession.get(candidate["accession"])
        if protein is None:
            continue
        evidence = _evidence_for(candidate, protein, target, live=live,
                                 allow_predictions=allow_predictions,
                                 timeout=timeout)
        evidence["accession"] = candidate["accession"]
        evidence["name"] = candidate["name"]
        record["evidence"].append(evidence)

    if any(ev["structure_kind"] == "deposited" for ev in record["evidence"]):
        record["caveats"] += [SIZE_MATCH_IS_NOT_BINDING, SIZE_RANK_SELF_CHECK]
    if any(site["size_match_is_counterfactual"]
           for ev in record["evidence"] for site in ev["sites"]):
        record["caveats"] += [
            f"At least one site below holds a different element than {target}. "
            f"Its size comparison asks whether {target} would fit a sphere "
            "measured around another ion; it is not evidence that this protein "
            f"was observed binding {target}.",
            SPHERE_CLOSED_AROUND_THE_DEPOSITED_ION]
    return record


def headline(record: dict) -> str:
    """One sentence a user can read before any of the tables."""
    if not record["answered"]:
        return "That question did not resolve to a target ion this platform screens."
    shortlist = record["shortlist"]
    n, total = shortlist["selected_count"], shortlist["considered"]
    target = record["plan"]["target"]
    verified = sum(e["site_count"] for e in record["evidence"])
    tail = (f" {verified} deposited metal site(s) were measured across them."
            if verified else " No deposited coordinates were available to measure.")
    return (f"{n} of {total} protein(s) pass every design rule for the "
            f"lanmodulin architecture, the fold that binds {target}.{tail}")
