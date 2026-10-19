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

THE UNIT OF REPLICATION IS THE FAMILY, NOT THE SITE OR THE ENTRY. Lanmodulin
carries four sites per chain and 8FNR contributes fourteen. Collapsing to one
median per entry fixes that much, but it is still too generous: the fourteen
lanthanide entries are three families, and four of them are one protein
crystallised with four different lanthanides, which are technical replicates
and not independent observations. Both levels are printed. The entry level is
labelled optimistic because it is, and the family level is the one to quote.

Taking the entry level at face value reverses the conclusion, which is how
this was noticed: at 14 entries net charge reaches p<0.0001 and looks like
the best descriptor in the table, because LanD's four entries drag the median
to -4. At three families it is still significant but 17 of 55 calcium
accessions overlap it, so it does not separate. Pseudo-replication did not
just inflate confidence here, it changed the ranking.

THE TEST IS ONE-SIDED AND EXACT, NOT A PERMUTATION ON THE DIFFERENCE OF
MEDIANS. At n=3 that permutation misbehaves: it counts random triples whose
median falls far *below* the pooled median, the calcium lower tail is fat, and
so coordination number -- which no calcium accession in the set reaches --
scored p=0.15 while a descriptor with 17 overlapping units scored p=0.03.
Perfect separation came out worse than partial separation. The direction each
descriptor should move is fixed in advance by Ln3+ coordination chemistry
(bigger ion, higher CN; harder cation, more anionic donors), so a one-sided
rank test is the honest statistic, and at n=3 the null can be enumerated
exactly rather than sampled.

BOTH SIDES ARE HELD TO THE SAME RESOLUTION CUTOFF. Coordination number and
donor distance are refinement-dependent, and filtering one side alone
manufactures a difference -- that is not hypothetical, it is what the first
run of the matched analysis did (S3.15).

BOTH SIDES ARE ALSO BUILT THE SAME WAY FROM THE SAME COORDINATES. A metal on
a symmetry axis is coordinated by two protomers and the deposited asymmetric
unit holds one, so parsing the ASU finds half the site. The assembly audit
is run over both corpora by one rule, and the mix is printed below rather
than assumed: 15.6% of Corpus A and 11.7% of the calcium set need the
biological assembly, and had the correction been applied to one side only it
would have been the resolution bug again. S3.17.

Thresholds here are fitted and scored on the same points. Balanced accuracy
is therefore optimistic and is reported as a descriptive separation, not a
validated classifier.

Usage:
    python -I scripts/selectivity_contrast.py
    python -I scripts/selectivity_contrast.py --max-resolution 2.0
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np                                         # noqa: E402
import pandas as pd                                        # noqa: E402

LN_TABLE = ROOT / "data" / "lanthanide_sites.parquet"
CA_TABLE = ROOT / "data" / "calcium_sites.parquet"

COUNTERPARTS = ROOT / "data" / "calcium_counterparts.json"

# Which way each descriptor should move for a lanthanide-selective site, set
# from coordination chemistry BEFORE the test and not from the result: Ln3+
# is larger than Ca2+ so it takes a higher coordination number at longer
# donor distances, and carries more charge so it pulls in more anionic
# donors and buries itself more. +1 means "higher in Ln", -1 "lower in Ln".
# Fixing the direction is what licenses the one-sided test.
DIRECTION = {
    "coordination_number": +1, "protein_donor_count": +1,
    "bidentate_carboxylates": +1, "carboxylate_residues": +1,
    "protein_atoms_within_8A": +1, "mean_donor_distance_A": +1,
    "net_charge": -1, "shell_net_charge": -1, "metal_sasa_A2": -1,
}
DESCRIPTORS = list(DIRECTION)

