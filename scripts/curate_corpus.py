#!/usr/bin/env python3
"""Shortlist Corpus A entries for the M2 hand curation, using
annotation rather than entry titles.

WHY NOT TITLES. `title_first_pass` in build_site_table.py leaves 590 of 636
entries unclassified, and the misses are not harmless. 9C8X is titled "X-ray
crystal structure of Methylorubrum extorquens La(III)-bound LanD": no keyword
in it says lanthanide biology, and the entry sat unclassified while being the
most on-target protein in the corpus -- a lanthanide chaperone whose published
function is separating light lanthanides (ROADMAP 3.17). Titles are written by
depositors for humans, and the fix for a missed title is usually a substring
that also matches something else; "land" matches "Ignicoccus islandicus".

WHAT THIS USES INSTEAD. Four signals that live in structured metadata, not in
prose, fetched per polymer entity:

    description   the entity name. 6OC5's title says nothing, its description
                  says "Lanthanide-dependent methanol dehydrogenase XoxF".
    keywords      struct_keywords, where the depositor states what the entry
                  is *for*. This is the signal that matters most and the one
                  added last. The 9VY4-9VYA series is titled "Structure of MIF
                  binding with Ytterbium ions" and described as "Propeptide,
                  PepSY amd peptidase M4" -- neither says lanthanide biology,
                  and it reached the first run of this script only through the
                  weak organism tier. Its keywords say "Rare earth,
                  Metalloprotein". A phasing soak gets keyworded by the
                  protein's own function; an entry deposited *because* it binds
                  a rare earth says so here.
    annotation    Pfam / InterPro / GO terms assigned by the databases, not by
                  the depositor.
    organism      NCBI scientific name. A methylotroph is where lanthanide
                  biology lives; it is weak evidence alone and strong beside
                  either of the others.

Element names are deliberately absent from every vocabulary. "ytterbium" in a
title means a lanthanide is present, which is true of all 636 entries by
construction, so it separates nothing.

WHAT THIS IS NOT. It does not label anything. It writes a ranked shortlist with
the matched evidence recorded per entry, for a human to accept or reject, and
the output says so in its own provenance block. The reason is the one the
project keeps rediscovering: a keyword that assigns a class silently is a
keyword whose false positives end up inside a p-value. An organism match on its
own is listed as `supporting` precisely so that it cannot promote an entry by
itself -- a methylotroph can also deposit an unrelated protein with a terbium
soak, which is what 6QSS turned out to be.

Usage:
    python -I scripts/curate_corpus.py
    python -I scripts/curate_corpus.py --limit 50        # sample first
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests                                           # noqa: E402

GRAPHQL = "https://data.rcsb.org/graphql"
ENUMERATION = ROOT / "data" / "ree_pdb_entries.json"
DEFAULT_OUT = ROOT / "data" / "curation_candidates.json"
VERDICTS = ROOT / "data" / "curation_verdicts.json"
BATCH = 50
TIMEOUT = 90

QUERY = """query($ids:[String!]!){ entries(entry_ids:$ids){ rcsb_id
  struct{title}
  struct_keywords{pdbx_keywords text}
  polymer_entities{
    rcsb_polymer_entity{pdbx_description}
    rcsb_entity_source_organism{ncbi_scientific_name}
    rcsb_polymer_entity_container_identifiers{
      reference_sequence_identifiers{database_accession database_name}}
    rcsb_polymer_entity_annotation{type name}
  } } }"""

# Phrases that name lanthanide-dependent biology outright. Each is a whole
# word or a multi-word phrase, matched with word boundaries, because the
# single costly mistake in this project's keyword work has been a short
# substring landing inside an unrelated word.
STRONG = (
    "lanthanide", "lanthanoid", "rare earth", "rare-earth",
    "landiscernin", "lanmodulin", "lanm", "land",
    "xoxf", "exaf", "pedh", "xoxg", "xoxj",
)

# Families where lanthanide dependence is common but not universal: the
# calcium-dependent MxaFI methanol dehydrogenase shares this chemistry and
# this vocabulary. Enough to shortlist, never enough to label.
FAMILY = (
    "methanol dehydrogenase", "methanol/ethanol", "ethanol dehydrogenase",
    "quinoprotein", "pyrroloquinoline", "pqq",
    "alcohol dehydrogenase, beta-propeller",
)

# Where lanthanide biology is found. Methylotrophs as a prefix, plus genera
# that have yielded characterised lanthanide proteins -- 9PI2's lanmodulin is
# from Ancylobacter lacus, which no "methylo" rule would catch.
TAXA_PREFIX = ("methylo", "methylacidi", "methylacidimicro")
TAXA = ("ancylobacter", "hyphomicrobium", "bradyrhizobium", "beijerinckia",
        "methylorubrum", "methylobacterium")


def _words(*values) -> str:
    return " ".join(v for v in values if v).lower()


def _matches(text: str, phrases) -> list[str]:
    """Whole-word matches only. `land` as a substring matches islandicus;
    `land` as a word does not."""
    return [p for p in phrases
            if re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", text)]


def evidence_for(entry: dict) -> dict:
    """Every signal this entry carries, with what matched recorded alongside.

    An entry with no basis recorded cannot be audited later, which is the same
    rule `title_first_pass` follows.
    """
    descriptions, organisms, annotations, accessions = [], [], [], []
    for pe in entry.get("polymer_entities") or []:
        descriptions.append((pe.get("rcsb_polymer_entity") or {}).get("pdbx_description") or "")
        organisms += [o.get("ncbi_scientific_name") or ""
                      for o in (pe.get("rcsb_entity_source_organism") or [])]
        annotations += [a.get("name") or ""
                        for a in (pe.get("rcsb_polymer_entity_annotation") or [])]
        ids = ((pe.get("rcsb_polymer_entity_container_identifiers") or {})
               .get("reference_sequence_identifiers") or [])
        accessions += [i["database_accession"] for i in ids
                       if i.get("database_name") == "UniProt"]

    described = _words(*descriptions)
    annotated = _words(*annotations)
    organism = _words(*organisms)
    title = (entry.get("struct") or {}).get("title") or ""
    kw = entry.get("struct_keywords") or {}
    keywords = _words(kw.get("pdbx_keywords"), kw.get("text"))

    hits = {
        "description_strong": _matches(described, STRONG),
        "description_family": _matches(described, FAMILY),
        "annotation_family": _matches(annotated, FAMILY + STRONG),
        "title_strong": _matches(title.lower(), STRONG),
        "keywords_strong": _matches(keywords, STRONG),
    }
    organism_hit = [t for t in TAXA if t in organism] or \
                   [p for p in TAXA_PREFIX if re.search(rf"(?<![a-z]){p}", organism)]

    # Deliberately ordered: a named lanthanide protein outranks a family that
    # merely often binds one, which outranks an organism that merely often
    # has them. The organism tier exists so that a methylotroph entry is read
    # by a human, not so that it is labelled by a script.
    if hits["description_strong"] or hits["title_strong"] or hits["keywords_strong"]:
        tier = "strong"
    elif hits["description_family"] or hits["annotation_family"]:
        tier = "family"
    elif organism_hit:
        tier = "supporting"
    else:
        tier = "none"

    return {
        "tier": tier,
        "matched": {k: v for k, v in hits.items() if v} | (
            {"organism": organism_hit} if organism_hit else {}),
        "description": "; ".join(sorted({d for d in descriptions if d}))[:200],
        "organism": "; ".join(sorted({o for o in organisms if o}))[:120],
        "uniprot": sorted(set(accessions)),
        "title": title[:160],
        "keywords": (kw.get("text") or "")[:160],
    }


def fetch(ids: list[str]) -> dict[str, dict]:
    out = {}
    for start in range(0, len(ids), BATCH):
        batch = ids[start:start + BATCH]
        response = requests.post(GRAPHQL, timeout=TIMEOUT,
                                 json={"query": QUERY, "variables": {"ids": batch}})
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise SystemExit(f"GraphQL error: {payload['errors'][0].get('message')}")
        for entry in payload["data"]["entries"] or []:
            out[entry["rcsb_id"]] = evidence_for(entry)
        print(f"  {min(start + BATCH, len(ids))}/{len(ids)}")
    return out


# Entries already hand-checked as genuine natural lanthanide biology
# (ROADMAP 3.16 label audit, 3.17 for LanD, 3.19 for PepSY). Used only to
# report recall: a rule set that misses a known positive is reported as
# missing it rather than quietly shipped. The 9VY* series is in this list
# because the first run of this script ranked it `supporting` on organism
# alone -- it is the regression test for the keywords signal.
KNOWN_POSITIVES = ("8FNS", "8FNR", "8DQ2", "9PI2", "6MI5",
                   "6OC5", "6OC6", "4MAE", "6FKW", "6DAM", "7O6Z",
                   "6ZCV", "6ZCW", "9C8X", "9C8Y", "9C8Z", "9C90",
                   "9VY4", "9VY5", "9VY6", "9VY7", "9VY8", "9VY9", "9VYA")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enumeration", type=Path, default=ENUMERATION)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, help="only the first N entries")
    args = parser.parse_args()

    ids = sorted(json.loads(args.enumeration.read_text())["entries"])
    if args.limit:
        ids = ids[:args.limit]
    print(f"{len(ids)} entries from {args.enumeration.name}")

    found = fetch(ids)
    tiers = {t: sorted(p for p, v in found.items() if v["tier"] == t)
             for t in ("strong", "family", "supporting", "none")}

    missed = [p for p in KNOWN_POSITIVES
              if p in found and found[p]["tier"] not in ("strong", "family")]

    payload = {
        "_provenance": {
            "source": GRAPHQL,
            "retrieved": time.strftime("%Y-%m-%d"),
            "enumeration": str(args.enumeration.relative_to(ROOT)),
            "signals": "entity description, struct_keywords, Pfam/InterPro/GO "
                       "annotation, source organism",
            "curation_status": "UNCURATED SHORTLIST. A tier is evidence that an "
                               "entry is worth a human reading, not a class. "
                               "Nothing here may be used as a label until a "
                               "person has accepted it; an organism match in "
                               "particular is 'supporting' because a "
                               "methylotroph can deposit an unrelated protein "
                               "with a lanthanide soaked in.",
            "known_positives_missed": missed,
        },
        "counts": {t: len(v) for t, v in tiers.items()},
        "tiers": {t: v for t, v in tiers.items() if t != "none"},
        "entries": dict(sorted(found.items())),
    }
    args.out.write_text(json.dumps(payload, indent=2))

    print(f"\n  strong      {len(tiers['strong']):4d}  named lanthanide protein")
    print(f"  family      {len(tiers['family']):4d}  family that often binds one")
    print(f"  supporting  {len(tiers['supporting']):4d}  organism only -- read, do not label")
    print(f"  none        {len(tiers['none']):4d}")
    print(f"\nknown positives missed by these rules: {missed or 'none'}")
    print(f"wrote {args.out.relative_to(ROOT)}")

    # Which shortlisted entries a person has already read. Without this the
    # shortlist says what to do and nothing says what is left, so the second
    # pass starts by re-reading the first pass's entries.
    print("\nNothing above is a label. The next step is a person reading the "
          "strong and family tiers\nand recording a verdict per entry in "
          f"{VERDICTS.relative_to(ROOT)}.")
    if VERDICTS.is_file():
        verdicts = json.loads(VERDICTS.read_text())
        # An entry the title pass already got right was still *read*; it just
        # needed no override. Counting it as unread would send the next pass
        # back over it.
        decided = {p.upper() for group in verdicts["groups"]
                   for p in group["entries"]}
        decided |= {p.upper() for p in verdicts.get("confirmed_by_title_pass", ())
                    if not p.startswith("_")}
        for tier in ("strong", "family", "supporting"):
            done = [p for p in tiers[tier] if p.upper() in decided]
            todo = [p for p in tiers[tier] if p.upper() not in decided]
            print(f"  {tier:11s} {len(done):3d} verdicted, {len(todo):3d} to read"
                  + (f": {', '.join(todo[:12])}"
                     + (" ..." if len(todo) > 12 else "") if todo else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
