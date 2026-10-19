#!/usr/bin/env python3
"""Extract every rare-earth and calcium site in Corpus A into one table.

This is M2's core asset: the download is not the deliverable, the per-site
measurement is. Input is `.cache/corpus/*.cif.gz` from `download_corpus.py`;
output is `data/lanthanide_sites.parquet` plus a printed summary.

WHAT IS AND IS NOT CLASSIFIED HERE. The roadmap asks for four classes --
natural Ln biology, Ln-substituted Ca site, engineered lanthanide-binding
tag, phasing/surface artefact -- "by deposition metadata and title text for a
first pass, then hand-check". The title pass is implemented and recorded as
`class_first_pass`, with `class_basis` naming the rule that fired, because a
label whose provenance is not recorded cannot be audited later.

It is a *hint*, not a classification, and the honest limit is specific: a
title cannot tell a phasing derivative from genuine biology. "STRUCTURE OF X"
is the commonest title in the corpus and says nothing. The geometric evidence
that actually separates those two -- coordination number, protein donor
count, bidentate carboxylates, whether the first shell is mostly buffer --
is carried in its own columns, unmixed with the title guess, so hand curation
can weigh them independently. Any row whose basis is `title:none` is
unclassified and should be read as such.

Usage:
    python -I scripts/build_site_table.py
    python -I scripts/build_site_table.py --limit 50 --out /tmp/sample.parquet
"""
import argparse
import gzip
import json
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd                                       # noqa: E402

from reefinder.structure import (ALL_METAL_CODES,         # noqa: E402
                                 REE_LIGAND_CODES, WATER_RESNAMES,
                                 binding_neighborhood)

CORPUS = ROOT / ".cache" / "corpus"
ENUMERATION = ROOT / "data" / "ree_pdb_entries.json"
DEFAULT_OUT = ROOT / "data" / "lanthanide_sites.parquet"

# Title keywords, lowercase, first match wins in this order. Ordered most
# specific first: "lanthanide-binding tag" must beat "calmodulin" for a
# construct that is an LBT fused to calmodulin.
TITLE_RULES = [
    ("engineered_lbt", ("lanthanide-binding tag", "lanthanide binding tag",
                        "de novo", "designed protein", "computational design")),
    # "lanm", not "lanmodulin": 9PI2 is titled "Ancylobacter lacus LanM" and
    # the longer keyword silently dropped a known lanmodulin into the
    # unclassified pile. Checked against all 636 titles -- the five that
    # contain "lanm" are all lanmodulins, so the shorter key costs nothing.
    ("natural_ln_biology", ("lanm", "methanol dehydrogenase", "xoxf",
                            "methylotroph", "lanthanide-dependent",
                            "pyrroloquinoline")),
    ("ln_substituted_ca", ("calmodulin", "troponin", "parvalbumin", "ef-hand",
                           "calbindin", "recoverin", "calcineurin",
                           "s100", "annexin", "synaptotagmin")),
]

# Metal-chelating co-solutes called out in the roadmap's component survey.
# Presence in the *first shell* is what matters, not presence in the entry.
KNOWN_CHELATORS = {
    "BTB": "bis-tris", "ACT": "acetate", "DO3": "DO3A macrocycle",
    "DOT": "DOTA", "PDC": "pyridine-2,6-dicarboxylate", "CIT": "citrate",
    "FLC": "citrate", "TLA": "L-tartrate", "EDT": "EDTA", "EDO": "ethylene glycol",
}


def title_first_pass(title: str) -> tuple[str, str]:
    """(class, basis). Returns ('unclassified', 'title:none') when nothing fires."""
    lowered = (title or "").lower()
    for label, keywords in TITLE_RULES:
        for keyword in keywords:
            if keyword in lowered:
                return label, f"title:{keyword}"
    return "unclassified", "title:none"


