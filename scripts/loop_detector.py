#!/usr/bin/env python3
"""Build and validate a *balanced-recall* EF-loop detector -- the instrument,
kept strictly separate from the shipped classifier.

ROADMAP M3.0 calls this the limiting item, and §3.8.1 showed why it bites: the
shipped pattern `[DN].[DN].[DN]..[ILV][DE]..E` is deliberately biased toward
lanmodulin loops, so any loop property measured *through* it is measured on a
skewed population. Freeing position 9 in that pattern put Glu-at-9 in calcium
loops at 3.3%; a neutral definition put it at 13.3%. Same proteins, 4x
difference, entirely an artefact of the detector.

Spacing (EF-hand period) and Pro-at-position-2 both need a detector that finds
loops in calcium proteins at a rate comparable to lanmodulins, or the numbers
mean nothing. This script builds one against external ground truth.

GROUND TRUTH, and the asymmetry in it
-------------------------------------
UniProt annotates EF-hand domains (PROSITE PS50222 / ProRule). Within an
annotated domain the 12-residue loop sits at a fixed offset, measured here
rather than assumed -- see validate_offset(), which recovers it from residue
composition alone.

That annotation is trustworthy for *reviewed calcium* proteins and is NOT
trustworthy for the lanmodulin family: the profile is calcium-trained, and on
unreviewed LanM entries it finds roughly 1.5 domains per protein where the
family has 4. So this script uses it as ground truth on the calcium side only
-- which is the side the shipped pattern cannot measure -- and uses
structurally confirmed loops on the lanmodulin side.

Usage:  python scripts/loop_detector.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Bio.Data.IUPACData import protein_letters_3to1 as THREE_TO_ONE  # noqa: E402

from lantern.chemistry import EF_HAND_HINT          # noqa: E402
from lantern.structure import (ALL_METAL_CODES, REE_LIGAND_CODES,  # noqa: E402
                                 _parse, binding_neighborhood,
                                 cached_structure)
from scripts.analyze_motifs import family_sequences   # noqa: E402
from scripts.validate_motif import NEGATIVE_QUERY     # noqa: E402

# Every cached structure. 8FNR and 8DQ2 are the same protein with different
# ions, so loops are deduplicated by sequence before use.
STRUCTURES = ("8FNS", "8FNR", "8DQ2", "9PI2", "1CLL")

CACHE = ROOT / ".cache" / "ef_hand_domains.json"
LOOP_LENGTH = 12
# 1-based position of the loop within a UniProt EF-hand domain annotation.
# Measured, not assumed; validate_offset() re-derives it on every run.
LOOP_OFFSET_IN_DOMAIN = 14


def _fetch(query: str) -> list[dict]:
    """Accession, sequence and EF-hand domain spans for a UniProt query."""
    records, cursor = [], None
    while True:
        params = {"query": query, "fields": "accession,sequence,ft_domain",
                  "format": "json", "size": "500"}
        if cursor:
            params["cursor"] = cursor
        r = requests.get("https://rest.uniprot.org/uniprotkb/search",
                         params=params, timeout=120)
        r.raise_for_status()
        for item in r.json().get("results", []):
            seq = item.get("sequence", {}).get("value", "")
            if not seq:
                continue
            domains = [f["location"]["start"]["value"]
                       for f in item.get("features", [])
                       if f["type"] == "Domain"
                       and "EF-hand" in (f.get("description") or "")]
            records.append({"accession": item["primaryAccession"],
                            "sequence": seq, "domain_starts": domains})
        link = r.links.get("next", {}).get("url")
        if not link:
            break
        cursor = link.split("cursor=")[1].split("&")[0]
    return records


def annotated_sets() -> tuple[list[dict], list[dict]]:
    """Calcium EF-hand proteins and LanM family, both with domain spans."""
    if CACHE.exists():
        payload = json.loads(CACHE.read_text())
        return payload["calcium"], payload["lanm"]
    calcium = _fetch(NEGATIVE_QUERY)
    accessions = [r["accession"] for r in family_sequences()]
    lanm = []
    for i in range(0, len(accessions), 100):
        chunk = accessions[i:i + 100]
        lanm += _fetch(" OR ".join(f"accession:{a}" for a in chunk))
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps({"calcium": calcium, "lanm": lanm}, indent=1))
    return calcium, lanm


def loops_from_annotation(records: list[dict], offset: int = LOOP_OFFSET_IN_DOMAIN
                          ) -> list[tuple[str, int, str]]:
    """(accession, 1-based loop start, loop) for every annotated domain."""
    out = []
    for record in records:
        seq = record["sequence"]
        for start in record["domain_starts"]:
            i = start - 1 + offset - 1          # 0-based index of loop start
            loop = seq[i:i + LOOP_LENGTH]
            if len(loop) == LOOP_LENGTH:
                out.append((record["accession"], i + 1, loop))
    return out


def validate_offset(calcium: list[dict]) -> None:
    """Recover the loop offset from composition instead of trusting a constant.

    The EF-loop's two most conserved positions are Asp at 1 and the invariant
    bidentate Glu at 12. Only the correct offset makes both appear; one
    residue either way destroys them. If this table ever stops peaking at
    LOOP_OFFSET_IN_DOMAIN, the annotation convention changed and every number
    downstream is wrong.
    """
    print("Offset of the 12-residue loop within a UniProt EF-hand domain")
    print(f"  {'offset':>6} {'loops':>6} {'pos1=Asp':>9} {'pos12=Glu':>10}")
    best = None
    for offset in range(10, 18):
        loops = [loop for _, _, loop in loops_from_annotation(calcium, offset)]
        n = len(loops) or 1
        d = sum(1 for x in loops if x[0] == "D") / n
        e = sum(1 for x in loops if x[11] == "E") / n
        mark = ""
        if best is None or d + e > best[0]:
            best, mark = (d + e, offset), ""
        print(f"  {offset:6d} {len(loops):6d} {d:9.1%} {e:10.1%}{mark}")
    print(f"  -> composition peaks at offset {best[1]}; "
          f"constant is {LOOP_OFFSET_IN_DOMAIN}")
    assert best[1] == LOOP_OFFSET_IN_DOMAIN, "annotation convention changed"


def annotation_is_biased(calcium: list[dict], lanm: list[dict]) -> None:
    """Why the curated annotation cannot be ground truth on the LanM side."""
    print("\nEF-hand domains per protein, as annotated by UniProt/PROSITE")
    for name, records in (("calcium EF-hands", calcium),
                          ("lanmodulin family", lanm)):
        n = len(records) or 1
        total = sum(len(r["domain_starts"]) for r in records)
        none = sum(1 for r in records if not r["domain_starts"])
        print(f"  {name:20s} n={n:4d}  {total:5d} domains  "
              f"{total/n:4.2f}/protein  {none/n:5.1%} with none")
    print("  Lanmodulins have four EF-hands each (Mattocks 2023, and 8FNS/8FNR")
    print("  resolve four sites). The profile finds well under half of them, so")
    print("  it is used as ground truth for the CALCIUM side only.")


def structural_loops() -> dict[str, set[str]]:
    """Loops read off deposited coordinates, keyed by the ion they bind.

    The only lanthanide-loop ground truth that owes nothing to a sequence
    profile. For each metal site the loop starts at its lowest-numbered
    protein donor -- that donor is ligand position 1 (X) by definition of the
    EF-hand -- and runs 12 residues. Reproduces the §3.8 table exactly,
    including the calcium-like EF4 of each lanmodulin.

    Splitting by ion matters more than splitting by protein: 9PI2 holds Nd3+
    and Ca2+ in one crystal, so its four loops are a within-structure control.
    """
    by_ion = {"lanthanide": set(), "calcium": set()}
    for pdb_id in STRUCTURES:
        cached = cached_structure(pdb_id)
        if cached is None:
            continue
        text, fmt = cached
        model = next(iter(_parse(text, fmt)))
        residues = {(chain.id, res.id[1]): res.get_resname()
                    for chain in model for res in chain if res.id[0] == " "}
        for site in binding_neighborhood(text, fmt=fmt, metals=ALL_METAL_CODES):
            donors = [d for d in site["donors"] if d["kind"] == "protein"]
            if not donors:
                continue
            chain = site["chain"]
            start = min(d["residue_number"] for d in donors)
            loop = "".join(
                THREE_TO_ONE.get(
                    residues.get((chain, start + i), "XXX").capitalize(), "X")
                for i in range(LOOP_LENGTH))
            if "X" in loop:
                continue
            kind = ("lanthanide" if site["metal"] in REE_LIGAND_CODES
                    else "calcium")
            by_ion[kind].add(loop)
    return by_ion


def composition(truth: list[tuple[str, int, str]]) -> None:
    """Per-position residue composition of the curated calcium loops.

    This is what a detector should be designed against: positions that are
    invariant here are structural, positions that vary are free. Guessing
    which is which is how the canonical regex ended up demanding Gly at 6.
    """
    print("\nPer-position composition of curated calcium EF-loops "
          f"(n={len(truth)})")
    print(f"  {'pos':>3}  {'top residues (>=5%)':48s} {'ligand?':>8}")
    ligands = {1, 3, 5, 7, 9, 12}
    for p in range(1, LOOP_LENGTH + 1):
        counts = Counter(loop[p - 1] for _, _, loop in truth)
        n = sum(counts.values())
        top = " ".join(f"{res} {c/n:.0%}" for res, c in counts.most_common()
                       if c / n >= 0.05)
        tag = "X Y Z -Y -X -Z".split()[sorted(ligands).index(p)] if p in ligands else ""
        print(f"  {p:3d}  {top:48s} {tag:>8}")


def precision_proxy(pattern: re.Pattern, records: list[dict],
                    truth: list[tuple[str, int, str]]) -> float:
    """Matches per curated loop. A pure instrument wants this near 1.

    Recall can always be bought with permissiveness. If a detector fires five
    times for every real loop, any period or spacing computed from its hits is
    measuring its own false positives.
    """
    total = sum(len(pattern.findall(r["sequence"])) for r in records)
    return total / (len(truth) or 1)


def recall_at_position(pattern: re.Pattern, records: list[dict],
                       truth: list[tuple[str, int, str]]) -> tuple[int, int]:
    """Share of ground-truth loops the pattern finds *at the right position*.

    Matching somewhere in the protein is not enough -- a detector firing on an
    unrelated stretch would otherwise score as a hit. Start positions must
    agree with the curated annotation.
    """
    hits = {r["accession"]: {m.start() + 1 for m in pattern.finditer(r["sequence"])}
            for r in records}
    found = sum(1 for accession, start, _ in truth
                if start in hits.get(accession, ()))
    return found, len(truth)


# Candidate detectors. The design question is which positions are invariant
# ACROSS both families rather than diagnostic of either, so the instrument
# does not encode the answer it is used to measure.
CANDIDATES = {
    "shipped classifier":   EF_HAND_HINT,
    "PS00018-like":         re.compile(r"D.[DNS][^ILVFYW][DENSTG][DNQGHRK][^GP]"
                                       r"[LIVMC][DENQSTAGC]..[DE][LIVMFYW]"),
    "neutral (3.8.1)":      re.compile(r"D.{6}[ILVMFC].{3}E"),
    "anchors only":         re.compile(r"[DNSE].{6}[ILVMFCAT].{3}[ED]"),
    # The three positions the composition table shows are invariant across
    # both families: 1 (Asp 91%), 8 (Ile/Val/Leu 92%), 12 (Glu 87%). Nothing
    # here is chosen for what it does to the Ln/Ca contrast.
    "pos 1+12":             re.compile(r"[DN].{10}E"),
    "pos 1+8+12":           re.compile(r"[DN].{6}[ILV].{3}E"),
    "pos 1+8+12 strict":    re.compile(r"D.{6}[ILV].{3}E"),
}


def main() -> int:
    calcium, lanm = annotated_sets()
    validate_offset(calcium)
    annotation_is_biased(calcium, lanm)

    truth = loops_from_annotation(calcium)
    print(f"\nGround truth: {len(truth)} curated calcium EF-loops "
          f"in {len(calcium)} reviewed proteins")

    structural = structural_loops()
    lanthanide, structural_ca = structural["lanthanide"], structural["calcium"]
    print(f"Lanthanide side: {len(lanthanide)} distinct loops read off "
          f"coordinates ({', '.join(STRUCTURES)})")
    print(f"                 plus {len(structural_ca)} Ca-bound loops from the "
          f"same structures, as a within-crystal control\n")

    composition(truth)

    print(f"\n  {'detector':22s} {'Ca recall':>10} {'Ln recall':>10} "
          f"{'gap':>7} {'matches/loop':>13}")
    for label, pattern in CANDIDATES.items():
        found, total = recall_at_position(pattern, calcium, truth)
        ca = found / total
        ln = sum(1 for loop in lanthanide if pattern.fullmatch(loop)) / len(lanthanide)
        print(f"  {label:22s} {ca:10.1%} {ln:10.1%} {ln - ca:+7.1%} "
              f"{precision_proxy(pattern, calcium, truth):13.2f}")

    print("\nA detector for MEASURING loop properties wants the gap near zero")
    print("AND matches/loop near 1. Recall bought with permissiveness is not")
    print("balance -- it relocates the bias into false positives, which is")
    print("worse, because spacing between spurious hits looks like data.")
    print("The shipped classifier wants the gap LARGE: that is what makes it")
    print("discriminate. Two instruments, opposite objectives, never swapped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
