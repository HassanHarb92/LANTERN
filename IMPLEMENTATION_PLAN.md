# LANTERN: Complete Hackathon Implementation Plan

**Version:** 0.1 scaffold / 1.0 target  
**Audience:** hackathon developers, scientific advisors, coding agents  
**Runtime:** local macOS/Linux Python, optional Argonne Argo LLM, external scientific databases  
**Scientific goal:** prioritize *existing* proteins as candidates for rare-earth binding, with intelligible evidence and explicit uncertainty.  
**Strict limitation:** neither a plausible AlphaFold structure nor an acidic sequence is evidence of REE-over-Ca selectivity.

---

## 0. Deliverable contract and scope

### MVP demonstrated now (v0.1)

- Streamlit GUI: target/competitor selection, family selector, source mode, screen, table, detail pane, structure viewer, Argo questions and export.
- Synthetic educational protein sequences in offline mode. No fabricated biological discoveries.
- Real UniProtKB retrieval in live mode (constrained predefined queries).
- Deterministic sequence-only heuristic: acidic composition plus EF-hand-like pattern hint; transparent and not metal-specific.
- Fetch experimental PDB text, optionally visualize deposited coordinates in 3Dmol, and compute protein residues near *deposited* lanthanide atoms.
- Argo `/v1/chat/completions` text-only reasoning on compact campaign records.
- Offline unit tests for screen ranking and provenance.

### Target hackathon v1.0 (NOT YET IMPLEMENTED)

- Fully curated set of real lanmodulin and comparator sequences, matched to corresponding experimental structures and literature claims.
- Actual geometry-based screening and annotated 3D pockets, including candidate sites in metal-free predicted structures.
- Verified competitor evaluation based on experimentally observed data, without pretending heuristics yield selectivity thermodynamics.
- Bounded LLM tool-selection loop and explicit source-linked run trace.
- Reproducibility metadata, error handling, stronger tests, caching, user-friendly guided workflow, responsive molecular highlighting.

### Not in the hackathon MVP

De novo protein sequence generation, training/fine-tuning AlphaFold, high-throughput DFT or MD, measuring absolute free energies from structure alone, automated laboratory control, or claims of validated extraction performance.

---

## 1. Scientific question and success criteria

**Question:** Which known natural proteins and homologs have plausible structural environments for binding Nd(III) or related lanthanides, and what evidence is available for preferential capture over Ca(II)?

**Scientific deliverable:** a short, explicitly qualified list of protein candidates with identifiers, verified sequences, structural information, pocket residues, references, chemical rationale, evidence labels and suggested experiments.

**Hackathon success:** starting from "Find natural proteins for Nd3+ rather than Ca2+", the user sees a trace, 5-20 *real* protein candidates, an interactive example structure, and defensible reasons for promising candidates. Presenting a *hypothesis* is success. Measuring/predicting Kd is NOT required.

**Controls:** lanmodulin family as positive REE-binding reference and calcium-binding EF-hand proteins as informative comparator; these are not automatically negative controls for REE binding. Choose a verified negative control only where quantitative experiments show weak/absent binding under comparable conditions. Calcium affinity alone is insufficient.

**Definitions:**

- *Binding affinity*: experimental Kd or derived thermodynamic quantity at specified conditions.
- *REE selectivity*: quantitative preference measured or calculated with a validated method under matched conditions.
- *Pocket compatibility*: structural/chemical hypothesis, not affinity.
- *Sequence motif*: annotation/signature, not a verified metal-binding site.

---

## 2. UX and visual design

**Product identity:** LANTERN; deep navy background, teal primary accent, neutral evidence tags, spacious cards. Aim for professional but approachable scientific UI.

**Welcome page:** three actions: "Use an example", "Discover real proteins", "Open existing run". Explain that a demo score is not predicted affinity.

**Guided campaign wizard:** (1) Select target Nd3+/Dy3+/La3+/Ce3+; (2) competitor Ca2+ or another REE; (3) focus broad/lanmodulin/EF-hand; (4) candidate count; (5) click Discover. Show preset "Find Nd3+ candidates vs Ca2+".

