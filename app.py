"""Run using `streamlit run app.py`.

One question box. Everything below it is the answer to what was typed in it.

The page is laid out in the order the pipeline runs -- question, rules,
structure, reading -- because that order is also the argument: each section
is only as good as the one above it, and a reader who stops early should
stop at something true rather than at a conclusion whose basis was further
down the page.
"""
import json
import os

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from lantern.catalog import load_reference
from lantern.discover import (NARRATION_IS_NOT_A_SOURCE, NARRATION_TIMEOUT_S,
                              and_list, answer, exportable, headline, narrate)
from lantern.explorer import render_explorer
from lantern.geometry import SCORE_VERSION
from lantern.history import render_runs
from lantern.runs import save as save_run
from lantern.llm import LLMError, PROVIDERS, make_client, provider_status
from lantern.plan import SOURCE_LLM, TARGETS
from lantern.viewer import (RARE_EARTH_ELEMENTS, overview_html,
                            site_viewer_html, theme_control, tmol_sources,
                            viewer_spec)

# Vendored 3Dmol first, CDN behind it. Resolved once: it is a file-existence
# check, and the answer cannot change while the process runs.
TMOL_PRIMARY, TMOL_FALLBACK = tmol_sources()

EXAMPLES = [
    "What proteins should I try for capturing Ce3+?",
    "Which proteins bind Nd3+ rather than calcium?",
    "Give me 5 candidates for Dy3+ recovery",
]

load_dotenv()
st.set_page_config(page_title="LANTERN · Ask about a lanthanide",
                   page_icon="🧬", layout="wide")
st.markdown("""<style>
.block-container {padding-top:2rem;max-width:1250px}
.hero{padding:1.4rem;border-radius:18px;background:linear-gradient(105deg,#102c42,#125c60);color:#f0fbf9;margin-bottom:1.1rem}
.hero h1{margin:0;font-size:2.2rem}.hero p{opacity:.86;margin-bottom:0}
.small{color:#a9bcc9;font-size:.86rem}
.stepnum{color:#1f8a8a;font-weight:700;letter-spacing:.06em;font-size:.78rem}
.ion{display:flex;gap:1.1rem;align-items:center;padding:1rem 1.2rem;border-radius:16px;margin:.1rem 0 1rem;border-left:10px solid}
.ion .sym{font-size:2.6rem;font-weight:700;line-height:1;white-space:nowrap}
.ion .sym sup{font-size:1.1rem;vertical-align:super}
.ion .txt{font-size:.92rem;line-height:1.5}
.ion-yes{background:#0f3324;border-color:#35a06a;color:#e8f7ee}
.ion-no{background:#3a2c0f;border-color:#d7a12b;color:#fcf3e0}
.ion-none{background:#17262d;border-color:#4e8294;color:#e8f3f7}
</style>""", unsafe_allow_html=True)
st.markdown(
    '<div class="hero"><h1>🧬 LANTERN</h1><p>Learning and Analysis of '
    "Nature's Tools for Element Recovery Networks · Ask a question, get "
    'candidates you can check</p></div>', unsafe_allow_html=True)


def embed(html: str, height: int) -> None:
    """Put a self-contained HTML document on the page, inside an iframe.

    Streamlit has renamed this API twice, and requirements.txt allows any
    1.x, so resolve it in order instead of pinning one spelling. st.iframe is
    current and does take a raw HTML string -- anything that is not a URL, a
    "/" path or a Path is embedded as HTML. st.components.v1.html is the old
    name, and it is a deprecate_func_name shim whose stated removal date of
    2026-06-01 has passed, so prefer the st._main._html it delegates to over
    the shim itself. st.html is not a candidate at any version: it is not
    iframed and it drops the <script> that draws the scene.

    The iframe is *not* a security boundary. Streamlit's own warning on both
    functions is that it "allows JavaScript execution and same-origin access
    to the Streamlit app", so a script that got in could reach the parent
    document. What makes a deposited coordinate file safe to embed is
    viewer._js(), which escapes < > & so the text can neither leave its JSON
    string literal nor close the <script> element around it.
    """
    iframe = getattr(st, "iframe", None)
    if iframe is not None:
        iframe(html, height=height)
        return
    renderer = getattr(getattr(st, "_main", None), "_html", None) or components.html
    renderer(html, height=height)


