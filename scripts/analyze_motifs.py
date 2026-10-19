#!/usr/bin/env python3
"""Reproduce the motif-blindness and EF-hand-spacing findings of ROADMAP.md 3.6 and 3.8.

The headline results:

  * The canonical EF-hand regex hard-codes Asp at loop position 1 and Gly at
    position 6. All three Dy3+-coordinating loops of Hansschlegelia quercus
    lanmodulin violate both, so the regex scores a confirmed lanthanide binder
    at zero motifs.
  * 16% of LanM-family metal-binding loops are invisible to that regex.
  * EF-hand spacing (loop-start period 24-25 in lanmodulins, ~36 in calcium
    EF-hand proteins) does separate them, and is the first sequence-only
    discriminator found for this problem.

Family sequences are cached under .cache/ so reruns are offline.

Usage:  python scripts/analyze_motifs.py
"""
import collections
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reefinder.catalog import load_reference          # noqa: E402
from reefinder.chemistry import EF_HAND_HINT          # noqa: E402
from reefinder.uniprot import search_proteins         # noqa: E402

CACHE = ROOT / ".cache" / "lanm_family.json"

# Position-by-position requirements of D.[DN].[DN]G.[ILV][DE]..E, so a failure
# can be attributed to a specific position rather than reported as "no match".
CANONICAL_POSITIONS = [
    ("D", "Asp only"), (".", "any"), ("DN", "Asp/Asn"), (".", "any"),
    ("DN", "Asp/Asn"), ("G", "Gly only"), (".", "any"), ("ILV", "Ile/Leu/Val"),
    ("DE", "Asp/Glu"), (".", "any"), (".", "any"), ("E", "Glu only"),
]

# The same 12-residue loop with positions 1 and 6 unconstrained. Anchors kept:
# the acidic/amide triad at 1/3/5, hydrophobic at 8, invariant Glu at 12.
PERMISSIVE_LOOP = re.compile(r"[DN].[DN].[DN]..[ILV][DE]..E")

# PROSITE PS00018, transcribed from the curated pattern:
# D-x-[DNS]-{ILVFYW}-[DENSTG]-[DNQGHRK]-{GP}-[LIVMC]-[DENQSTAGC]-x(2)-[DE]-[LIVMFYW]
PS00018 = re.compile(
    r"D.[DNS][^ILVFYW][DENSTG][DNQGHRK][^GP][LIVMC][DENQSTAGC]..[DE][LIVMFYW]")

# Loops whose donors are resolved in the deposited structures, not predicted.
CONFIRMED_LOOPS = {
    "A0A4V2JDD3": ("Hans-LanM, Dy3+ donors in 8FNR",
                   [("34-45", "NKDNDDSLEIAE"), ("58-69", "NPDGDTTLESGE"),
                    ("83-94", "NKDGDQTLEMDE")]),
    "C5B164": ("Mex-LanM, Nd3+ donors in 8FNS",
               [("35-46", "DPDKDGTIDLKE"), ("59-70", "DPDKDGTLDAKE"),
                ("84-95", "DPDNDGTLDKKE")]),
}


def family_sequences() -> list[dict]:
    """The 189 NCBIfam NF053806 members, cached after the first fetch."""
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    proteins = search_proteins("lanm-family", limit=200, timeout=120)
    records = [{"accession": p.accession, "sequence": p.sequence} for p in proteins]
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(records, indent=1))
    return records


def audit_confirmed_loops() -> None:
    print("=" * 72)
    print("3.6  Canonical regex vs structurally confirmed metal-binding loops")
    print("=" * 72)
    print(f"pattern: {EF_HAND_HINT.pattern}\n")
    for accession, (label, loops) in CONFIRMED_LOOPS.items():
        print(f"{accession}  {label}")
        for span, seq in loops:
            failures = [(i + 1, seq[i], why)
                        for i, (allowed, why) in enumerate(CANONICAL_POSITIONS)
                        if allowed != "." and seq[i] not in allowed]
            caret = "".join("^" if any(f[0] == i + 1 for f in failures) else "."
                            for i in range(12))
            print(f"  {span:<7} {seq}   {'MATCH' if not failures else 'MISS'}")
            if failures:
                print(f"  {'':<7} {caret}")
                for position, residue, why in failures:
                    print(f"  {'':<7}   position {position:>2}: "
                          f"has {residue}, pattern demands {why}")
        print()


