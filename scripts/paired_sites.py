#!/usr/bin/env python3
"""The matched Ca2+ contrast: the same site holding a lanthanide and a calcium.

WHY THIS AND NOT THE OBVIOUS COMPARISON. The corpus holds 2570 lanthanide and
225 calcium sites, and comparing those two piles directly is a trap that S3.13
Q2 measured: the lanthanides come out *more solvent-exposed* than the calciums
(median SASA 68.3 vs 1.7 A^2) with *fewer* protein atoms around them. That is
not chemistry. Most corpus lanthanides are soaked into a crystal grown without
them, most corpus calciums are structural ions the protein folded around, and
the comparison measures provenance. Any descriptor calibrated on it learns the
soak and inverts the real preference.

The fix is to control for the fold. A *site signature* is the set of protein
residues coordinating the ion with the chain dropped -- "ASP20;ASP22;ASP24;
THR26;GLU31" is an EF-hand loop whichever chain and whichever entry it sits
in. Two sites sharing a signature are the same site; if one holds a lanthanide
and the other a calcium, the difference between them is the ion, because the
protein is held fixed.

WHAT SUCH A PAIR CAN AND CANNOT TELL YOU. Same signature means the same
residues, so the charge descriptors are near-identical *by construction* --
net charge cannot discriminate inside a pair, and should not be expected to.
S3.13 reached that from the other direction (net charge scores 94% at telling
a real site from an artefact and 75% at telling which ion a real site prefers)
and this is the same fact seen in a mirror. What is free to vary is geometry:
Ln3+ is smaller and more charge-dense than Ca2+ and pulls carboxylates into
bidentate contact, so the testable prediction is higher coordination number
and more bidentate carboxylates on the lanthanide side of a pair.

TIERS, strongest first, because they do not control for the same things:
  within-entry   same deposition, same signature, different ion -- usually NCS
                 copies refined with different ions. Controls for crystal,
                 resolution and refinement protocol as well as fold.
  cross-entry    same signature in two depositions. Controls for fold only;
                 resolution and refinement differ and that moves geometry on
                 its own. Titles are printed so a curator can confirm the two
                 entries really are the same protein rather than a numbering
                 coincidence.

THE LIMIT, STATED UP FRONT. Corpus A is "entries containing a rare earth", so
every calcium here is a calcium that happens to sit in a rare-earth structure.
A fully matched set needs the Ca-only depositions of these same proteins,
which are not in this corpus and have to be fetched by UniProt accession. This
script measures what the current corpus supports and prints the shortfall.

Usage:
    python -I scripts/paired_sites.py
    python -I scripts/paired_sites.py --min-donors 3 --out data/paired_sites.csv
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd                                        # noqa: E402

DEFAULT_TABLE = ROOT / "data" / "lanthanide_sites.parquet"

# Descriptors compared across a pair. Geometry first because that is what a
# matched pair is able to move; the charge columns are kept precisely to show
# that they do *not* move, which is the control that makes the rest readable.
COMPARED = [
    "coordination_number",
    "protein_donor_count",
    "water_donor_count",
    "bidentate_carboxylates",
    "monodentate_carboxylates",
    "mean_donor_distance_A",
    "net_charge",
    "carboxylate_residues",
]


def load(path: Path, min_donors: int, min_residues: int) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if "site_signature" not in frame.columns:
        raise SystemExit(
            f"{path} has no site_signature column -- rebuild it with "
            "scripts/build_site_table.py")
    # A site with no protein donors has an empty signature and would "match"
    # every other such site, which would be 757 sites of pure noise.
    kept = frame[frame["site_signature"].str.len() > 0].copy()
    kept["signature_residues"] = kept["site_signature"].str.count(";") + 1
    kept = kept[kept["protein_donor_count"] >= min_donors]
    # Residues, not donor atoms, are what make a signature specific, and the
    # two come apart: one bidentate carboxylate is two donors from a single
    # residue, so a --min-donors of 2 still admits "GLU113". A one-residue
    # signature is not a site, it is a string that many unrelated sites
    # share -- the first run of this matched GLU113 across 2V15, 4LL7, 6FRM
    # and 6FRN and called it a pair.
    return kept[kept["signature_residues"] >= min_residues]


def pair_table(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Median descriptor per (key..., family), for signatures holding both."""
    families = frame.groupby(keys)["family"].nunique()
    both = families[families > 1].index
    if not len(both):
        return pd.DataFrame()
    subset = frame.set_index(keys).loc[both].reset_index()
    numeric = [c for c in COMPARED if c in subset.columns]
    # Median across NCS copies: a signature can occur eight times in one entry
    # and the mean would let one badly-refined copy carry the pair.
    grouped = subset.groupby(keys + ["family"]).agg(
        copies=("metal", "size"),
        metals=("metal", lambda s: ",".join(sorted(set(s)))),
        **{c: (c, "median") for c in numeric})
    return grouped.reset_index()


