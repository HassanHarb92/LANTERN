#!/usr/bin/env python3
"""Download Corpus A -- the 636 rare-earth-containing PDB entries -- as
gzipped mmCIF, resumably.

FORMAT CHOICE, measured rather than assumed. The roadmap suggested BinaryCIF
(`models.rcsb.org/{ID}.bcif`) as "much smaller than mmCIF", which is true only
against *uncompressed* mmCIF. Measured over the wire on 2026-10-19:

    entry   bcif (--compressed)   cif.gz     verdict
    8FNS           52,461         59,183     bcif 11% smaller
    1CLL           37,612         46,563     bcif 19% smaller
    6EK0              404!      5,044,832    bcif absent for large entries

So BinaryCIF buys about 15% of bandwidth, costs a new dependency (msgpack,
which this venv does not have), and 404s on exactly the large entries that
motivated moving off the legacy `.pdb` endpoint in the first place. Gzipped
mmCIF needs nothing new and `MMCIFParser` reads it through `gzip.open`.

WHERE IT LANDS, and why not `data/`. The corpus goes to `.cache/corpus/`,
which is gitignored. `data/structures/` holds five hand-picked entries that
are *meant* to be committed, so tests run offline; 636 more would be a few
hundred megabytes of downloaded third-party coordinates in version control.
It is also its own directory containing nothing but downloaded files, which
is where untrusted input belongs.

Usage:
    python -I scripts/download_corpus.py                 # all 636, resumable
    python -I scripts/download_corpus.py --limit 20      # a sample first
    python -I scripts/download_corpus.py --out DIR
"""
import argparse
import hashlib
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests                                           # noqa: E402

ENUMERATION = ROOT / "data" / "ree_pdb_entries.json"
DEFAULT_OUT = ROOT / ".cache" / "corpus"
URL = "https://files.rcsb.org/download/{pdb_id}.cif.gz"

# Six at a time is brisk without being rude: RCSB serves this endpoint from a
# CDN, but 636 simultaneous connections would be abuse whether or not it
# survived them.
WORKERS = 6
ATTEMPTS = 3
TIMEOUT = 60
USER_AGENT = "REE-Finder/0.1 (research; contact via repository)"

_print_lock = threading.Lock()


def entry_ids(enumeration: Path = ENUMERATION) -> list[str]:
    payload = json.loads(enumeration.read_text())
    return sorted(payload["entries"])


def fetch_one(session: requests.Session, pdb_id: str, out_dir: Path) -> dict:
    """Download one entry, or report why not. Never raises."""
    target = out_dir / f"{pdb_id}.cif.gz"
    if target.exists() and target.stat().st_size > 0:
        body = target.read_bytes()
        return {"pdb_id": pdb_id, "status": "cached", "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest()}

    last = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = session.get(URL.format(pdb_id=pdb_id), timeout=TIMEOUT)
            if response.status_code == 404:
                return {"pdb_id": pdb_id, "status": "missing", "http": 404}
            response.raise_for_status()
            body = response.content
            if not body:
                raise ValueError("empty body")
            # Written whole, then moved: a half-written file left by an
            # interrupted run would otherwise look cached on the next one and
            # be skipped forever.
            temporary = target.with_suffix(".part")
            temporary.write_bytes(body)
            temporary.replace(target)
            return {"pdb_id": pdb_id, "status": "downloaded", "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest()}
        except Exception as error:                        # noqa: BLE001
            last = f"{type(error).__name__}: {error}"
            if attempt < ATTEMPTS:
                time.sleep(2 ** attempt)
    return {"pdb_id": pdb_id, "status": "failed", "error": last}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None,
                        help="download only the first N entries (sampling)")
    # The matched-calcium counterparts are a second corpus in the same
    # shape. They must land in their own empty directory, so --out and
    # --enumeration are set together or not at all.
    parser.add_argument("--enumeration", type=Path, default=ENUMERATION,
                        help="JSON with an 'entries' mapping of PDB IDs")
    args = parser.parse_args()

    ids = entry_ids(args.enumeration)
    if args.limit:
        ids = ids[:args.limit]
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"{len(ids)} entries -> {args.out}")

    results, started = [], time.time()
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_one, session, i, args.out): i for i in ids}
        for done, future in enumerate(as_completed(futures), start=1):
            record = future.result()
            results.append(record)
            if done % 50 == 0 or done == len(ids):
                with _print_lock:
                    rate = done / max(time.time() - started, 1e-9)
                    print(f"  {done}/{len(ids)}  ({rate:.1f}/s)")

    by_status = {}
    for record in results:
        by_status.setdefault(record["status"], []).append(record["pdb_id"])
    manifest = {
        "_provenance": {
            "source": URL,
            "format": "gzipped mmCIF (see module docstring for why not bcif)",
            "retrieved": time.strftime("%Y-%m-%d"),
            "entries_requested": len(ids),
            "enumeration": str(args.enumeration.relative_to(ROOT)
                               if args.enumeration.is_relative_to(ROOT)
                               else args.enumeration),
            "curation_status": "uncurated -- raw deposited coordinates",
        },
        "counts": {k: len(v) for k, v in sorted(by_status.items())},
        "entries": {r["pdb_id"]: r for r in sorted(results, key=lambda r: r["pdb_id"])},
    }
    (args.out / "_manifest.json").write_text(json.dumps(manifest, indent=2))

    print("\n" + "  ".join(f"{k}={len(v)}" for k, v in sorted(by_status.items())))
    total = sum(r.get("bytes", 0) for r in results)
    print(f"{total / 1e6:.1f} MB on disk, manifest written to "
          f"{(args.out / '_manifest.json').relative_to(ROOT)}")
    for status in ("failed", "missing"):
        if by_status.get(status):
            print(f"  {status}: {', '.join(sorted(by_status[status])[:20])}"
                  f"{' ...' if len(by_status[status]) > 20 else ''}")
    return 1 if by_status.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
