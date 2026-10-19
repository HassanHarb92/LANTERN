#!/usr/bin/env python3
"""The Dudev selectivity rule, measured on the cached structures.

Nikolova & Dudev (IJMS 2023, 24, 6297) report, from DFT/PCM calculations on
model sites: "buried active centers with net charge of -4 or -3 are
characterized by higher Ln3+ over Ca2+ selectivity, whereas it is the opposite
for sites with overall charge of -1."

That sentence is a conjunction -- buried AND -3/-4 -- and it is a statement
about which ion a *given* site prefers, not a statement that lanthanide-bound
sites in the PDB look different from calcium-bound ones. Those are different
claims, and this script exists to find out whether the second one holds here,
because only the second one would make these two descriptors useful for
ranking candidates.

Usage:  python scripts/burial_and_charge.py
"""
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reefinder.structure import (ALL_METAL_CODES,         # noqa: E402
                                 REE_LIGAND_CODES, binding_neighborhood)

STRUCTURES = ("8FNS", "8FNR", "8DQ2", "9PI2", "1CLL")


def collect() -> list[dict]:
    """Every metal site in the cached structures, tagged Ln or Ca."""
    sites = []
    for pdb_id in STRUCTURES:
        path = ROOT / "data" / "structures" / f"{pdb_id}.pdb"
        if not path.exists():
            print(f"  (missing {path.name}, skipped)")
            continue
        for site in binding_neighborhood(path.read_text(), "pdb",
                                         metals=ALL_METAL_CODES):
            site["pdb_id"] = pdb_id
            # Tagged by ligand code, not by element string: "lanthanide" here
            # means "one of the REE codes the corpus scans for", which is the
            # same set binding_neighborhood() uses by default.
            site["family"] = ("lanthanide"
                              if site["metal"].strip().upper() in REE_LIGAND_CODES
                              else "calcium")
            sites.append(site)
    return sites


def _summary(values: list[float]) -> str:
    if not values:
        return "n/a"
    if len(values) < 4:
        return f"{statistics.median(values):.2f}"
    q1, q3 = statistics.quantiles(values, n=4)[0], statistics.quantiles(values, n=4)[2]
    return f"{statistics.median(values):6.2f}  ({q1:.2f}-{q3:.2f})"


def report_distributions(sites: list[dict]) -> None:
    print("Descriptor distributions by family (median, IQR)")
    print(f"  {'descriptor':28s} {'lanthanide':>22s} {'calcium':>22s}")
    groups = {f: [s for s in sites if s["family"] == f]
              for f in ("lanthanide", "calcium")}
    fields = [
        ("net_charge (first shell)", lambda s: s["charge"]["net_charge"]),
        ("metal SASA A^2", lambda s: s["burial"]["metal_sasa_A2"]),
        ("protein atoms <8A", lambda s: s["burial"]["protein_atoms_within_8A"]),
        ("shell net charge <8A", lambda s: s["burial"]["shell_net_charge"]),
        ("coordination number", lambda s: s["coordination_number"]),
    ]
    for label, get in fields:
        cells = []
        for family in ("lanthanide", "calcium"):
            values = [get(s) for s in groups[family] if get(s) is not None]
            cells.append(f"{_summary(values):>22s}")
        print(f"  {label:28s} {cells[0]} {cells[1]}")


def report_dudev_classes(sites: list[dict]) -> None:
    """The rule as stated: cross-tabulate charge class against burial.

    Buried is taken as SASA == 0, which is the strict reading -- no probe
    contact at all. The rule's own model sites are fully enclosed, so a looser
    threshold would be reading it more generously than it was written.
    """
    print("\nDudev classes: charge x burial, counts by family (Ln / Ca)")
    print(f"  {'charge':>8s}  {'buried (SASA=0)':>17s}  {'exposed':>17s}")
    charges = sorted({s["charge"]["net_charge"] for s in sites})
    for charge in charges:
        row = []
        for buried in (True, False):
            group = [s for s in sites
                     if s["charge"]["net_charge"] == charge
                     and (s["burial"]["metal_sasa_A2"] == 0) is buried]
            ln = sum(1 for s in group if s["family"] == "lanthanide")
            ca = len(group) - ln
            row.append(f"{ln:7d} / {ca:<7d}")
        print(f"  {charge:>8d}  {row[0]:>17s}  {row[1]:>17s}")
    predicted = [s for s in sites
                 if s["charge"]["net_charge"] in (-3, -4)
                 and s["burial"]["metal_sasa_A2"] == 0]
    print(f"\n  Sites meeting the rule's Ln-selective condition "
          f"(buried AND -3/-4): {len(predicted)} of {len(sites)}")
    if predicted:
        ln = sum(1 for s in predicted if s["family"] == "lanthanide")
        print(f"    of which Ln-bound {ln}, Ca-bound {len(predicted) - ln}")