@st.cache_data(ttl=300, show_spinner=False)
def llm_health(provider: str, base_url: str, model: str, has_key: bool):
    """Cached so the badge does not fire a request on every widget rerun.
    Keyed on configuration only -- never on the credential itself."""
    return make_client(provider).health()


def step(number: str, title: str, caption: str = "") -> None:
    st.markdown(f'<div class="stepnum">STEP {number}</div>', unsafe_allow_html=True)
    st.subheader(title)
    if caption:
        st.caption(caption)


def ion_banner(report: dict, own: dict | None = None) -> None:
    """The ion the question named, drawn at the size it was asked in.

    Everything below this point is organised by protein, and for thirteen of
    the fifteen askable lanthanides the page opened on a structure holding
    something else: ask about Eu3+ and the first thing on screen was a tab
    reading "Lanmodulin", a PDB metric reading 8FNR, a 3D viewer labelled Dy
    and a table column headed "Eu3+ size fit". Every one of those is true and
    none of them answers the question. So the element goes first, in a colour
    that encodes the only thing the rest of the page cannot say at a glance:
    whether anything here was measured holding it.
    """
    symbol, target = report["element"], report["target"]
    charge = target[len(symbol):] or "3+"
    tone = {"observed": "ion-yes", "counterfactual": "ion-no"}.get(
        report["verdict_kind"], "ion-none")
    # A lead, not a summary: the statement under it carries the elements and
    # the consequence, and saying those twice in consecutive sentences is how
    # a reader learns to skip the second one.
    #
    # "candidate sites", not "metal sites", because there are now two kinds of
    # site below and only one of them is counted here. On a page that draws
    # the ion its own structure, "none of the 18 metal sites below" would be
    # contradicted four inches further down by four sites of exactly this
    # element -- and the lead has to point at them rather than deny them.
    found = f", but measured in {own['pdb_id']}, shown first" if own else ""
    verdict = {
        "observed": f"measured in {report['sites_holding_the_target']} of the "
                    f"{report['sites_measured']} metal sites below",
        "counterfactual": f"in none of the {report['sites_measured']} "
                          f"candidate sites below{found}",
    }.get(report["verdict_kind"],
          f"nothing structural was measured on the candidates{found}"
          if found else "nothing structural was measured")
    st.markdown(
        f'<div class="ion {tone}">'
        f'<div class="sym">{symbol}<sup>{charge}</sup></div>'
        f'<div class="txt"><b>You asked about {report["name"]} ({target})</b> '
        f'&mdash; {verdict}.<br>{report["statement"]}</div></div>',
        unsafe_allow_html=True)


# ---------------------------------------------------------------- settings --
with st.sidebar:
    st.header("⚙️ How to search")
    live = st.toggle(
        "Search UniProt live", value=False,
        help="Off: screen the six bundled reference sequences offline. On: "
             "pull the family named in your question from UniProt/InterPro "
             "and measure whichever structures those entries cross-reference.")
    allow_predictions = st.toggle(
        "Fall back to AlphaFold", value=False,
        help="Only used when a candidate has no deposited structure. A "
             "prediction has no metal in it, so it can show fold confidence "
             "at the binding loops and never a coordination number.")
    max_structures = st.slider("Candidates to verify", 1, 5, 3,
                               help="How many shortlisted proteins to measure "
                                    "structurally. Fewer is faster.")
    st.divider()
    st.subheader("🤖 Language model")
    # Default to whatever LLM_PROVIDER names, so .env alone can drive a
    # headless run. An unrecognised value must not take the whole app down
    # with it -- nothing on this page needs a model.
    status = {row["name"]: row for row in provider_status()}
    requested = (os.getenv("LLM_PROVIDER") or "argo").strip().lower()
    if requested not in PROVIDERS:
        st.warning(f"LLM_PROVIDER={requested!r} is not one of "
                   f"{', '.join(PROVIDERS)}; using argo.")
        requested = "argo"
    provider = st.selectbox(
        "Provider", list(PROVIDERS), index=list(PROVIDERS).index(requested),
        format_func=lambda p: f"{status[p]['label']}"
                              f"{'' if status[p]['configured'] else ' — no key'}",
        help="Used to read messy questions and to summarise results. Every "
             "number on this page is computed without it.")
    llm = make_client(provider)
    st.caption("Credentials are read from .env. Never paste them into chat.")
    if not llm.configured():
        st.info(f"{llm.label} not configured. Questions are still parsed by "
                "the deterministic reader and the whole pipeline still runs.")
    else:
        ok, detail = llm_health(provider, llm.base_url, llm.model, True)
        st.success(detail) if ok else st.warning(detail)
    st.caption("Research prototype, not a validated affinity predictor.")


