#!/usr/bin/env python3
"""Which entries are parsed with half a metal site, because the deposited
asymmetric unit is smaller than the biological assembly.

THE BUG THIS EXISTS TO FIND. A metal sitting on a crystallographic symmetry
axis is coordinated by residues from two or more protomers, but only one of
them is in the deposited coordinates. Parsing the asymmetric unit then finds
half the coordination sphere, and *every* descriptor moves at once, all in
the direction that makes a real site look like an adventitious one.

Measured on 9C8X (landiscernin, a lanthanide chaperone whose site lies on a
C2 dimer axis):

    descriptor              ASU     assembly
    coordination_number       5           10
    carboxylate_residues      3            6     GLU70/73/75 from both chains
    bidentate_carboxylates    1            2
    net_charge               -3           -6
    metal_sasa_A2         47.94         0.00     "surface" site is buried

Every one of those is wrong in the ASU, and the entry looked like junk.

WHAT THIS SCRIPT DOES. Nothing but metadata: for each entry it records the
number of polymer chains deposited and the largest number in any biological
assembly. An entry where the second exceeds the first *may* have a truncated
site -- only re-parsing the assembly shows whether any metal actually sits on
the interface. The audit is kept separate from the download so the cheap
question (how many entries are at risk) can be answered without fetching a
few hundred megabytes to answer it.

Usage:
    python -I scripts/assembly_audit.py
    python -I scripts/assembly_audit.py --enumeration data/calcium_counterparts.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests                                           # noqa: E402

GRAPHQL = "https://data.rcsb.org/graphql"
DEFAULT_OUT = ROOT / "data" / "assembly_counts.json"
ENUMERATIONS = [ROOT / "data" / "ree_pdb_entries.json",
                ROOT / "data" / "calcium_counterparts.json"]
BATCH = 50
TIMEOUT = 90

QUERY = """query($ids:[String!]!){ entries(entry_ids:$ids){ rcsb_id
  rcsb_entry_info{deposited_polymer_entity_instance_count}
  assemblies{rcsb_assembly_info{polymer_entity_instance_count}} } }"""


def counts_for(ids: list[str]) -> dict[str, dict]:
    """{pdb_id: {asu, assembly}} -- chains deposited vs chains in the
    largest biological assembly."""
    out = {}
    for start in range(0, len(ids), BATCH):
        batch = ids[start:start + BATCH]
        response = requests.post(GRAPHQL, timeout=TIMEOUT,
                                 json={"query": QUERY, "variables": {"ids": batch}})
        response.raise_for_status()
        for entry in response.json()["data"]["entries"] or []:
            asu = entry["rcsb_entry_info"]["deposited_polymer_entity_instance_count"] or 0
            sizes = [a["rcsb_assembly_info"]["polymer_entity_instance_count"] or 0
                     for a in (entry["assemblies"] or [])]
            # The largest assembly, not assembly 1: a deposition may list a
            # monomer first and the functional dimer second. Taking the max
            # over-collects rather than under-collects, and re-parsing is
            # what decides whether a site actually gained donors.
            out[entry["rcsb_id"]] = {"asu": asu, "assembly": max(sizes, default=asu)}
        print(f"  {min(start + BATCH, len(ids))}/{len(ids)}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enumeration", type=Path, action="append",
                        help="JSON with an 'entries' mapping (repeatable); "
                             "defaults to Corpus A plus the Ca counterparts")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    sources = args.enumeration or [p for p in ENUMERATIONS if p.exists()]
    ids = sorted({i for s in sources
                  for i in json.loads(s.read_text())["entries"]})
    print(f"{len(ids)} entries from {', '.join(s.name for s in sources)}")

    counts = counts_for(ids)
    expanded = sorted(p for p, v in counts.items() if v["assembly"] > v["asu"])
    payload = {
        "_provenance": {
            "source": GRAPHQL,
            "retrieved": time.strftime("%Y-%m-%d"),
            "enumerations": [str(s.relative_to(ROOT)) for s in sources],
            "meaning": "asu = polymer chains in the deposited coordinates; "
                       "assembly = chains in the largest biological assembly",
            "curation_status": "uncurated -- assembly > asu flags an entry as "
                               "AT RISK of a truncated metal site, it does not "
                               "show that any site is truncated. Re-parsing the "
                               "assembly is what decides that.",
        },
        "counts": {"entries": len(counts), "expanded": len(expanded)},
        "expanded": expanded,
        "entries": dict(sorted(counts.items())),
    }
    args.out.write_text(json.dumps(payload, indent=2))

    print(f"\n{len(expanded)}/{len(counts)} entries "
          f"({100 * len(expanded) / max(len(counts), 1):.1f}%) have "
          f"assembly > ASU and may hold a truncated site")
    print(f"wrote {args.out.relative_to(ROOT)}")
    print("\nnext: fetch those assemblies into their own empty directory\n"
          "  python -I scripts/download_corpus.py --assembly \\\n"
          "      --enumeration data/assembly_counts.json --out .cache/assembly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
