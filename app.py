"""Run using `streamlit run app.py`."""
import io
import json
import os
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from reefinder.agent import run_campaign, explain_campaign, SCORE_LIMITATION
from reefinder.argo import ArgoClient, ArgoError
from reefinder.chemistry import METALS
from reefinder.structure import fetch_structure, binding_neighborhood
from reefinder.uniprot import TOPICS

# Pinned rather than floating: an unversioned third-party script can change
# under the demo. Vendor this locally before any judged or offline run.
TMOL_SRC = "https://cdn.jsdelivr.net/npm/3dmol@2.5.5/build/3Dmol-min.js"

load_dotenv()
st.set_page_config(page_title="REE-Finder · Protein Discovery", page_icon="🧬", layout="wide")
st.markdown("""<style>
.block-container {padding-top:2rem;max-width:1250px}
.hero{padding:1.4rem;border-radius:18px;background:linear-gradient(105deg,#102c42,#125c60);color:#f0fbf9;margin-bottom:1.3rem}
.hero h1{margin:0;font-size:2.2rem}.hero p{opacity:.86;margin-bottom:0}
.small{color:#a9bcc9;font-size:.86rem}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🧬 REE-Finder</h1><p>Explore nature’s proteins for rare-earth-binding hypotheses · Chemistry-guided · Evidence-aware · Powered by Argo</p></div>', unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def argo_health(base_url: str, model: str, has_user: bool):
    """Cached so the badge does not fire a request on every widget rerun.
    Keyed on configuration only -- never on the credential itself."""
    return ArgoClient().health()


with st.sidebar:
    st.header("⚗️ Discovery settings")
    target = st.selectbox("Target rare earth", ["Nd3+", "Dy3+", "La3+", "Ce3+"])
    competitor = st.selectbox("Compare against", ["Ca2+", "Nd3+", "Dy3+", "La3+", "Ce3+"], index=0)
    mode = st.radio("Source", ["Offline demo", "Live database"], index=0,
                    help="Demo uses synthetic educational sequences. Live fetches real sequences.")
    topic = st.selectbox("Protein search family", list(TOPICS),
                         disabled=mode == "Offline demo",
                         help="lanm-family resolves the lanmodulin family through InterPro, "
                              "then fetches sequences from UniProt.")
    limit = st.slider("Maximum proteins", 5, 50, 20, step=5, disabled=mode == "Offline demo")
    st.divider()
    st.caption("Argo model and username are read from .env. Never paste credentials into chat.")
    argo = ArgoClient()
    if not argo.configured():
        st.info("Argo not configured; screening still works.")
    else:
        ok, detail = argo_health(argo.base_url, argo.model, bool(argo.user))
        st.success(detail) if ok else st.warning(detail)
    st.caption("Research prototype, not a validated affinity predictor.")

st.info(f"**Scientific limitation:** {SCORE_LIMITATION} Coordination number and bidentate "
        "carboxylate count are what separate the two, and both require 3D structure.")
if st.button("🔎 Run protein discovery", type="primary", width='stretch'):
    try:
        with st.spinner("Collecting proteins and screening sequences..."):
            st.session_state.campaign = run_campaign(topic=topic, target=target, competitor=competitor,
                                                     live=mode == "Live database", limit=limit)
            st.session_state.pop("explanation", None)
    except Exception as exc:
        st.error(f"Discovery failed ({type(exc).__name__}). Check the internet or switch to Offline demo.")

if "campaign" not in st.session_state:
    st.markdown("### Get started")
    a,b,c=st.columns(3)
    a.metric("Demo proteins", "4", help="All demo protein sequences are synthetic")
    b.metric("Supported targets", "4")
    c.metric("Cloud LLM", "Argonne Argo")
    st.markdown("Click **Run protein discovery** to see a ranked exploratory shortlist. Use **Live database** for real sequences, then explore a known PDB structure.")
    st.stop()

campaign = st.session_state.campaign
candidates = campaign["candidates"]
a,b,c,d = st.columns(4)
a.metric("Candidate sequences", len(candidates))
b.metric("Target", campaign["target"])
c.metric("Competitor", campaign["competitor"])
d.metric("Source", campaign["mode"])
st.caption(campaign["disclaimer"])

tab1,tab2,tab3 = st.tabs(["🏆 Candidates", "🔬 Protein explorer", "💬 Ask Argo"])
with tab1:
    st.subheader("Exploratory protein shortlist")
    st.caption("Scores are relative sequence heuristics, not predictions of experimentally measured REE binding or metal selectivity.")
    df = pd.DataFrame([{"Protein": c["name"], "Organism": c["organism"],
                        "Heuristic score": c["score"], "Motif hints": c["motif_count"],
                        "Acidic fraction": c["acidic_fraction"], "Accession": c["accession"],
                        "Provenance": c["protein"]["source"]} for c in candidates])
    st.dataframe(df, width='stretch', hide_index=True)
    st.download_button("⬇️ Download results (JSON)", data=json.dumps(campaign, indent=2),
                       file_name="reefinder_campaign.json", mime="application/json")
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
        # Embed coordinates as a JSON literal; never inject fetched metadata as HTML.
        coords_js = json.dumps(text)
        html = f'''<div id="viewer" style="width:100%;height:460px;background:#0c1424;border-radius:12px"></div>
<script src="{TMOL_SRC}"></script>
<script>const v=$3Dmol.createViewer(document.getElementById('viewer'),{{backgroundColor:'#0c1424'}});
v.addModel({coords_js},'{fmt}');v.setStyle({{}},{{cartoon:{{color:'spectrum'}}}});
v.addStyle({{hetflag:true}},{{sphere:{{scale:0.45}}}});v.zoomTo();v.render();</script>'''
        components.html(html, height=480)
        try:
            sites = binding_neighborhood(text, fmt)
            if sites:
                st.success(f"Found {len(sites)} deposited rare-earth ion site(s) in these coordinates.")
                st.dataframe(pd.DataFrame([{
                    "Element": s["element"], "Chain": s["chain"], "Site": s["site"],
                    "Coordination number": s["coordination_number"],
                    "Protein donors": s["protein_donor_count"],
                    "Water donors": s["water_donor_count"],
                    "Mean donor distance (Å)": s["mean_donor_distance_A"],
                } for s in sites]), width='stretch', hide_index=True)
                st.caption("Coordination number counts O/N/S first-shell donors within 3.2 Å, waters "
                           "included. Biological lanthanide sites typically show CN 9–10; calcium "
                           "sites in the same fold show CN ≈ 7.")
                with st.expander("Per-site donor atoms"):
                    st.json(sites)
            else:
                st.info("No deposited rare-earth ions found. No hypothetical coordinates have been invented.")
        except Exception as exc:
            st.warning(f"Coordinate parsing unavailable: {type(exc).__name__}")
        st.download_button(f"Download deposited {fmt.upper()}", text,
                           file_name=f"{pdb_id.upper()}.{fmt}")
with tab3:
    st.subheader("Research assistant")
    st.caption("Argo receives the campaign summary, not your credentials or full protein coordinates.")
    question = st.text_area("Ask a scientific question", value=f"What can we infer about {campaign['target']} versus {campaign['competitor']} from these results? What experiments should we do?", height=115)
    if st.button("✨ Ask Argo", disabled=not argo.configured()):
        try:
            with st.spinner("Reasoning from the campaign evidence..."):
                st.session_state.explanation = explain_campaign(campaign, argo, question)
        except ArgoError as exc:
            st.error(str(exc))
    if "explanation" in st.session_state:
        st.markdown(st.session_state.explanation)
    if not argo.configured():
        st.info("To enable Argo: create `.env` from `.env.example`, set `ARGO_USER` and `ARGO_MODEL`, then restart the app.")