**Progress/trace:** stepper for plan, discovery, structure retrieval, chemistry assessment, evidence review, ranking. Streaming status should be from the actual event log, not fabricated token-by-token text.

**Results:** searchable/sortable table with identity, organism, PDB/AlphaFold availability, evidence class, site geometry indicators, score version, caveat. Show badges for experimental support and hypotheses separately. Do not display score percentages like "95% binding likelihood".

**Candidate detail:** protein identifiers, UniProt and PDB links, sequence metadata, confidence/coverage, annotated coordination residues with atom distances, 3D viewer, full evidence ledger, reasons *for* and *against*, unknowns and suggested validation.

**Chat:** messages with evidence snippets and citations; preset prompt chips: "Why this protein?", "What is the Ca competition evidence?", "Show coordination shell", "How would we test this?". Never claim real-time retrieval if not performed.

**Export:** JSON and CSV; later HTML report / screenshot. Include disclaimers, versions, access dates, selected ions and source identifiers.

**Accessibility:** high contrast; explanations in plain language; keyboard-reachable controls; loading/error states; readable units (Å, M, pH); mobile single-column fallback; avoid color-only evidence labels.

---

## 3. Architecture, components and data flow

```text
                          Streamlit UI
         settings | progress | results | protein 3D | chat
                               |
                     Campaign controller
              (run ID, configuration, event log)
                               |
                      Bounded agent planner
                 (Argo tool selection / summaries)
                               |
       +-----------------------+-----------------------+
       |                       |                       |
 Protein discovery       Structural pipeline       Evidence engine
 UniProt / RCSB /        PDB / AlphaFold DB        References, ligand,
 homolog search          BioPython / geometry      Kd, conditions
       |                       |                       |
       +-----------------------+-----------------------+
                               |
                 Deterministic screening core
            evidence gates | versioned score | audit
                               |
               SQLite / JSON run persistence
```

**Design rule:** external LLM never directly mutates scores or invents references. It invokes typed, allowlisted tools; Python validates arguments, executes and records observations. Numeric features, thresholds and provenance are deterministic and versioned.

### Modules, purpose, existing status, implementation tickets

| Module | v0.1 status | v1.0 ticket |
|---|---|---|
| `app.py` | Basic working Streamlit | Split into multipage views and reusable UX components; empty/loading/error states |
| `models.py` | `Protein`, `Candidate` dataclasses | Pydantic data models: `ProteinRecord`, `StructureRecord`, `BindingSite`, `EvidenceRecord`, `ScoreBreakdown`, `Campaign` |
| `catalog.py` | Synthetic demo | Verified seed fixtures; explicit source/date/checksum |
| `uniprot.py` | Live keyword search | Query pagination, reviewed/unreviewed toggle, entry access, retries, protein/organism deduplication |
| `structure.py` | PDB fetch; deposited metal neighbors | mmCIF fallback, chain mapping, alternate locations, explicit ion-specific coordination, candidate pocket detection |
| `chemistry.py` | Composition/motif hints | Metal-aware feature vector, structural geometry, strict missingness model, benchmark-calibrated ranking |
| `argo.py` | OpenAI-style chat completions | Model discovery, health check, retry/backoff, separate planner/summarizer, safe token budget |
| `agent.py` | Deterministic steps + Argo summary | LLM-directed bounded planner, tool schemas, validation, state machine, audit events |
| `evidence.py` | Not created | Source-linked literature facts with measured Kd/metal/pH/ionic-strength/assay |
| `storage.py` | Not created | SQLite runs, observations, cache and migrations |
| `evaluation.py` | Not created | Benchmark, ablations, ranking quality and failure analysis |
| `report.py` | JSON download via UI | Source-linked reproducible result cards, CSV/HTML exports |

---

## 4. Canonical records / schemas

### ProteinRecord

