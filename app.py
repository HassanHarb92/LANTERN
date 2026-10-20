"""Run using `streamlit run app.py`."""
import io
import json
import os
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from lantern.agent import run_campaign, explain_campaign, SCORE_LIMITATION
from lantern.llm import LLMError, PROVIDERS, make_client, provider_status
from lantern.catalog import load_reference
from lantern.chemistry import METALS
from lantern.geometry import SCORE_VERSION, score_site
from lantern.structure import (ALL_METAL_CODES, fetch_structure, binding_neighborhood,
                                 resolution_from_coordinates)
from lantern.uniprot import TOPICS
from lantern.viewer import (RARE_EARTH_ELEMENTS, overview_html, site_viewer_html,
                              viewer_spec)

load_dotenv()
st.set_page_config(page_title="LANTERN · Protein Discovery", page_icon="🧬", layout="wide")
st.markdown("""<style>
.block-container {padding-top:2rem;max-width:1250px}
.hero{padding:1.4rem;border-radius:18px;background:linear-gradient(105deg,#102c42,#125c60);color:#f0fbf9;margin-bottom:1.3rem}
.hero h1{margin:0;font-size:2.2rem}.hero p{opacity:.86;margin-bottom:0}
.small{color:#a9bcc9;font-size:.86rem}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🧬 LANTERN</h1><p>Lanthanide-Aware Network for Targeted Exploration and Recognition in Nature · Chemistry-guided · Evidence-aware</p></div>', unsafe_allow_html=True)


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


with st.sidebar:
    st.header("⚗️ Discovery settings")
    target = st.selectbox("Target rare earth", ["Nd3+", "Dy3+", "La3+", "Ce3+"])
    competitor = st.selectbox("Compare against", ["Ca2+", "Nd3+", "Dy3+", "La3+", "Ce3+"], index=0)
    mode = st.radio("Source", ["Reference set", "Live database"], index=0,
                    help="Reference set screens six authentic sequences offline. Live fetches from UniProt/InterPro.")
    topic = st.selectbox("Protein search family", list(TOPICS),
                         disabled=mode == "Reference set",
                         help="lanm-family resolves the lanmodulin family through InterPro, "
                              "then fetches sequences from UniProt.")
    limit = st.slider("Maximum proteins", 5, 50, 20, step=5, disabled=mode == "Reference set")
    st.divider()
    st.subheader("🤖 Language model")
    # Default to whatever LLM_PROVIDER names, so .env alone can drive a
    # headless run. An unrecognised value must not take the whole app down
    # with it -- the screening pipeline does not need a model at all.
    status = {row["name"]: row for row in provider_status()}
    requested = (os.getenv("LLM_PROVIDER") or "argo").strip().lower()
    if requested not in PROVIDERS:
        st.warning(f"LLM_PROVIDER={requested!r} is not one of {', '.join(PROVIDERS)}; using argo.")
        requested = "argo"
    provider = st.selectbox(
        "Provider", list(PROVIDERS), index=list(PROVIDERS).index(requested),
        format_func=lambda p: f"{status[p]['label']}{'' if status[p]['configured'] else ' — no key'}",
        help="Narration only. Screening and scoring are deterministic and never call a model.")
    llm = make_client(provider)
    st.caption("Credentials are read from .env. Never paste them into chat.")
    if not llm.configured():
        st.info(f"{llm.label} not configured; screening still works.")
    else:
        ok, detail = llm_health(provider, llm.base_url, llm.model, True)
        st.success(detail) if ok else st.warning(detail)
    st.caption("Research prototype, not a validated affinity predictor.")

st.info(f"**Scientific limitation:** {SCORE_LIMITATION} Coordination number is what separates "
        "the two, and it requires 3D structure.")
if st.button("🔎 Run protein discovery", type="primary", width='stretch'):
    try:
        with st.spinner("Collecting proteins and screening sequences..."):
            st.session_state.campaign = run_campaign(topic=topic, target=target, competitor=competitor,
                                                     live=mode == "Live database", limit=limit)
            st.session_state.pop("explanation", None)
    except Exception as exc:
        st.error(f"Discovery failed ({type(exc).__name__}). Check the internet or switch to the Reference set.")

if "campaign" not in st.session_state:
    st.markdown("### Get started")
    a,b,c=st.columns(3)
    a.metric("Reference proteins", str(len(load_reference())),
             help="Authentic UniProt sequences: 2 lanmodulins, 2 calcium proteins, 2 negatives")
    b.metric("Supported targets", str(sum(1 for m in METALS.values() if m["kind"] == "lanthanide")))
    c.metric("Cloud LLM", llm.label, help="Switch providers in the sidebar.")
    st.markdown("Click **Run protein discovery** to screen the reference set, or switch to "
                "**Live database** to pull the lanmodulin family, then explore a known structure.")
    st.stop()

campaign = st.session_state.campaign
candidates = campaign["candidates"]
a,b,c,d = st.columns(4)
a.metric("Candidate sequences", len(candidates))
b.metric("Target", campaign["target"])
c.metric("Competitor", campaign["competitor"])
d.metric("Source", campaign["mode"])
st.caption(campaign["disclaimer"])

tab1,tab2,tab3 = st.tabs(["🏆 Candidates", "🔬 Protein explorer", "💬 Ask the model"])
with tab1:
    st.subheader("Exploratory protein shortlist")
    st.caption("Scores are relative sequence heuristics, not predictions of experimentally measured REE binding or metal selectivity.")
    df = pd.DataFrame([{"Protein": c["name"], "Organism": c["organism"],
                        "Heuristic score": c["score"], "Motif hints": c["motif_count"],
                        "Acidic fraction": c["acidic_fraction"], "Accession": c["accession"],
                        "Provenance": c["protein"]["source"]} for c in candidates])
    st.dataframe(df, width='stretch', hide_index=True)
    st.download_button("⬇️ Download results (JSON)", data=json.dumps(campaign, indent=2),
                       file_name="lantern_campaign.json", mime="application/json")
    st.subheader("Workflow trace")
    for i, step in enumerate(campaign["trace"], 1):
        st.write(f"**{i}.** {step}")
    st.caption(f"Pipeline: {campaign.get('pipeline', 'fixed sequence')}.")
with tab2:
    options = {f"{i+1}. {c['name']}": c for i, c in enumerate(candidates)}
    selected_label = st.selectbox("Select protein", list(options))
    selected = options[selected_label]
    st.markdown(f"**{selected['name']}** · {selected['organism']}")
    st.caption(selected["protein"]["notes"])
    st.write(selected["rationale"])
    st.write("**Evidence level:**", selected["protein"]["evidence"])
    if selected["protein"]["source_url"]:
        st.link_button("Source record", selected["protein"]["source_url"])
    pdb_id = st.text_input("PDB accession (optional)", value=selected.get("pdb_id") or "", max_chars=4,
                           help="Fetches experimentally deposited coordinates. Many live results do not have a PDB ID linked yet.")
    if st.button("🧬 View structure"):
        try:
            text, fmt = fetch_structure(pdb_id)
            st.session_state.coords = (text, fmt)
            st.session_state.pdb_id = pdb_id.upper()
        except Exception as exc:
            st.warning(f"Could not load structure: {type(exc).__name__}.")
    if st.session_state.get("coords") and st.session_state.get("pdb_id") == pdb_id.upper():
        text, fmt = st.session_state.coords
        # Parse before drawing: the site list decides what the viewer offers.
        sites, calls, parse_error = [], [], None
        try:
            sites = binding_neighborhood(text, fmt, metals=ALL_METAL_CODES)
            # RCSB serves the deposited asymmetric unit here, not the
            # biological assembly, so every call made on this page is
            # marked "asu" and geometry-v2 downgrades its negatives.
            resolution = resolution_from_coordinates(text, fmt)
            calls = [score_site(s, resolution_A=resolution, coordinate_source="asu")
                     for s in sites]
        except Exception as exc:
            parse_error = type(exc).__name__

        views = ["Whole structure"] + [
            f"{s['element']} {s['site']} · chain {s['chain']} — CN {s['coordination_number']}"
            for s in sites]
        # Open on a site rather than the fold: the question this page exists
        # to answer is where the element binds, and a whole-chain cartoon does
        # not answer it. Prefer a rare-earth site; fall back to the first site
        # of any element, so a calcium-only structure still opens on a shell.
        opening = next((i for i, s in enumerate(sites, start=1)
                        if s["element"] in RARE_EARTH_ELEMENTS), 1 if sites else 0)
        # Keyed on the accession so a new structure starts at its own opening
        # site. Without that, two entries with the same number of sites share
        # a widget identity and the second one inherits the first's selection.
        chosen = st.selectbox("View", range(len(views)), index=opening,
                              format_func=lambda i: views[i],
                              key=f"site_view_{st.session_state.get('pdb_id')}",
                              help="Pick a metal site to see its first coordination shell, "
                                   "or keep the whole fold for orientation.")
        if chosen == 0:
            embed(overview_html(text, fmt, sites), 480)
            if sites:
                st.caption("Every deposited metal is marked and named. Select one above to see "
                           "the donor atoms it binds and the distance to each.")
        else:
            site = sites[chosen - 1]
            call = calls[chosen - 1] if calls else None
            embed(site_viewer_html(text, fmt, site, call=call), 620)
            st.caption(f"**{site['element']} {site['site']}, chain {site['chain']}** — "
                       f"{viewer_spec(site)['summary']}. Dashed bonds run from the ion to each "
                       "O/N/S atom within 3.2 Å; the view is cropped to that first shell, so "
                       "atoms further out are not drawn. Distances are measured from the "
                       "deposited coordinates, not modelled.")
            if call:
                st.caption(f"{SCORE_VERSION} call for this site: **{call['call']}**"
                           f"{'' if call['call_reliable'] else ' — not reliable from these coordinates'}.")
        if parse_error:
            st.warning(f"Coordinate parsing unavailable: {parse_error}")
        elif sites:
            st.success(f"Found {len(sites)} deposited metal site(s) in these coordinates.")
            st.dataframe(pd.DataFrame([{
                "Element": s["element"], "Chain": s["chain"], "Site": s["site"],
                "Coordination number": s["coordination_number"],
                "Bidentate carboxylates": s["chemistry"]["bidentate_carboxylates"],
                "Protein donors": s["protein_donor_count"],
                "Water donors": s["water_donor_count"],
                "Mean donor distance (Å)": s["mean_donor_distance_A"],
                f"{SCORE_VERSION} call": c["call"],
                "Call reliable": c["call_reliable"],
            } for s, c in zip(sites, calls)]), width='stretch', hide_index=True)
            st.caption("Coordination number counts O/N/S first-shell donors within 3.2 Å, waters "
                       "included. Biological lanthanide sites typically show CN 9–10; calcium "
                       "sites in the same fold show CN ≈ 7.")
            st.markdown(f"**{SCORE_VERSION}** calls a site lanthanide-like when it reaches "
                        "**CN ≥ 9** — the one descriptor of nine that separates four natural "
                        "lanthanide families from all 55 calcium accessions with no overlap "
                        "(ROADMAP §3.19). Bidentate carboxylate count was scored in v1 and "
                        "was dropped when a fourth family turned out to reach CN 9 using "
                        "five *monodentate* carboxylates; at a threshold low enough to keep "
                        "that family, 30 of the 55 calcium accessions pass it too. It is "
                        "shown above, with net charge and solvent accessibility below, and "
                        "all three are deliberately **not** scored.")
            shown = {caveat for c in calls for caveat in c["caveats"]}
            st.warning("  \n".join(f"• {c}" for c in sorted(shown)))
            with st.expander("Per-site donor atoms and full geometry-v2 output"):
                st.json([{"site": s, SCORE_VERSION: c} for s, c in zip(sites, calls)])
        else:
            st.info("No deposited rare-earth or calcium ions found. No hypothetical "
                    "coordinates have been invented.")
        st.download_button(f"Download deposited {fmt.upper()}", text,
                           file_name=f"{pdb_id.upper()}.{fmt}")
with tab3:
    st.subheader("Research assistant")
    st.caption(f"{llm.label} receives the campaign summary, not your credentials or "
               "full protein coordinates.")
    question = st.text_area("Ask a scientific question", value=f"What can we infer about {campaign['target']} versus {campaign['competitor']} from these results? What experiments should we do?", height=115)
    if st.button(f"✨ Ask {llm.label}", disabled=not llm.configured()):
        try:
            with st.spinner("Reasoning from the campaign evidence..."):
                st.session_state.explanation = explain_campaign(campaign, llm, question)
        except LLMError as exc:
            st.error(str(exc))
    if "explanation" in st.session_state:
        st.markdown(st.session_state.explanation)
    if not llm.configured():
        st.info(f"To enable {llm.label}: create `.env` from `.env.example`, set "
                f"`{llm.key_variable}`, then restart the app. Any of the three "
                "providers works; pick one in the sidebar.")