# Hard-coded rather than inferred from the title, because the point of the
# table is to show how few independent observations there are, and a rule
# that silently mislabels one would hide exactly that.
#
# LanD (landiscernin) is the third family and was found late: the title
# keywords missed it, and its site sits on a C2 dimer axis, so the
# asymmetric unit showed CN 5 and SASA 47.9 and it read as adventitious
# surface binding. From the assembly it is CN 10, net charge -6, SASA 0.0 --
# the most anionic site in the corpus. S3.17.
FAMILIES = {
    "4MAE": "MDH/XoxF", "6DAM": "MDH/XoxF", "6FKW": "MDH/XoxF",
    "6OC5": "MDH/XoxF", "6OC6": "MDH/XoxF", "6ZCV": "MDH/XoxF",
    "6ZCW": "MDH/XoxF", "7O6Z": "MDH/XoxF",
    "6MI5": "lanmodulin", "8DQ2": "lanmodulin", "8FNR": "lanmodulin",
    "8FNS": "lanmodulin", "9PI2": "lanmodulin",
    "9C8X": "LanD", "9C8Y": "LanD", "9C8Z": "LanD", "9C90": "LanD",
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
    """Two-sided, on the difference of medians. Entry level only.

    Kept for the entry-level table, where n is large enough for it to behave.
    It is the wrong test at n=3 -- see exact_rank_p and the module docstring.
    """
    observed = abs(np.median(x) - np.median(y))
    pool = np.concatenate([x, y])
    cut, hits = len(x), 0
    for _ in range(rounds):
        rng.shuffle(pool)
        if abs(np.median(pool[:cut]) - np.median(pool[cut:])) >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (rounds + 1)


def exact_rank_p(x: np.ndarray, y: np.ndarray, sense: int) -> float:
    """Exact one-sided rank-sum p: how often could so few of the pooled
    units outrank the Ln group by chance.

    The null is enumerated rather than sampled. With three families against
    fifty-odd accessions that is C(58,3) = 30856 assignments, which is
    cheaper than a permutation loop and has no sampling error -- and at this
    n the sampling error is the difference between 3e-5 and "p < 0.05".
    Ties take average ranks, so two families on the same value cannot
    manufacture separation.
    """
    pool = np.concatenate([x, y]) * sense
    ranks = pd.Series(pool).rank().to_numpy()
    n = len(x)
    observed = ranks[:n].sum()
    total = hits = 0
    for combo in itertools.combinations(range(len(pool)), n):
        total += 1
        if ranks[list(combo)].sum() >= observed - 1e-9:
            hits += 1
    return hits / total


def overlap(x: np.ndarray, y: np.ndarray, sense: int) -> int:
    """How many comparison units reach the weakest Ln family.

    Quoted beside the p-value because it is the statement that survives a
    small n: "no calcium accession in this set reaches CN 9" is a claim
    about separation, where a p-value at n=3 is mostly a claim about n.
    """
    return int((y * sense >= (x * sense).min()).sum())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ln-table", type=Path, default=LN_TABLE)
    parser.add_argument("--ca-table", type=Path, default=CA_TABLE)
    parser.add_argument("--counterparts", type=Path, default=COUNTERPARTS,
                        help="JSON mapping Ca entries to UniProt accessions, "
                             "used to collapse the Ca side to one unit per protein")
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
    # Printed, not assumed: an asymmetric correction is the same class of
    # error as an asymmetric resolution filter, and it is invisible unless
    # the mix is stated.
    for name, frame in (("Ln", lanthanide), ("Ca", calcium)):
        if "coordinate_source" in frame.columns:
            mix = (frame.groupby("pdb_id")["coordinate_source"].first()
                   .value_counts().to_dict())
            print(f"  {name} coordinates: "
                  f"{', '.join(f'{k}={v}' for k, v in sorted(mix.items()))}")
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

    # The honest level. Lanthanides collapse to the family; calcium has no
    # family label, so it collapses to UniProt accession, which is the
    # nearest equivalent the counterpart search already recorded.
    unlabelled = sorted(set(lanthanide["pdb_id"]) - set(FAMILIES))
    if unlabelled:
        print(f"\n!! {len(unlabelled)} Ln entries have no family label "
              f"({', '.join(unlabelled)}) -- add them to FAMILIES, they are "
              f"being dropped from the family-level test")
    by_family = lanthanide.assign(group=lanthanide["pdb_id"].map(FAMILIES))
    by_family = by_family[by_family["group"].notna()]

    accession = {}
    if args.counterparts.exists():
        for pdb_id, record in json.loads(
                args.counterparts.read_text())["entries"].items():
            got = record.get("accessions") or []
            accession[pdb_id] = got[0] if got else pdb_id
    by_accession = calcium.assign(
        group=calcium["pdb_id"].map(lambda p: accession.get(p, p)))

    fam_ln = by_family.groupby("group")[columns].median()
    fam_ca = by_accession.groupby("group")[columns].median()
    print(f"\nFAMILY level -- {len(fam_ln)} Ln families vs {len(fam_ca)} Ca "
          f"accessions. THIS IS THE ONE TO QUOTE.")
    print(f"  exact one-sided rank test, enumerating all "
          f"C({len(fam_ln) + len(fam_ca)},{len(fam_ln)}) assignments")
    print(f"  {'descriptor':26s} {'Ln':>7s} {'Ca':>7s} "
          f"{'Ca units reaching it':>21s}  exact p")
    separating = []
    for column in columns:
        x = fam_ln[column].dropna().to_numpy(dtype=float)
        y = fam_ca[column].dropna().to_numpy(dtype=float)
        if len(x) < 2 or len(y) < 2:
            continue
        sense = DIRECTION[column]
        p = exact_rank_p(x, y, sense)
        reach = overlap(x, y, sense)
        if p < 0.05:
            separating.append((column, reach, p))
        print(f"  {column:26s} {np.median(x):7.2f} {np.median(y):7.2f} "
              f"{reach:>10d} / {len(y):<8d}  {p:.5f}"
              f"{'' if p < 0.05 else '   (n.s.)'}")

    print("\nper family:")
    print(fam_ln.to_string(float_format=lambda v: f"{v:.2f}"))

    clean = [c for c, reach, _ in separating if reach == 0]
    print(f"\nseparating at p<0.05 on {len(fam_ln)} families: "
          f"{', '.join(c for c, _, _ in separating) if separating else 'none'}")
    print(f"separating with NO overlap at all: "
          f"{', '.join(clean) if clean else 'none'}")
    print("a p-value at n=3 is mostly a statement about n; the overlap count "
          "is the one that survives.")
    print("thresholds are fitted and scored on the same points; treat the "
          "balanced accuracies as descriptive, not validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
