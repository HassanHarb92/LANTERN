"""Select proteins worth trying for a lanthanide, by stated rules, from sequence.

WHY THIS EXISTS. "What proteins should I try for capturing Ce3+" is a request
for a shortlist and a reason. `chemistry.screen` gives a number -- an acidic
fraction and a motif count folded into one score -- and that number cannot be
argued with, cannot be checked, and by its own docstring cannot tell a
lanthanide binder from a calcium binder. This module gives rules instead: each
one names the question it answers, the evidence behind it, and what it measured
on this sequence, so a user can disagree with a specific rule rather than with
a score.

THE RULE THAT DOES THE WORK is the lanmodulin architecture criterion from
Mattocks et al., Nature 2023 -- four EF-hand loops, at least one adjacent pair
separated by fewer than 14 residues, under 200 residues in total. The short
linker is the point. Lanmodulins pack their EF-hands roughly twice as tightly
as calcium EF-hand proteins do, and that spacing is visible in sequence alone.
Measured on this project's reference set (`scripts` are not needed; the test
suite re-measures it):

    protein                        loops   min adjacent gap   verdict
    C5B164      Mex-LanM             4            12          select
    A0A4V2JDD3  Hans-LanM            4            12          select
    P0DP23      Calmodulin-1         4            24          reject
    P02585      Troponin C           4            24          reject
    P69905      Haemoglobin alpha    0            --          reject
    P00766      Chymotrypsinogen A   0            --          reject

Two for two on the lanthanide binders, zero for four on everything else, and
the separation is 12 against 24 rather than a margin of one or two residues.
Six proteins is six proteins -- this is a replication of a published criterion
on a small set, not an independent validation of it.

TWO RULES THAT ARE DELIBERATELY NOT RULES. Both looked obvious and both are
wrong, which is why they are named here instead of being quietly absent.

  Counting EF-hands with `chemistry.EF_HAND_HINT`. That pattern is the
  lanthanide-biased *classifier*, and it finds only three loops in Hans-LanM.
  A "four EF-hands" rule built on it rejects one of the two proteins the rule
  exists to find. Counting and spacing therefore use
  `chemistry.EF_LOOP_INSTRUMENT`, the neutral pattern, which finds all four.
  This is the same defect ROADMAP §3.6 records, reached from a different
  direction.

  Requiring Asp at loop position 9. `chemistry` measures it at 82.1% across
  the lanmodulin family against 26.4% in calcium EF-hands, which makes it look
  like the strongest single descriptor available. On the two proteins here it
  inverts: Mex-LanM is Asp at all four positions, but Hans-LanM is Glu at
  three and Thr at one -- zero Asp -- while troponin C, a calcium protein, has
  three. Ranking on Asp-at-9 puts a calcium protein above a real lanthanide
  binder. `chemistry` already reports position 9 without scoring it, and that
  separation is preserved here: it appears in `observations`, never in a rule.

WHAT NO RULE HERE CAN DO. None of this is ion-specific. Every rule is a
lanmodulin-architecture rule, and the architecture is the same whether the
user asked about Ce3+, Nd3+, La3+ or Dy3+ -- nothing in a sequence separates
one trivalent lanthanide from another, because the thing that separates them
is ionic radius against coordination number, and that needs coordinates. A
shortlist from this module answers "which proteins have the fold that binds
lanthanides"; it does not answer "which binds Ce3+ best". The second question
is `ions.size_match` on a measured site, and it needs a structure.

Nor is any of it affinity. A protein that passes every rule has the
architecture and nothing more: no Kd, no selectivity over calcium, no evidence
it folds, no evidence it is expressed.
"""
from dataclasses import dataclass

from .chemistry import EF_HAND_HINT, EF_LOOP_INSTRUMENT, LOOP_LENGTH, ef_hand_loops
from .models import Protein

# Mattocks et al., Nature 618:87-93 (2023), the lanmodulin-family filter.
#
# The criterion is "at least one pair", not "every pair". Hans-LanM's own
# adjacent gaps measured here are 12, 13 and 12, and the ROADMAP records 14 for
# one of them under the paper's own EF-hand boundaries; a rule reading "every
# adjacent pair is 12 to 13 residues apart" rejects it on either measurement.
# The published filter was also a curation aid applied to PSI-BLAST hits and
# followed by manual review -- it was never a retrieval method, and it is not
# one here.
MAX_LENGTH_AA = 200
MIN_EF_HAND_LOOPS = 4
MAX_ADJACENT_GAP_AA = 14          # strictly fewer than this