- `uniprot_accession` (required for live biological entries)
- `canonical_sequence`, `sequence_sha256`, `length`, `taxon_id`, `organism`, `protein_name`
- `reviewed`, `source_url`, `retrieved_at_utc`, `source_version`
- `pdb_ids[]`, `alphafold_id?`, `cross_references[]`
- `is_synthetic` (true for teaching records; cannot enter biological discovery reports)

### StructureRecord

- `structure_id`, `source` (`PDB` / `AlphaFoldDB`), `format` (`mmCIF` / `PDB`)
- `chain`, `uniprot_mapping`, `model_index`, `resolution_angstrom?`, `experiment_type?`
- `mean_local_plddt?`, `coverage_fraction`, `retrieved_at_utc`, `coordinate_checksum`
- `is_metal_bound` and `metal_identity` only if explicit deposited ligand present

### BindingSite

- `site_id`, `structure_id`, `chain`, `residues[]`, `coordinates`
- `site_detection_method` (`deposited-ion` / `geometric-candidate` / `homology-transfer`)
- `ligands[]`: `{atom_name, element, residue, distance_A, role, source}`
- `donor_count`, `coordination_number?`, `geometry_metrics`, `solvent_exposure?`
- `quality_flags[]`, `unknowns[]`; distinguish water oxygen from protein oxygen

### EvidenceRecord

- `claim`, `evidence_level` (`experimental` / `deposited-structure` / `database-annotation` / `computed-hypothesis` / `synthetic-demo`)
- `doi?`, `pdb_id?`, `uniprot_id?`, `source_url`, `access_date`
- for binding constants: `ion`, `Kd_value`, `Kd_units`, `uncertainty`, `assay`, `pH`, `temperature_K`, `buffer`, `ionic_strength`, `competitor`, `protein_construct`, `citation`
- `verified_by_retrieval` boolean; no assertion of primary-paper evidence without retrieved source

### ScoreBreakdown

- `score_version`, `raw_features`, `normalized_features`, `applicability_domain`, `missing_values`, `weights`, `score`, `warnings`
- never name the raw output `binding_probability` or `selectivity_probability` unless statistically calibrated against measured values

### Campaign

- `run_id` (UUID), `query`, `target_ion`, `competitor_ion`, `search_scope`, `limits`, `started_at`, `finished_at`, `status`, `sources`, `tool_events`, `candidate_ids`, `settings_hash`, `code_version`, `result_digest`

---

## 5. Source adapters and APIs

### 5.1 UniProt

Use `https://rest.uniprot.org/uniprotkb/search` with explicit size, format JSON and allowlisted queries; parse `primaryAccession`, `sequence.value`, `organism.scientificName`, recommended/submitted protein names, and cross-references. Retry transient 429/5xx with bounded exponential backoff. Page via response `Link` header where present. Log query and retrieval timestamp. Never combine records with conflicting isoforms automatically.

Query families: lanmodulin name and organism context; known EF-hand annotations; homolog similarity should be done through UniRef/BLAST/MMseqs with appropriate service availability, not by unsupported plain-text name matching. Verify `KW-0254` with current UniProt keyword definitions before relying on it.

### 5.2 RCSB PDB

Use `https://search.rcsb.org/rcsbsearch/v2/query` with documented `full_text`, molecular sequence or chemical component searches as appropriate, plus `https://data.rcsb.org/rest/v1/` / GraphQL for metadata. Download coordinates from `https://files.rcsb.org/download/{PDB_ID}.cif` first, PDB fallback where supported. PDB-to-UniProt mapping can be chain-dependent; resolve IDs explicitly.

Seed PDBs: **8FNS** (experimentally characterized lanmodulin Nd-binding reference); **8FNR** (related Dy-binding reference); **1CLL** (calmodulin comparator; verify chain/conditions). Structure accession selection must be checked for biological construct match before ranking.

### 5.3 AlphaFold DB

Use `https://alphafold.ebi.ac.uk/api/prediction/{uniprot_accession}` to retrieve predicted protein structure metadata. Use AlphaFoldDB to retrieve *protein* structures and confidence metrics. If a structure is predicted without a metal, do not claim the metal is accommodated without additional modelling.

