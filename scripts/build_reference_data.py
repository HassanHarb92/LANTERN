#!/usr/bin/env python3
"""Rebuild data/reference_proteins.json from UniProt.

Replaces the synthetic demo set with authentic sequences so the default view
ranks real proteins. Every record carries its accession, a SHA-256 of the
sequence, the retrieval date and a source URL, satisfying rule 9 of
docs/SCIENTIFIC_CONTRACT.md.

Usage:  python scripts/build_reference_data.py
"""
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "reference_proteins.json"
ENDPOINT = "https://rest.uniprot.org/uniprotkb/{accession}.json"
FIELDS = "accession,protein_name,organism_name,sequence"

# Two lanthanide binders, two calcium proteins that are not lanthanide
# binders, and two proteins with no EF-hand at all. The calcium pair is the
# discriminating test: a sequence score that cannot separate them from the
# lanmodulins is measuring the wrong variable, which is exactly the finding
# recorded in ROADMAP.md 3.1.
REFERENCES = [
    {
        "accession": "C5B164",
        "pdb_id": "8FNS",
        "role": "lanthanide binder",
        "evidence": "experimentally characterized; Nd3+ sites resolved in PDB 8FNS",
        "notes": "Lanmodulin from Methylorubrum extorquens AM1. The one reviewed "
                 "member of the family and the positive control for the pipeline.",
    },
    {
        "accession": "A0A4V2JDD3",
        "pdb_id": "8FNR",
        "role": "lanthanide binder",
        # UniProt has not reviewed this entry, so its submitted name is the
        # generic "EF-hand domain-containing protein". Both names are kept:
        # the curated one for display, the database one for traceability.
        "display_name": "Lanmodulin (Hansschlegelia quercus)",
        "evidence": "structure with bound Dy3+ deposited as PDB 8FNR",
        "notes": "Lanmodulin from Hansschlegelia quercus. A distinct site "
                 "architecture from 8FNS: CN 9 with three bidentate carboxylates "
                 "and no coordinating water.",
    },
    {
        "accession": "P0DP23",
        "pdb_id": "1CLL",
        "role": "calcium protein",
        "evidence": "experimentally characterized calcium sensor; Ca2+ sites in PDB 1CLL",
        "notes": "Human calmodulin. Four EF-hands at coordination number 7. The "
                 "key negative: it is calcium-selective, not lanthanide-selective.",
    },
    {
        "accession": "P02585",
        "pdb_id": None,
        "role": "calcium protein",
        "evidence": "experimentally characterized calcium-binding protein",
        "notes": "Human fast skeletal troponin C. A second EF-hand calcium "
                 "protein, included because the sequence heuristic ranks it "
                 "almost level with lanmodulin.",
    },
    {
        "accession": "P69905",
        "pdb_id": None,
        "role": "true negative",
        "evidence": "no EF-hand domain; oxygen transport via haem iron",
        "notes": "Human haemoglobin subunit alpha. Binds a metal, but through "
                 "a porphyrin rather than a carboxylate-rich EF-hand.",
    },
    {
        "accession": "P00766",
        "pdb_id": None,
        "role": "true negative",
        "evidence": "serine protease zymogen; no characterized metal site",
        "notes": "Bovine chymotrypsinogen A. Included as an unrelated protein "
                 "that should rank at the bottom.",
    },
]


def fetch(accession: str, timeout: int = 30) -> dict:
    response = requests.get(ENDPOINT.format(accession=accession),
                            params={"fields": FIELDS}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def main() -> int:
    today = date.today().isoformat()
    records = []
    for reference in REFERENCES:
        accession = reference["accession"]
        payload = fetch(accession)
        sequence = payload.get("sequence", {}).get("value", "")
        if not sequence:
            # A demerged or withdrawn accession returns HTTP 200 with no
            # sequence. Failing loudly beats shipping an empty record.
            print(f"ERROR: {accession} returned no sequence", file=sys.stderr)
            return 1

        description = payload.get("proteinDescription", {})
        database_name = (description.get("recommendedName", {}).get("fullName", {}).get("value")
                         or (description.get("submissionNames") or [{}])[0]
                         .get("fullName", {}).get("value") or accession)
        name = reference.get("display_name") or database_name
        curated = name != database_name

        records.append({
            "accession": accession,
            "name": name,
            "uniprot_name": database_name,
            "name_is_curated": curated,
            "organism": payload.get("organism", {}).get("scientificName", "Unknown"),
            "sequence": sequence,
            "pdb_id": reference["pdb_id"],
            "source": "UniProt reference set (authentic sequence)",
            "evidence": reference["evidence"],
            "source_url": f"https://www.uniprot.org/uniprotkb/{accession}/entry",
            "notes": reference["notes"],
        })
        print(f"  {accession:<12} {len(sequence):>4} aa  {name[:52]}")

    document = {
        "_provenance": {
            "description": "Authentic reference proteins for the default screening view.",
            "source": "UniProtKB REST API",
            "retrieved": today,
            "record_count": len(records),
            "sequence_sha256": {r["accession"]: hashlib.sha256(
                r["sequence"].encode()).hexdigest() for r in records},
            "roles": {r["accession"]: ref["role"]
                      for r, ref in zip(records, REFERENCES)},
            "warning": "These are real sequences. Do not describe heuristic scores "
                       "over them as measured binding or selectivity.",
        },
        "proteins": records,
    }
    OUT.write_text(json.dumps(document, indent=2) + "\n")
    print(f"\nWrote {len(records)} records to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
