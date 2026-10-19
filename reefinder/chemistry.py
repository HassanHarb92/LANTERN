"""Transparent pre-screen; NOT metal affinity or selectivity prediction."""
import re
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
METALS = {
    "Nd3+": {"name": "Neodymium(III)", "kind": "lanthanide", "notes": "Hard trivalent cation; often prefers oxygen donors."},
    "Dy3+": {"name": "Dysprosium(III)", "kind": "lanthanide", "notes": "Hard trivalent cation; often prefers oxygen donors."},
    "La3+": {"name": "Lanthanum(III)", "kind": "lanthanide", "notes": "Large trivalent lanthanide; often oxygen-coordinated."},
    "Ce3+": {"name": "Cerium(III)", "kind": "lanthanide", "notes": "Trivalent oxidation state used for this screening."},
    "Ca2+": {"name": "Calcium(II)", "kind": "competitor", "notes": "Divalent competitor for oxygen-rich binding sites."},
}

def score_sequence(protein: Protein) -> Candidate:
    seq = protein.sequence.upper().replace(" ", "").replace("\n", "")
    if not seq or not re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWY]+", seq):
        return Candidate(protein, 0., 0, 0., ["Missing or unsupported amino-acid sequence"],
                         "Insufficient sequence information for scoring")
    acidic = (seq.count("D") + seq.count("E")) / len(seq)
    motifs = len(EF_HAND_HINT.findall(seq))
    # Consciously modest score and no metal-specific component.
    score = round(min(100., 10. + min(acidic / 0.22, 1.) * 35. + min(motifs, 4) * 12.), 1)
    flags = ["Sequence-only screening", "Does not predict metal affinity or selectivity"]
    if motifs:
        flags.append(f"{motifs} EF-hand-like sequence motif(s); structural validation needed")
    if acidic > 0.17:
        flags.append("Acidic-residue enriched, not proof of an accessible pocket")
    return Candidate(protein, score, motifs, round(acidic, 4), flags,
                     f"Acidic-residue fraction {acidic:.1%}; EF-hand-like motif matches {motifs}. "
                     "No 3D coordination geometry or binding free energy has been evaluated.")

def screen(proteins: list[Protein]) -> list[Candidate]:
    return sorted((score_sequence(p) for p in proteins), key=lambda c: c.score, reverse=True)