# A gap here is `next_loop_start - this_loop_start - LOOP_LENGTH`: the residues
# lying between the end of one 12-residue loop and the start of the next. The
# loops come from a fixed-width regex, so this is a sequence distance between
# pattern matches and not necessarily the distance between the EF-hand
# boundaries a curator would draw. The measured headroom is what makes that
# tolerable: lanmodulins come in at 12 against a threshold of 14, calcium
# EF-hand proteins at 24. A definition disagreeing by one or two residues
# changes no verdict on the reference set; one disagreeing by five would.
GAP_DEFINITION = ("residues between the end of one 12-residue EF-loop match "
                  "and the start of the next")

SELECTION_IS_NOT_AFFINITY = (
    "These rules select for the lanmodulin architecture -- four tightly spaced "
    "EF-hand loops in a short protein. They are not an affinity, not a "
    "selectivity over calcium, and not specific to any one lanthanide: the "
    "same rules fire for all fifteen trivalent lanthanides because sequence "
    "cannot "
    "separate them. Telling two lanthanides apart needs ionic radius against "
    "a coordination number measured from structure."
)

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"


@dataclass(frozen=True)
class Rule:
    """One stated, checkable reason a protein is or is not worth trying."""
    id: str
    question: str
    basis: str


RULES = (
    Rule("length",
         f"Is it shorter than {MAX_LENGTH_AA} residues?",
         "Mattocks 2023 length bound. Lanmodulins are small; the bound mostly "
         "removes large multi-domain proteins that happen to carry EF-hands."),
    Rule("ef_hand_count",
         f"Does it carry at least {MIN_EF_HAND_LOOPS} EF-hand loops?",
         "Mattocks 2023, counted with chemistry.EF_LOOP_INSTRUMENT, the "
         "pattern that is neutral between the two families. The lanthanide-"
         "biased classifier finds only 3 of Hans-LanM's 4 and would reject it."),
    Rule("compact_pair",
         f"Are two adjacent EF-hands fewer than {MAX_ADJACENT_GAP_AA} residues apart?",
         "Mattocks 2023, and the rule that does the discriminating: both "
         "lanmodulins in the reference set measure 12, calmodulin and troponin "
         "C measure 24. At least one pair, not every pair."),
)


def ef_hand_layout(sequence: str) -> dict:
    """Where the EF-hand loops are and how tightly they are packed.

    Uses the neutral instrument pattern, never the classifier. Returns start
    positions (1-based), the gap between each adjacent pair, and the smallest
    of those gaps -- `None` when there are fewer than two loops, which is the
    honest answer and not zero.
    """
    loops = ef_hand_loops(sequence, EF_LOOP_INSTRUMENT)
    starts = [loop["start"] for loop in loops]
    gaps = [starts[i + 1] - starts[i] - LOOP_LENGTH for i in range(len(starts) - 1)]
    return {"loops": loops, "count": len(loops), "starts": starts,
            "gaps": gaps, "min_gap": min(gaps) if gaps else None,
            "gap_definition": GAP_DEFINITION}


def _clean_sequence(sequence) -> str:
    if not isinstance(sequence, str):
        return ""
    return "".join(sequence.split()).upper()


