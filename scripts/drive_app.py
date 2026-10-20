"""Drive the whole page the way a user does, and report what rendered.

Not a test: it needs a configured gateway and ~25 s of network. The offline
guarantees are covered by tests/test_discover.py. This exists because the app
is the product, and the only way to know the question box, the tabs, the
viewer and the narration still work together is to click them.

    .venv/bin/python scripts/drive_app.py ["a question"] [--live]

--live flips the sidebar toggle, which is the path that reaches UniProt and
RCSB. Worth driving separately: the offline path reads structures from the
bundled cache, so it cannot tell you whether a searched protein arrives with
a structure attached to it.
"""
import pathlib
import sys

from dotenv import load_dotenv
from streamlit.testing.v1 import AppTest

# AppTest resolves a relative path against the file that calls it, not the
# working directory, so this script would otherwise look for scripts/app.py.
APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")

ARGS = [a for a in sys.argv[1:] if a != "--live"]
LIVE = "--live" in sys.argv
QUESTION = ARGS[0] if ARGS else "what proteins should I try for capturing Ce3+"
FINISHED = ".!?)*`\"'"


def main() -> int:
    load_dotenv()
    app = AppTest.from_file(APP, default_timeout=300).run()

    print(f"live search: {LIVE}")
    if LIVE:
        app.toggle[0].set_value(True).run()

    app.text_input(key="question").set_value(QUESTION).run()
    app.button[0].click().run()
    if app.exception:
        for err in app.exception:
            print("EXCEPTION:", err.value)
        return 1

    record = app.session_state["record"]
    print(f"question   : {QUESTION}")
    print(f"answered   : {record['answered']}  target={record['plan']['target']}"
          f"  parsed_by={record['plan']['parsed_by']}")
    print(f"shortlist  : {record['shortlist']['selected_count']}"
          f" of {record['shortlist']['considered']}")
    print(f"evidence   : {len(record['evidence'])} structure(s), "
          f"{sum(e['site_count'] for e in record['evidence'])} site(s)")
    for ev in record["evidence"]:
        choice = ev.get("structure_choice")
        print(f"  {ev['accession']:12} {ev['structure_kind']:9} "
              f"{ev.get('pdb_id') or '—':6} {ev['site_count']:2} site(s)"
              + (f"  (chose 1 of {len(choice['deposited'])} deposited)"
                 if choice else ""))
    print(f"rendered   : {len(app.tabs)} tab(s), {len(app.dataframe)} table(s), "
          f"{len(app.selectbox)} selectbox(es)")

    for box in app.selectbox:
        # Each must format with its own structure's labels; a stale closure
        # here silently labelled one structure's sites with another's.
        print(f"  {box.label:9} -> {box.format_func(box.value)!r}")

    summarise = [b for b in app.button if "Summarise" in b.label]
    if not summarise or summarise[0].disabled:
        print("narration  : skipped (no provider configured)")
        return 0

    summarise[0].click().run()
    if app.exception:
        for err in app.exception:
            print("EXCEPTION:", err.value)
        return 1

    text = app.session_state.get("narration", "")
    errors = [e.value for e in app.error]
    print(f"narration  : {len(text)} chars, "
          f"ends_cleanly={bool(text) and text.rstrip()[-1] in FINISHED}, "
          f"truncated={'truncated' in text}")
    print(f"disclaimer : {any('written by a language model' in str(c.value) for c in app.caption)}")
    print(f"page errors: {errors or 'none'}")
    return 1 if errors or not text else 0


if __name__ == "__main__":
    raise SystemExit(main())