# ------------------------------------------------------------- the explorer --
# A section switch rather than st.tabs: every st.tabs body runs on every
# rerun, so the Ask page's existing widgets would share the script with the
# Explorer's, and the Explorer would load its data on every question. Here the
# unselected section simply does not run. st.stop() ends the script, so the
# rest of the page is untouched when Explorer is chosen.
section = st.segmented_control("Section", ["Ask", "Explorer", "Saved runs"],
                               default="Ask", key="section",
                               label_visibility="collapsed")
if section == "Explorer":
    render_explorer(embed)
    st.stop()
if section == "Saved runs":
    render_runs(embed)
    st.stop()

# ---------------------------------------------------------------- the ask --
if "question" not in st.session_state:
    st.session_state.question = ""


def ask_this(text: str) -> None:
    """Put `text` in the box and run it on the next pass.

    This has to be an on_click callback rather than straight-line code after
    the button. Streamlit instantiates the text_input above before any button
    below it is read, and assigning to a widget's own session_state key after
    that raises StreamlitWidgetAlreadyInstantiatedError. Callbacks run before
    the rerun builds its widgets, which is the window where the assignment is
    legal.
    """
    st.session_state.question = text
    st.session_state.pending = text


box, go = st.columns([6, 1], vertical_alignment="bottom")
question = box.text_input(
    "Ask about a lanthanide", key="question",
    placeholder=EXAMPLES[0],
    help="Name the ion you care about. The platform will not substitute one "
         "lanthanide for another on your behalf.")
asked = go.button("Ask", type="primary", width="stretch")

chips = st.columns(len(EXAMPLES))
for column, example in zip(chips, EXAMPLES):
    column.button(example, key=f"ex_{example}", width="stretch",
                  on_click=ask_this, args=(example,))


def archive(record: dict, narration: str | None = None) -> None:
    """Keep this run, so the Saved runs page can open it again.

    Never allowed to break the page it is called from. An answer that was
    computed is worth showing whether or not the disk accepted a copy of
    it, and the failure is reported where it happened rather than raised
    over the top of the measurements.
    """
    try:
        save_run(record, record["question"],
                 {"live": live, "allow_predictions": allow_predictions,
                  "max_structures": max_structures}, narration=narration)
    except Exception as exc:                            # noqa: BLE001
        st.caption(f"This run was answered but could not be archived "
                   f"({type(exc).__name__}). It is on screen but will not "
                   f"appear under Saved runs.")


pending = st.session_state.pop("pending", None)
if asked or pending:
    text = pending or question
    if not text.strip():
        st.warning("Type a question first, or pick one of the examples.")
    else:
        try:
            with st.spinner("Reading the question, applying design rules, "
                            "measuring structures…"):
                st.session_state.record = answer(
                    text, client=llm if llm.configured() else None, live=live,
                    allow_predictions=allow_predictions,
                    max_structures=max_structures)
            st.session_state.pop("narration", None)
            # Refusals are archived too. "This question did not resolve to a
            # target" is a result about the question, and losing it would
            # make the archive read as though it had never been asked.
            archive(st.session_state.record)
        except Exception as exc:
            st.error(f"The search failed ({type(exc).__name__}). If live "
                     "search is on, try turning it off to use the offline "
                     "reference set.")

if "record" not in st.session_state:
    a, b, c = st.columns(3)
    a.metric("Reference proteins", str(len(load_reference())),
             help="Authentic UniProt sequences: 2 lanmodulins, 2 calcium "
                  "proteins, 2 negatives.")
    b.metric("Ions screened", str(len(TARGETS)), help=", ".join(sorted(TARGETS)))
    c.metric("Language model", llm.label, help="Switch providers in the sidebar.")
    st.markdown(
        "Ask a question above. LANTERN reads it, selects proteins by "
        "published design rules, measures the metal sites in their deposited "
        "structures, and shows you where the ion sits — offline, with no "
        "model required.")
    st.stop()

record = st.session_state.record

