"""Run using `streamlit run app.py`."""
import io
import json
import os
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from reefinder.agent import run_campaign, explain_campaign
from reefinder.argo import ArgoClient, ArgoError
from reefinder.chemistry import METALS
from reefinder.structure import fetch_pdb, binding_neighborhood

load_dotenv()
st.set_page_config(page_title="REE-Finder · Protein Discovery", page_icon="🧬", layout="wide")
st.markdown("""<style>
.block-container {padding-top:2rem;max-width:1250px}
.hero{padding:1.4rem;border-radius:18px;background:linear-gradient(105deg,#102c42,#125c60);color:#f0fbf9;margin-bottom:1.3rem}
.hero h1{margin:0;font-size:2.2rem}.hero p{opacity:.86;margin-bottom:0}
.small{color:#a9bcc9;font-size:.86rem}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🧬 REE-Finder</h1><p>Explore nature’s proteins for rare-earth-binding hypotheses · Chemistry-guided · Evidence-aware · Powered by Argo</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚗️ Discovery settings")
    target = st.selectbox("Target rare earth", ["Nd3+", "Dy3+", "La3+", "Ce3+"])
    competitor = st.selectbox("Compare against", ["Ca2+", "Nd3+", "Dy3+", "La3+", "Ce3+"], index=0)
    mode = st.radio("Source", ["Offline demo", "Live UniProt"], index=0,
                    help="Demo uses synthetic educational sequences. Live fetches real sequences.")
    topic = st.selectbox("Protein search family", ["lanmodulin", "calmodulin", "ef-hand"],
                         disabled=mode == "Offline demo")
    limit = st.slider("Maximum proteins", 5, 50, 20, step=5, disabled=mode == "Offline demo")
    st.divider()
    st.caption("Argo model and credential are read from .env. Never paste credentials into chat.")
    argo = ArgoClient()
    st.success("Argo configured") if argo.ready() else st.info("Argo not configured; screening still works.")
    st.caption("Research prototype, not a validated affinity predictor.")

st.info("**Scientific limitation:** The current screening score uses sequence composition and a motif hint. It does not assess actual 3D geometry, binding free energy, selectivity, or experimentally verified performance.")
if st.button("🔎 Run protein discovery", type="primary", use_container_width=True):
    try:
        with st.spinner("Collecting proteins and screening sequences..."):
            st.session_state.campaign = run_campaign(topic=topic, target=target, competitor=competitor,
                                                     live=mode == "Live UniProt", limit=limit)
            st.session_state.pop("explanation", None)
    except Exception as exc:
        st.error(f"Discovery failed ({type(exc).__name__}). Check the internet or switch to Offline demo.")

if "campaign" not in st.session_state:
    st.markdown("### Get started")
    a,b,c=st.columns(3)
    a.metric("Demo proteins", "4", help="All demo protein sequences are synthetic")
    b.metric("Supported targets", "4")
    c.metric("Cloud LLM", "Argonne Argo")
    st.markdown("Click **Run protein discovery** to see a ranked exploratory shortlist. Use **Live UniProt** for real sequences, then explore a known PDB structure.")
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
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download results (JSON)", data=json.dumps(campaign, indent=2),
                       file_name="reefinder_campaign.json", mime="application/json")
    st.subheader("Workflow trace")
    for i, step in enumerate(campaign["trace"], 1):
        st.write(f"**{i}.** {step}")
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
                           help="Fetches experimentally deposited PDB coordinates. Many live UniProt results do not have a PDB ID linked yet.")
    if st.button("🧬 View structure"):
        try:
            pdb = fetch_pdb(pdb_id)
            st.session_state.pdb = pdb
            st.session_state.pdb_id = pdb_id.upper()
        except Exception as exc:
            st.warning(f"Could not load PDB: {type(exc).__name__}. Some entries are mmCIF-only.")
    if st.session_state.get("pdb") and st.session_state.get("pdb_id") == pdb_id.upper():
        pdb = st.session_state.pdb
        # Embed PDB text as a JSON literal; avoid injecting HTML from fetched metadata.
        pdb_js = json.dumps(pdb)
        html = f'''<div id="viewer" style="width:100%;height:460px;background:#0c1424;border-radius:12px"></div>
<script src="https://3Dmol.org/build/3Dmol-min.js"></script>
<script>const v=$3Dmol.createViewer(document.getElementById('viewer'),{{backgroundColor:'#0c1424'}});
v.addModel({pdb_js},'pdb');v.setStyle({{}},{{cartoon:{{color:'spectrum'}}}});
v.addStyle({{hetflag:true}},{{sphere:{{scale:0.45}}}});v.zoomTo();v.render();</script>'''
        components.html(html, height=480)
        try:
            sites = binding_neighborhood(pdb)
            if sites:
                st.success(f"Found {len(sites)} deposited lanthanide ion site(s) in these coordinates.")
                st.json(sites)
            else:
                st.info("No deposited lanthanide ions found. No hypothetical coordinates have been invented.")
        except Exception as exc:
            st.warning(f"Coordinate parsing unavailable: {type(exc).__name__}")
        st.download_button("Download deposited PDB", pdb, file_name=f"{pdb_id.upper()}.pdb")
with tab3:
    st.subheader("Research assistant")
    st.caption("Argo receives the campaign summary, not your credentials or full protein coordinates.")
    question = st.text_area("Ask a scientific question", value=f"What can we infer about {campaign['target']} versus {campaign['competitor']} from these results? What experiments should we do?", height=115)
    if st.button("✨ Ask Argo", disabled=not argo.ready()):
        try:
            with st.spinner("Reasoning from the campaign evidence..."):
                st.session_state.explanation = explain_campaign(campaign, argo, question)
        except ArgoError as exc:
            st.error(str(exc))
    if "explanation" in st.session_state:
        st.markdown(st.session_state.explanation)
    if not argo.ready():
        st.info("To enable Argo: create `.env` from `.env.example`, set `ARGO_API_KEY` and `ARGO_MODEL`, then restart the app.")
