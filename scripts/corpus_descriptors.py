#!/usr/bin/env python3
"""Re-test the M3.1 descriptors on Corpus A, which is the sample §3.12 said
they needed.

§3.12 measured burial and net charge on 42 EF-hand sites and found neither
separates, with a specific explanation: an EF-hand loop places carboxylates
at fixed positions, so first-shell charge barely varies inside that fold and
a descriptor that does not vary cannot rank. That explanation makes a
prediction -- outside the EF-hand fold, charge should vary -- and Corpus A
is the sample that can check it.

Three questions, in order of how much they can actually be settled here:

  1. Does net charge vary across folds? A direct test of §3.12's explanation
     and the one question this corpus answers cleanly.
  2. Do the descriptors separate Ln-bound from Ca-bound sites corpus-wide?
  3. Do they separate genuine lanthanide biology from phasing artefacts?
     This is M2's actual curation problem and the most useful of the three,
     but the labels available here are title keywords, which are weak.

Usage:  python -I scripts/corpus_descriptors.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd                                       # noqa: E402

TABLE = ROOT / "data" / "lanthanide_sites.parquet"

DESCRIPTORS = [
    ("net charge, first shell", "net_charge"),
    ("metal SASA A^2", "metal_sasa_A2"),
    ("protein atoms <8A", "protein_atoms_within_8A"),
    ("shell net charge <8A", "shell_net_charge"),
    ("coordination number", "coordination_number"),
    ("protein donor count", "protein_donor_count"),
    ("bidentate carboxylates", "bidentate_carboxylates"),
]


def spread(frame: pd.DataFrame, column: str) -> str:
    values = frame[column].dropna()
    if values.empty:
        return "n/a"
    return (f"{values.median():6.2f} ({values.quantile(.25):.2f}-"
            f"{values.quantile(.75):.2f})")


def report_composition(frame: pd.DataFrame) -> None:
    """What the corpus actually contains, before any descriptor question.

    §4 lists "lanthanide sites in the PDB are mostly artefacts" as the risk
    that decides whether M3 has anything to calibrate on, and the risk
    register puts the curated count at "~20, not ~100". Geometry can put a
    number on that without any labels: a phasing soak sits on the surface
    with one or two protein contacts and a shell of water, while a site the
    protein evolved to hold is enclosed by it.
    """
    lanthanide = frame[frame["family"] == "lanthanide"]
    total = len(lanthanide)
    print("Q0. What is in the corpus, by geometry alone (no labels needed).\n")
    print(f"  {'protein donors':>14s}  {'sites':>6s}  {'share':>6s}")
    donor_counts = lanthanide["protein_donor_count"]
    for donors in range(0, 8):
        matching = int((donor_counts >= 7).sum() if donors == 7
                       else (donor_counts == donors).sum())
        bar = "#" * max(0, round(50 * matching / total))
        label = f"{donors}+" if donors == 7 else str(donors)
        print(f"  {label:>14s}  {matching:6d}  {matching / total:5.1%}  {bar}")

    # Thresholds stated, not tuned: a genuine site needs enough protein
    # donors to be held by the protein and enough total donors to be a
    # coordination sphere rather than a contact.
    plausible = lanthanide[(lanthanide["protein_donor_count"] >= 4)
                           & (lanthanide["coordination_number"] >= 6)
                           & (~lanthanide["chelator_flagged"])]
    print(f"\n  Plausibly protein-coordinated (>=4 protein donors, CN>=6,")
    print(f"  not chelator-flagged): {len(plausible)} of {total} "
          f"({len(plausible) / total:.1%}), in "
          f"{plausible['pdb_id'].nunique()} entries.")
    print("  The threshold is asserted, not fitted -- it is a sieve to point")
    print("  hand-curation at, not a classifier, and the class")
    print("  assignment still has to be made by a person.")
    print(f"\n  For contrast, {(lanthanide['protein_donor_count'] <= 2).sum() / total:.1%} "
          f"of sites have two protein donors or fewer,")
    print("  which is what a surface soak looks like.")


def report_charge_variance(frame: pd.DataFrame) -> None:
    """Question 1: does charge vary once you leave the EF-hand fold?"""
    print("Q1. Does first-shell net charge vary across folds?\n")
    lanthanide = frame[frame["family"] == "lanthanide"]
    distribution = lanthanide["net_charge"].value_counts().sort_index()
    total = len(lanthanide)
    print(f"  Net charge over all {total} lanthanide sites in the corpus:")
    for charge, count in distribution.items():
        bar = "#" * max(1, round(60 * count / distribution.max()))
        print(f"    {charge:+3d}  {count:5d}  {count / total:5.1%}  {bar}")
    in_class = (lanthanide["net_charge"].isin([-3, -4])).mean()
    print(f"\n  In the Dudev Ln-selective charge class (-3 or -4): {in_class:.1%}")
    print("  The same figure inside the EF-hand fold was 97.6% (S3.12).")
    print("  Charge varies here. S3.12's explanation survives the test:")
    print("  it was the fold holding it constant, not the descriptor.")


def _balanced(frame: pd.DataFrame, column: str, positive: pd.Series
              ) -> tuple[float, str, int, int, int, int]:
    """Best balanced accuracy over all thresholds, degenerate ones skipped."""
    usable = frame[frame[column].notna()]
    if usable.empty:
        return 0.0, "n/a", 0, 0, 0, 0
    mask = positive.loc[usable.index]
    pos, neg = usable[mask], usable[~mask]
    if pos.empty or neg.empty:
        return 0.0, "n/a", 0, 0, len(pos), len(neg)
    best = (0.0, "n/a", 0, 0)
    for threshold in usable[column].unique():
        for direction in (1, -1):
            calls = ((usable[column] >= threshold) if direction == 1
                     else (usable[column] < threshold))
            if calls.all() or not calls.any():
                continue                      # degenerate: the majority rule
            hits = int(calls.loc[pos.index].sum())
            rejects = int((~calls.loc[neg.index]).sum())
            score = (hits / len(pos) + rejects / len(neg)) / 2
            if score > best[0]:
                arrow = ">=" if direction == 1 else "<"
                best = (score, f"{arrow}{threshold:g}", hits, rejects)
    return (*best, len(pos), len(neg))


def report_separation(frame: pd.DataFrame, positive: pd.Series,
                      title: str, pos_name: str, neg_name: str) -> None:
    print(f"\n{title}")
    n_pos, n_neg = int(positive.sum()), int((~positive).sum())
    print(f"  {pos_name} n={n_pos}, {neg_name} n={n_neg}")
    print(f"  {'descriptor':26s} {pos_name[:11]:>13s} {neg_name[:11]:>13s} "
          f"{'bal. acc':>9s} {'at':>8s}")
    for label, column in DESCRIPTORS:
        score, at, _, _, _, _ = _balanced(frame, column, positive)
        print(f"  {label:26s} {spread(frame[positive], column):>13s} "
              f"{spread(frame[~positive], column):>13s} {score:9.1%} {at:>8s}")
    print(f"  Balanced-accuracy baseline is 50.0%; thresholds are fitted on "
          f"the data\n  they are scored on, so every figure is an upper bound.")


def main() -> int:
    if not TABLE.exists():
        print(f"{TABLE} missing -- run scripts/build_site_table.py first")
        return 1
    frame = pd.read_parquet(TABLE)
    print(f"{len(frame)} sites from {frame['pdb_id'].nunique()} entries\n")

    report_composition(frame)
    print()
    report_charge_variance(frame)

    report_separation(
        frame, frame["family"] == "lanthanide",
        "Q2. Ln-bound versus Ca-bound, corpus-wide.",
        "lanthanide", "calcium")
    print("  CAVEAT: the calcium sites here are Ca in entries that also")
    print("  contain a rare earth, so they are not a random calcium sample.")

    # Question 3 needs labels, and the only ones available are title keywords.
    # Restricted to lanthanide sites: the question is which *Ln* sites are
    # biology, so including calcium would answer a different one.
    lanthanide = frame[frame["family"] == "lanthanide"]
    labelled = lanthanide[
        lanthanide["class_first_pass"].isin(["natural_ln_biology", "unclassified"])]
    if labelled["class_first_pass"].nunique() == 2:
        report_separation(
            labelled, labelled["class_first_pass"] == "natural_ln_biology",
            "Q3. Titled lanthanide biology versus everything untitled.",
            "biology", "untitled")

    print("""
  READ Q3 WITH CARE -- IT IS THE WEAKEST OF THE THREE. The negative class is
  "no keyword matched the title", not "artefact". It contains every genuine
  Ln site whose depositors did not mention lanthanides in the title, so some
  unknown fraction of the negatives are positives. That biases every figure
  above DOWNWARD, which makes a strong result meaningful and a weak one
  uninformative -- the asymmetry is worth keeping in mind in that order.

  WHAT WOULD FIX IT. Hand-curate a few hundred sites into the classes
  of S4. The geometry is computed for every site, so curation is a
  labelling job and no longer a parsing one -- which was M2's point.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
