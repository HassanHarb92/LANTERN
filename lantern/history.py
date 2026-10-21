"""The saved runs, reopened: every question this platform has answered.

The Ask page shows one answer and forgets it. This page is the other half:
it lists every run in the archive and lets any of them be opened again --
the proteins the design rules selected, the structures that were measured,
the metal sites inside those structures, and the same 3D view of the first
coordination shell that the live page drew.

Nothing here is recomputed. Every number shown is the number that was saved
when the question was answered, so this page is a record of what the
platform said, not a fresh run that might say something else. The one thing
rebuilt at view time is the picture: coordinates are too large to archive
per run, so the viewer re-reads the cached coordinate file and is withheld
entirely if re-measuring it no longer reproduces the sites that were saved.

Pure functions first, Streamlit only inside `render_runs`, matching
explorer.py -- the table-building and structure-collecting logic is then
testable without a browser.
"""
import json
import zlib

import pandas as pd

from .geometry import SCORE_VERSION
from .runs import COORDINATES_ARE_NOT_IN_THE_RUN, index, load, rehydrate

# Saved runs are a record of what was asked, not a dataset. A question asked
# five times is one row here, and nothing about the archive implies the runs
# in it were chosen to be representative of anything.
CAVEAT_ARCHIVE_IS_NOT_A_SURVEY = (
    "This archive is whatever has been asked, in whatever order. It is not "
    "a screen, not a sample, and counts across runs do not support a "
    "comparison between ions: an ion asked about twice appears once, and an "
    "ion nobody asked about does not appear at all.")

# The same point the live page makes, restated because this page can be
# reached without ever seeing the live one.
CAVEAT_SHORTLIST_IS_ION_INDEPENDENT = (
    "The design rules are sequence rules. They fire identically for every "
    "trivalent lanthanide, so the proteins below are the same whichever ion "
    "was asked about -- only the structural measurements differ.")


def run_table(summaries: list[dict]) -> pd.DataFrame:
    """One row per archived run, in the order the archive lists them."""
    return pd.DataFrame([{
        "Question": s["question"],
        "Ion": s["target"] or "—",
        "Holds the ion": s["ion_structure"] or (
            ", ".join(s["structures"]) if s["sites_holding_the_target"]
            else "—"),
        "Candidates": s["candidates"],
        "Structures": len(s["structures"]),
        "Asked": s["times_answered"],
        "Last answered": s["last_answered"],
        "Live search": s["settings"].get("live", False),
    } for s in summaries])


def structures_measured(summaries: list[dict]) -> set[str]:
    """Every distinct deposited entry the archive has measured.

    The ion's own structure counts. It was measured the same way a
    candidate's was and it is the entry named in most rows of the run table,
    so leaving it out puts a count of three above a column showing eleven.
    """
    return {pdb for s in summaries
            for pdb in [*s["structures"], s["ion_structure"]] if pdb}


def structures_in(record: dict) -> list[dict]:
    """The measured structures in a run, the ion's own first.

    The ion structure leads for the same reason it leads on the live page:
    somebody who asked about Eu3+ came to see europium, and it is the only
    block guaranteed to hold it. It is tagged so the detail view can keep
    saying it is not a design-rule candidate, which is the whole distinction
    the block exists to preserve.
    """
    found = []
    own = record.get("ion_structure")
    if own:
        found.append({**own, "is_candidate": False,
                      "label": f"{own['pdb_id']} — the ion itself"})
    for ev in record.get("evidence", []):
        if ev.get("structure_kind") != "deposited":
            continue
        found.append({**ev, "is_candidate": True,
                      "label": f"{ev['pdb_id']} — {ev.get('name') or ev.get('accession')}"})
    return found


def site_rows(sites: list[dict]) -> pd.DataFrame:
    """The site table, with the same columns the live page shows."""
    return pd.DataFrame([{
        "Element": s["deposited_element"], "Chain": s["chain"],
        "Site": s["site"], "CN": s["coordination_number"],
        "Mean donor distance (Å)": s["mean_donor_distance_A"],
        "Protein donors": s["protein_donors"],
        "Water donors": s["water_donors"],
        f"{SCORE_VERSION} call": s["call"],
        "Call reliable": s["call_reliable"],
    } for s in sites])


def protein_rows(shortlist: dict) -> pd.DataFrame:
    """The proteins the design rules selected, and how far each one got."""
    return pd.DataFrame([{
        "Protein": c["name"],
        "Accession": c["accession"],
        "Rules passed": f"{c['passed']} / {c['of']}",
        "Selected": c["selected"],
    } for c in shortlist.get("candidates", [])])


