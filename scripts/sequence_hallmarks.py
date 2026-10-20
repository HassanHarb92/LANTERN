#!/usr/bin/env python3
"""The two remaining Mattocks et al. 2023 sequence hallmarks, measured through
the balanced instrument rather than the biased classifier.

  Hallmark 2 -- EF-hand period. "Adjacent EF hands in LanMs are separated by
                24-25 residues, compared with ~36 in canonical EF-hand
                proteins."
  Hallmark 3 -- Pro at loop position 2. The 4P2A mutant loosens Ln3+ by only
                5-10x but Ca2+ by ~300x, so Pro at 2 reads as near-pure Ca2+
                rejection rather than Ln3+ affinity.

Both were blocked on §3.10's detector and for a specific reason: period is
measured BETWEEN loops, so a detector that misses one loop reports double the
period, and `EF_HAND_HINT` misses four calcium loops in five. Measuring either
hallmark through the classifier would have produced a confident wrong number.

This script reports each hallmark under both detectors so the size of that
error is visible rather than asserted.

Usage:  python scripts/sequence_hallmarks.py
"""
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lantern.chemistry import (EF_HAND_HINT,          # noqa: E402
                                 EF_LOOP_INSTRUMENT, ef_hand_loops)
from scripts.loop_detector import annotated_sets        # noqa: E402

DETECTORS = (("classifier EF_HAND_HINT", EF_HAND_HINT),
             ("instrument EF_LOOP_INSTRUMENT", EF_LOOP_INSTRUMENT))
PUBLISHED = {"lanmodulin family": (24, 25), "calcium EF-hands": (36, 36)}


def periods(records: list[dict], pattern) -> list[int]:
    """Gaps between consecutive loop starts, pooled over all proteins."""
    out = []
    for record in records:
        starts = [loop["start"] for loop in ef_hand_loops(record["sequence"], pattern)]
        out += [b - a for a, b in zip(starts, starts[1:])]
    return out


def report_period(sets: dict[str, list[dict]]) -> None:
    print("Hallmark 2 -- EF-hand period (gap between consecutive loop starts)")
    print(f"  {'detector':32s} {'set':20s} {'gaps':>5} {'median':>7} "
          f"{'IQR':>13} {'in 20-28':>9}")
    for label, pattern in DETECTORS:
        for name, records in sets.items():
            gaps = periods(records, pattern)
            if not gaps:
                continue
            q1, q3 = (statistics.quantiles(gaps, n=4)[0],
                      statistics.quantiles(gaps, n=4)[2]) if len(gaps) > 3 else (0, 0)
            short = sum(1 for g in gaps if 20 <= g <= 28) / len(gaps)
            print(f"  {label:32s} {name:20s} {len(gaps):5d} "
                  f"{statistics.median(gaps):7.1f} {f'{q1:.0f}-{q3:.0f}':>13} "
                  f"{short:9.1%}")
    print("  Published: 24-25 for lanmodulins, ~36 for canonical EF-hand proteins.")


def report_proline(sets: dict[str, list[dict]]) -> None:
    print("\nHallmark 3 -- Pro at loop position 2")
    print(f"  {'detector':32s} {'set':20s} {'loops':>6} {'Pro at 2':>9} "
          f"{'proteins with >=1':>18}")
    for label, pattern in DETECTORS:
        for name, records in sets.items():
            loops, with_pro = 0, 0
            for record in records:
                found = ef_hand_loops(record["sequence"], pattern)
                loops += len(found)
                hits = sum(1 for lp in found if lp["loop"][1] == "P")
                with_pro += bool(hits)
            share = sum(1 for r in records
                        for lp in ef_hand_loops(r["sequence"], pattern)
                        if lp["loop"][1] == "P") / (loops or 1)
            print(f"  {label:32s} {name:20s} {loops:6d} {share:9.1%} "
                  f"{with_pro/len(records):18.1%}")


def report_position_2_composition(sets: dict[str, list[dict]]) -> None:
    """What is at position 2 instead, which is the part that decides whether
    Pro-at-2 is usable as a feature or merely true."""
    print("\n  Position 2 composition, instrument only (top 6):")
    for name, records in sets.items():
        counts = Counter(lp["loop"][1] for r in records
                         for lp in ef_hand_loops(r["sequence"], EF_LOOP_INSTRUMENT))
        n = sum(counts.values()) or 1
        top = "  ".join(f"{res} {c/n:.0%}" for res, c in counts.most_common(6))
        print(f"    {name:20s} {top}")


def main() -> int:
    calcium, lanm = annotated_sets()
    sets = {"lanmodulin family": lanm, "calcium EF-hands": calcium}
    print(f"lanmodulin family n={len(lanm)}, calcium EF-hands n={len(calcium)}\n")

    report_period(sets)
    report_proline(sets)
    report_position_2_composition(sets)

    print("\nRead the two detector blocks against each other, not in isolation.")
    print("Where they disagree, the classifier is wrong by construction: it is")
    print("tuned to miss calcium loops, and a missed loop inflates the period")
    print("it sits inside -- which is why it puts the calcium period at 45.5")
    print("from 46 gaps where the instrument gets 36.0 from 793.")
    print()
    print("THE CIRCULARITY CAVEAT, which bounds all of the above.")
    print("  The positive set is whatever NCBIfam NF053806 retrieves. These")
    print("  hallmarks are therefore measured on exactly the set an HMM chose,")
    print("  and cannot be used to validate that HMM. Two observations argue")
    print("  the signal is not purely definitional -- per-protein Pro-at-2")
    print("  runs 25%-100% (median 67%) rather than saturating, and the HMM")
    print("  misses A0A4V2JDD3 entirely despite two deposited Ln structures")
    print("  -- but neither settles it. The real test is M4: retrieve by these")
    print("  criteria and see what comes back that the HMM did not contain.")
    print("  Until then these are descriptions of a known family, not")
    print("  validated discovery features, and neither enters the score.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