# ------------------------------------------------------- a refusal, or not --
if not record["answered"]:
    st.error(headline(record))
    for note in record["notes"]:
        st.write("•", note)
    proposed = record["plan"].get("target")
    if proposed:
        # plan.py's third outcome: a model read an ion out of a question that
        # never named one. It is offered back, never run. Clicking rewrites
        # the question so the ion is in the text -- which makes the user, not
        # the model, the reason it is accepted.
        st.info(f"A language model read this as a question about **{proposed}**, "
                "but your question does not name an ion. Confirm it and the "
                "question will be re-asked with the ion written in.")
        st.button(f"Yes — I'm asking about {proposed}", on_click=ask_this,
                  args=(f"{record['question']} ({proposed})",))
    st.stop()

plan = record["plan"]
shortlist = record["shortlist"]
sites_measured = sum(ev["site_count"] for ev in record["evidence"])

st.success(headline(record))
report = record.get("ion_report") or {}
if report:
    ion_banner(report, record.get("ion_structure"))

a, b, c, d = st.columns(4)
a.metric("Target ion", plan["target"], help=report.get("name"))
b.metric("Pass every rule", f"{shortlist['selected_count']} / {shortlist['considered']}")
c.metric(f"Sites holding {plan['target']}",
         f"{report.get('sites_holding_the_target', 0)} / {sites_measured}",
         help="Deposited metal sites on this page whose element is the one "
              "asked about, out of every site measured. The denominator is "
              "what used to be shown alone, and it hid the numerator.")
d.metric("Question read by", "language model"
         if plan["parsed_by"] == SOURCE_LLM else "deterministic reader")
if plan["notes"]:
    with st.expander("How your question was read"):
        for note in plan["notes"]:
            st.write("•", note)

# Where the ion actually is, when it is nowhere on this page. The shortlist
# is architecture-based and cannot reach these, so offering them as candidates
# would be a lie; withholding them makes "none was measured" unfalsifiable.
# They are listed as what they are: an element lookup against the same index
# that decided which file to measure.
elsewhere = report.get("deposited_elsewhere") or []
if elsewhere:
    with st.expander(f"{report['deposited_elsewhere_count']} deposited "
                     f"structure(s) in this platform's index do hold "
                     f"{report['element']} — the {len(elsewhere)} sharpest"):
        st.dataframe(pd.DataFrame([{
            "PDB": e["id"], "Resolution (Å)": e["resolution_A"] or "—",
            "Method": e["method"], "Title": e["title"],
        } for e in elsewhere]), width="stretch", hide_index=True)
        st.caption(
            "Found by looking the element up in the rare-earth entry index, "
            "not by the design rules above. These are not candidates: none "
            "was screened for the lanmodulin architecture, and an entry can "
            "contain a lanthanide because it was soaked in to phase the "
            "crystal, so presence is not a binding claim. They are here so "
            "that 'none was measured' can be checked against what exists.")

# The ion report's statement is a caveat and is exported as one, but it is
# already the body of the banner above; repeating it verbatim a few hundred
# pixels later trains the reader to skip the block that carries the rest.
st.warning("  \n".join(f"• {c}" for c in record["caveats"]
                       if c != report.get("statement")))

# ------------------------------------------------------------ design rules --
st.divider()
step("1", "Selected by design rules",
     "Published rules for the lanmodulin architecture, applied to every "
     "sequence. A rule that could not be checked is 'unknown', and an "
     "unknown is not a pass.")

rule_ids = [r["id"] for r in shortlist["rules"]]
rows = []
for candidate in shortlist["candidates"]:
    verdicts = {r["id"]: r for r in candidate["rules"]}
    row = {"": "✅" if candidate["selected"] else "—",
           "Protein": candidate["name"],
           "Accession": candidate["accession"],
           "Rules passed": f"{candidate['passed']}/{candidate['of']}"}
    for rule_id in rule_ids:
        entry = verdicts[rule_id]
        mark = {"pass": "pass", "fail": "fail"}.get(entry["verdict"], "unknown")
        measured = entry["measured"]
        row[rule_id] = f"{mark}" + (f" ({measured})" if measured is not None else "")
    rows.append(row)
st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

with st.expander("What each rule asks, and where it comes from"):
    for rule in shortlist["rules"]:
        st.markdown(f"**{rule['id']}** — {rule['question']}")
        st.caption(rule["basis"])
st.caption(shortlist["ordering"])

# --------------------------------------------------------------- structure --
st.divider()
step("2", "Verified against structure",
     "Coordination numbers measured from deposited coordinates, not modelled. "
     "This is the only step where the ion you asked about enters.")

