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

The hand-check needed six: reading the shortlist turned up a lanthanide in a
native site for a metal that is not calcium (Fe3+ in lactoferrin, Mg2+ in
EcoRV) and a lanthanide-binding DNA aptamer, neither of which the four can
name. The class list lives in `data/curation_verdicts.json`, not here -- this
file applies whatever classes that file declares and never invents one.

It is a *hint*, not a classification, and the honest limit is specific: a
title cannot tell a phasing derivative from genuine biology. "STRUCTURE OF X"
is the commonest title in the corpus and says nothing. The geometric evidence
that actually separates those two -- coordination number, protein donor
count, bidentate carboxylates, whether the first shell is mostly buffer --
is carried in its own columns, unmixed with the title guess, so hand curation
can weigh them independently. Any row whose basis is `title:none` is
unclassified and should be read as such.

HAND CURATION OVERRIDES THE TITLE PASS. `data/curation_verdicts.json` holds
the verdicts reached by reading entries one at a time, and they are applied
here, after the keyword rules and winning over them. The basis then reads
`curated:<reason>` instead of `title:<keyword>`, so which labels are machine
guesses and which are human judgements stays legible in the table itself.

The title pass earned this the hard way. The fourth natural lanthanide family
(ROADMAP 3.19, seven entries of a wild-type tandem-PepSY protein) is titled
"Structure of MIF binding with Ytterbium ions" and contains no keyword at
all, so it sat in the unclassified pile while the geometric score was being
derived without it -- and when it was added, it removed one of the score's
two criteria. The rule is not fixable by adding keywords: a title is written
by a depositor who was not thinking about this question.

The verdicts file carries the evidence, not just the label, and for
`natural_ln_biology` that evidence is deliberately non-geometric (construct
provenance, mutation record, citation). Promoting an entry into the positive
class *because of its coordination number* and then measuring coordination
number on the positive class would be circular.

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

from lantern.structure import (ALL_METAL_CODES,         # noqa: E402
                                 REE_LIGAND_CODES, WATER_RESNAMES,
                                 binding_neighborhood)

CORPUS = ROOT / ".cache" / "corpus"
ASSEMBLY_DIR = ROOT / ".cache" / "assembly"
ENUMERATION = ROOT / "data" / "ree_pdb_entries.json"
VERDICTS = ROOT / "data" / "curation_verdicts.json"
DEFAULT_OUT = ROOT / "data" / "lanthanide_sites.parquet"