def evaluate(protein: Protein) -> dict:
    """Run every rule against one protein and report each verdict separately.

    `selected` is True only when every rule passes. A rule that could not be
    evaluated -- no sequence, or a sequence with characters that are not amino
    acids -- is `unknown`, and an unknown is not a pass: a protein whose
    sequence could not be read is not selected, and the record says which rule
    could not be checked rather than reporting a plausible verdict.
    """
    seq = _clean_sequence(getattr(protein, "sequence", None))
    readable = bool(seq) and set(seq) <= set("ACDEFGHIKLMNPQRSTVWY")

    if not readable:
        why = ("No sequence on this record" if not seq
               else "Sequence contains characters that are not amino acids")
        return {
            "accession": getattr(protein, "accession", None),
            "name": getattr(protein, "name", None),
            "selected": False,
            "passed": 0, "of": len(RULES),
            "rules": [{"id": rule.id, "question": rule.question,
                       "basis": rule.basis, "verdict": UNKNOWN,
                       "measured": None, "detail": why} for rule in RULES],
            "observations": {},
            "disclaimer": SELECTION_IS_NOT_AFFINITY,
        }

    layout = ef_hand_layout(seq)
    length = len(seq)
    min_gap = layout["min_gap"]

    verdicts = {
        "length": (
            PASS if length < MAX_LENGTH_AA else FAIL, length,
            f"{length} residues; the bound is {MAX_LENGTH_AA}."),
        "ef_hand_count": (
            PASS if layout["count"] >= MIN_EF_HAND_LOOPS else FAIL, layout["count"],
            f"{layout['count']} EF-hand loop(s) at {layout['starts'] or 'no'} "
            f"(1-based); the bound is {MIN_EF_HAND_LOOPS}."),
        "compact_pair": (
            (PASS if min_gap < MAX_ADJACENT_GAP_AA else FAIL) if min_gap is not None
            else FAIL,
            min_gap,
            (f"adjacent gaps {layout['gaps']}, smallest {min_gap}; the bound is "
             f"under {MAX_ADJACENT_GAP_AA}." if min_gap is not None
             else "fewer than two EF-hand loops, so no pair to measure.")),
    }

    rows = [{"id": rule.id, "question": rule.question, "basis": rule.basis,
             "verdict": verdicts[rule.id][0], "measured": verdicts[rule.id][1],
             "detail": verdicts[rule.id][2]} for rule in RULES]
    passed = sum(row["verdict"] == PASS for row in rows)

    return {
        "accession": getattr(protein, "accession", None),
        "name": getattr(protein, "name", None),
        "selected": passed == len(RULES),
        "passed": passed, "of": len(RULES),
        "rules": rows,
        "observations": _observations(seq, layout),
        "disclaimer": SELECTION_IS_NOT_AFFINITY,
    }


def _observations(seq: str, layout: dict) -> dict:
    """Measurements worth showing that are deliberately not rules.

    `position_9` is here and not in RULES for the reason the module docstring
    gives: on the reference set it ranks troponin C, a calcium protein, above
    Hans-LanM, a lanthanide binder. `classifier_loops` is here because the
    biased pattern is informative about loop chemistry and useless for
    counting. Neither affects `selected`.
    """
    acidic = (seq.count("D") + seq.count("E")) / len(seq)
    position_9: dict[str, int] = {}
    for loop in layout["loops"]:
        position_9[loop["position_9"]] = position_9.get(loop["position_9"], 0) + 1
    return {
        "length_aa": len(seq),
        "acidic_fraction": round(acidic, 4),
        "ef_loops": layout["count"],
        "ef_loop_starts": layout["starts"],
        "adjacent_gaps": layout["gaps"],
        "gap_definition": layout["gap_definition"],
        "classifier_loops": len(ef_hand_loops(seq, EF_HAND_HINT)),
        "position_9": position_9,
        "position_9_note": (
            "Reported, never scored. Asp here is the family-wide signal (82.1% "
            "of lanmodulins against 26.4% of calcium EF-hands) but Hans-LanM "
            "carries none, and troponin C carries three."),
    }


# Below the pass/fail line the order is a presentation choice, not a
# calibration. Ranking first on rules passed is defensible; everything after
# that is a tie-break chosen so the list is stable and reads sensibly, and no
# claim is made that a protein with a 12-residue gap is a better candidate than
# one with a 13-residue gap.
RANK_IS_NOT_CALIBRATED = (
    "Candidates are ordered by how many design rules they pass. Within a tier "
    "the order is a stable tie-break on EF-hand count and spacing, not a "
    "ranking by any measured or predicted quantity."
)


def _rank_key(record: dict) -> tuple:
    obs = record["observations"]
    gap = obs.get("adjacent_gaps") or []
    return (-record["passed"],
            -obs.get("ef_loops", 0),
            min(gap) if gap else 10 ** 6,
            str(record.get("accession") or ""))


def rank(proteins, target: str | None = None) -> dict:
    """Evaluate every protein and order them, selected first.

    `target` is accepted and recorded, not used. Every rule is a lanmodulin
    architecture rule and fires identically for every askable lanthanide;
    taking the argument and ignoring it is the honest shape, because the caller
    does have a target and the answer genuinely does not depend on it. The
    returned record says so where a reader will see it.
    """
    records = sorted((evaluate(p) for p in proteins), key=_rank_key)
    selected = [r for r in records if r["selected"]]
    return {
        "target": target,
        "target_was_used": False,
        "candidates": records,
        "selected_count": len(selected),
        "considered": len(records),
        "rules": [{"id": r.id, "question": r.question, "basis": r.basis}
                  for r in RULES],
        "disclaimer": SELECTION_IS_NOT_AFFINITY,
        "ordering": RANK_IS_NOT_CALIBRATED,
    }