# Called once per run and before the first viewer, which is now the ion's own
# structure rather than the first candidate tab.
own = record.get("ion_structure")
viewer_theme = "dark"
if own or any(ev["structure_kind"] == "deposited" for ev in record["evidence"]):
    viewer_theme = theme_control()

# ------------------------------------------------- the ion's own structure --
# First in this step, because a user who asked about Eu3+ came to see europium
# and no candidate below has any. It stays outside the candidate tabs and
# carries its own not-a-candidate caveat: the shortlist answers "what should I
# try", this answers "show me my ion", and the two must not read as one list.
if own:
    st.markdown(f"#### {plan['target']} itself, measured")
    held_here = own["sites_holding_the_target"]
    st.success(f"**{own['pdb_id']} holds {plan['target']}.** {held_here} of its "
               f"{own['site_count']} measured metal site(s) contain "
               f"{report['element']}, at {own['resolution_A']} Å — "
               f"{own['title']}.")
    st.caption(f"{own['selection']} {own['entries_tried']} of the "
               f"{own['entries_in_index']} {report['element']} entries in the "
               f"index were measured to get here.")
    st.warning(own["caveat"])

    own_text, own_fmt = own["coordinates"]
    own_sites = own["sites"]
    own_raw = [s["raw"] for s in own_sites]
    # Same label order as the candidate tabs: element first, because a reader
    # scanning for their own ion is scanning the first token.
    own_views = ["Whole structure"] + [
        f"{s['deposited_element']} {s['site']} · chain {s['chain']} "
        f"— CN {s['coordination_number']}" for s in own_sites]
    # Opens on a site of the element asked about. Falling back to the whole
    # fold rather than to another element's site: this block exists to show
    # one atom, so if it cannot open on that atom it should not pretend to.
    own_opening = next((i for i, s in enumerate(own_sites, start=1)
                        if (s["deposited_element"] or "").capitalize()
                        == report["element"]), 0)
    own_chosen = st.selectbox(
        "View", range(len(own_views)), index=own_opening,
        format_func=lambda i, v=own_views: v[i], key=f"view_ion_{own['pdb_id']}",
        help=f"Pick a metal site to see its first coordination shell. The "
             f"{report['element']} sites are the ones this block is for.")
    if own_chosen == 0:
        embed(overview_html(own_text, own_fmt, own_raw, script_src=TMOL_PRIMARY,
                            fallback_src=TMOL_FALLBACK, theme=viewer_theme), 480)
    else:
        own_site = own_sites[own_chosen - 1]
        embed(site_viewer_html(
            own_text, own_fmt, own_raw[own_chosen - 1],
            call={"call": own_site["call"],
                  "call_reliable": own_site["call_reliable"],
                  "score_version": own["score_version"]},
            script_src=TMOL_PRIMARY, fallback_src=TMOL_FALLBACK,
            theme=viewer_theme), 620)
        st.caption(
            f"**{own_site['deposited_element']} {own_site['site']}, chain "
            f"{own_site['chain']}** — {viewer_spec(own_raw[own_chosen - 1])['summary']}. "
            "Distances are measured from the deposited coordinates, not "
            "modelled. No size fit is shown: the deposited element is the "
            "one asked about, so there is no counterfactual to score.")
    st.dataframe(pd.DataFrame([{
        "Element": s["deposited_element"], "Chain": s["chain"],
        "Site": s["site"], "CN": s["coordination_number"],
        "Mean donor distance (Å)": s["mean_donor_distance_A"],
        "Protein donors": s["protein_donors"],
        "Water donors": s["water_donors"],
        f"{SCORE_VERSION} call": s["call"],
        "Call reliable": s["call_reliable"],
    } for s in own_sites]), width="stretch", hide_index=True)
    if own["rejected"]:
        with st.expander(f"{len(own['rejected'])} {report['element']} "
                         f"entry/entries measured before it and passed over"):
            st.dataframe(pd.DataFrame([{
                "PDB": r["id"], "Resolution (Å)": r.get("resolution_A") or "—",
                "Why it was passed over": r["why"],
                "What was measured": r.get("detail") or "—",
            } for r in own["rejected"]]), width="stretch", hide_index=True)
            st.caption("Each was downloaded and measured by the same code that "
                       "measured the structure above, in sharpest-first order. "
                       "A chelate soaked in to phase a crystal gives a site "
                       "with no protein donors, which is what most of these "
                       "rows are, and it is why resolution alone was not "
                       "enough to choose.")
    st.divider()
    st.markdown("#### The candidates from step 1, measured")

