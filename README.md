# 🧬 REE-Finder

**An Argo-powered, evidence-aware prototype for exploring naturally occurring rare-earth-binding proteins.**

This is a *hackathon MVP scaffold*, not a validated discovery pipeline. It includes a working web UI, synthetic offline demo, live UniProt sequence retrieval, deterministic exploratory sequence scores, PDB viewer, deposited lanthanide-site inspection, and Argo-based explanations. **It does not yet compute structural coordination scores, experimentally grounded metal selectivity, or autonomous multi-tool planning.** Those are documented in `IMPLEMENTATION_PLAN.md`.

## Quick start (macOS/Linux)

```bash
unzip REE-Finder.zip  # If downloaded as a zip
cd REE-Finder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Open the Streamlit URL, select **Offline demo**, and click **Run protein discovery**. The demo uses **synthetic sequences** and real PDB accessions only for separately viewing experimental structures. Scores from the demo must never be described as findings on real protein sequences.

## Argo configuration

Edit `.env`:

```dotenv
ARGO_BASE_URL=https://apps.inside.anl.gov/argoapi/v1
ARGO_API_KEY=your_credential_here
ARGO_MODEL=your_approved_model_name
```

Use the model name available to your Argonne account. Check your organization's authentication policies. **Do not commit `.env` or share credentials.** The app uses the OpenAI-compatible chat completions endpoint and sends only a bounded summary of screening results. Some networks require Argonne connectivity/VPN. Endpoints and models can change.

Start live discovery by selecting **Live UniProt** in the sidebar. This queries the public UniProtKB REST API and can fail when offline. The `ef-hand` keyword query requires verification against the current UniProt indexing conventions before use in a judged demonstration.

## Project layout

```text
REE-Finder/
├── app.py                        # Streamlit user experience
├── reefinder/
│   ├── __init__.py
│   ├── models.py                 # Typed data records
│   ├── chemistry.py              # Unvalidated transparent sequence heuristic
│   ├── catalog.py                # Synthetic offline demo
│   ├── uniprot.py                # Real UniProt retrieval
│   ├── structure.py              # Experimental PDB fetch + ion-neighborhood detection
│   ├── argo.py                   # Configurable Argo chat client
│   └── agent.py                  # Deterministic campaign + Argo evidence summary
├── data/demo_proteins.json       # Synthetic teaching data, not discoveries
├── tests/test_chemistry.py       # Offline regression tests
├── docs/SCIENTIFIC_CONTRACT.md   # Scientific claims and evidence gates
├── IMPLEMENTATION_PLAN.md       # End-to-end execution roadmap
├── requirements.txt
├── .env.example
├── .streamlit/config.toml
└── .gitignore
```

## Run tests

```bash
pytest -q
```

## What is implemented

- Synthetic offline demonstration and explicitly labeled source provenance.
- Restricted live UniProt family search with basic protein metadata.
- Sequence acid fraction and limited EF-hand-like motif hints.
- Transparent, deterministic score (not metal-specific and not selectivity).
- Interactive result table, workflow trace, downloadable JSON.
- Experimental PDB structure retrieval; 3Dmol.js viewer requires CDN connectivity.
- Report of protein residues near *existing experimentally deposited* lanthanide ions.
- Argo text explanations constrained to screening output.

## What remains for a credible discovery claim

- Verified real positive/negative reference sequences and experimental protein–metal binding constants.
- PDB↔UniProt residue mapping and accessible metal-site detection for structures without deposited ions.
- Validated calcium-versus-lanthanide discrimination, not merely sequence heuristics.
- Sequence homology and redundancy controls; hold-out evaluation.
- A planner with bounded dynamic tool selection, provenance and source citation aggregation.
- Robust security, UI and automated integration tests.

Read `IMPLEMENTATION_PLAN.md` for detailed modules, schemas, agent steps, scientific validation, safety checks, demo script, acceptance tests, and rollout phases.
