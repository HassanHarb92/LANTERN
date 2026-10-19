#!/usr/bin/env python3
"""Enumerate every PDB entry containing a bare rare-earth ion.

The seed corpus for M2. The important design choice is in step 1: the set of
rare-earth chemical components is *discovered* by asking RCSB which components
have a lanthanide, Y or Sc in their formula, not by writing down the codes
someone remembers. The hand-written list that shipped first was missing Y1 --
a bare yttrium ion, chemically identical to YT3 -- and with it 19 entries, and
nothing in the pipeline could have noticed.

Each discovered component is then classified against reefinder.structure:
bare ions (REE_LIGAND_CODES) are queried for entries, pre-chelated reagents
(CHELATED_REE_CODES) are excluded with their reason recorded. A component in
neither table is a hard error -- that is the Y1 failure, and it should stop
the build rather than quietly shrink the corpus.

The output is explicitly uncurated: it contains phasing derivatives,
Ln-substituted calcium sites, engineered lanthanide-binding tags and genuine
Ln biology, all unlabelled. Separating those is M2's actual work.

Usage:  python scripts/build_ree_corpus.py [--out data/ree_pdb_entries.json]
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reefinder.structure import (CHELATED_REE_CODES,  # noqa: E402
                                 REE_LIGAND_CODES)

SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
GRAPHQL = "https://data.rcsb.org/graphql"

# IUPAC rare earths: the 15 lanthanides plus Sc and Y.
RARE_EARTHS = ["La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb",
               "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Sc", "Y"]


def _post(url: str, payload: dict) -> dict | None:
    r = requests.post(url, json=payload, timeout=120)
    if r.status_code == 204:          # RCSB says "no hits" with 204, not [].
        return None
    r.raise_for_status()
    return r.json()


def discover_components() -> dict[str, list[str]]:
    """Every chemical component whose formula contains a rare earth."""
    by_element: dict[str, list[str]] = {}
    for element in RARE_EARTHS:
        payload = {
            "query": {"type": "terminal", "service": "chemical",
                      "parameters": {"value": element, "type": "formula",
                                     "match_subset": True}},
            "return_type": "mol_definition",
            "request_options": {"return_all_hits": True},
        }
        data = _post(SEARCH, payload)
        by_element[element] = sorted(h["identifier"] for h in data["result_set"]) if data else []
        time.sleep(0.25)
    return by_element


def entries_for(code: str) -> set[str]:
    payload = {
        "query": {"type": "terminal", "service": "text",
                  "parameters": {
                      "attribute": "rcsb_nonpolymer_entity_container_identifiers"
                                   ".nonpolymer_comp_id",
                      "operator": "exact_match", "value": code}},
        "return_type": "entry",
        "request_options": {"return_all_hits": True},
    }
    data = _post(SEARCH, payload)
    return {h["identifier"] for h in data["result_set"]} if data else set()


def titles_for(ids: list[str]) -> dict[str, str]:
    """Entry titles, batched -- 600+ single REST calls would be rude."""
    out: dict[str, str] = {}
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        query = ('{entries(entry_ids:%s){rcsb_id struct{title}}}'
                 % json.dumps(chunk))
        r = requests.post(GRAPHQL, json={"query": query}, timeout=120)
        r.raise_for_status()
        for entry in r.json()["data"]["entries"] or []:
            out[entry["rcsb_id"]] = (entry.get("struct") or {}).get("title", "")
        time.sleep(0.25)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path,
                        default=ROOT / "data" / "ree_pdb_entries.json")
    args = parser.parse_args()

    print("1. discovering rare-earth chemical components ...")
    by_element = discover_components()
    discovered = sorted({c for codes in by_element.values() for c in codes})
    print(f"   {len(discovered)} components across "
          f"{sum(1 for e in by_element if by_element[e])} elements")

    unclassified = [c for c in discovered
                    if c not in REE_LIGAND_CODES and c not in CHELATED_REE_CODES]
    if unclassified:
        print(f"\nERROR: {len(unclassified)} component(s) in neither table: "
              f"{', '.join(unclassified)}")
        print("Classify each in reefinder/structure.py as a bare ion or a")
        print("pre-chelated reagent before rebuilding. Refusing to guess.")
        return 1

    print("\n2. querying entries for each bare-ion code ...")
    elements_of: dict[str, set[str]] = {}
    for code, element in sorted(REE_LIGAND_CODES.items()):
        hits = entries_for(code)
        for pdb_id in hits:
            elements_of.setdefault(pdb_id, set()).add(element)
        print(f"   {code:4s} -> {element:2s}  {len(hits):4d} entries")
        time.sleep(0.2)

    ids = sorted(elements_of)
    print(f"\n3. fetching titles for {len(ids)} entries ...")
    titles = titles_for(ids)

    payload = {
        "_provenance": {
            "description": "Complete enumeration of PDB entries containing at "
                           "least one bare rare-earth ion. Seed corpus for "
                           "ROADMAP.md milestone M2. NOT yet curated: contains "
                           "phasing derivatives, Ln-substituted Ca sites, "
                           "engineered lanthanide-binding tags, and genuine Ln "
                           "biology, all unlabelled.",
            "source": "RCSB Search API v2, attribute rcsb_nonpolymer_entity_"
                      "container_identifiers.nonpolymer_comp_id",
            "component_discovery": "RCSB chemical formula search (match_subset) "
                                   "over the 17 IUPAC rare earths, so the code "
                                   "list is enumerated rather than recalled",
            "retrieved_at_utc": datetime.now(timezone.utc)
                                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ligand_codes_queried": sorted(REE_LIGAND_CODES),
            "ligand_codes_excluded": CHELATED_REE_CODES,
            "components_discovered": len(discovered),
            "elements_with_zero_entries": sorted(
                e for e in RARE_EARTHS
                if not any(elements_of[i] & {e} for i in elements_of)),
            "entry_count": len(ids),
            "curation_status": "uncurated",
        },
        "entries": {
            pdb_id: {"elements": sorted(elements_of[pdb_id]),
                     "title": titles.get(pdb_id, "")}
            for pdb_id in ids
        },
    }
    args.out.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"\nwrote {args.out.relative_to(ROOT)}: {len(ids)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