if not record["evidence"]:
    st.info("No candidate had a structure to measure.")


def tab_label(evidence: dict) -> str:
    """Accession always survives truncation; it is the unambiguous half.

    The element the file holds is in the label because the tab strip is where
    a reader chooses what to open, and until it was there the only way to find
    out that a question about Eu3+ had been answered with a Dy structure was
    to open the tab and read down to the site table.
    """
    name = evidence["name"]
    head = (f"{name if len(name) <= 24 else name[:23] + '…'} · "
            f"{evidence['accession']}")
    elements = sorted({s["deposited_element"] for s in evidence["sites"]
                       if s["deposited_element"]})
    if not elements:
        return head
    mark = "✅ " if evidence.get("holds_the_target_element") else ""
    return f"{head} · {mark}{'/'.join(elements)}"


tabs = st.tabs([tab_label(ev) for ev in record["evidence"]] or ["—"])
for tab, ev in zip(tabs, record["evidence"]):
    with tab:
        st.markdown(f"**{ev['name']}**"
                    + (f" · {ev['organism']}" if ev.get("organism") else ""))
        for note in ev.get("notes", []):
            st.caption(note)

        if ev["structure_kind"] == "none":
            st.info("No deposited structure and no prediction, so the "
                    "coordination number is unknown. The rules above are "
                    "sequence-only and cannot supply it.")
            continue

        if ev["structure_kind"] == "predicted":
            st.info(ev["why_no_sites"])
            gate = ev["ef_loop_confidence"]
            x, y, z = st.columns(3)
            x.metric("Mean pLDDT", ev["mean_plddt"])
            y.metric("EF-loop residues found",
                     f"{ev['ef_loop_residues_found']} / {ev['ef_loop_residues']}")
            z.metric("Loops confidently modelled",
                     "yes" if gate and gate["scorable"] else "no")
            if gate:
                st.caption(gate["reason"])
            st.caption(ev["what_this_is"])
            continue

        # Deposited coordinates: the full measurement.
        text, fmt = ev["coordinates"]
        sites = ev["sites"]
        held = ev.get("sites_holding_the_target") or 0
        in_file = sorted({s["deposited_element"] for s in sites
                          if s["deposited_element"]})
        w, x, y, z = st.columns(4)
        w.metric("PDB", ev["pdb_id"])
        x.metric("Resolution (Å)", ev["resolution_A"] or "—")
        y.metric("Metal sites", ev["site_count"])
        z.metric(f"Holding {plan['target']}", f"{held} / {ev['site_count']}")

        # Said at structure level, not only per site: the per-site caption
        # lives inside the single-site branch of the view picker, so on the
        # whole-structure view -- and in the site table, which is drawn for
        # every view -- there was nothing on screen saying the file holds a
        # different element from the one in the column headings.
        others = [e for e in in_file if e != report.get("element")]
        if ev.get("holds_the_target_element"):
            rest = (f"The other {ev['site_count'] - held} hold "
                    f"{and_list(others)}." if others else "")
            st.success(f"**{ev['pdb_id']} holds {plan['target']}.** {held} of "
                       f"its {ev['site_count']} measured site(s) contain "
                       f"{report.get('element', plan['target'])}. {rest}")
        else:
            st.warning(
                f"**{ev['pdb_id']} does not hold {plan['target']}** — its "
                f"metal sites contain {and_list(in_file) or 'no rare earth'}. "
                f"Every {plan['target']} number below is a counterfactual fit "
                f"against a sphere that closed around another ion.")

        # A live search can find several deposited structures for one
        # accession and this page measures exactly one of them. Saying which
        # rule picked it, and naming what it passed over, is what keeps the
        # numbers below from resting on a choice the user never saw.
        choice = ev.get("structure_choice")
        if choice:
            st.caption(choice["reason"])
            with st.expander(f"{len(choice['not_measured'])} other deposited "
                             f"structure(s) for {ev['accession']}, not measured"):
                st.dataframe(pd.DataFrame([{
                    "PDB": o["id"], "Method": o["method"],
                    "Resolution (Å)": o["resolution_A"] or "—",
                    "Chains": o["chains"],
                } for o in choice["not_measured"]]),
                    width="stretch", hide_index=True)
                st.caption("Listed from the UniProt cross-references, which "
                           "state the method and resolution but not which "
                           "metal each file holds. Measuring one of these "
                           "instead could give different sites.")

        raw_sites = [s["raw"] for s in sites]
        # The element stays first in every label: a reader scanning this list
        # for their own ion is scanning the first token, and a marker in front
        # of it would be the one thing they have to read past to find out the
        # site holds something else.
        views = ["Whole structure"] + [
            f"{s['deposited_element']} {s['site']} · chain {s['chain']} "
            f"— CN {s['coordination_number']} · "
            + ("✅ " + plan["target"] if not s["size_match_is_counterfactual"]
               else "not " + plan["target"]) for s in sites]
        # Open on a site rather than the fold: the question this page exists
        # to answer is where the element binds, and a whole-chain cartoon does
        # not answer it. Prefer a rare-earth site; fall back to the first site
        # of any element, so a calcium-only structure still opens on a shell.
        opening = next((i for i, s in enumerate(raw_sites, start=1)
                        if s["element"] in RARE_EARTH_ELEMENTS),
                       1 if raw_sites else 0)
        # Keyed on the accession so a new structure starts at its own opening
        # site. Without that, two entries with the same number of sites share
        # a widget identity and the second one inherits the first's selection.
        # `v=views` binds this structure's labels now. A bare `views[i]` would
        # close over the loop variable, so every structure's formatter would
        # read the last structure's list -- harmless while Streamlit calls it
        # inside this line, wrong the moment anything calls it later, and an
        # IndexError when an earlier structure has more sites than the last
        # one (8FNR has 14 and 8FNS 4, so the canonical question is that case).
        chosen = st.selectbox(
            "View", range(len(views)), index=opening,
            format_func=lambda i, v=views: v[i], key=f"view_{ev['accession']}",
            help="Pick a metal site to see its first coordination shell, or "
                 "keep the whole fold for orientation.")
        if chosen == 0:
            embed(overview_html(text, fmt, raw_sites, script_src=TMOL_PRIMARY,
                                fallback_src=TMOL_FALLBACK, theme=viewer_theme), 480)
            st.caption("Every deposited metal is marked and named. Select one "
                       "above to see the donor atoms it binds and the "
                       "distance to each.")
        else:
            site, raw = sites[chosen - 1], raw_sites[chosen - 1]
            call = {"call": site["call"], "call_reliable": site["call_reliable"],
                    "score_version": ev["score_version"]}
            embed(site_viewer_html(text, fmt, raw, call=call,
                                   script_src=TMOL_PRIMARY,
                                   fallback_src=TMOL_FALLBACK,
                                   theme=viewer_theme), 620)
            st.caption(
                f"**{site['deposited_element']} {site['site']}, chain "
                f"{site['chain']}** — {viewer_spec(raw)['summary']}. Dashed "
                "bonds run from the ion to each O/N/S atom within 3.2 Å; the "
                "view is cropped to that first shell. Distances are measured "
                "from the deposited coordinates, not modelled.")
            fit = site["size_match"]
            context = site["ion_context"]
            if site["size_match_is_counterfactual"]:
                st.caption(
                    f"This site holds **{site['deposited_element']}**, not "
                    f"{plan['target']}. The fit below asks whether "
                    f"{plan['target']} would fit the sphere measured around "
                    f"{site['deposited_element']}.")
            if fit["status"] == "scored":
                st.caption(f"{plan['target']} size fit **{fit['fit']}** "
                           f"(rank {context['target_rank']} of "
                           f"{context['ions_scored']} scored lanthanides; "
                           f"best fit {context['best_fitting_ion']}). "
                           f"{fit['basis']}")
            else:
                st.caption(f"Size fit unavailable. {fit['basis']}")
            # The one verdict on this page that is genuinely about the ion
            # asked for. A coordination number is read off the coordinates and
            # the per-ion ranges were never fitted to this corpus, so unlike
            # the size fit -- which ranks the deposited ion 6th and 9th on
            # these very structures -- it says something checkable about the
            # named ion whether or not that ion was ever crystallised here.
            geometry = site.get("target_coordination_fit")
            if geometry:
                st.caption(f"**{plan['target']} geometry:** "
                           f"{geometry['statement']}")
            if context["deposited_rank"] is not None:
                st.caption(
                    f"**Calibration:** this score ranks "
                    f"{site['deposited_element']}3+ — the ion actually in "
                    f"this site — **{context['deposited_rank']} of "
                    f"{context['ions_scored']}**."
                    + ("" if context["deposited_rank"] == 1 else
                       " It does not recover the ion known to bind here, so "
                       "it cannot be used to choose between lanthanides."))
            else:
                st.caption(f"**Calibration unavailable.** "
                           f"{context['deposited_rank_unavailable']}")

        st.dataframe(pd.DataFrame([{
            "Element": s["deposited_element"],
            f"Is {plan['target']}?":
                "no" if s["size_match_is_counterfactual"] else "✅ yes",
            "Chain": s["chain"],
            "Site": s["site"], "CN": s["coordination_number"],
            "Mean donor distance (Å)": s["mean_donor_distance_A"],
            "Protein donors": s["protein_donors"],
            "Water donors": s["water_donors"],
            f"{SCORE_VERSION} call": s["call"],
            "Call reliable": s["call_reliable"],
            f"CN usual for {plan['target']}": (
                ("yes" if s["target_coordination_fit"]["compatible"] else "no")
                if s["target_coordination_fit"] else "—"),
            f"{plan['target']} size fit": s["size_match"]["fit"],
            "Rank of bound ion": s["ion_context"]["deposited_rank"],
        } for s in sites]), width="stretch", hide_index=True)
        st.caption(
            "Coordination number counts O/N/S first-shell donors within 3.2 Å, "
            f"waters included. 'Is {plan['target']}?' is the element in the "
            "site compared with the one you asked about, so a column of 'no' "
            f"means every {plan['target']} number in this table is a "
            f"counterfactual. 'CN usual for {plan['target']}' asks only "
            "whether the coordination number falls in that ion's normal "
            "range, which neighbouring lanthanides share. 'Rank of bound "
            "ion' is where the size score places the element that is actually "
            "in each site — the score's own calibration, shown next to the "
            "number it qualifies. Blank means that element is not tabulated "
            "at that coordination number.")

        # The call column above is the strongest claim on this page. Every
        # site in a structure is scored against the same bar, so the bar and
        # the evidence for it are stated once here rather than per row.
        for criterion in sites[0]["criteria"]:
            st.caption(
                f"**The bar: {criterion['descriptor'].replace('_', ' ')} ≥ "
                f"{criterion['threshold']}.** {criterion['basis']}.")

        shown = {caveat for s in sites for caveat in s["caveats"]}
        with st.expander(f"{SCORE_VERSION} caveats on these calls"):
            st.warning("  \n".join(f"• {c}" for c in sorted(shown)))
        st.download_button(f"Download deposited {fmt.upper()}", text,
                           file_name=f"{ev['pdb_id']}.{fmt}",
                           key=f"dl_{ev['accession']}")