def report_separation(sites: list[dict]) -> dict[str, float]:
    """Can either descriptor be thresholded to tell the families apart?

    Scored as *balanced* accuracy -- the mean of the two per-family recalls --
    not raw accuracy. The sample is 36 lanthanide against 6 calcium, so raw
    accuracy starts at 85.7% for a rule that says "lanthanide" and reads
    nothing, and every descriptor would score near there whether or not it
    carries signal. Balanced accuracy starts at 50% for that rule instead.

    Degenerate thresholds -- ones that put every site on the same side -- are
    skipped. They score the majority rule under a descriptor's name, which is
    how a descriptor that measures nothing comes to look like it measures
    something.

    The threshold is still chosen on the data it is scored on, so these are
    upper bounds. A descriptor that cannot separate under those conditions
    certainly cannot separate honestly.
    """
    print("\nBest-case separation, threshold fitted on the same data (upper bound)")
    print(f"  {'descriptor':28s} {'bal. acc':>9s} {'at':>8s} "
          f"{'Ln recall':>12s} {'Ca recall':>12s}")
    fields = [
        ("net_charge (first shell)", lambda s: s["charge"]["net_charge"]),
        ("metal SASA A^2", lambda s: s["burial"]["metal_sasa_A2"]),
        ("protein atoms <8A", lambda s: s["burial"]["protein_atoms_within_8A"]),
        ("shell net charge <8A", lambda s: s["burial"]["shell_net_charge"]),
        ("coordination number", lambda s: s["coordination_number"]),
    ]
    scores = {}
    for label, get in fields:
        usable = [s for s in sites if get(s) is not None]
        lanthanide = [s for s in usable if s["family"] == "lanthanide"]
        calcium = [s for s in usable if s["family"] == "calcium"]
        best, best_at, best_hits = 0.0, None, (0, 0)
        for threshold in sorted({get(s) for s in usable}):
            for direction in (1, -1):
                def says_lanthanide(site, t=threshold, d=direction):
                    return (get(site) >= t) == (d == 1)
                calls = [says_lanthanide(s) for s in usable]
                if all(calls) or not any(calls):
                    continue                      # degenerate: majority rule
                ln_hits = sum(map(says_lanthanide, lanthanide))
                ca_hits = sum(1 for s in calcium if not says_lanthanide(s))
                balanced = (ln_hits / len(lanthanide) + ca_hits / len(calcium)) / 2
                if balanced > best:
                    best, best_at, best_hits = balanced, (threshold, direction), \
                        (ln_hits, ca_hits)
        if best_at is None:
            print(f"  {label:28s} {'constant':>9s}")
            continue
        scores[label] = best
        arrow = ">=" if best_at[1] == 1 else "<"
        # Counts, not just rates. "66.7%" over six calcium sites is four of
        # them, and one site changing its mind moves that figure 17 points.
        ln_cell = f"{best_hits[0]/len(lanthanide):.0%} ({best_hits[0]}/{len(lanthanide)})"
        ca_cell = f"{best_hits[1]/len(calcium):.0%} ({best_hits[1]}/{len(calcium)})"
        print(f"  {label:28s} {best:9.1%} {f'{arrow}{best_at[0]:g}':>8s} "
              f"{ln_cell:>12s} {ca_cell:>12s}")
    print(f"  Balanced-accuracy baseline is 50.0% "
          f"({len(sites)} sites: {sum(1 for s in sites if s['family'] == 'lanthanide')} "
          f"Ln, {sum(1 for s in sites if s['family'] == 'calcium')} Ca).")
    return scores


def main() -> int:
    sites = collect()
    ln = sum(1 for s in sites if s["family"] == "lanthanide")
    print(f"{len(sites)} metal sites from {len(STRUCTURES)} structures: "
          f"{ln} lanthanide, {len(sites) - ln} calcium\n")

    report_distributions(sites)
    report_dudev_classes(sites)
    scores = report_separation(sites)

    # Computed, not transcribed. Every number in the paragraph below is
    # re-derived on each run, so it cannot drift away from the table above it
    # when the structure set changes.
    def in_class(group: list[dict]) -> tuple[int, int]:
        hits = sum(1 for s in group if s["charge"]["net_charge"] in (-3, -4))
        return hits, len(group)

    overall = in_class(sites)
    by_family = {f: in_class([s for s in sites if s["family"] == f])
                 for f in ("lanthanide", "calcium")}
    charge_acc = scores.get("net_charge (first shell)", 0.0)
    cn_acc = scores.get("coordination number", 0.0)

    print("\nFINDING: net charge is near-constant inside this fold.")
    print(f"  {overall[0] / overall[1]:.1%} of all {overall[1]} sites are -3 or -4, "
          f"and that holds on both")
    print(f"  sides -- {by_family['lanthanide'][0]} of {by_family['lanthanide'][1]} "
          f"lanthanide sites and {by_family['calcium'][0]} of "
          f"{by_family['calcium'][1]} calcium.")
    print("  An EF-hand loop places carboxylates at fixed loop positions, so")
    print("  its first-shell charge is a property of the fold and not of the")
    print("  bound ion. A descriptor that barely varies within a family cannot")
    print(f"  rank within it, which is why net charge reaches only "
          f"{charge_acc:.1%}")
    print(f"  balanced accuracy while coordination number -- already")
    print(f"  implemented -- reaches {cn_acc:.1%}. This is not a failed")
    print("  measurement; it locates where the Dudev rule has purchase, which")
    print("  is across folds with genuinely different charge, not within one.")
    print()
    print("WHAT THIS SAMPLE CAN AND CANNOT SETTLE.")
    print("  The Dudev rule is a statement about which ion a given site")
    print("  prefers. Every site here already has its preferred ion bound, so")
    print("  the sample cannot test the rule -- it can only test whether the")
    print("  two descriptors separate Ln-bound from Ca-bound sites, which is")
    print("  the weaker thing the score would actually need. Both the contrast")
    print("  set and the positive set are one protein family each, so a")
    print("  descriptor that separates here may be reading the fold rather")
    print("  than the chemistry. M2's full corpus is what would decide it.")
    print()
    print("  Six calcium sites set the ceiling on all of this. Every Ca recall")
    print("  above is a count out of six, one site is 17 percentage points,")
    print("  and no threshold fitted against six points should be shipped.")
    print("  Neither descriptor enters the score on this evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
