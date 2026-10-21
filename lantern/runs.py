"""Every run this platform answers, kept so it can be opened again.

An answer used to live for exactly as long as the browser tab did. Ask a
second question and the first was gone -- not archived, not summarised,
gone -- so nothing could be compared against it, no colleague could be sent
it, and the only record that a run ever happened was a screenshot. This
module is the archive that fixes that: every answered run is written to
`results/runs/`, where it can be reopened in the app, diffed, and pushed to
GitHub for people who will never run the code.

What is stored is `exportable(record)` -- every measurement, verdict, caveat
and basis -- plus the question, the settings it was answered under, and the
narration if one was generated. Coordinates and per-atom donor lists are the
two things left out, because they are megabytes of picture and they are
already on disk in `data/structures/`. `rehydrate()` puts them back by
re-measuring the cached file, so a reopened run draws the same viewer as a
live one.

Runs are keyed by what was asked, not by when: asking the same question
under the same settings updates that run in place rather than growing a
third copy of it. A click is not a result, and an archive that counts
clicks buries the fifteen answers that matter under five hundred that do
not. `times_answered` keeps the count that is actually interesting.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .discover import exportable, headline
from .structure import ALL_METAL_CODES, binding_neighborhood, cached_structure

# Where the archive lives, and how to send it somewhere else. The override
# exists so a test run cannot write into the committed archive -- a suite
# that archives its own fixtures would rewrite the repository every time it
# passed -- and so a deployment can keep its runs outside the checkout.
# Read on every call rather than at import, because the tests that rely on
# it set it after this module is already loaded.
RUNS_ENV = "LANTERN_RUNS_DIR"
DEFAULT_RUNS_DIR = Path(__file__).resolve().parent.parent / "results" / "runs"


def runs_dir() -> Path:
    return Path(os.environ.get(RUNS_ENV) or DEFAULT_RUNS_DIR)


def index_path() -> Path:
    return runs_dir() / "index.json"

# The settings that change an answer. A run keyed without these would let a
# live-search result silently overwrite the offline one it disagrees with,
# which is the one comparison most worth keeping.
SETTING_KEYS = ("live", "allow_predictions", "max_structures")

# Why a reopened run may show its numbers but not its viewer. Displayed
# verbatim; the alternative is drawing a structure the saved measurements
# were never taken from.
COORDINATES_ARE_NOT_IN_THE_RUN = (
    "The 3D view is drawn from the coordinate file on disk, not from the "
    "saved run -- coordinates are too large to archive per run. Where the "
    "file is missing from the cache, or where re-measuring it no longer "
    "reproduces the sites that were saved, the view is withheld and the "
    "saved numbers are shown alone.")


def run_id(question: str, settings: dict) -> str:
    """A stable name for "this question under these settings"."""
    stamp = json.dumps({"question": " ".join(question.lower().split()),
                        **{k: settings.get(k) for k in SETTING_KEYS}},
                       sort_keys=True)
    return hashlib.sha256(stamp.encode()).hexdigest()[:12]


def _summary(run: dict) -> dict:
    """The part of a run that the browser's list needs, and nothing more.

    Kept small deliberately: the list renders from the index alone, so
    opening the browser costs one small read rather than a parse of every
    archived record.
    """
    record = run["record"]
    report = record.get("ion_report") or {}
    own = record.get("ion_structure")
    structures = [ev["pdb_id"] for ev in record.get("evidence", [])
                  if ev.get("pdb_id")]
    return {
        "id": run["id"],
        "question": run["question"],
        "origin": run.get("origin", "app"),
        "target": (record.get("plan") or {}).get("target"),
        "answered": record.get("answered", False),
        "headline": run["headline"],
        "verdict_kind": report.get("verdict_kind"),
        "sites_holding_the_target": report.get("sites_holding_the_target", 0),
        "candidates": (record.get("shortlist") or {}).get("selected_count", 0),
        "structures": structures,
        "ion_structure": (own or {}).get("pdb_id"),
        "narrated": bool(run.get("narration")),
        "first_answered": run["first_answered"],
        "last_answered": run["last_answered"],
        "times_answered": run["times_answered"],
        "settings": run["settings"],
    }


def save(record: dict, question: str, settings: dict,
         narration: str | None = None, origin: str = "app") -> dict:
    """Archive one answered run and return its summary.

    Re-answering a question it has seen keeps the first timestamp and bumps
    the count, so the archive says how often a question was asked without
    keeping a file per asking.

    `origin="seed"` is for runs generated in bulk by a script rather than
    asked by a person. A seeded run whose measurements have not changed is
    left on disk exactly as it was: nobody asked it a second time, so there
    is no count to bump and no time to record, and rewriting the timestamp
    anyway would put fifteen meaningless lines in every diff and bury the
    one line where an answer actually moved.
    """
    directory = runs_dir()
    directory.mkdir(parents=True, exist_ok=True)
    identifier = run_id(question, settings)
    path = directory / f"{identifier}.json"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    previous = {}
    if path.exists():
        try:
            previous = json.loads(path.read_text())
        except json.JSONDecodeError:
            previous = {}

    payload = exportable(record)
    unchanged = (previous.get("record") == json.loads(
        json.dumps(payload, default=str))
        and previous.get("narration") == narration)
    if origin == "seed" and unchanged and previous:
        return _summary(previous)

    run = {
        "id": identifier,
        "question": question,
        "origin": origin,
        "settings": {k: settings.get(k) for k in SETTING_KEYS},
        "first_answered": previous.get("first_answered", now),
        "last_answered": previous.get("last_answered", now) if (
            origin == "seed" and unchanged) else now,
        "times_answered": (previous.get("times_answered", 1) if origin == "seed"
                           else previous.get("times_answered", 0) + 1),
        "headline": headline(record),
        # A narration belongs to the run that produced it. Carrying the old
        # one forward would caption new measurements with a model's reading
        # of the previous ones.
        "narration": narration,
        "record": payload,
    }
    path.write_text(json.dumps(run, indent=2, default=str, sort_keys=True)
                    + "\n")
    summary = _summary(run)
    _write_index({**{s["id"]: s for s in _scan_index()}, identifier: summary})
    return summary


def _scan_index() -> list[dict]:
    if not index_path().exists():
        return []
    try:
        return json.loads(index_path().read_text()).get("runs", [])
    except json.JSONDecodeError:
        return []


def _write_index(by_id: dict) -> None:
    runs = sorted(by_id.values(), key=lambda s: s["last_answered"], reverse=True)
    index_path().write_text(json.dumps(
        {"description": ("One line per archived run. Derived from the run "
                         "files beside it and rebuilt automatically when "
                         "they disagree, so it is a cache and never the "
                         "record of truth."),
         "runs": runs}, indent=2, default=str) + "\n")


def index(*, rebuild: bool = False) -> list[dict]:
    """Every archived run, newest first.

    Self-healing: the cached index is trusted only while it names exactly
    the runs on disk. A file copied in from a colleague's branch, or one
    deleted by hand, rebuilds it rather than being invisible.
    """
    directory = runs_dir()
    if not directory.exists():
        return []
    on_disk = {p.stem for p in directory.glob("*.json")
               if p.stem != "index"}
    cached = _scan_index()
    if not rebuild and {s["id"] for s in cached} == on_disk:
        return cached

    summaries = {}
    for identifier in sorted(on_disk):
        run = load(identifier)
        if run:
            summaries[identifier] = _summary(run)
    _write_index(summaries)
    return sorted(summaries.values(), key=lambda s: s["last_answered"],
                  reverse=True)


def load(identifier: str) -> dict | None:
    path = runs_dir() / f"{identifier}.json"
    if not path.exists():
        return None
    try:
        run = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return run if isinstance(run, dict) and "record" in run else None


def _identity(chain, site, element) -> tuple:
    """How a saved site and a freshly measured one are matched.

    Chain, label and element rather than position in the list: the order is
    deterministic today, but a parser change that renumbered sites would
    otherwise pair every saved measurement with the wrong shell and draw it
    without complaint. The raw sites call this field `element` and the saved
    ones `deposited_element`, which is the whole reason this is a function.
    """
    return chain, site, (element or "").upper()


def rehydrate(record: dict) -> dict:
    """Put the coordinates and donor atoms back, from the cache on disk.

    Returns a copy of `record` in which every deposited structure whose file
    is cached carries `coordinates` and per-site `raw` again, so a saved run
    draws the same viewer the live one did. A structure that cannot be
    restored is marked `viewer_unavailable` with the reason rather than being
    dropped: its measurements are still the archive's, and only the picture
    is missing.

    Nothing measured is taken from the re-measurement. The archived numbers
    are the answer and they stay; this pass re-reads the coordinate file for
    the donor geometry the viewer needs, and hands it over only for sites it
    can match to a saved one. `binding_neighborhood` rather than the full
    evidence builder because it is the minimal path -- it recovers exactly
    what `exportable` removed, without recomputing verdicts the record
    already holds and without a chance of disagreeing with them.
    """
    restored = dict(record)

    def restore(item: dict) -> dict:
        pdb_id = item.get("pdb_id")
        if not pdb_id or item.get("structure_kind") != "deposited":
            return item
        try:
            found = cached_structure(pdb_id)
        except ValueError:
            return {**item, "viewer_unavailable":
                    f"{pdb_id!r} is not a well-formed PDB identifier."}
        if found is None:
            return {**item, "viewer_unavailable":
                    f"{pdb_id} is not in the local structure cache, so the "
                    f"3D view cannot be drawn for it here."}
        text, fmt = found
        try:
            # The same metal table the measurement used. The default omits
            # calcium, which would drop those sites and leave every later
            # site matched against the wrong shell.
            fresh = binding_neighborhood(text, fmt, metals=ALL_METAL_CODES)
        except Exception as exc:                        # noqa: BLE001
            return {**item, "viewer_unavailable":
                    f"{pdb_id} could not be re-measured ({type(exc).__name__})."}

        by_identity = {_identity(r.get("chain"), r.get("site"),
                                 r.get("element")): r for r in fresh}
        saved = item.get("sites", [])
        matched = [by_identity.get(_identity(s.get("chain"), s.get("site"),
                                             s.get("deposited_element")))
                   for s in saved]
        if any(m is None for m in matched):
            return {**item, "viewer_unavailable":
                    f"Re-measuring {pdb_id} no longer reproduces "
                    f"{sum(m is None for m in matched)} of the {len(saved)} "
                    f"site(s) saved with this run, so the view is withheld."}
        return {**item, "coordinates": (text, fmt),
                "sites": [{**site, "raw": raw}
                          for site, raw in zip(saved, matched)]}

    restored["evidence"] = [restore(ev) for ev in record.get("evidence", [])]
    if record.get("ion_structure"):
        restored["ion_structure"] = restore(record["ion_structure"])
    return restored
