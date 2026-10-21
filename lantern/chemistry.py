"""Transparent pre-screen; NOT metal affinity or selectivity prediction."""
import re
from collections import Counter

from .ions import LANTHANIDES_III, element_name
from .models import Protein, Candidate

# Flexible EF-hand-like patterns are search hints, not proof of a functional site.
#
# The 12-residue loop ligates at positions 1, 3, 5, 7, 9, 12. The textbook
# consensus D-x-D/N-x-D/N-G-x-I/L/V-D/E-x-x-E is a *calcium* consensus, and
# using it cost this project its best positive control: all three
# Dy3+-binding loops of A0A4V2JDD3 carry Asn at position 1 and a non-Gly at
# position 6, so it scored zero motifs and ranked below calmodulin.
#
# Two relaxations, both read off resolved coordinates rather than fitted:
#   position 1 -> [DN]  Asn Od1 is a genuine first-shell donor in 8FNR, 8DQ2
#                       and 9PI2; it is not a degraded Asp.
#   position 6 -> free  Gly at 6 is a backbone-flexibility requirement of the
#                       7-coordinate calcium geometry, not a donor at all.
# Position 9 keeps the [DE] the calcium consensus already had. That constraint
# is inherited, not added, and it turns out to be the one doing the
# discriminating: Glu at 9 is a bidentate first-shell ligand that expels water
# (8DQ2, 9PI2: CN 10, zero waters), Asp at 9 works second-sphere (8FNS: CN 9,
# two waters), and canonical calcium loops have Thr/Ser/Asn there with a
# bridging water at that vertex. Directed evolution reached the same answer
# independently -- the lanthanide-binding tag (1TJB) is bidentate at 9 and 12.
#
# Validated on 694 sequences by scripts/validate_motif.py: against 505
# reviewed calcium EF-hand proteins, sensitivity for the 189-member
# lanmodulin family rises 91.0% -> 96.8% while specificity holds at ~91%, and
# the share of family members scoring zero motifs falls from 1.1% to 0.0%.
EF_HAND_HINT = re.compile(r"[DN].[DN].[DN]..[ILV][DE]..E")

# The *instrument*, as distinct from the classifier above. Never used for
# scoring -- scripts/loop_detector.py and anything measuring loop properties
# across both families uses this instead, and tests pin the separation.
#
# EF_HAND_HINT is deliberately biased: it recovers 83.3% of lanthanide loops
# read off deposited coordinates but only 20.4% of 1421 curated calcium
# EF-loops. That 63-point gap is exactly what makes it discriminate, and
# exactly what makes it useless for measuring anything. Freeing position 9 in
# it put Glu-at-9 in calcium loops at 3.3%; a neutral definition put the same
# proteins at 13.3%.
#
# This pattern keeps only the three positions that are invariant in BOTH
# families, measured over those 1421 curated loops rather than assumed:
#   position 1  -> [DN]   Asp 91% (and Asn in lanmodulins; see below)
#   position 8  -> [ILV]  Ile 69% + Val 16% + Leu 7%
#   position 12 -> E      Glu 87%, the invariant bidentate anchor
# Everything else is free, including position 9 -- the most variable ligand
# position of the six (Asp 24%, Ser 19%, Thr 15%, Glu 13%, Asn 13%).
#
# Recall 83.0% calcium / 91.7% lanthanide, an 8.7-point gap, at 0.88 matches
# per curated loop. Tightening position 1 from [DN] to [D] collapses
# lanthanide recall to 33.3% while leaving calcium at 82.8% -- an independent
# reconstruction of the §3.6 defect, from curated annotations rather than
# from the four structures that first exposed it.
EF_LOOP_INSTRUMENT = re.compile(r"[DN].{6}[ILV].{3}E")

# The loop is 12 residues and the pattern above spans exactly those 12, so a
# match *is* a loop and can be indexed by position directly.
LOOP_LENGTH = 12
LIGAND_POSITIONS = (1, 3, 5, 7, 9, 12)   # X, Y, Z, -Y, -X, -Z

