# Agent handoff

For the next agent (or person) picking this up. Read this first, then `README.md`, `ROADMAP.md` and `docs/SCIENTIFIC_CONTRACT.md`.
Everything described here works from a clone of this repository alone; nothing needs the private notes folder.

## What LANTERN is
An evidence-aware prototype that triages rare-earth (lanthanide, Ln) binding proteins and sequences. A typed question goes to `plan.py`
(optional LLM intent extraction, checked against allow-lists and the question text; deterministic fallback), then `discover.py`
selects by stated rules, verifies on a structure and records every number. The language model only parses and narrates; it never
writes a score or citation. It is a prototype: **no experiment, no calibrated selectivity, no autonomous tool-selecting planner.**

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # app + tests
pip install -r requirements-figures.txt    # only for scripts/figures
streamlit run app.py                        # keep "Reference set"; no LLM key needed
```
LLM providers (Argo, OpenAI, Anthropic) are optional; copy `.env.example` to `.env`.
The viewer tests drive a Node scene check: put `node` on PATH or those tests skip (about 28 skipped).

## Run the tests
```bash
PYTHONPATH=. python -m pytest -q tests
```
Last full run: 838 passed, 1 xfailed (with Node). `tests/golden/` holds the dark-viewer goldens; do not regenerate them to make a
test pass, since `TestDarkIsUnchanged` exists to catch accidental change to the dark scene.

## Map of the code
| Path | Role |
|---|---|
| `app.py` | Streamlit UI. A segmented control switches Ask / Explorer. "Viewer background" radio (Dark/Light). |
| `lantern/plan.py`, `discover.py` | Question parsing and the discovery run. |
| `lantern/chemistry.py` | Sequence scoring (`score_sequence`); exploratory, no metal term. |
| `lantern/geometry.py`, `structure.py` | First-shell coordination (O/N/S within 3.2 Å), CN descriptor, structure loading. |
| `lantern/viewer.py` | 3D site viewer (3Dmol.js, self-hosted via `static/`). `theme='dark'\|'light'`; unknown theme raises. Bonds are drawn from measured donor xyz, so the bond count equals the CN. |
| `lantern/explorer.py` | Explorer: Altair `on_select` views over site tables, paired sites, loop-spacing hits, ranked candidates. Reads `data/figures/retrieval_hits.json`; `LANTERN_HITS_JSON` overrides. |
| `lantern/alphafold.py`, `uniprot.py` | AlphaFold DB retrieval (models are fetched, never run) and UniProt/InterPro queries. |
| `lantern/llm.py`, `argo.py` | Provider clients. |
| `scripts/` | Corpus build and analysis (`download_corpus.py`, `build_site_table.py`, `curate_corpus.py`, `paired_sites.py`, `matched_calcium.py`, `crosscheck_metalpdb.py`, ...). |
| `scripts/figures/` | Figure 1 and 2 builders, UI capture. See `scripts/figures/README.md`. |
| `data/` | Site tables (parquet), curation verdicts, paired sites, reference proteins, `figures/*.json`. |
| `docs/figures/paper/` | Published figure outputs (PNG 300 dpi + SVG, panels saved separately). |

## Reproduce the results
Headline numbers and where they come from (all from files in `data/`):
- Corpus A: 636 PDB entries, 3,375 site records (3,116 Ln + 259 Ca); 681 further Ca sites from 172 Ca-only entries.
- Curation: 62 entries read by hand; 221 natural / 2,510 unclassified of 3,116 Ln sites (`data/curation_verdicts.json`).
- Descriptor: CN >= 9 flags 89 of 136 natural Ln sites versus 5 of 664 Ca sites (`data/lanthanide_sites.parquet`, `calcium_sites.parquet`).
  The cutoff was chosen in-sample, so treat it as a coarse filter, not a classifier.
- Paired sites: 19 pairs, median delta CN 0, sign test p = 1.0 (`data/paired_sites.csv`).
- Spacing retrieval over 165,902 EF-hand sequences: 2,266 loose hits, 156 strict (107 in family, 49 outside, 15 with Pro at position 2)
  (`data/figures/retrieval_hits.json`, with an `in_family` flag).
- AlphaFold coverage: 110 of 190 family sequences have a model (`data/figures/corpusb_coverage.json`).

To rebuild the figures from the repo alone:
```bash
python scripts/figures/build_figure2.py     # -> docs/figures/paper/fig2
python scripts/figures/build_figure1.py     # -> docs/figures/paper/fig1
```
`tests/test_figures.py` builds both into a temp directory. Regenerating `data/figures/*.json` from raw downloads is
`scripts/figures/prepare_figure_data.py --assets DIR` (default `$LANTERN_ASSETS`; the script documents its one fallback path).
Re-capturing the UI panels (Figure 1D/E) is `scripts/figures/capture_ui.py` and needs Playwright + chromium.

Independent validation lives in `scripts/validation/` (outputs in `data/validation/`):
```bash
export LANTERN_ASSETS=/path/to/asset_tree   # corpus_A_mmcif/, uniprot_efhand_short/, corpus_B_alphafold/
python scripts/validation/validate_results.py            # V1-V6: gemmi CN recount (96/96), Fisher/bootstrap, retrieval rerun, ...
python scripts/validation/validate_cutoff_sensitivity.py # cutoff 2.8-3.4 A; MetalPDB agreement is in results.json
```
These need the downloaded mmCIF/FASTA assets and some network access (V5 fetches one assembly file). `validate_results.py` was
re-run from the repo and reproduced `data/validation/results.json` exactly.

## Conventions
- Figures: DejaVu Sans, white background, fixed palette (Ln blue, Ca orange), no figure titles, panel letters only. Each panel is a
  `draw_*(ax)` function used both standalone and in the composite. Style lives only in `scripts/figures/style.py`.
- The viewer must keep both themes working; add a test for any new scene element in both.
- Never describe a sequence score or an AlphaFold-retrieved structure as measured binding. Models are labelled hypothetical.
- Give new data files provenance (a short note in the script that makes them). Keep large downloads out of the repo.
- Run python with `-I` or from outside the repo when scripting, to avoid picking up stray modules.

## Known gaps and open questions
- Explorer histogram text in Figure 1E is about 4.2 pt, below the 5 pt target.
- Dense distance labels overlap near the ion in the viewer.
- Emoji columns render as tofu in headless Chromium (screenshots crop them out).
- 44 of the 4-loop candidates have no AlphaFold entry. Open decision: predict them (ESMFold/ColabFold) or screen on sequence only.
- ESMFold and the tool-selecting planner (<= 8 steps, audit log) are planned, not built.
- Only 62 entries are hand-curated; 2,510 Ln sites remain unclassified, so natural-site statistics rest on four families (20 entries).
- No experimental validation of any shortlisted candidate.

## Contributing
Branch: `as_dev`. Write a test first or alongside any change, run the full suite, and keep commits small and described by the
reason, not only the diff. Do not commit credentials or `.env`.
