#!/usr/bin/env python3
"""Does the structure-derived EF-loop pattern separate lanmodulins from
calcium EF-hand proteins, or does it only work on the six-protein demo set?

M1 found that the canonical pattern scores a confirmed Dy3+ binder at zero
motifs, below two calcium proteins. Auditing the resolved coordinates of
8FNR/8DQ2/9PI2 gave two structure-derived relaxations -- Asn is a real
first-shell donor at loop position 1, and Gly at position 6 is a backbone
requirement of the 7-coordinate calcium geometry rather than a donor -- which
together make those loops visible.

Six proteins cannot tell you whether that generalises. This script scores the
whole 189-member lanmodulin family against a calcium EF-hand set pulled from
UniProt, so the claim is tested on hundreds of sequences rather than two.

Both sets are cached under .cache/ so reruns are offline.

Usage:  python scripts/validate_motif.py
"""
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.analyze_motifs import family_sequences  # noqa: E402

CACHE = ROOT / ".cache" / "calcium_ef_hand.json"

# As shipped: Asp at position 1, Gly at 6.
CANONICAL = re.compile(r"D.[DN].[DN]G.[ILV][DE]..E")
# Position 1 relaxed to Asp/Asn and position 6 freed, both from resolved
# donors. Position 9 keeps the [DE] requirement the canonical pattern already
# had -- it is inherited, not fitted, which matters because it turns out to be
# the constraint doing the discriminating work.
STRUCTURE_DERIVED = re.compile(r"[DN].[DN].[DN]..[ILV][DE]..E")

# Classic calcium EF-hand families. These are the competitors that matter:
# a pattern that only beats haemoglobin has proved nothing.
NEGATIVE_QUERY = (
    '(protein_name:calmodulin OR protein_name:"troponin C" OR '
    'protein_name:parvalbumin OR protein_name:calbindin OR '
    'protein_name:calretinin OR protein_name:"S100") '
    'AND reviewed:true AND length:[50 TO 400]'
)


def calcium_ef_hands() -> list[dict]:
    """Reviewed calcium EF-hand proteins, cached after the first fetch."""
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    records, cursor = [], None
    while True:
        params = {"query": NEGATIVE_QUERY, "fields": "accession,protein_name,sequence",
                  "format": "json", "size": "500"}
        if cursor:
            params["cursor"] = cursor
        r = requests.get("https://rest.uniprot.org/uniprotkb/search",
                         params=params, timeout=120)
        r.raise_for_status()
        for item in r.json().get("results", []):
            seq = item.get("sequence", {}).get("value", "")
            if seq:
                records.append({"accession": item["primaryAccession"], "sequence": seq})
        link = r.links.get("next", {}).get("url")
        if not link:
            break
        cursor = link.split("cursor=")[1].split("&")[0]
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(records, indent=1))
    return records


def counts(records: list[dict], pattern: re.Pattern) -> list[int]:
    return [len(pattern.findall(r["sequence"])) for r in records]


def summarise(label: str, pattern: re.Pattern,
              pos: list[dict], neg: list[dict]) -> None:
    p, n = counts(pos, pattern), counts(neg, pattern)
    print(f"\n{label}")
    print(f"  lanmodulin family (n={len(p)}):   mean {sum(p)/len(p):5.2f}  "
          f"median {sorted(p)[len(p)//2]:2d}  zero-motif {100*p.count(0)/len(p):5.1f}%")
    print(f"  calcium EF-hands  (n={len(n)}):   mean {sum(n)/len(n):5.2f}  "
          f"median {sorted(n)[len(n)//2]:2d}  zero-motif {100*n.count(0)/len(n):5.1f}%")

    # The operational question is not "is the mean higher" but "can a single
    # threshold separate them". Report the best one and what it costs.
    best = None
    for t in range(0, 9):
        tp = sum(1 for v in p if v >= t)
        fp = sum(1 for v in n if v >= t)
        sens, spec = tp / len(p), 1 - fp / len(n)
        bal = (sens + spec) / 2
        if best is None or bal > best[0]:
            best = (bal, t, sens, spec)
    bal, t, sens, spec = best
    print(f"  best threshold >={t} motifs: sensitivity {sens:.1%}, "
          f"specificity {spec:.1%}, balanced accuracy {bal:.1%}")


def main() -> int:
    pos = family_sequences()
    neg = calcium_ef_hands()
    print(f"Lanmodulin family: {len(pos)} sequences (InterPro NF053806)")
    print(f"Calcium EF-hands:  {len(neg)} sequences (UniProt reviewed)")

    summarise("CANONICAL  D.[DN].[DN]G.[ILV][DE]..E   (as shipped)",
              CANONICAL, pos, neg)
    summarise("STRUCTURE-DERIVED  [DN].[DN].[DN]..[ILV][DE]..E",
              STRUCTURE_DERIVED, pos, neg)

    print("\nCAUTION: the negative set is reviewed calcium EF-hand proteins only.")
    print("It does not test specificity against the whole proteome, and a motif")
    print("count is not an affinity. Separation here licenses triage, not ranking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