### 5.4 Literature evidence

Use primary publications linked through RCSB/UniProt and optionally Crossref/PubMed (respect APIs, policies, and caching). Extract Kd and competition evidence only with exact source, assay conditions and appropriate units. Persist direct citation URLs. Keep separate "known REE binding" and "REEx versus Ca selectivity" columns. If no verified comparison exists, set `selectivity_evidence = not_available`.

**Implemented (branch `arxiv_rag`, live test pending):** a commentary-only literature critic. Retrieval from Crossref/ChemRxiv abstracts (`lantern/scholarbud/`), claims derived from the measured record, an LLM judge whose verdicts pass a citation/number post-check, and a frozen policy (`lantern/critic/policy.py`) that can badge or flag for review but never changes a number or promotes a candidate. It does not extract Kd values; that remains open.

---

## 6. Structural and chemical screening algorithm

**Stage A: sequence triage**

1. Validate standard 20 amino-acid sequence; flag ambiguous residues instead of silently dropping them.
2. Identify annotated motifs/domains; count acidic donor-capable positions, but keep secondary-structure context unknown.
3. Deduplicate close homologs and stratify family representation.
4. Calculate early-stage low-confidence discovery heuristic. Do not compare scores across chemical elements: v0.1 scores do not depend on element identity.

**Stage B: structural screening**

1. Retrieve structure; verify UniProt chain mapping and coordinate coverage.
2. Classify sites: (i) direct deposited metal site, (ii) metal-site annotation, (iii) geometric candidate, (iv) transferred homolog site. Keep provenance in result.
3. For experimentally bound metal, find coordinating O/N/S protein atoms plus water/other ligands within justified element-/ligand-specific cutoffs. Never classify all residues within a 4 Å shell as directly coordinating atoms.
4. For a metal-free candidate, identify plausible pockets by clustering solvent-accessible donor atoms and/or aligning conserved motifs to reference sites. Do **not** infer a metal center solely from nearby acidic sidechains. Keep predicted center marked as hypothetical.
5. Calculate interpretable descriptors: potential oxygen donor count, carboxylate arrangement, water coordination, residue local geometry, site exposure, steric hindrance, local structural confidence and alignment RMSD where applicable.
6. Annotate whether sidechain protonation and local environmental dynamics are not modeled. Do not report free energies from geometry alone.
7. Visualize each donor atom, residue, hypothetical/deposited center, geometry lines, Å distances and supporting method.

**Stage C: chemical scoring**

Propose a transparent composite of `[site completeness, coordination geometry, confidence, motif conservation, experimental evidence]`. Missing geometry means `not scored`, NOT zero geometry or average data. Weights must be marked provisional until calibrated on a curated dataset. Store the full breakdown; report uncertainty and applicability domain. Experimental quantitative comparisons, when present, should be displayed independently from heuristic chemistry scores.

**Stage D: selectivity and comparison**

1. Determine whether any quantitative REE and Ca2+ Kd measurements exist for the *same* protein construct and compatible experimental conditions.
2. Only then display `log10(Kd_Ca / Kd_REE)` as an experimental selectivity indicator, with uncertainty and source.
3. If not, say "Unknown; no matched selectivity data". Distinguish absence of evidence from demonstrated nonbinding.
4. To improve predictions later, investigate hydration/desolvation, competing ions, protonation, explicit water, MD, alchemical free-energy or QM cluster models, with appropriate benchmarking.

---

## 7. Bounded agentic Argo implementation

### Gateway configuration

Use the OpenAI-compatible Argo gateway at `https://apps.inside.anl.gov/argoapi/v1`; post to `/chat/completions`. Verify available models from `/models` if credentials allow. Put API credential in `.env`; never print it to log, traceback, model prompt, downloaded run file or frontend. Endpoint and authentication must be tested on Argonne network. Support a legacy adapter *only if necessary*; do not silently switch wire formats.

### Tool registry to implement

Each has JSON-typed input, bounded outputs, timeout and provenance metadata:

