"""Every askable question, answered offline and written to results/.

The app answers one question at a time, in a browser, on one person's
machine. That is the wrong medium for a result somebody else has to check:
a collaborator cannot rerun a Streamlit session from a screenshot, and a
reviewer cannot diff one. So the same records the page draws are written to
disk here, committed, and rendered by GitHub.

Two formats, because they have two readers:

  results/<ion>.json  the full exportable record -- every measurement,
                      verdict, caveat and basis, exactly what the page's
                      download button produces. This is the artifact to
                      check, cite or diff.
  results/README.md   one table GitHub renders when anyone opens the folder,
                      so the headline answer for all fifteen lanthanides is
                      visible without cloning anything or running Python.

Deterministic by construction: `answer(live=False)` reads only bundled data
and the structure cache, and the records carry no timestamps, so rerunning
this on unchanged code and unchanged data produces byte-identical JSON. A
diff in results/ therefore means a real change in what the platform claims,
which is the only property that makes committing generated files worth it.
The one timestamp lives in results/_provenance.json, alone, so it cannot
churn the fifteen files that matter.

Run:  .venv/bin/python scripts/export_results.py [--ion Eu3+] [--check]
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lantern.catalog import structure_search  # noqa: E402
from lantern.discover import answer, exportable  # noqa: E402
from lantern.geometry import SCORE_VERSION  # noqa: E402
from lantern.ions import LANTHANIDES_III  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

QUESTION = "what proteins should I try for capturing {ion}"


def _git(*args: str) -> str:
    try:
        out = subprocess.run(("git", *args), cwd=ROOT, capture_output=True,
                             text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:                                   # noqa: BLE001
        return "unknown"


def _nothing_found(ion: str) -> str:
    """Which kind of "no" this is, taken from the build's own counters.

    "No structure holds this ion" and "every deposited structure holding it
    was measured and none was a protein site" are different answers, and a
    third exists: the walk stopped at its cap before exhausting the index.
    The counters that tell them apart live in the build record, so they are
    read from there rather than inferred from how many entries exist -- an
    element with more entries than the cap would otherwise be reported as
    fully measured when it was not.
    """
    search = structure_search(ion)
    if search is None:
        return "not searched"
    tried, indexed = search["entries_tried"], search["entries_in_index"]
    if not indexed:
        return "nothing holding it is deposited"
    if tried < indexed:
        return (f"{tried} of {indexed} deposited entries measured "
                f"(cap {search['limit']}), none is a protein site")
    return (f"all {indexed} deposited entries measured, "
            f"none is a protein site")


def _ion_row(ion: str, record: dict) -> dict:
    """The one line of this ion's answer that belongs in a summary table.

    Every structural column describes the structure(s) actually shown for
    this ion, never the run as a whole, so the resolution and the site count
    in a row cannot belong to a different entry than the one named beside
    them.
    """
    report = record["ion_report"]
    own = record.get("ion_structure")

    # What the reader wants to know first: did this page show them their own
    # atom, and if not, which kind of "no" is it?
    if report["verdict_kind"] == "observed":
        holding = [ev for ev in record["evidence"]
                   if ev["pdb_id"] in report["structures_holding_the_target"]]
        sharpest = min(holding, key=lambda ev: ev["resolution_A"] or 99)
        shown = ", ".join(ev["pdb_id"] for ev in holding)
        basis = "in the screened corpus"
        held = sum(ev["sites_holding_the_target"] for ev in holding)
        resolution, title = sharpest["resolution_A"], sharpest["name"]
    elif own:
        shown, basis = own["pdb_id"], "found by element lookup, not a candidate"
        held = own["sites_holding_the_target"]
        resolution, title = own["resolution_A"], own["title"]
    else:
        shown, basis = "--", _nothing_found(ion)
        held, resolution, title = 0, None, None

    return {
        "ion": ion,
        "element": report["element"],
        "name": report["name"],
        "verdict": report["verdict_kind"],
        "structure_shown": shown,
        "how": basis,
        "sites_holding_the_ion": held,
        "resolution_A": resolution,
        "title": title,
        "passes_every_rule": record["shortlist"]["selected_count"],
        "considered": record["shortlist"]["considered"],
    }


def _readme(rows: list[dict], provenance: dict) -> str:
    """The page GitHub shows when someone opens results/."""
    # The design rules are sequence rules and fire identically for every
    # trivalent lanthanide, so the shortlist is expected to be the same for
    # all fifteen -- but the sentence saying so is checked against the rows
    # instead of asserted, because it stops being true the moment a rule
    # starts reading the ion.
    passing = {(r["passes_every_rule"], r["considered"]) for r in rows}
    if len(passing) == 1:
        selected, considered = passing.pop()
        rules = (f"All {len(rows)} share the same {selected} of {considered} "
                 f"design-rule candidates: the rules are sequence rules and "
                 f"fire identically for every trivalent lanthanide. That "
                 f"column is therefore not a result about the ion, and is "
                 f"left out below. Only the structure columns differ.")
    else:
        rules = ("The design-rule shortlist differs between these ions. It "
                 "is built from sequence rules that do not read the ion, so "
                 "this is unexpected and worth checking: "
                 + ", ".join(f"{r['ion']} {r['passes_every_rule']}/"
                             f"{r['considered']}" for r in rows))
    lines = [
        "# Results",
        "",
        "Every question this platform can be asked, answered offline and "
        "written out so it can be read, checked and diffed without running "
        "anything.",
        "",
        "**Generated** by `scripts/export_results.py`. Do not edit by hand -- "
        "rerun it. The JSON beside this file is the artifact to cite; this "
        "table is only its headline.",
        "",
        f"- code: `{provenance['commit']}` on `{provenance['branch']}`",
        f"- geometry: `{provenance['score_version']}`",
        f"- generated: {provenance['generated_at_utc']}",
        "",
        "## What each column means",
        "",
        "| column | meaning |",
        "| --- | --- |",
        "| **Structure shown** | the deposited entry on the page that holds "
        "the ion asked about, if any |",
        "| **How** | why that structure is there -- the design rules reached "
        "it, or an element lookup did |",
        "| **Sites** | measured metal sites holding that element, in the "
        "structure(s) named beside them |",
        "| **Res / Protein** | of the sharpest structure shown |",
        "",
        rules,
        "",
        "## Answers",
        "",
        "| Ion | Structure shown | How | Sites | Res (Å) | Protein |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        res = r["resolution_A"] if r["resolution_A"] is not None else ""
        title = (r["title"] or "")[:54]
        lines.append(
            f"| **{r['ion']}** | {r['structure_shown']} | {r['how']} | "
            f"{r['sites_holding_the_ion']} | {res} | {title} |")

    shown = sum(1 for r in rows if r["structure_shown"] != "--")
    lines += [
        "",
        f"{shown} of {len(rows)} show a deposited structure holding the ion "
        f"asked about. The rest say which kind of nothing they are: an "
        f"element with no deposited structure anywhere is a different answer "
        f"from one whose every deposited entry was measured and turned out "
        f"to be a soaked chelate the protein never coordinates.",
        "",
        "## Reproducing",
        "",
        "```sh",
        ".venv/bin/python scripts/export_results.py --check",
        "```",
        "",
        "`--check` regenerates every record in memory and fails if it differs "
        "from what is committed here. It needs no network: the answers read "
        "bundled data and the cached coordinates under `data/structures/`. "
        "A difference means the platform's claims changed, and the diff says "
        "how.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ion", action="append",
                        help="restrict to these ions (repeatable)")
    parser.add_argument("--check", action="store_true",
                        help="verify committed results match, write nothing")
    args = parser.parse_args()

    ions = args.ion or list(LANTHANIDES_III)
    RESULTS.mkdir(exist_ok=True)

    rows, stale = [], []
    for ion in ions:
        record = exportable(answer(QUESTION.format(ion=ion), live=False))
        text = json.dumps(record, indent=2, default=str, sort_keys=True) + "\n"
        path = RESULTS / f"{ion.replace('+', '')}.json"

        if args.check:
            current = path.read_text() if path.exists() else None
            if current != text:
                stale.append(path.name)
        else:
            path.write_text(text)
        rows.append(_ion_row(ion, record))
        mark = rows[-1]["structure_shown"]
        print(f"{ion:5} -> {mark}", flush=True)

    provenance = {
        "description": (
            "Answers generated offline by scripts/export_results.py. Each "
            "<ion>.json is the full record the app's download button "
            "produces: every measurement, verdict, caveat and basis, with "
            "coordinates and per-atom donor lists left out. Regenerating on "
            "unchanged code and data is byte-identical, so a diff here is a "
            "change in what the platform claims."),
        "generated_by": "scripts/export_results.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "commit": _git("rev-parse", "--short", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "score_version": SCORE_VERSION,
        "question_template": QUESTION,
        "live": False,
        "ions": len(rows),
    }

    if args.check:
        # The README carries the same numbers, so it is checked too -- minus
        # the provenance header, which holds the one value that moves on its
        # own. Checking it as a whole would fail on every rerun and teach
        # everyone to ignore the check.
        committed = (RESULTS / "README.md")
        want = _readme(rows, {**provenance, "commit": "", "branch": "",
                              "generated_at_utc": ""})
        moves = ("- code:", "- generated:")
        have = committed.read_text() if committed.exists() else ""
        have = "\n".join(ln for ln in have.splitlines()
                         if not ln.startswith(moves))
        want = "\n".join(ln for ln in want.splitlines()
                         if not ln.startswith(moves))
        if have.strip() != want.strip():
            stale.append("README.md")
        if stale:
            print(f"\nSTALE: {', '.join(stale)}")
            print("Run scripts/export_results.py to regenerate.")
            return 1
        print(f"\nall {len(rows)} committed results match")
        return 0

    (RESULTS / "README.md").write_text(_readme(rows, provenance))
    (RESULTS / "_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n")
    print(f"\nwrote {len(rows)} records, README.md and _provenance.json "
          f"to {RESULTS.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