# ----------------------------------------------------------------- reading --
st.divider()
step("3", "Read it back",
     "A language model summarises the measurements above. It is shown the "
     "caveats along with the numbers and instructed not to contradict them.")

ask = st.text_input("Anything specific you want addressed?",
                    placeholder="What should I test first in the lab?")
if st.button(f"✨ Summarise with {llm.label}", disabled=not llm.configured()):
    try:
        with st.spinner("Reading the evidence…"):
            # A separate client, because this is the one long call on the page
            # (~24 s measured) and the shared one is sized for question
            # parsing. Giving the shared client this timeout would let a dead
            # gateway stall the question box for a minute and a half.
            narrator = make_client(provider, timeout=NARRATION_TIMEOUT_S)
            st.session_state.narration = narrate(record, narrator, ask)
        # Re-archived with the summary attached, so a reopened run carries
        # the reading that was written from its own numbers.
        archive(record, st.session_state.narration)
    except LLMError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"The summary failed ({type(exc).__name__}). Every number "
                 "above was computed without a model and is unaffected.")
if "narration" in st.session_state:
    st.markdown(st.session_state.narration)
    st.caption(NARRATION_IS_NOT_A_SOURCE)
if not llm.configured():
    st.info(f"To enable {llm.label}: create `.env` from `.env.example`, set "
            f"`{llm.key_variable}`, then restart. Any of the three providers "
            "works; pick one in the sidebar.")

st.divider()
st.download_button("⬇️ Download this answer (JSON)",
                   data=json.dumps(exportable(record), indent=2, default=str),
                   file_name="lantern_answer.json", mime="application/json")
st.caption("The download carries every measurement, verdict, caveat and "
           "basis on this page. Coordinates and per-atom donor lists are "
           "left out; they are in the structure download above.")
