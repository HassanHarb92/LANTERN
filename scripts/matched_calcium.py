#!/usr/bin/env python3
"""Find the Ca-only depositions of the proteins that hold Corpus A's lanthanides.

THE GAP THIS CLOSES. Corpus A is defined as "PDB entries containing a rare
earth", so every calcium in it is a calcium that happens to share a structure
with a lanthanide. Comparing those two piles is the S3.13 Q2 trap: the
lanthanides come out more solvent-exposed with fewer protein contacts, because
most were soaked into a crystal grown without them while most of the calciums
are structural. The comparison measures provenance and inverts the chemistry.

A matched pair fixes that by holding the protein fixed. The strongest version
is the same protein deposited twice -- once with its native calcium, once with
a lanthanide -- which is a comparison of two ions in one fold rather than two
sample-preparation histories. Those Ca-only depositions exist, but by
construction they are exactly the entries Corpus A excludes, so they have to
be fetched deliberately.

HOW A COUNTERPART IS IDENTIFIED. Not by title string, which cannot tell a
point mutant from a different protein: by UniProt accession, through the
SIFTS mapping RCSB publishes per polymer entity. For every accession behind a
lanthanide site, this asks RCSB for the other entries mapped to the same
accession that contain CA, then subtracts everything already in Corpus A. The
result is a manifest, not a conclusion -- same accession means same protein
sequence, not same construct, ligand state or resolution, and the pairing is
only as good as the hand check that follows.

This writes a manifest and optionally downloads. It deliberately does not
parse: the downloaded entries go to their own empty directory and are fed to
the existing builder by path, so untrusted coordinates are never on an
interpreter's import path.

    python -I scripts/matched_calcium.py                       # manifest only
    python -I scripts/matched_calcium.py --download
    python -I scripts/download_corpus.py --out .cache/calcium \\
        --enumeration data/calcium_counterparts.json
    python -I scripts/build_site_table.py --corpus .cache/calcium \\
        --enumeration data/calcium_counterparts.json \\
        --out data/calcium_sites.parquet
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd                                        # noqa: E402
import requests                                            # noqa: E402

SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
GRAPHQL = "https://data.rcsb.org/graphql"
ENUMERATION = ROOT / "data" / "ree_pdb_entries.json"
TABLE = ROOT / "data" / "lanthanide_sites.parquet"
DEFAULT_OUT = ROOT / "data" / "calcium_counterparts.json"

ACCESSION_FIELD = ("rcsb_polymer_entity_container_identifiers"
                   ".reference_sequence_identifiers.database_accession")
CA_FIELD = ("rcsb_nonpolymer_entity_container_identifiers"
            ".nonpolymer_comp_id")


def _post(url: str, payload: dict) -> dict | None:
    """RCSB answers 'no hits' with 204 and an empty body, not with []."""
    response = requests.post(url, json=payload, timeout=120)
    if response.status_code == 204:
        return None
    response.raise_for_status()
    return response.json()


def accessions_for(pdb_ids: list[str]) -> dict[str, list[str]]:
    """{PDB_ID: [UniProt accession, ...]} via SIFTS, batched over GraphQL."""
    out: dict[str, list[str]] = {}
    for start in range(0, len(pdb_ids), 50):
        chunk = pdb_ids[start:start + 50]
        query = ("""{entries(entry_ids:%s){rcsb_id polymer_entities{
                 rcsb_polymer_entity_container_identifiers{
                 reference_sequence_identifiers{database_name
                 database_accession}}}}}""" % json.dumps(chunk))
        response = requests.post(GRAPHQL, json={"query": query}, timeout=120)
        response.raise_for_status()
        for entry in response.json()["data"]["entries"] or []:
            found: list[str] = []
            for entity in entry.get("polymer_entities") or []:
                identifiers = (entity.get(
                    "rcsb_polymer_entity_container_identifiers") or {})
                for reference in (identifiers.get(
                        "reference_sequence_identifiers") or []):
                    if reference.get("database_name") == "UniProt":
                        found.append(reference["database_accession"])
            out[entry["rcsb_id"]] = sorted(set(found))
        time.sleep(0.25)
    return out


def calcium_entries_for(accession: str) -> set[str]:
    """Entries mapped to this accession that contain a CA ion."""
    payload = {
        "query": {"type": "group", "logical_operator": "and", "nodes": [
            {"type": "terminal", "service": "text", "parameters": {
                "attribute": ACCESSION_FIELD,
                "operator": "exact_match", "value": accession}},
            {"type": "terminal", "service": "text", "parameters": {
                "attribute": CA_FIELD,
                "operator": "exact_match", "value": "CA"}},
        ]},
        "return_type": "entry",
        "request_options": {"return_all_hits": True},
    }
    data = _post(SEARCH, payload)
    return {hit["identifier"] for hit in data["result_set"]} if data else set()


def metadata_for(pdb_ids: list[str]) -> dict[str, dict]:
    """{PDB_ID: {title, resolution_A, method}}, batched."""
    out: dict[str, dict] = {}
    for start in range(0, len(pdb_ids), 100):
        chunk = pdb_ids[start:start + 100]
        query = ("""{entries(entry_ids:%s){rcsb_id struct{title}
                 exptl{method} rcsb_entry_info{resolution_combined}}}"""
                 % json.dumps(chunk))
        response = requests.post(GRAPHQL, json={"query": query}, timeout=120)
        response.raise_for_status()
        for entry in response.json()["data"]["entries"] or []:
            info = entry.get("rcsb_entry_info") or {}
            resolutions = info.get("resolution_combined") or []
            methods = [m.get("method", "") for m in entry.get("exptl") or []]
            out[entry["rcsb_id"]] = {
                "title": (entry.get("struct") or {}).get("title", ""),
                "resolution_A": min(resolutions) if resolutions else None,
                "method": methods[0] if methods else "",
            }
        time.sleep(0.25)
    return out


def select(candidates: dict[str, list[str]], meta: dict[str, dict],
           max_resolution: float, per_accession: int) -> dict[str, list[str]]:
    """Keep the best-resolved few counterparts per accession.

    Two reasons to cut, and the first is chemistry rather than bandwidth.
    What a matched pair measures is coordination number and donor distance,
    and both are refinement artefacts below about 2.5 A -- waters go
    unmodelled, occupancies are guessed, and a "7-coordinate" site may just
    be an 8-coordinate one with a missing density peak. Admitting a 3.5 A
    structure into the contrast set adds noise shaped exactly like signal.
    The second is that calmodulin alone offers 229 counterparts, and the
    229th adds nothing the best five did not.

    NMR entries are dropped rather than ranked: they have no resolution, and
    an NMR ensemble's metal-donor distances come from a restraint set, not
    from density.
    """
    chosen: dict[str, list[str]] = {}
    for accession, entries in candidates.items():
        usable = [
            pdb_id for pdb_id in entries
            if (meta.get(pdb_id, {}).get("resolution_A") is not None
                and meta[pdb_id]["resolution_A"] <= max_resolution)]
        usable.sort(key=lambda pdb_id: (meta[pdb_id]["resolution_A"], pdb_id))
        if usable:
            chosen[accession] = usable[:per_accession]
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", type=Path, default=TABLE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--min-donors", type=int, default=3,
                        help="only chase entries holding a lanthanide site "
                             "with at least this many protein donors")
    parser.add_argument("--limit-entries", type=int, default=None)
    parser.add_argument("--max-resolution", type=float, default=2.5,
                        help="drop counterparts refined worse than this; "
                             "coordination number is not reliable below it")
    parser.add_argument("--per-accession", type=int, default=5,
                        help="keep at most this many counterparts per "
                             "accession, best resolution first")
    args = parser.parse_args()

    frame = pd.read_parquet(args.table)
    lanthanide = frame[(frame["family"] == "lanthanide")
                       & (frame["protein_donor_count"] >= args.min_donors)
                       & (~frame["chelator_flagged"])]
    sources = sorted(lanthanide["pdb_id"].unique())
    if args.limit_entries:
        sources = sources[:args.limit_entries]
    print(f"{len(lanthanide)} lanthanide sites with >= {args.min_donors} "
          f"protein donors and no chelator flag, in {len(sources)} entries")

    print("resolving UniProt accessions ...")
    by_entry = accessions_for(sources)
    accessions = sorted({a for group in by_entry.values() for a in group})
    without = [e for e in sources if not by_entry.get(e)]
    print(f"  {len(accessions)} distinct accessions; {len(without)} entries "
          f"map to none (likely peptides or designed constructs)")

    corpus = set(json.loads(ENUMERATION.read_text())["entries"])
    counterparts: dict[str, list[str]] = {}
    for index, accession in enumerate(accessions, start=1):
        try:
            hits = calcium_entries_for(accession)
        except requests.RequestException as error:         # noqa: PERF203
            print(f"  {accession}: query failed ({type(error).__name__})")
            continue
        fresh = sorted(hits - corpus)
        if fresh:
            counterparts[accession] = fresh
        if index % 25 == 0 or index == len(accessions):
            print(f"  {index}/{len(accessions)} accessions, "
                  f"{sum(len(v) for v in counterparts.values())} candidate "
                  "entries so far")
        time.sleep(0.2)

    found = sorted({e for group in counterparts.values() for e in group})
    print(f"\n{len(found)} Ca-containing entries outside Corpus A, "
          f"covering {len(counterparts)} of {len(accessions)} accessions")
    if not found:
        print("nothing to fetch")
        return 0

    print("fetching resolutions and titles ...")
    meta = metadata_for(found)
    counterparts = select(counterparts, meta, args.max_resolution,
                          args.per_accession)
    new_ids = sorted({e for group in counterparts.values() for e in group})
    dropped = len(found) - len(new_ids)
    print(f"  keeping {len(new_ids)} ({dropped} dropped: worse than "
          f"{args.max_resolution} A, no resolution, or beyond the best "
          f"{args.per_accession} for their accession)")
    if not new_ids:
        print("nothing survived selection")
        return 0

    # Which Corpus A entry each counterpart is matched to, carried through so
    # the pairing can be audited without re-running the accession lookup.
    partners: dict[str, list[str]] = {}
    for entry, group in by_entry.items():
        for accession in group:
            for counterpart in counterparts.get(accession, []):
                partners.setdefault(counterpart, []).append(entry)

    payload = {
        "_provenance": {
            "generated": datetime.now(timezone.utc).isoformat(),
            "script": "scripts/matched_calcium.py",
            "basis": ("UniProt accessions of Corpus A entries holding a "
                      f"lanthanide site with >= {args.min_donors} protein "
                      "donors and no chelator flag; RCSB entries sharing an "
                      "accession and containing CA; Corpus A subtracted; "
                      f"kept at <= {args.max_resolution} A, best "
                      f"{args.per_accession} per accession"),
            "source_entries": len(sources),
            "accessions": len(accessions),
            "candidates_before_selection": len(found),
            "curation_status": ("uncurated -- same UniProt accession is the "
                                "same sequence, not the same construct, "
                                "ligand state or oligomeric form"),
        },
        "entries": {
            pdb_id: {
                "title": meta.get(pdb_id, {}).get("title", ""),
                "resolution_A": meta.get(pdb_id, {}).get("resolution_A"),
                "method": meta.get(pdb_id, {}).get("method", ""),
                "matched_to": sorted(set(partners.get(pdb_id, []))),
                "accessions": sorted({a for a, g in counterparts.items()
                                      if pdb_id in g}),
            } for pdb_id in new_ids},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    shown = (args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT)
             else args.out)
    print(f"wrote {shown}")
    print("\nnext: download into its own empty directory, then parse by path")
    print("  python -I scripts/download_corpus.py --out .cache/calcium \\")
    print(f"      --enumeration {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