# Title keywords, lowercase, first match wins in this order. Ordered most
# specific first: "lanthanide-binding tag" must beat "calmodulin" for a
# construct that is an LBT fused to calmodulin.
TITLE_RULES = [
    ("engineered_lbt", ("lanthanide-binding tag", "lanthanide binding tag",
                        "lanthanide-binding peptide", "lanthanide binding motif",
                        "lanthanoid tagging", "artificial metalloprotein",
                        "clanp", "de novo", "designed protein", "designed coiled",
                        "computational design")),
    # "lanm", not "lanmodulin": 9PI2 is titled "Ancylobacter lacus LanM" and
    # the longer keyword silently dropped a known lanmodulin into the
    # unclassified pile. Checked against all 636 titles -- the five that
    # contain "lanm" are all lanmodulins, so the shorter key costs nothing.
    # "methylo", not "methylotroph": the four LanD entries (9C8X/Y/Z/90) are
    # titled "Methylorubrum extorquens ...-bound LanD" and the longer keyword
    # matched none of them, so a third natural family sat unclassified. LanD
    # is landiscernin, the lanthanide chaperone of PNAS 2024 (PMID 39467132),
    # and a pointed omission: its published function is separating light
    # lanthanides from each other, which is the selectivity this project is
    # looking for. Checked against all 808 titles -- the eight containing
    # "methylo" are XoxF, lanmodulin and LanD, all genuine. The residual risk
    # is an unrelated Methylobacterium protein soaked with a lanthanide for
    # phasing; none is in the corpus today, and the hand curation is where
    # that would be caught.
    #
    # NOT "land", though it is the name in the title: it also matches
    # "Ignicoccus islandicus" (6QSS, a malate dehydrogenase co-crystallised
    # with Tb-Xo4), which is a phasing experiment and not lanthanide biology.
    # "methylo" already catches all four LanD entries, so the substring buys
    # nothing and costs a false positive.
    ("natural_ln_biology", ("lanm", "landiscernin", "methanol dehydrogenase",
                            "xoxf", "methylo", "lanthanide-dependent",
                            "lanthanide chaperone", "pyrroloquinoline")),
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


def load_verdicts(path: Path) -> dict[str, tuple[str, str]]:
    """{PDB_ID: (class, basis)} from the hand-curation file.

    Missing file is not an error -- the table is still buildable from the
    title pass alone, it just reverts to what 3.19 was working with. A
    duplicate entry *is* an error: two verdicts for one deposition means two
    curators disagreed, and silently keeping the last one read is how a
    disagreement becomes invisible.
    """
    if not path.is_file():
        print(f"no curation verdicts at {path} -- title pass only")
        return {}
    document = json.loads(path.read_text())
    verdicts: dict[str, tuple[str, str]] = {}
    for group in document.get("groups", []):
        label, basis = group["class"], group["basis"]
        for pdb_id in group["entries"]:
            pdb_id = pdb_id.upper()
            if pdb_id in verdicts and verdicts[pdb_id] != (label, basis):
                raise SystemExit(
                    f"{path.name}: {pdb_id} has two different verdicts, "
                    f"{verdicts[pdb_id]} and {(label, basis)}")
            verdicts[pdb_id] = (label, basis)
    return verdicts


def site_rows(pdb_id: str, text: str, meta: dict,
              coordinate_source: str = "asu",
              verdict: tuple[str, str] | None = None) -> list[dict]:
    """One flat row per metal site in one entry."""
    sites = binding_neighborhood(text, "cif", metals=ALL_METAL_CODES)
    label, basis = verdict or title_first_pass(meta.get("title", ""))
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
            # Carried per site rather than looked up later because every
            # geometric column above is resolution-dependent, and the matched
            # Ca contrast proved that a filter applied to one side only
            # manufactures a difference: the Ln sides ran 0.17 A worse than
            # their Ca partners, which on its own produced a +0.08 A donor
            # distance "effect" that vanished once both sides were held to
            # the same cutoff. None for NMR and EM, which have no resolution
            # in this sense and whose distances come from restraints.
            "resolution_A": meta.get("resolution_A"),
            "method": meta.get("method", ""),
            "title": meta.get("title", ""),
            # "asu" or "assembly1". Not cosmetic: a site parsed from the ASU
            # when its partner protomer is missing is wrong in every
            # geometric column, so any contrast that mixes the two sources
            # unevenly between its arms is confounded by this.
            "coordinate_source": coordinate_source,
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
    # A metal on a symmetry axis is coordinated by two protomers, and the
    # deposited asymmetric unit holds one of them. Parsing the ASU then finds
    # half the site and moves every descriptor at once: 9C8X (landiscernin)
    # read CN 5, charge -3, SASA 47.9 from the ASU and CN 10, charge -6,
    # SASA 0.0 from the dimer -- a buried, highly anionic lanthanide site
    # that the ASU made look like adventitious surface binding. Where an
    # assembly file is supplied it wins, and the row records which was used.
    parser.add_argument("--assembly-dir", type=Path, default=ASSEMBLY_DIR,
                        help="directory of {ID}-assembly1.cif.gz to prefer "
                             "over the deposited coordinates")
    parser.add_argument("--verdicts", type=Path, default=VERDICTS,
                        help="hand-curation verdicts, applied over the title "
                             "pass; pass a nonexistent path to build without them")
    args = parser.parse_args()

    enumeration = json.loads(args.enumeration.read_text())["entries"]
    verdicts = load_verdicts(args.verdicts)
    files = sorted(args.corpus.glob("*.cif.gz"))
    if args.limit:
        files = files[:args.limit]
    if not files:
        print(f"no .cif.gz under {args.corpus} -- run download_corpus.py first")
        return 1

    assemblies = {}
    if args.assembly_dir and args.assembly_dir.is_dir():
        assemblies = {p.name.removesuffix("-assembly1.cif.gz"): p
                      for p in args.assembly_dir.glob("*-assembly1.cif.gz")}
    print(f"parsing {len(files)} entries from {args.corpus}")
    if assemblies:
        covered = sum(1 for p in files
                      if p.name.removesuffix(".cif.gz") in assemblies)
        print(f"  {covered} of them from biological assemblies in "
              f"{args.assembly_dir}")

    rows, failures, started = [], [], time.time()
    with warnings.catch_warnings():
        # BioPython warns copiously about discontinuous chains and missing
        # elements across a corpus this size. Those are properties of the
        # depositions, not of this code, and the count is reported instead.
        warnings.simplefilter("ignore")
        for done, path in enumerate(files, start=1):
            pdb_id = path.name.removesuffix(".cif.gz")
            source = assemblies.get(pdb_id, path)
            try:
                text = gzip.open(source, "rt", errors="replace").read()
                rows += site_rows(pdb_id, text, enumeration.get(pdb_id, {}),
                                  "assembly1" if pdb_id in assemblies else "asu",
                                  verdicts.get(pdb_id.upper()))
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

    print("\n  class, title first pass (a hint) overridden by hand curation:")
    for label, count in frame["class_first_pass"].value_counts().items():
        curated = int((frame["class_basis"].str.startswith("curated:")
                       & (frame["class_first_pass"] == label)).sum())
        note = f"   ({curated} of them curated)" if curated else ""
        print(f"    {label:28s} {count:6d}{note}")
    if verdicts:
        seen = set(frame["pdb_id"].str.upper())
        applied = sorted(v for v in verdicts if v in seen)
        print(f"\n  curation verdicts: {len(applied)} of {len(verdicts)} "
              f"applied, from {args.verdicts.name}")
        # Only meaningful for the corpus the verdicts were written against;
        # on the calcium corpus every one of them is legitimately absent.
        if applied:
            for pdb_id in sorted(set(verdicts) - seen):
                print(f"    !! {pdb_id} has a verdict but is not in this corpus")
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