def audit_prosite() -> None:
    print("PROSITE PS00018 -- the curated pattern InterPro annotates with:")
    reference = {p.accession: p for p in load_reference()}
    for accession, (label, loops) in CONFIRMED_LOOPS.items():
        sequence = reference[accession].sequence
        hits = [m.start() + 1 for m in PS00018.finditer(sequence)]
        confirmed = [int(span.split("-")[0]) for span, _ in loops]
        covered = sorted(set(hits) & set(confirmed))
        print(f"  {accession:<12} PS00018 at {hits or '[]'};  "
              f"confirmed metal loops at {confirmed}")
        print(f"  {'':<12} covers {len(covered)} of {len(confirmed)} confirmed sites")
    print()


def family_motif_counts(records: list[dict]) -> None:
    print("=" * 72)
    print(f"3.6  Scale across {len(records)} LanM-family sequences")
    print("=" * 72)
    asn_at_one = re.compile(r"[DN].[DN].[DN]G.[ILV][DE]..E")
    counts = [
        ("canonical D.[DN].[DN]G.[ILV][DE]..E", EF_HAND_HINT),
        ("...allowing Asn at position 1", asn_at_one),
        ("...also allowing non-Gly at position 6", PERMISSIVE_LOOP),
    ]
    totals = []
    for label, pattern in counts:
        total = sum(len(pattern.findall(r["sequence"])) for r in records)
        totals.append(total)
        delta = f"  (+{total - totals[0]})" if totals and total != totals[0] else ""
        print(f"  {label:<42} {total:>4}{delta}")

    hits = [m for r in records for m in PERMISSIVE_LOOP.findall(r["sequence"])]
    invisible = totals[-1] - totals[0]
    print(f"\n  invisible to the canonical pattern: {invisible}/{totals[-1]} "
          f"({100 * invisible / totals[-1]:.0f}%)\n")
    for position, index in (("1", 0), ("6", 5)):
        composition = collections.Counter(h[index] for h in hits)
        rendered = ", ".join(f"{a} {n}" for a, n in composition.most_common())
        print(f"  position {position} composition: {rendered}")
    print()


def spacing(records: list[dict]) -> None:
    print("=" * 72)
    print("3.8  EF-hand spacing (Mattocks et al. 2023, Nature 618:87, hallmark 2)")
    print("=" * 72)

    def periods(sequence: str) -> list[int]:
        starts = [m.start() for m in PERMISSIVE_LOOP.finditer(sequence)]
        return [b - a for a, b in zip(starts, starts[1:])]

    print("Reference set:")
    for protein in load_reference():
        starts = [m.start() + 1 for m in PERMISSIVE_LOOP.finditer(protein.sequence)]
        gaps = periods(protein.sequence)
        verdict = ""
        if gaps:
            verdict = ("LanM-like (24-25)" if all(22 <= g <= 27 for g in gaps)
                       else "Ca-like (~36)" if all(33 <= g <= 40 for g in gaps)
                       else "mixed")
        print(f"  {protein.accession:<12} {len(protein.sequence):>4} aa  "
              f"loops {str(starts):<26} periods {str(gaps):<14} {verdict}")

    gaps = [g for r in records for g in periods(r["sequence"])]
    in_band = sum(1 for g in gaps if 22 <= g <= 27)
    print(f"\n  LanM family: {len(gaps)} periods, median "
          f"{statistics.median(gaps):.1f}, {100 * in_band / len(gaps):.0f}% in 22-27\n")
    print("  CAUTION: this loop finder has poor recall on calcium EF-hands -- it")
    print("  catches 1 of calmodulin's 4 known loops. The LanM-vs-CaM comparison")
    print("  is NOT yet a valid test. See the ROADMAP 3.8 caveat.")


def main() -> int:
    records = family_sequences()
    audit_confirmed_loops()
    audit_prosite()
    family_motif_counts(records)
    spacing(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