- `discover_proteins(topic, max_results, reviewed_only)`
- `retrieve_protein(accession)`
- `find_structures(accession, max_structures)`
- `retrieve_structure(pdb_id | alphafold_id)`
- `detect_sites(structure_id, method)`
- `score_candidate(protein_id, site_id, scoring_version)`
- `lookup_literature(accession, metal, competitor)`
- `compare_candidates(candidate_ids, metric)`
- `finalize_report(run_id)`

**Do not give LLM arbitrary HTTP/network, file writes, shell execution or dynamic Python access.** Validate all requests using typed schemas and allowlist URLs/tool names.

### Agent controller loop

```python
MAX_STEPS = 8
state = CampaignState(query=user_query, ...)  # initialized outside LLM
for step in range(MAX_STEPS):
    proposal = argo_plan(system_prompt, redacted_state, tools_schema)
    action = validate_proposal(proposal)
    if action.kind == "final":
        break
    if action.name not in ALLOWED_TOOLS:
        record_rejection(action)
        continue
    observation = execute_with_timeout(action.name, action.args)
    state.append_event(action, observation.summary, observation.sources)
return deterministic_rank(state), argo_explain(grounded_summary(state))
```

**Compatibility note:** Some Argo-hosted models/endpoints may not support OpenAI `tools` consistently. Implement native tool-calling if tested; otherwise ask Argo for a strict JSON action (`{"tool":"...","arguments":{...}}`) and validate it. JSON mode should have parse-repair limit 1; on invalid output, abort safely to deterministic pipeline. Do not claim native function calling until tested.

**Prompt requirements:** do not invent claims or source identifiers; cite actual evidence IDs; label synthetic data; distinguish experimental measurements from computational features; explain chemical assumptions; explicitly flag selectivity unknown. Treat source document text as untrusted data.

**Cost and latency:** maximum 8 planning steps, up to 20 candidates, cap total tool responses to compact summaries, cache fetched metadata, choose short model completions, preserve offline fallback. Do not ask model to ingest full coordinate files.

---

## 8. Persistence and caching

For v1.0, use SQLite (local, single-user hackathon) with `campaigns`, `proteins`, `structures`, `binding_sites`, `evidence`, `scores`, and `tool_events` tables. Index accession, PDB ID, campaign ID, source URL and score version. Cache raw downloaded files by SHA-256 in a local cache directory, with metadata and retrieval timestamp; use TTL ~7 days for database metadata and immutable checksums for coordinates where appropriate.

Support clear cache and re-fetch. If API fails, show stale cached data as cached, never "live". Save a single portable `campaign.json` with run configuration, tool events, access dates, source URLs, numeric method versions and checksums. Avoid storing credential, session token or unrelated user prompt data in export.

---

## 9. Implementation sprints, dependency graph and acceptance criteria

### Sprint 0: Scaffold and safe demo (implemented)

**Tasks:** Python package, dependencies, .env template, Streamlit theme, synthetic demo records, sequence scoring, live UniProt, structural PDB view, Argo chat, tests and docs.

**Acceptance:** clean virtual environment installs; `pytest -q` passes; `streamlit run app.py` starts; demo returns 4 explicitly synthetic records; JSON export works; no credentials checked in. Real-world network integration must be verified on user machine.

### Sprint 1: Real scientific foundation (TOP PRIORITY)

- [ ] Replace `data/demo_proteins.json` for live-demo seed with a new `data/reference_proteins.json` populated from downloaded authentic protein sequences.
- [ ] Independently verify actual UniProt records and chain-to-PDB alignment for 8FNS, 8FNR and 1CLL.
- [ ] Add reference bibliography with citation, type of measurement and exact pH/buffer conditions.
- [ ] Add `source` and `is_synthetic` gates to every ranking/export pathway.
- [ ] Implement prefetch script to populate reproducible real local fixtures for event-day demonstration.
- [ ] Add reference tests to confirm sequence checksum and identity mapping.

