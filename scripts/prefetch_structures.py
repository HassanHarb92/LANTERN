#!/usr/bin/env python3
"""Cache the demo structures locally so the app runs without a network.

Downloads the three structures the reference set points at and writes a
manifest with a SHA-256 per file. Files are stored verbatim as RCSB serves
them; nothing is edited, so the checksums are meaningful.

Usage:  python scripts/prefetch_structures.py
"""
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reefinder.structure import STRUCTURE_CACHE, fetch_structure  # noqa: E402

WANTED = {
    "8FNS": "Lanmodulin (M. extorquens, C5B164) with Nd3+; CN 9-10",
    "8FNR": "Lanmodulin (H. quercus, A0A4V2JDD3) with Dy3+; CN 9",
    "1CLL": "Calmodulin (human, P0DP23) with Ca2+; CN 7 -- the contrast set",
}


def main() -> int:
    STRUCTURE_CACHE.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for code, description in WANTED.items():
        # use_cache=False so re-running actually refreshes rather than
        # re-reading what is already on disk.
        text, fmt = fetch_structure(code, timeout=60, use_cache=False)
        path = STRUCTURE_CACHE / f"{code}.{fmt}"
        path.write_text(text)
        digest = hashlib.sha256(text.encode()).hexdigest()
        manifest[code] = {"file": path.name, "format": fmt,
                          "sha256": digest, "description": description,
                          "bytes": len(text)}
        print(f"  {code}  {fmt}  {len(text):>9,} bytes  {digest[:16]}...")

    (STRUCTURE_CACHE / "manifest.json").write_text(json.dumps({
        "_provenance": {
            "description": "Verbatim RCSB downloads cached for offline demo use.",
            "source": "https://files.rcsb.org/download/",
            "retrieved": date.today().isoformat(),
        },
        "structures": manifest,
    }, indent=2) + "\n")
    print(f"\nCached {len(manifest)} structures in {STRUCTURE_CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