# Position 9 is reported as a named feature rather than left implicit in the
# regex, because the obvious reading of the structural evidence is wrong and
# somebody will otherwise implement it.
#
# Structurally, Glu at 9 is the tighter architecture: bidentate, expels the
# water, CN 10 (8DQ2, 9PI2). Asp at 9 gives CN 9 with two waters (8FNS).
# Both bind lanthanides. It is tempting to conclude Glu-at-9 is the
# lanthanide marker. At the sequence level that is backwards. Measured over
# 694 sequences with position 9 unconstrained (scripts/validate_motif.py):
#
#                     pos 9 = Asp      pos 9 = Glu     any carboxylate
#   LanM family          82.1%             0.5%             82.6%
#   calcium EF-hands     26.4%            13.3%             39.7%
#
# So the discriminating fact is "position 9 is a carboxylate", and Asp
# carries essentially all of it. Glu at 9 is 27x *more* common in calcium
# EF-hands than in lanmodulins -- it marks the H. quercus sub-architecture,
# not lanthanide binding. A descriptor keyed on Glu-at-9 would select
# calcium proteins.
POSITION_9 = 9
LANTHANIDE_LIKE_POSITION_9 = frozenset("DE")
# The whole trivalent series, derived rather than listed. Five entries used to be
# written out here, which made four lanthanides askable and eleven not: plan.py gates
# the parsed ion on `ion in METALS`, so "proteins for capturing Gd3+" parsed the ion
# correctly and then dropped it, and the run continued on a fallback plan with no
# target at all. Nothing about the scoring was ever specific to those four -- ions.py
# carries Shannon radii for all fifteen and the site corpus holds fourteen of them --
# so the short list was a typo's worth of coverage, not a claim about chemistry.
#
# Pm3+ is included for the same reason ions.py includes it: leaving a hole in the
# series is how a loop over "the lanthanides" silently becomes a loop over fourteen.
# It is flagged instead, because no protein structure with promethium exists to find.
_LN_NOTE = "Hard trivalent lanthanide; oxygen-donor preference, binds EF-hand loops."
METALS = {ion: {"name": f"{element_name(ion[:-2])}(III)", "kind": "lanthanide",
                "notes": _LN_NOTE} for ion in LANTHANIDES_III}
METALS["Pm3+"]["notes"] = ("Hard trivalent lanthanide, but radioactive with no natural "
                           "isotopes: no protein structure contains it, so a search will "
                           "return size scores against other ions' structures and nothing else.")
METALS["Ca2+"] = {"name": "Calcium(II)", "kind": "competitor",
                  "notes": "Divalent competitor for oxygen-rich binding sites."}

def ef_hand_loops(sequence: str, pattern: re.Pattern = EF_HAND_HINT) -> list[dict]:
    """Every loop `pattern` matches, with its ligand positions named.

    Returns the residue sitting at each of the six coordinating positions, so
    the thing doing the discriminating is inspectable instead of buried in a
    regex. Non-overlapping, in sequence order, consistent with the motif
    count used by the score.

    Defaults to the classifier. Pass EF_LOOP_INSTRUMENT to *measure* loop
    properties across both families -- the default will under-report calcium
    loops by roughly 4x, which is intended behaviour for a classifier and a
    silent error for a measurement.
    """
    seq = sequence.upper().replace(" ", "").replace("\n", "")
    loops = []
    for match in pattern.finditer(seq):
        loop = match.group(0)
        loops.append({
            "start": match.start() + 1,       # 1-based residue number
            "loop": loop,
            "ligands": {p: loop[p - 1] for p in LIGAND_POSITIONS},
            "position_9": loop[POSITION_9 - 1],
        })
    return loops


def score_sequence(protein: Protein) -> Candidate:
    seq = protein.sequence.upper().replace(" ", "").replace("\n", "")
    if not seq or not re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWY]+", seq):
        return Candidate(protein, 0., 0, 0., ["Missing or unsupported amino-acid sequence"],
                         "Insufficient sequence information for scoring")
    acidic = (seq.count("D") + seq.count("E")) / len(seq)
    loops = ef_hand_loops(seq)
    motifs = len(loops)
    # Consciously modest score and no metal-specific component. Position 9 is
    # deliberately NOT a term here -- it is already implicit in which loops
    # matched, and adding it again would double-count the same evidence.
    score = round(min(100., 10. + min(acidic / 0.22, 1.) * 35. + min(motifs, 4) * 12.), 1)
    position_9 = Counter(loop["position_9"] for loop in loops)
    flags = ["Sequence-only screening", "Does not predict metal affinity or selectivity"]
    if motifs:
        flags.append(f"{motifs} EF-hand-like sequence motif(s); structural validation needed")
    if acidic > 0.17:
        flags.append("Acidic-residue enriched, not proof of an accessible pocket")
    rationale = (f"Acidic-residue fraction {acidic:.1%}; EF-hand-like motif matches {motifs}. "
                 "No 3D coordination geometry or binding free energy has been evaluated.")
    if position_9:
        spread = ", ".join(f"{res}x{n}" for res, n in sorted(position_9.items()))
        rationale += (f" Loop position 9 (the discriminating position): {spread}. "
                      "Asp there is the lanthanide-family signal; Glu marks a rarer "
                      "sub-architecture and is commoner in calcium EF-hands.")
    return Candidate(protein, score, motifs, round(acidic, 4), flags, rationale,
                     position_9=dict(position_9))

def screen(proteins: list[Protein]) -> list[Candidate]:
    return sorted((score_sequence(p) for p in proteins), key=lambda c: c.score, reverse=True)