**Acceptance:** at least 3 authentic protein entries with IDs and accession links, at least 2 experimental metal structures, reproducible saved cache, no synthetic data presented as natural protein discovery.

### Sprint 2: Real structural interpretation

- [ ] Implement mmCIF loader with Bio.PDB.MMCIFParser; PDB fallback.
- [ ] Extract metal ions, chemically relevant donor atoms and explicit solvent molecules.
- [ ] Correctly handle alternate locations, occupancy, multiple chains, model numbers and chain mappings.
- [ ] Compute coordination distances / donor identities and classify direct ligand versus nearby residue.
- [ ] Render metal spheres, distance dashed-lines and labeled residues in 3D viewer.
- [ ] Compare bound-reference environments (Nd vs Dy) without inferring affinities.
- [ ] Implement pocket finder for metal-free proteins, with an explicit "hypothetical" label.

**Acceptance:** annotated 8FNS lanthanide center with actual deposited coordinating atoms, geometry tables matching manual inspection, and a negative test with no metal that produces no fabricated ion.

### Sprint 3: Agent tools and evidence

- [ ] Add vetted function registry with schemas and strict argument validation.
- [ ] Implement native Argo tool calls or JSON-plan fallback after testing gateway compatibility.
- [ ] Add source provenance to every observation; store run events and real status.
- [ ] Add evidence extractor for primary sources with uncertainty/conditions.
- [ ] Prevent unsupported affinity/selectivity claims at answer-generation time.

**Acceptance:** agent can call at least 3 real tools, handle malformed model action, recover from transient network failure, and produce an audit log containing which tool/source supports each claim.

### Sprint 3b: Literature critic live test (HIGH PRIORITY until done)

- [x] `lantern/scholarbud/`: Crossref/ChemRxiv search, dedup library, BM25 (offline tests).
- [x] `lantern/critic/`: claims, judge + post-check, policy with lineage weight 0.3 and frozen trainable parameters, pipeline, hook in `discover.answer`.
- [x] Live retrieval on the canonical question (table in `docs/critic/CRITIC_LIVE_TRIAL.md`); three defects found and fixed.
- [ ] Full live run with a real judge model (needs a provider key or Argonne network): `scripts/critic_live_trial.py`.
- [ ] Consolidate per-site claims to distinct (element, CN) pairs.
- [ ] Populate `data/critic_lineage.json` with the rules' source DOIs.
- [ ] Hand-labelled claim set (>= 30) and judge scoring; with/without-critic ablation on controls and known negatives.
- [ ] Narrator integration of verdicts (with citation check), then push the branch.

| Stage | Artefact | Status (2026-10-21) |
|---|---|---|
| 1 Input and plan | `proteins for capturing Ce3+` -> target Ce3+, parsed by the deterministic fallback | live, done |
| 2 Claims from the measured record | 12 claims: 9 site coordination numbers (8FNR Dy, 8FNS Nd, CN 7-10) + 3 design-rule claims | live, done |
| 3 Retrieval | 78 records from live Crossref/ChemRxiv; top 4 per claim by BM25; PDB depositions and abstract-less records dropped | live, done |
| 4 Judge verdicts | supports / contradicts / no_evidence per claim, with cited evidence numbers | **NOT RUN: no model access yet** |
| 5 Policy decision | keep / badge / review per protein (frozen parameters, lineage weight 0.3) | **NOT RUN** (all keep by construction) |
| 6 Final shortlist | order unchanged: A0A4V2JDD3, C5B164, P02585, P0DP23, P69905, P00766; measured numbers identical | verified unchanged |

Full per-claim table (claim, source field, evidence DOIs, verdict): `docs/critic/CRITIC_LIVE_TRIAL.md` (+ `.json`). Regenerate with
`python scripts/critic_live_trial.py --provider <argo|openai|anthropic> --out docs/critic/CRITIC_LIVE_TRIAL.md`.

