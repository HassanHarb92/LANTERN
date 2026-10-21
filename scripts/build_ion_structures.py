"""One deposited structure per lanthanide, chosen by measuring candidates.

The question "which proteins should I try for capturing Eu3+" and the question
"show me Eu3+ in a protein" are different, and until now this platform could
only answer the first. The design rules are architecture rules: they fire the
same for every lanthanide, so they return lanmodulins, and the only lanmodulin
coordinates deposited anywhere hold Y, La, Nd or Dy. Ask about the other
eleven and every number on the page was measured on somebody else's ion.

This script answers the second question offline. For each trivalent lanthanide
it walks the rare-earth entry index sharpest first and measures candidates with
the same geometry code the rest of the platform uses, keeping the first entry
that has a site of that element which the platform calls a real protein site.

The admission test is a measurement, not a judgement, and that is the whole
point. Most entries holding a lanthanide hold it as a soaked phasing
derivative -- the metal sits in a synthetic chelate that crystallographers add
to get anomalous signal, and the protein coordinates none of it. 4BAR is the
canonical case: thaumatin with a europium tris-dipicolinate complex at 1.2 A,
the sharpest Eu entry in the index, and geometry-v2 reads its Eu site as CN 9
with *zero protein donors* and calls it `not callable`. 6FKW, europium-bound
methanol dehydrogenase at 1.4 A, reads CN 9 with six protein donors and calls
it `lanthanide-like`. Sorting on resolution alone takes the thaumatin; adding
"and the protein has to be holding it" takes the dehydrogenase. No title
keyword, no hand-picked list, nothing a later curator has to agree with.

Writes data/ion_structures.json and caches the chosen coordinates under
data/structures/ so the app needs no network. Rejections are recorded with
the measurement that rejected them, because a reader has to be able to ask
why the sharpest entry was passed over.

Run:  .venv/bin/python scripts/build_ion_structures.py [--limit N] [--ion Eu3+]
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lantern.catalog import entries_holding  # noqa: E402
from lantern.discover import _structure_evidence  # noqa: E402
from lantern.ions import LANTHANIDES_III  # noqa: E402
from lantern.structure import STRUCTURE_CACHE, fetch_structure  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "ion_structures.json"

# How far down the index to look before giving up on an element. Gd has 179
# entries and most of them are lysozyme and thaumatin derivatives, so the
# walk has to be allowed to go well past the sharpest few; it also has to
# stop, because a cap that is never reached is not a cap. Recorded in the
# output either way, so "nothing found" can be told from "stopped looking".
DEFAULT_LIMIT = 30

# What makes a site count as the protein holding the ion rather than the
# crystallographer. Both halves are read straight off geometry-v2: the call
# is its verdict, and call_reliable is its own statement about whether the
# resolution supports making one. A site failing either is not evidence of
# anything about this element and must not be shown as if it were.
ADMITTED_CALL = "lanthanide-like"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _admissible(sites: list[dict]) -> list[dict]:
    """The sites of this ion that this platform is willing to call real.

    "Is this the ion asked for" is read off the site's own counterfactual
    flag rather than re-compared here, so the build and the page cannot
    drift: that flag already knows a YB2 site is ytterbium(II) and does not
    answer a Yb3+ question, and a second element-string comparison in this
    file would not.
    """
    return [s for s in sites
            if not s["size_match_is_counterfactual"]
            and s["call"] == ADMITTED_CALL and s["call_reliable"]]


def prospect(ion: str, limit: int, timeout: int, pause: float) -> dict:
    """Measure index entries holding `ion`'s element until one is admitted."""
    element = "".join(c for c in ion if c.isalpha()).capitalize()
    candidates = entries_holding(element)
    record = {"ion": ion, "element": element,
              "entries_in_index": len(candidates),
              "entries_tried": 0, "limit": limit,
              "chosen": None, "rejected": []}

    for entry in candidates[:limit]:
        record["entries_tried"] += 1
        pdb_id = entry["id"]
        try:
            text, fmt = fetch_structure(pdb_id, timeout=timeout)
        except Exception as exc:                       # noqa: BLE001
            record["rejected"].append({"id": pdb_id, "why": "not retrievable",
                                       "detail": f"{type(exc).__name__}"})
            continue
        try:
            evidence = _structure_evidence(ion, text, fmt, pdb_id)
        except Exception as exc:                       # noqa: BLE001
            record["rejected"].append({"id": pdb_id, "why": "not measurable",
                                       "detail": f"{type(exc).__name__}"})
            continue

        of_element = [s for s in evidence["sites"]
                      if (s["deposited_element"] or "").capitalize() == element]
        admitted = _admissible(evidence["sites"])
        if not admitted:
            # Why it failed, in the platform's own words, so the rejection is
            # as checkable as the acceptance.
            worst = of_element[0] if of_element else None
            record["rejected"].append({
                "id": pdb_id,
                "why": ("no site of this element" if not of_element
                        else "site is not a protein site"),
                "detail": (None if worst is None else
                           f"CN {worst['coordination_number']}, "
                           f"{worst['protein_donors']} protein donor(s), "
                           f"call {worst['call']}, "
                           f"reliable {worst['call_reliable']}"),
                "resolution_A": entry["resolution_A"], "title": entry["title"]})
            if pause:
                time.sleep(pause)
            continue

        path = STRUCTURE_CACHE / f"{pdb_id}.{fmt}"
        path.write_text(text)
        record["chosen"] = {
            "id": pdb_id, "file": path.name, "format": fmt,
            "bytes": len(text.encode()), "sha256": _sha256(text),
            "resolution_A": evidence["resolution_A"],
            "title": entry["title"], "method": entry["method"],
            "sites_of_this_element": len(of_element),
            "sites_admitted": len(admitted),
            "coordination_numbers": sorted({s["coordination_number"]
                                            for s in admitted}),
            "mean_donor_distance_A": round(
                sum(s["mean_donor_distance_A"] for s in admitted)
                / len(admitted), 2),
            "protein_donors": sorted({s["protein_donors"] for s in admitted}),
        }
        return record
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help="index entries to try per ion")
    parser.add_argument("--ion", action="append",
                        help="restrict to these ions (repeatable)")
    parser.add_argument("--timeout", type=int, default=40)
    parser.add_argument("--pause", type=float, default=0.3,
                        help="seconds between RCSB requests")
    args = parser.parse_args()

    ions = args.ion or list(LANTHANIDES_III)
    results = {}
    for ion in ions:
        record = prospect(ion, args.limit, args.timeout, args.pause)
        results[ion] = record
        chosen = record["chosen"]
        print(f"{ion:5} tried {record['entries_tried']:3}/"
              f"{record['entries_in_index']:3}  "
              + (f"-> {chosen['id']} {chosen['resolution_A']} A, "
                 f"{chosen['sites_admitted']} site(s), CN "
                 f"{chosen['coordination_numbers']}  {chosen['title'][:48]}"
                 if chosen else "-> none admitted"), flush=True)

    payload = {
        "_provenance": {
            "description": (
                "One deposited structure per trivalent lanthanide, chosen by "
                "measuring candidates rather than by resolution or by title. "
                "A structure is admitted when it has at least one site of "
                "that element which geometry-v2 calls lanthanide-like with a "
                "reliable call, which excludes the soaked chelate complexes "
                "that make up most of the index. These are NOT design-rule "
                "candidates: nothing here was screened for the lanmodulin "
                "architecture, and being listed means only that the protein "
                "is measurably holding the element."),
            "built_by": "scripts/build_ion_structures.py",
            "admitted_call": ADMITTED_CALL,
            "entries_tried_per_ion": args.limit,
            "source": "https://files.rcsb.org/download/",
        },
        "ions": results,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
    found = sum(1 for r in results.values() if r["chosen"])
    print(f"\n{found} of {len(results)} ions have an admitted structure.")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