def deltas(paired: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """One row per pair: lanthanide value, calcium value, and the difference."""
    if not len(paired):
        return pd.DataFrame()
    wide = paired.pivot_table(index=keys, columns="family", aggfunc="first")
    rows = []
    for key, record in wide.iterrows():
        entry = {k: v for k, v in zip(keys, key if isinstance(key, tuple) else (key,))}
        entry["ln_copies"] = record.get(("copies", "lanthanide"))
        entry["ca_copies"] = record.get(("copies", "calcium"))
        entry["metals"] = record.get(("metals", "lanthanide"))
        for column in COMPARED:
            if (column, "lanthanide") not in record.index:
                continue
            ln, ca = record[(column, "lanthanide")], record[(column, "calcium")]
            entry[f"{column}_ln"] = ln
            entry[f"{column}_ca"] = ca
            entry[f"{column}_delta"] = (
                ln - ca if pd.notna(ln) and pd.notna(ca) else None)
        rows.append(entry)
    return pd.DataFrame(rows)


def report(name: str, table: pd.DataFrame) -> None:
    if not len(table):
        print(f"\n{name}: none found")
        return
    print(f"\n{name}: {len(table)} matched signatures")
    print("  descriptor                  Ln median   Ca median   delta   "
          "Ln>Ca / n")
    for column in COMPARED:
        delta = f"{column}_delta"
        if delta not in table.columns:
            continue
        values = table[delta].dropna()
        if not len(values):
            continue
        higher = int((values > 0).sum())
        lower = int((values < 0).sum())
        print(f"  {column:26s} {table[f'{column}_ln'].median():9.2f} "
              f"{table[f'{column}_ca'].median():11.2f} "
              f"{values.median():7.2f}   {higher:3d} / {higher + lower}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--min-donors", type=int, default=2,
                        help="skip sites with fewer protein donor atoms")
    parser.add_argument("--min-residues", type=int, default=3,
                        help="skip signatures with fewer distinct residues; "
                             "one or two residues match by coincidence")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    frame = load(args.table, args.min_donors, args.min_residues)
    print(f"{len(frame)} sites with >= {args.min_residues} signature "
          f"residues and >= {args.min_donors} protein donors, from "
          f"{frame['pdb_id'].nunique()} entries "
          f"({(frame['family'] == 'calcium').sum()} calcium)")

    within = deltas(pair_table(frame, ["pdb_id", "site_signature"]),
                    ["pdb_id", "site_signature"])
    report("WITHIN-ENTRY (same deposition, same site, different ion)", within)
    if len(within):
        print("\n  the pairs:")
        for _, row in within.sort_values("pdb_id").iterrows():
            print(f"    {row['pdb_id']}  {row['metals']:6s} "
                  f"Ln x{int(row['ln_copies'])} Ca x{int(row['ca_copies'])}  "
                  f"CN {row['coordination_number_ln']:.0f}/"
                  f"{row['coordination_number_ca']:.0f}  "
                  f"{row['site_signature'][:52]}")

    cross = deltas(pair_table(frame, ["site_signature"]), ["site_signature"])
    report("CROSS-ENTRY (same signature, any deposition)", cross)
    if len(cross):
        print("\n  top signatures by copy count (confirm these are the same "
              "protein before using them):")
        listed = cross.sort_values("ln_copies", ascending=False).head(12)
        for _, row in listed.iterrows():
            entries = sorted(set(
                frame[frame["site_signature"] == row["site_signature"]]["pdb_id"]))
            print(f"    {row['site_signature'][:46]:46s} "
                  f"Ln x{int(row['ln_copies']):3d} Ca x{int(row['ca_copies']):3d}  "
                  f"{len(entries)} entries: {','.join(entries[:4])}"
                  f"{' ...' if len(entries) > 4 else ''}")

    if args.out and len(cross):
        args.out.parent.mkdir(parents=True, exist_ok=True)
        cross.to_csv(args.out, index=False)
        shown = (args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT)
                 else args.out)
        print(f"\nwrote {len(cross)} cross-entry pairs -> {shown}")

    # The shortfall, stated in numbers rather than left for the reader to
    # discover: how many lanthanide sites got no calcium partner at all.
    matched = set(cross["site_signature"]) if len(cross) else set()
    lanthanide = frame[frame["family"] == "lanthanide"]
    unmatched = lanthanide[~lanthanide["site_signature"].isin(matched)]
    print(f"\n{len(unmatched)} of {len(lanthanide)} lanthanide sites have no "
          f"calcium partner in this corpus "
          f"({len(unmatched) / max(len(lanthanide), 1):.1%}). Closing that "
          "needs Ca-only depositions of the same proteins, which Corpus A "
          "does not contain by construction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