# ------------------------------------------------------------------- page --
def render_runs(embed) -> None:
    """Draw the saved-runs browser. `embed` is app.embed, to avoid a cycle."""
    import streamlit as st

    from .viewer import (overview_html, site_viewer_html, theme_control,
                         tmol_sources, viewer_spec)

    script_src, fallback_src = tmol_sources()

    # ttl, because unlike the corpus files this directory changes while the
    # app is running -- every question answered on the Ask page writes to it.
    @st.cache_data(show_spinner=False, ttl=5)
    def summaries() -> list[dict]:
        return index()

    @st.cache_data(show_spinner=False, ttl=5)
    def one(identifier: str) -> dict | None:
        return load(identifier)

    st.subheader("Saved runs")
    st.caption("Every question this platform has answered, kept so it can be "
               "opened again. Select a run to see the proteins it selected "
               "and the structures it measured.")

    archive = summaries()
    if not archive:
        st.info("No runs are saved yet. Ask a question on the Ask page and it "
                "will be archived here automatically.")
        return

    ions = sorted({s["target"] for s in archive if s["target"]})
    measured = structures_measured(archive)
    a, b, c = st.columns(3)
    a.metric("Runs archived", len(archive),
             help="One per distinct question and settings, not per click.")
    b.metric("Ions asked about", len(ions), help=", ".join(ions) or "none")
    c.metric("Structures measured", len(measured))

    table = run_table(archive)
    key = zlib.crc32(",".join(s["id"] for s in archive).encode())
    picked = st.dataframe(table, width="stretch", hide_index=True,
                          on_select="rerun", selection_mode="single-row",
                          key=f"viz_runs_rows_{key}")
    st.caption(CAVEAT_ARCHIVE_IS_NOT_A_SURVEY)

    rows = picked.selection.rows
    if not rows:
        st.info("Select a run above to open it.")
        return

    chosen = archive[rows[0]]
    run = one(chosen["id"])
    if run is None:
        st.warning(f"Run {chosen['id']} could not be read from disk.")
        return

    # ------------------------------------------------------------ the run --
    st.divider()
    st.markdown(f"#### {run['question']}")
    record = run["record"]
    settings = run["settings"]
    st.caption(
        f"Answered {run['times_answered']}× — first {run['first_answered']}, "
        f"last {run['last_answered']}. Live search "
        f"{'on' if settings.get('live') else 'off'}, predictions "
        f"{'allowed' if settings.get('allow_predictions') else 'off'}, "
        f"up to {settings.get('max_structures')} structures measured.")

    if record.get("answered"):
        st.success(run["headline"])
    else:
        st.error(run["headline"])
        for note in record.get("notes", []):
            st.write("•", note)
        return

    report = record.get("ion_report") or {}
    if report.get("statement"):
        st.info(report["statement"])
    for caveat in record.get("caveats", []):
        st.warning(caveat)

    # -------------------------------------------------------- the proteins --
    st.markdown("##### Proteins the design rules selected")
    shortlist = record.get("shortlist") or {}
    proteins = protein_rows(shortlist)
    if proteins.empty:
        st.info("No protein passed every rule in this run.")
    else:
        st.dataframe(proteins, width="stretch", hide_index=True)
    st.caption(CAVEAT_SHORTLIST_IS_ION_INDEPENDENT
               + " " + (shortlist.get("disclaimer") or ""))

    # ------------------------------------------------------ the structures --
    st.markdown("##### Structures that were measured")
    drawn = structures_in(rehydrate(record))
    if not drawn:
        st.info("No candidate in this run had a deposited structure to "
                "measure.")
        return

    which = st.selectbox("Structure", range(len(drawn)),
                         format_func=lambda i, d=drawn: d[i]["label"],
                         key=f"runs_structure_{chosen['id']}")
    item = drawn[which]
    sites = item.get("sites", [])

    if not item["is_candidate"]:
        st.caption("Found by looking up the element, not by the design "
                   "rules. It is here because it holds the ion, not because "
                   "it is a protein to try.")
    w, x, y, z = st.columns(4)
    w.metric("PDB", item["pdb_id"])
    x.metric("Resolution (Å)", item.get("resolution_A") or "—")
    y.metric("Metal sites", item.get("site_count") or len(sites))
    z.metric(f"Holding {record['plan']['target']}",
             item.get("sites_holding_the_target", 0))

    unavailable = item.get("viewer_unavailable")
    if unavailable:
        st.warning(unavailable)
        st.caption(COORDINATES_ARE_NOT_IN_THE_RUN)
    elif sites:
        theme = theme_control()
        raw = [s["raw"] for s in sites]
        views = ["Whole structure"] + [
            f"{s['deposited_element']} {s['site']} · chain {s['chain']} "
            f"— CN {s['coordination_number']}" for s in sites]
        view = st.selectbox("View", range(len(views)),
                            format_func=lambda i, v=views: v[i],
                            key=f"runs_view_{chosen['id']}_{item['pdb_id']}",
                            help="Pick a metal site to see its first "
                                 "coordination shell.")
        text, fmt = item["coordinates"]
        if view == 0:
            embed(overview_html(text, fmt, raw, script_src=script_src,
                                fallback_src=fallback_src, theme=theme), 480)
        else:
            site = sites[view - 1]
            embed(site_viewer_html(
                text, fmt, raw[view - 1],
                call={"call": site["call"],
                      "call_reliable": site["call_reliable"],
                      "score_version": item["score_version"]},
                script_src=script_src, fallback_src=fallback_src,
                theme=theme), 620)
            st.caption(f"**{site['deposited_element']} {site['site']}, chain "
                       f"{site['chain']}** — {viewer_spec(raw[view - 1])['summary']}. "
                       "Measured from the deposited coordinates when this run "
                       "was answered, not modelled.")

    if sites:
        st.dataframe(site_rows(sites), width="stretch", hide_index=True)

    # --------------------------------------------------------- the reading --
    if run.get("narration"):
        st.markdown("##### What the model said about this run")
        st.markdown(run["narration"])
        st.caption("Written by a language model from the measurements above, "
                   "and saved with them. It is not a source.")

    st.download_button("⬇️ Download this run (JSON)",
                       data=json.dumps(run, indent=2, default=str),
                       file_name=f"lantern_run_{chosen['id']}.json",
                       mime="application/json",
                       key=f"runs_dl_{chosen['id']}")
