#!/usr/bin/env python3
"""Which descriptors separate a lanthanide-selective site from a calcium site.

THREE COMPARISONS ARE AVAILABLE IN THIS DATA AND TWO OF THEM CANNOT WORK.

  1. Corpus A's lanthanides vs Corpus A's calciums. Measures provenance, not
     chemistry: most corpus lanthanides were soaked into a crystal grown
     without them, most calciums are structural, and the lanthanides come out
     *more* solvent-exposed. S3.13 Q2. Any score fitted here inverts.

  2. Matched pairs -- the same site signature holding each ion. Controls the
     fold perfectly, and returns nothing: across 19 fold- and
     resolution-matched pairs every descriptor delta is non-significant.
     That null is structural rather than disappointing. A matched pair is by
     construction a site observed with *both* ions, which is a site that is
     not selective; the set is selected for promiscuity, so there is no
     selectivity in it to find. Confirmed by what is absent -- not one
     natural-lanthanide-biology site has a calcium partner, because not
     binding calcium is the entire point of lanmodulin. S3.15.

  3. What this script runs. Sites that bind lanthanide and not calcium
     (natural Ln biology: lanmodulin, XoxF/MDH) against sites that bind
     calcium in their own Ca-only depositions. Unmatched, so it does not
     control the fold -- but unlike (1) both sides are native: each protein
     crystallised with the ion it actually uses. That is the comparison the
     selectivity question is asking.

THE UNIT OF REPLICATION IS THE ENTRY, NOT THE SITE. Lanmodulin carries four
sites per chain and 8FNR contributes fourteen; counting those as fourteen
observations would quadruple the apparent evidence for one protein. Everything
below collapses to one median per entry first. Even that is generous: the ten
lanthanide entries are six methanol/alcohol dehydrogenases and four
lanmodulins, so the honest n is nearer two families than ten entries, and the
per-family table is printed to make that visible rather than to hide it.

BOTH SIDES ARE HELD TO THE SAME RESOLUTION CUTOFF. Coordination number and
donor distance are refinement-dependent, and filtering one side alone
manufactures a difference -- that is not hypothetical, it is what the first
run of the matched analysis did (S3.15).

Thresholds here are fitted and scored on the same points. Balanced accuracy
is therefore optimistic and is reported as a descriptive separation, not a
validated classifier.

Usage:
    python -I scripts/selectivity_contrast.py
    python -I scripts/selectivity_contrast.py --max-resolution 2.0
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np                                         # noqa: E402
import pandas as pd                                        # noqa: E402

LN_TABLE = ROOT / "data" / "lanthanide_sites.parquet"
CA_TABLE = ROOT / "data" / "calcium_sites.parquet"

DESCRIPTORS = [
    "coordination_number", "protein_donor_count", "net_charge",
    "bidentate_carboxylates", "carboxylate_residues", "metal_sasa_A2",
    "protein_atoms_within_8A", "shell_net_charge", "mean_donor_distance_A",
]

# The ten natural-Ln-biology entries are two families. Hard-coded rather than
# inferred from the title, because the point of the table is to show how few
# independent observations there are, and a rule that silently mislabels one
# would hide exactly that.
FAMILIES = {
    "4MAE": "MDH/XoxF", "6DAM": "MDH/XoxF", "6FKW": "MDH/XoxF",
    "6ZCV": "MDH/XoxF", "6ZCW": "MDH/XoxF", "7O6Z": "MDH/XoxF",
    "8DQ2": "lanmodulin", "8FNR": "lanmodulin", "8FNS": "lanmodulin",
    "9PI2": "lanmodulin",
}


def quality(frame: pd.DataFrame, max_resolution: float) -> pd.DataFrame:
    return frame[frame["resolution_A"].notna()
                 & (frame["resolution_A"] <= max_resolution)
                 & (~frame["chelator_flagged"])]


def best_split(x: np.ndarray, y: np.ndarray) -> tuple[float, str]:
    """Highest balanced accuracy over every threshold, both directions."""
    best = (0.0, "")
    for threshold in np.unique(np.concatenate([x, y])):
        for sense in (1, -1):
            accuracy = (((x * sense >= threshold * sense).mean()
                         + (y * sense < threshold * sense).mean()) / 2)
            if accuracy > best[0]:
                best = (accuracy, f"{'>=' if sense == 1 else '<'}{threshold:g}")
    return best


def permutation_p(x: np.ndarray, y: np.ndarray, rounds: int,
                  rng: np.random.Generator) -> float:
    """Two-sided, on the difference of medians.

    A permutation test rather than a t-test because n=10 on one side and
    these distributions are small integers, and rather than Mann-Whitney
    because the difference of medians is the statistic actually quoted.
    """
    observed = abs(np.median(x) - np.median(y))
    pool = np.concatenate([x, y])
    cut, hits = len(x), 0
    for _ in range(rounds):
        rng.shuffle(pool)
        if abs(np.median(pool[:cut]) - np.median(pool[cut:])) >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (rounds + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ln-table", type=Path, default=LN_TABLE)
    parser.add_argument("--ca-table", type=Path, default=CA_TABLE)
    parser.add_argument("--max-resolution", type=float, default=2.5)
    parser.add_argument("--rounds", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    ln_all = pd.read_parquet(args.ln_table)
    ca_all = pd.read_parquet(args.ca_table)
    if "resolution_A" not in ln_all.columns:
        raise SystemExit("site tables predate the resolution column -- rebuild")

    lanthanide = quality(ln_all, args.max_resolution)
    lanthanide = lanthanide[(lanthanide["family"] == "lanthanide")
                            & (lanthanide["class_first_pass"]
                               == "natural_ln_biology")]
    calcium = quality(ca_all, args.max_resolution)
    calcium = calcium[calcium["family"] == "calcium"]

    print(f"both sides <= {args.max_resolution} A, chelator-flagged removed")
    print(f"  native Ln biology: {len(lanthanide)} sites in "
          f"{lanthanide['pdb_id'].nunique()} entries")
    print(f"  Ca-only corpus:    {len(calcium)} sites in "
          f"{calcium['pdb_id'].nunique()} entries")
    if lanthanide.empty or calcium.empty:
        print("one side is empty -- nothing to compare")
        return 1

    print("\nthe lanthanide entries (the unit of replication):")
    for pdb_id, group in lanthanide.groupby("pdb_id"):
        print(f"  {pdb_id}  {len(group):2d} sites  "
              f"{FAMILIES.get(pdb_id, '?'):11s} {group['title'].iat[0][:52]}")

    columns = [c for c in DESCRIPTORS if c in lanthanide.columns]
    per_ln = lanthanide.groupby("pdb_id")[columns].median()
    per_ca = calcium.groupby("pdb_id")[columns].median()

    print(f"\nENTRY level: {len(per_ln)} Ln entries vs {len(per_ca)} Ca entries")
    print(f"  {'descriptor':26s} {'Ln':>7s} {'Ca':>7s} {'bal.acc':>8s}  "
          f"{'split':9s} perm p")
    results = []
    for column in columns:
        x = per_ln[column].dropna().to_numpy(dtype=float)
        y = per_ca[column].dropna().to_numpy(dtype=float)
        if len(x) < 2 or len(y) < 2:
            continue
        accuracy, split = best_split(x, y)
        p = permutation_p(x, y, args.rounds, rng)
        results.append((column, accuracy, p))
        flag = "" if p < 0.05 else "   (n.s.)"
        print(f"  {column:26s} {np.median(x):7.2f} {np.median(y):7.2f} "
              f"{accuracy:8.3f}  {split:9s} {p:.4f}{flag}")

    print(f"\nFAMILY level -- ten entries are two families, which is the "
          f"honest n:")
    by_family = lanthanide.assign(
        family_name=lanthanide["pdb_id"].map(FAMILIES))
    table = by_family.groupby("family_name")[columns].median()
    print(table.to_string(float_format=lambda v: f"{v:.2f}"))

    survivors = [c for c, _, p in results if p < 0.05]
    print(f"\nseparating at p<0.05 on {len(per_ln)} entries: "
          f"{', '.join(survivors) if survivors else 'none'}")
    print("thresholds are fitted and scored on the same points; treat the "
          "balanced accuracies as descriptive, not validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
