"""Transparent pre-screen; NOT metal affinity or selectivity prediction."""
import re
from .models import Protein, Candidate

# Flexible EF-hand-like patterns are search hints, not proof of a functional site.
# Classical 12-residue EF-hand motif: D-x-D/N-x-D/N-G-x-I/L/V-D/E-x-x-E.
EF_HAND_HINT = re.compile(r"D.[DN].[DN]G.[ILV][DE]..E")
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