**Problems the live run found that the offline tests could not confirm** (all fixed, each with a regression test):
1. Crossref returned HTTP 400 for a `select` field (`subtype`) that the route does not support; recorded fixtures cannot reveal a bad request.
2. With no judge configured, retrieved evidence was discarded, so a retrieval-only trial showed an empty table.
3. The best-ranked "evidence" for claims about 8FNR was the PDB deposition of 8FNR itself (DOI 10.2210/pdb8fnr/pdb): the measured data
   cited in support of itself. PDB deposition DOIs and abstracts under 80 characters are now excluded.
4. Still open: per-site claims share one query and retrieve nearly the same papers, so judge calls are mostly redundant. Consolidate to
   one claim per distinct (element, coordination number) pair before paying for a full run.
5. Still open: the lineage list (`data/critic_lineage.json`) is empty, so no source is discounted yet; the CN >= 9 and loop-spacing
   rules' source DOIs must be added or the 30% lineage weight does nothing.

**Caveats** (these also belong in any write-up): abstract-level evidence only (ChemRxiv full text is behind Cloudflare; about 479
full texts are reachable through Europe PMC, mostly COVID-era); preprints are not peer reviewed; lexical (BM25) retrieval; the judge may
share a model family with the narrator; literature is biased toward reported successes and a missing paper is not evidence; judge
accuracy is unmeasured (no labelled claim set); the policy is frozen, not trained. The critic never writes or edits a number and never
promotes a candidate.

**Acceptance:** the table has verdicts and decisions for every claim; every cited evidence number exists; no measured number differs from the
input record; no candidate is promoted; failures degrade to `keep`; correct controls are unchanged with the critic on.

### Sprint 4: User-friendly presentation

- [ ] Guided search presets and launch example.
- [ ] Candidate cards, confidence/evidence explanations and saved run browsing.
- [ ] 3D site inspector with residues and legend; plain-English explanations.
- [ ] Responsive UI, clear errors, CSV and JSON export, example questions.
- [ ] Demo narration and 90-second backup video/screenshots.

**Acceptance:** a new user can launch the demo, run search, inspect a protein, see evidence and export findings without reading developer docs.

### Sprint 5: Benchmark and science review

- [ ] Assemble literature-backed positives, calcium binders and ambiguous examples.
- [ ] Evaluate retrieval recall of known REE binders; precision in top-k shortlist on curated labels.
- [ ] Blind reviewer evaluation of explanation/source correctness.
- [ ] Compare feature ablations: motifs only, acidic fraction, geometry, and evidence-supported shortlist.
- [ ] Add uncertainty and family-aware holdout testing (avoid homolog leakage).

**Acceptance:** report meaningful retrieval quality and honest limitations; no quantitative metal selectivity prediction is claimed without matched benchmark data.

---

## 10. Tests and failure scenarios

**Unit tests:** amino acid validation, motif edge cases, empty search, missing structure, scoring reproducibility, stable sorting, schema validation, model text redaction, chemistry labeling.

**Integration:** public UniProt response with mock + live smoke test; RCSB retrieval + mmCIF parser; Argo API response/mock and auth failures; export roundtrip and cache misses.

**Structural gold fixtures:** real metalloprotein reference with deposited lanthanide; reference protein without lanthanide; multiple chains; disordered sidechain; duplicate atom altloc; water ligand; Ca-only structure. Never assume `HETATM` or residue labels are consistent without inspecting mmCIF chemistry.

**Agent adversarial tests:** forged citation in source text; user asks "give me exact Kd" without measurement; malformed tool JSON; request for arbitrary URLs; prompt injection in metadata; noisy evidence that appears to conflict; unavailable target ion; LLM repeatedly calls same tool.

**UI:** blank state, empty live result, CDN viewer blocked, Argo inaccessible, UniProt rate limit, save/export, screen-reader labels, small viewport.

**Scientific acceptance:** correct provenance per protein, explicit unknown selectivity, no synthetic data as authentic, no correlation/score presented as experimentally validated affinity.

---

## 11. Security, reliability, observability

