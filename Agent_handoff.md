# Agent handoff

## PRIORITY 1 (do this before anything else): finish the live test of the literature critic
Branch `arxiv_rag` holds a built, offline-tested literature critic (`lantern/scholarbud/`, `lantern/critic/`). It has **never run with a real
judge model**. Finishing that test outranks every other task. **Do not push the branch until the live test is done and its table is
committed** (commits are fine). A collaborator holds the API key; the original author's cluster has no key and cannot reach Argo.

### Run it (about 10 minutes once a key exists)
```bash
git checkout arxiv_rag
pip install -r requirements.txt
cp .env.example .env     # set LLM_PROVIDER=anthropic (or openai, or argo on the Argonne network) and its key. Never commit .env
PYTHONPATH=. python -m pytest -q tests/test_critic_policy.py tests/test_critic_judge.py tests/test_critic_pipeline.py tests/test_scholarbud.py
PYTHONPATH=. python scripts/critic_live_trial.py --out docs/critic/CRITIC_LIVE_TRIAL.md --cache .critic_cache
```
The script health-checks the provider first and exits with a plain message if the key or network is wrong. It writes the stage-by-stage
table (`docs/critic/CRITIC_LIVE_TRIAL.md`) and the raw record (`.json`), and prints verdict counts, how many verdicts the post-check
downgraded, and the actions. Retrieval is live (Crossref, no key). `--no-judge` runs retrieval only; Crossref needs internet, nothing else.
Set `LANTERN_MAILTO` to your email so Crossref's polite pool gets a contact in the User-Agent.

### What a good result looks like
- Every one of the 12 claims has a verdict; every cited evidence number exists; `Numbers unchanged by the critic: True`.
- The shortlist order is unchanged unless a protein is marked `review`, and no protein moves up.
- Read the table by eye. Check that `contradicts` verdicts are real contradictions, not a mismatch of words, and that `supports` are not
  just the retrieved papers restating the rule. Note any wrong verdict; that is the judge-accuracy data point we lack.
- If the judge returns unusable JSON, all verdicts degrade to `no_evidence` and decisions to `keep`; the table will show it. Fix the prompt or
  the model choice (`ARGO_MODEL`, `OPENAI_MODEL`, `ANTHROPIC_MODEL`), not the post-check.

### Then, in order
1. Commit the table and any fixes. 2. Consolidate per-site claims to distinct (element, CN) pairs (judge calls are redundant today).
3. Fill `data/critic_lineage.json` with the DOIs of the papers the CN >= 9 and loop-spacing rules came from (otherwise the 0.3 lineage weight
does nothing). 4. Hand-label at least 30 claims, score the judge, and run the with/without-critic ablation on the controls (two lanmodulins,
calcium and negative sequences). 5. Pass verdicts into the narration with a citation check. 6. Only then push and open a PR. Exit criteria are in
`ROADMAP.md` (M7) and `IMPLEMENTATION_PLAN.md` (Sprint 3b).

### Problems the live run found that offline tests could not confirm (all fixed, regression-tested)
1. Crossref answered HTTP 400 to an unsupported `select` field (`subtype`). Recorded fixtures cannot show a bad request.
2. With no judge, retrieval was thrown away, so a retrieval-only trial printed an empty table.
3. The top "evidence" for claims about 8FNR was the PDB deposition of 8FNR itself (DOI 10.2210/pdb8fnr/pdb): circular. Now excluded, with abstract-less records.
Open: redundant per-site claims; empty lineage list. Expect more such problems: anything that touches a real service or a real model can fail in ways a
scripted test cannot, so read the live table before trusting the green tests.

### Caveats to carry into any write-up
Abstract-level evidence only (ChemRxiv full text is behind Cloudflare; about 479 reachable through Europe PMC, mostly COVID-era); preprints are not peer
reviewed; BM25 retrieval; the judge may share a model family with the narrator; literature is biased toward reported successes and a missing
paper is not evidence; judge accuracy is unmeasured; the policy is frozen, not trained. The critic never writes or edits a number and never
promotes a candidate: `contradicts` -> `review` (moved last), `supports` -> badge only. Lineage evidence counts at 0.3. Policy parameters are a
vector (`lantern/critic/policy.py`: `Params`, `PARAM_BOUNDS`, `objective`) for later GP/Bayesian tuning once labels exist; no training has been done.

---

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