def site_rows(pdb_id: str, text: str, meta: dict) -> list[dict]:
    """One flat row per metal site in one entry."""
    sites = binding_neighborhood(text, "cif", metals=ALL_METAL_CODES)
    label, basis = title_first_pass(meta.get("title", ""))
    rows = []
    for site in sites:
        chemistry, charge, burial = site["chemistry"], site["charge"], site["burial"]
        is_ree = site["metal"].strip().upper() in REE_LIGAND_CODES

        # Identity of the non-water heteroatom groups in the first shell. This
        # is what distinguishes "a bare Gd the protein holds" from "a Gd the
        # DO3A cage holds, near a protein" -- the second contamination class,
        # which a bare-ion filter passes straight through.
        shell_ligands = sorted({
            d["residue"].strip().upper() for d in site["donors"]
            if d["kind"] == "ligand"
            and d["residue"].strip().upper() not in WATER_RESNAMES})
        coordination = site["coordination_number"] or 1

        # Which residues actually hold the ion, as CHAIN:RESNAME:NUMBER. Two
        # uses, and the second is the one that justifies the column. A curator
        # reading "ASP20;ASN22;ASP24;THR26;GLU31" can recognise an EF-hand
        # loop at a glance where "5 protein donors" tells them nothing. And
        # stripped of its chain this is a *site signature*: the same signature
        # appearing once with a lanthanide and once with a calcium is the
        # same site holding two different ions, which is the only contrast in
        # this corpus that controls for the fold (S3.13 Q2 is what happens
        # without that control). Sorted by chain then number so the string is
        # stable across runs and comparable across entries.
        protein_residues = sorted({
            (d["chain"].strip(), d["residue"].strip().upper(),
             int(d["residue_number"])) for d in site["donors"]
            if d["kind"] == "protein"}, key=lambda r: (r[0], r[2], r[1]))

        rows.append({
            "pdb_id": pdb_id,
            "metal": site["metal"].strip(),
            "element": site["element"],
            "family": "lanthanide" if is_ree else "calcium",
            "chain": site["chain"],
            "site": site["site"],
            "coordination_number": site["coordination_number"],
            "protein_donor_count": site["protein_donor_count"],
            "water_donor_count": site["water_donor_count"],
            "other_ligand_donor_count": site["other_ligand_donor_count"],
            "mean_donor_distance_A": site["mean_donor_distance_A"],
            "carboxylate_O": chemistry["carboxylate"],
            "carboxylate_residues": chemistry["carboxylate_residues"],
            "bidentate_carboxylates": chemistry["bidentate_carboxylates"],
            "monodentate_carboxylates": chemistry["monodentate_carboxylates"],
            "glu_carboxylate_O": chemistry["glu_carboxylate_O"],
            "asp_carboxylate_O": chemistry["asp_carboxylate_O"],
            "backbone_carbonyl": chemistry["backbone_carbonyl"],
            "sidechain_amide": chemistry["sidechain_amide"],
            "hydroxyl": chemistry["hydroxyl"],
            "net_charge": charge["net_charge"],
            "unassigned_donors": charge["unassigned_donors"],
            "metal_sasa_A2": burial["metal_sasa_A2"],
            "protein_atoms_within_8A": burial["protein_atoms_within_8A"],
            "shell_anionic_residues": burial["shell_anionic_residues"],
            "shell_cationic_residues": burial["shell_cationic_residues"],
            "shell_net_charge": burial["shell_net_charge"],
            # Chelator evidence, recorded rather than acted on. The roadmap's
            # rule is half the first shell; the ligand names are kept so a
            # curator can see *what* it was before trusting the flag.
            "chelator_flagged": site["other_ligand_donor_count"] >= coordination / 2,
            "first_shell_ligands": ",".join(shell_ligands),
            "first_shell_protein_residues": ";".join(
                f"{chain}:{name}:{number}" for chain, name, number
                in protein_residues),
            # The same string with the chain dropped, which is what makes two
            # NCS copies -- or the same protein in two depositions -- compare
            # equal. Kept as its own column rather than derived at read time
            # so that every consumer matches sites the same way. Ordered from
            # the (number, name) pairs rather than by re-parsing the joined
            # token: slicing a name off the front assumes every residue name
            # is three characters, which is true of the standard twenty and
            # not guaranteed of whatever a 636-entry corpus contains.
            "site_signature": ";".join(
                f"{name}{number}" for number, name in
                sorted({(number, name) for _, name, number
                        in protein_residues})),
            # Semicolon, not comma: "pyridine-2,6-dicarboxylate" has a comma
            # in its name, and a comma-joined column splits it into two
            # fictitious chelators on the way back out.
            "first_shell_known_chelators": ";".join(
                sorted({KNOWN_CHELATORS[x] for x in shell_ligands
                        if x in KNOWN_CHELATORS})),
            "class_first_pass": label,
            "class_basis": basis,
            "title": meta.get("title", ""),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None)
    # The matched-calcium corpus is a second set of entries with its own
    # manifest; without this it would parse fine but lose every title, and
    # the title is what the class first pass runs on.
    parser.add_argument("--enumeration", type=Path, default=ENUMERATION,
                        help="JSON with {'entries': {PDB_ID: {'title': ...}}}")
    args = parser.parse_args()

    enumeration = json.loads(args.enumeration.read_text())["entries"]
    files = sorted(args.corpus.glob("*.cif.gz"))
    if args.limit:
        files = files[:args.limit]
    if not files:
        print(f"no .cif.gz under {args.corpus} -- run download_corpus.py first")
        return 1
    print(f"parsing {len(files)} entries from {args.corpus}")

    rows, failures, started = [], [], time.time()
    with warnings.catch_warnings():
        # BioPython warns copiously about discontinuous chains and missing
        # elements across a corpus this size. Those are properties of the
        # depositions, not of this code, and the count is reported instead.
        warnings.simplefilter("ignore")
        for done, path in enumerate(files, start=1):
            pdb_id = path.name.removesuffix(".cif.gz")
            try:
                text = gzip.open(path, "rt", errors="replace").read()
                rows += site_rows(pdb_id, text, enumeration.get(pdb_id, {}))
            except Exception as error:                    # noqa: BLE001
                failures.append((pdb_id, f"{type(error).__name__}: {error}"))
            if done % 100 == 0 or done == len(files):
                print(f"  {done}/{len(files)}  {len(rows)} sites  "
                      f"({done / max(time.time() - started, 1e-9):.1f}/s)")

    frame = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.out, index=False)

    shown = (args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT)
             else args.out)
    print(f"\n{len(frame)} sites from {frame['pdb_id'].nunique()} entries "
          f"-> {shown} ({args.out.stat().st_size / 1e6:.1f} MB)")
    if failures:
        print(f"{len(failures)} entries failed to parse:")
        for pdb_id, error in failures[:10]:
            print(f"    {pdb_id}  {error[:70]}")

    lanthanide = frame[frame["family"] == "lanthanide"]
    print(f"\n  lanthanide sites {len(lanthanide)}, calcium sites "
          f"{len(frame) - len(lanthanide)}")
    print("\n  by element:")
    counts = lanthanide.groupby("element").agg(
        sites=("element", "size"), entries=("pdb_id", "nunique"))
    for element, row in counts.sort_values("sites", ascending=False).iterrows():
        print(f"    {element:3s} {row['sites']:5d} sites in {row['entries']:4d} entries")

    print("\n  title first pass (a hint, not a classification):")
    for label, count in frame["class_first_pass"].value_counts().items():
        print(f"    {label:22s} {count:6d}")
    flagged = frame["chelator_flagged"].sum()
    print(f"\n  chelator-flagged (first shell at least half non-protein "
          f"non-water): {flagged} ({flagged / max(len(frame), 1):.1%})")
    named = frame[frame["first_shell_known_chelators"] != ""]
    print(f"  with a *named* chelator in the first shell: {len(named)}")
    if len(named):
        exploded = named["first_shell_known_chelators"].str.split(";").explode()
        for name, count in exploded.value_counts().head(8).items():
            print(f"    {name:28s} {count:5d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