- `.env` in `.gitignore`; never ship access tokens in zip or screenshot.
- All external requests use HTTPS, explicit timeout, bounded pages and limited results.
- No arbitrary shell commands or user-controlled unrestricted URL fetch.
- Sanitize viewer UI; serialize downloaded PDB as JSON before embedding JS; use hosted code only over HTTPS. Prefer self-hosting viewer dependency for network-constrained installations.
- Log event type, source, elapsed time, error class, retrieval date, cache hit. Redact auth headers and protein data supplied privately by users.
- Limit retries; provide retry button and explanatory errors rather than empty screens.
- Keep agent tools read-only and side-effect-free for hackathon.
- Give scientific provenance higher priority than model confidence.

---

## 12. End-to-end demo script (3–4 minutes)

**00:00–00:25 — Problem:** extracting/separating REEs is important; nature provides protein coordination environments, but identifying useful known proteins is information-intensive.

**00:25–00:50 — Ask:** select Nd3+ vs Ca2+, choose live discovery; show query and agent/provenance steps. If internet unavailable use a **precomputed authentic reference fixture**, not synthetic sample as scientific evidence.

**00:50–01:40 — Discovery:** show known lanmodulin positive control plus other real candidates; note the distinction between experimentally known and hypothesized binding.

**01:40–02:30 — Molecular view:** select a PDB structure; rotate protein, show deposited Nd center and annotated donor residues and distances. Show why geometry matters beyond counting Asp/Glu.

**02:30–03:10 — Argo explains:** ask why candidate ranks and which claims are supported; illustrate agent calling tools and synthesizing verified evidence.

**03:10–03:40 — Scientific humility:** explain missing Ca competition measurement and how a competition binding experiment would validate or reject the hypothesis.

**03:40–04:00 — Extension:** proteins -> peptides -> engineered variants -> actual wet-lab and rigorous molecular simulation, outside present hackathon scope.

**Fallback:** if live Argo offline, show precomputed previously generated and labelled report + event trace; do not claim the agent is running live. If PDB CDN fails, display residue tables and primary PDB link.

---

## 13. Coding agent handoff instructions

> You are implementing LANTERN v1.0 from this document. Read `README.md`, `docs/SCIENTIFIC_CONTRACT.md`, source files and tests first. Maintain the current runnable offline demo and stable public API. Work sprint by sprint, beginning with authentic scientific reference fixtures. Before modifying code, list the specific planned files and acceptance tests for the sprint. Never alter experimental claims without verifiable citations. Synthetic sequences must remain explicitly synthetic. All scores must remain labeled as heuristics until calibrated. Do not hardcode Argonne credentials. Keep Argo API optional and gracefully degrade when inaccessible. Run `pytest -q` after each change, add focused tests, and explain what evidence each new feature can and cannot establish.

**Recommended first task:** implement Sprint 1: retrieve genuine lanmodulin/calmodulin sequences, validate exact PDB-to-UniProt mapping, build a local reference fixture, introduce `is_synthetic` and access-date fields, and create acceptance tests that fail if synthetic educational data are presented as true binding discoveries.

---

## 14. References and live documentation

- Argonne Argo quickstart (community): https://github.com/NIAID-BRC-Codeathons/ANL-Argo-Quickstart
- Argo API browser (may require network access): https://apps.inside.anl.gov/argoapi/docs
- ALCF inference endpoint documentation (different authentication and endpoint): https://argonne-lcf.github.io/user-guides/services/inference-endpoints/api/
- UniProt REST API: https://www.uniprot.org/help/api_queries
- UniProtKB search: https://rest.uniprot.org/uniprotkb/search
- RCSB API overview: https://www.rcsb.org/docs/programmatic-access/web-apis-overview
- RCSB Search API: https://search.rcsb.org/
- RCSB structures: https://www.rcsb.org/structure/8FNS ; https://www.rcsb.org/structure/8FNR
- AlphaFold DB: https://alphafold.ebi.ac.uk/
- 3Dmol.js: https://3dmol.org/

Keep a versioned reference bibliography of primary studies as actual data are incorporated; links here are infrastructure documentation and entry points, not proof of protein selectivity.
