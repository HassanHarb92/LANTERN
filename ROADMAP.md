# REE-Finder — Roadmap to a Working System

**Status date:** 2026-10-19
**Method:** every claim below was verified by running the code in this repo and querying the live
APIs it depends on. Commands are reproducible; numbers are not estimates.
**Companion docs:** `IMPLEMENTATION_PLAN.md` (prior aspirational plan — see §7 for what to retire),
`docs/SCIENTIFIC_CONTRACT.md` (claim boundaries — keep, it is sound).

---

## 1. The one-paragraph version

The project is currently framed as *"search a vast protein universe and rank candidates."* That
framing is why it feels unfinished: the search space looks infinite, so no amount of work closes it.
The real problem is **much smaller and already enumerable**, and that is good news:

- **617** PDB entries in the entire world contain a rare-earth ion. Not 617,000. You can download
  and curate all of them in an afternoon.
- **189** proteins in UniProt belong to the lanmodulin (LanM) family. **188 of them are
  uncharacterized.** That is the discovery space, and it fits on one screen.
- Every one of those 188 has an AlphaFold model already computed.

So REE-Finder should stop being a search engine and become **a complete, curated, verified evidence
base over a finite corpus, plus a ranked shortlist of the 188 unstudied LanM homologs.** That is a
deliverable a structural biologist would actually use, it is achievable, and nobody has packaged it.
The agent layer orchestrates and explains; it is not the discovery mechanism.

---

## 2. Verified state of the code

Environment built clean (`python3 -m venv .venv`, Python 3.14.7, all deps install without pinning
problems). `pytest -q` → **5 passed**. The app imports and runs.

| Component | Verdict | Evidence |
|---|---|---|
| `structure.py` | **Genuinely good.** Keep and build on it. | Against real PDB 8FNS it finds all 4 Nd³⁺ sites in 0.4 s with correct donor residues (Asp35/37/39, Thr41, Glu46) and Nd–O distances 2.39–2.53 Å — textbook lanthanide coordination. |
| `chemistry.py` | Works, but measures the wrong variable (§3.1) | Real-sequence ranking is sane: LanM 74.7 > TnC 69.0 > CaM 57.0 ≫ haemoglobin 23.4 > chymotrypsinogen 19.1. |
| `uniprot.py` | **Two of three queries are broken** (§3.2) | `ef-hand` → 755 endocytosis proteins; `lanmodulin` → exactly 1 result. |
| `catalog.py` + demo data | **Degenerate** (§3.3) | 3 of 4 demo records tie at exactly 45.0 with 0 motif matches. |
| `argo.py` | **Silently renders auth failures as science** (§3.4) | Verified live against the real gateway. |
| `agent.py` | Not an agent; a 3-line fixed script | No planning, no tool selection, no branching. Honest naming needed. |
| `models.py`, `app.py` | Thin but fine as a base | — |
| Tests | 5 tests, all on the weakest module | Nothing covers `structure.py`, the strongest module. |

**Headline:** the part everyone assumes is hardest (structural parsing) is the part that already
works. The parts assumed easy (database queries, the LLM call) are the ones that are broken.

---

## 3. Defects found, in priority order

### 3.1 The score measures the one variable that does *not* discriminate

This is the central scientific problem. I computed coordination descriptors for real lanthanide
sites versus real calcium sites:

| Structure | Site type | Coord. number | Bidentate carboxylates | Carboxylate charge |
|---|---|---|---|---|
| 8FNS (LanM + Nd³⁺) | lanthanide | **9–10** | **2–3** | −3 to −4 |
| 8FNR (LanM + Dy³⁺) | lanthanide | **9** | **3** | −4 |
| 1CLL (calmodulin + Ca²⁺) | calcium | **7** | **1** | −3 to −4 |

Read the last column: **the carboxylate count is identical between lanthanide and calcium sites.**
Acidic-residue content — the thing `score_sequence()` actually measures — carries no signal for the
question the project exists to answer. What *does* separate them is **coordination number (9–10 vs 7)
and bidentate carboxylate count (2–3 vs 1)**, both of which are computable from structure and
neither of which is currently computed.

This is consistent with the underlying chemistry: Ln³⁺ and Ca²⁺ have similar ionic radii, so size
does not discriminate; charge density and the resulting higher coordination number do.

The empirical consequence is visible in the ranking: real LanM (74.7) barely edges out troponin C
(69.0). A 5.7-point gap between the canonical REE binder and a pure calcium protein is noise. **The
heuristic is a competent EF-hand detector and not a REE detector**, and the app should say so until
§5.3 lands.

### 3.2 `uniprot.py` — the "ef-hand" search returns endocytosis proteins

`ALLOWED_QUERIES["ef-hand"]` is `keyword:KW-0254`. Verified against the UniProt keyword API:

> **KW-0254 = "Endocytosis"** · category: Biological process

Top hits the app actually returns today: Huntingtin-interacting protein 1, Lymphocyte antigen 75,
Epsin-2 — 755 of them, none relevant. There is **no UniProt keyword for EF-hand**; it is a domain.
Correct handles (all verified live):

- EF-hand domain → `xref:interpro-IPR002048` (488,200 proteins — too broad to be a "family" option)
- Calcium → `KW-0106` · Metal-binding → `KW-0479`
- **Lanmodulin family → NCBIfam `NF053806`** (189 proteins) ← this is the one that matters

Also: `protein_name:lanmodulin` returns **exactly one** protein (C5B164). A one-row table is not a
discovery. The LanM *family* handle above is the fix — but it is **not reachable from UniProt
search**:

> **Second gotcha, also found the hard way.** `xref:ncbifam-NF053806` returns **0** results, and
> inspecting C5B164's cross-references shows why: UniProt records no NCBIfam xref for it at all.
> Its only family handles are the generic EF-hand ones (IPR002048, IPR011992, IPR018247, Pfam
> PF13202, PROSITE PS00018/PS50222) — every one of which matches hundreds of thousands of calcium
> proteins. **LanM family membership exists in InterPro, not in UniProt.** Retrieval is therefore
> two-step: list the 189 accessions from the InterPro API, then batch-fetch sequences from UniProt
> with `accession:A OR accession:B OR …`. Both halves verified live.

Counts of this kind drift as the databases grow — IPR002048 was 485,408 earlier in this analysis
and is 488,200 now. Record a retrieval date beside every count, and never hard-code one as a test
assertion.

### 3.3 The default demo is uninformative and self-contradicting

Offline demo is the default mode and the first thing any user or judge sees. Scoring the shipped
`data/demo_proteins.json`:

```
45.0  Lanmodulin (demonstration reference)      0 motifs
45.0  Calmodulin (demonstration comparator)     0 motifs
45.0  Hypothetical oxygen-rich candidate A      0 motifs
10.0  Hypothetical candidate B                  0 motifs
```

A three-way tie, and **zero of the four synthetic sequences match the EF-hand pattern the tool
searches for** — including the one labelled "lanmodulin". Real lanmodulin scores 74.7 with 3 motif
hits. The demo therefore showcases the tool failing, while the honest "these are synthetic" labels
(which are good, and should stay as a principle) cannot rescue a ranking that is a tie.

Fixing this is nearly free: real sequences are public, and swapping them in makes the demo *more*
honest, not less — §5.1.

### 3.4 `argo.py` renders authentication failures as scientific analysis

Verified live against `https://apps.inside.anl.gov/argoapi/v1`, and cross-checked against the
gateway's own OpenAPI spec (`/argoapi/openapi.json`) by a second, independent pass. Four findings:

1. **The gateway is reachable from this machine without VPN configuration.** `/v1/models` returns
   HTTP 200 and lists **37 models**, including Claude Opus 5, Claude Sonnet 5, GPT-5.6, Gemini 3.5
   Flash, and three embedding models (`v3large`, `v3small`, `ada002`). The embedding models matter
   later (§5.4). *Caveat:* the `apps.inside.anl.gov` hostname suggests an Argonne-internal service,
   and this machine may simply be on an ANL network. **Do not assume it resolves from an arbitrary
   external network** — confirm from a known-outside connection before promising that to anyone.
2. **Auth is an ANL domain username, not an API key.** Argo reads it from the bearer token or a
   `user` body field and validates it as a username. `.env.example` calling it `ARGO_API_KEY` and
   "your Argo credential" is actively misleading.
3. **Failures arrive as HTTP 200 with a well-formed chat completion.** Running the real client with
   a bad credential raises no exception and returns:

   > ⚠️ IMPORTANT AUTHENTICATION NOTICE FROM ARGO ⚠️ 🚫 ACCESS DENIED 🚫 …

   `ArgoClient.chat()` passes this straight through, and `app.py` renders it with `st.markdown()`
   in the research-assistant pane. **An unauthenticated user sees an access-denied notice displayed
   where scientific analysis should be.** The `raise_for_status()` guard cannot catch this, because
   nothing failed at the HTTP layer.

   Two structural signals detect it without string-matching the prose, which may change:
   the response `id` begins with **`chatcmpl-blocked-`**, and **`usage.total_tokens == 0`**. Check
   both; treat either as an auth failure.
4. **The hard-coded sampling parameters will break on several Argo models.** `argo.py` always sends
   `temperature=0.2` and `max_tokens=900`. Per the gateway spec: GPT-5.x rejects any `temperature`
   other than exactly `1` (omit it), o-series models accept only `max_completion_tokens` (not
   `max_tokens`), and Anthropic models *require* an explicit `max_tokens` ≤ 21,000 when not
   streaming. A single hard-coded parameter set cannot serve all three families — the client needs
   per-model-family parameter shaping.

### 3.5 `structure.py` reports proximity, not coordination

Four concrete bugs behind an otherwise solid module:

- **Carbon atoms counted as contacts.** The neighbour search is element-blind, so carboxylate
  carbons (Asp39.CG at 2.91 Å, Glu46.CD at 2.92 Å) enter the list alongside true O donors. Filter to
  O/N/S.
- **Waters silently dropped.** `residue.id[0] != " "` excludes HETATM, which excludes HOH. Every Nd
  site in 8FNS has 2 coordinating waters. Reported CN is therefore 5 when the true CN is 9 — and CN
  is exactly the discriminating variable from §3.1. This bug destroys the signal the project needs.
- **The ion table has the §4 ligand-code bug baked in.** `symbols` in `structure.py:24` lists
  `ER` and `TM`, which **are not real PDB chemical components**, while omitting `ER3`, `YT3`,
  `EU3`, `GD3`, `HO3`, and `YB2`, which are. The module therefore cannot see a single erbium or
  yttrium site, and silently misses the second code for europium, gadolinium, holmium, and
  ytterbium. Replace with the verified 18-code set in §4.
- **`fetch_pdb` requests the legacy `.pdb` format only**, which RCSB does not generate for large
  structures: `6EK0`, `7K00`, and `3J3Q` all return **HTTP 404** for `.pdb` and **HTTP 200** for
  `.cif`. `app.py:99` already half-knows this ("Some entries are mmCIF-only") but treats it as an
  unavoidable user-facing warning rather than a bug to fix. Fall back to mmCIF, and prefer
  BinaryCIF (`https://models.rcsb.org/{ID}.bcif`) for bulk work — it is far smaller over the wire.

---

## 4. The strategic reframe: three finite corpora

Everything below follows from sizing the problem honestly.

**Corpus A — the global rare-earth structure set: 617 entries.** Complete per-element counts, from
the RCSB Search API:

| Element | Entries | | Element | Entries | | Element | Entries |
|---|---:|---|---|---:|---|---|---:|
| Gd | 179 | | Sm | 52 | | Ho | 16 |
| Yb | 119 | | Y | 49 | | Ce | 6 |
| Tb | 64 | | Eu | 28 | | Er | 6 |
| Pr | 57 | | La | 23 | | **Nd** | **4** |
| | | | Lu | 17 | | **Dy** | **2** |

Sc, Pm, Tm: **zero**. For contrast, Ca²⁺ appears in **16,658** entries.

> **Implementation gotcha, found the hard way.** There is no single ligand code per element. Erbium
> is `ER3` (plain `ER` does not exist); yttrium is `YT3`; and Eu, Gd, Ho, Yb each have *two* codes
> (`EU`/`EU3`, `GD`/`GD3`, `HO`/`HO3`, `YB`/`YB2`) that must be merged. Querying the obvious
> two-letter symbols alone undercounts the corpus by ~15% and reports zero erbium structures. The
> verified code set is: `LA CE PR ND SM EU EU3 GD GD3 TB DY HO HO3 ER3 YB YB2 LU YT3`. Beware also
> that `Y`, `SC`, `TM3`, `ND3`, `LA3` are codes for unrelated *organic* molecules — matching on
> element symbol alone will silently poison the corpus.

Two things follow. First, this corpus is small enough to download, parse, and hand-check in full —
it should be a versioned asset in the repo, not something fetched live. Second, it is **not** mostly
natural lanthanide biology, and sampling the titles shows what it actually contains:

- **Heavy-atom phasing derivatives** (Gd, Yb, Sm, Lu, Ho, Pr on ordinary proteins — lysozyme,
  inositol monophosphatase, CMP kinase). Mostly surface sites; mostly noise, but they make a useful
  *negative* set of non-specific lanthanide binding.
- **Lanthanide-substituted calcium sites** — Tb in troponin C and calmodulin, Yb in Factor XIII's
  ion site and in cadherins, Gd in phosducin. **This is the richest seam in the corpus.** Each entry
  is an experimentally demonstrated Ca site that accepts a lanthanide, which is the closest thing
  available to direct evidence on the Ln-versus-Ca question driving the whole project.
- **Lanthanide-binding tags (LBTs)** — engineered high-affinity lanthanide peptides, several with
  structures (e.g. ubiquitin and interleukin-1β solved by SAD using inserted LBTs). Engineered
  rather than natural, so they cannot enter a "natural protein discovery" result, but they are an
  excellent validation set for M3: a descriptor that does not rank known high-affinity LBT sites
  highly is broken.
- **Genuine natural lanthanide biology** — a small set: lanmodulins, lanthanide-dependent methanol
  dehydrogenases, and relatives.

Curation into these four classes is therefore mandatory, and *is itself the scientific
contribution* — no public resource currently offers it.

**Corpus B — the discovery space: 189 LanM-family proteins, 188 uncharacterized.** NCBIfam
NF053806; 1 reviewed (C5B164), 188 unreviewed, mostly *Methylobacterium* and relatives. Spot-checked
AlphaFold coverage: all present, mean pLDDT 77–83. This is the project's headline deliverable.

**Corpus C — the broad screen: ~488,000 EF-hand proteins** (488,200 on 2026-10-19). Only attempt this after a descriptor
validated on A and B exists. It is the stretch goal, not the starting point.

---

## 5. Milestones

Each milestone is independently demoable and leaves the app working. Effort assumes one developer.

### M0 — Stop the bleeding (half a day) — ✅ **DONE 2026-10-19**

Small, high-leverage correctness fixes. No new capability.

> **Completed.** All five bullets below are implemented and verified. Test suite went from 5 tests
> to **47**, all offline, including the first coverage `structure.py` has ever had. Measured
> results: 8FNS reports CN = 9 (7 protein O + 2 water) on sites 201–203 and CN = 10 on site 204;
> 1CLL calcium sites report CN = 7 (6 protein + 1 water) under identical rules — the §3.1
> separation survives the rewrite. `lanm-family` retrieval returns real uncharacterized homologs
> scoring 59.7–75.5 with 2–3 motif hits. The Streamlit app runs clean under `AppTest` with zero
> exceptions. Baseline commit `5e7491f` is the restore point if any of this needs reverting.

- `argo.py`: reject auth-denial responses that arrive as HTTP 200 — test `id.startswith("chatcmpl-blocked-")`
  **or** `usage.total_tokens == 0`, and raise `ArgoError`; rename `ARGO_API_KEY` → `ARGO_USER`
  across `.env.example`/README with a note that it is an ANL username; send it in the `user` field;
  add a `/v1/models` health check behind the "Argo configured" badge, which currently only checks
  that two strings are non-empty. Shape sampling parameters per model family (§3.4.4) instead of
  hard-coding `temperature=0.2`/`max_tokens=900`.
- `uniprot.py`: delete the `ef-hand`/KW-0254 query. Add a `lanm-family` source that resolves the
  189 accessions through the **InterPro** API and then batch-fetches sequences from UniProt — the
  family is not selectable from UniProt search alone (§3.2).
- `structure.py`: filter neighbours to elements O/N/S; include HOH as explicitly labelled water
  donors; report protein donors, water donors, and total CN separately; replace the ion-symbol set
  with the verified 18 codes from §4; fall back to mmCIF when `.pdb` 404s.
- `app.py`: replace the generic "sequence composition" disclaimer with the specific, defensible
  statement from §3.1 — this score detects EF-hand-like metal-binding proteins and does not
  discriminate lanthanide from calcium.
- Rename `run_campaign` honestly, or make `agent.py` stop advertising agency it does not have.

**Done when:** a bad Argo credential surfaces as a visible error, not as prose; `binding_neighborhood("8FNS")`
reports CN = 9 (7 protein O + 2 water) per site; `fetch_pdb("6EK0")` returns coordinates instead of
raising; no query returns endocytosis proteins.

### M1 — Real reference data (1–2 days)

- Replace `data/demo_proteins.json` with `data/reference_proteins.json`: real sequences for C5B164
  (LanM), the *H. quercus* LanM of 8FNR, human calmodulin P0DP23, troponin C P02585, plus two true
  negatives (P69905, P00766). Store accession, SHA-256 of sequence, retrieval date, source URL.
- Keep the synthetic records in a separate `data/synthetic_examples.json` used **only** by tests.
  The §3.3 tie disappears; the existing provenance-labelling tests get stronger, not weaker.
- Add a prefetch script caching 8FNS, 8FNR, 1CLL coordinates locally so the demo is network-free.
- Tests: sequence checksums, and an acceptance test asserting real LanM outranks both calcium
  proteins and both negatives.

**Done when:** the default demo runs offline on authentic sequences and produces a non-degenerate,
chemically defensible ranking.

### M2 — The lanthanide structure corpus (3–5 days) ← *the core asset*

Build Corpus A as a versioned local database.

> **Head start:** `data/ree_pdb_entries.json` already ships the verified enumeration — all 617
> entry IDs with their rare-earth elements and structure titles, plus a provenance block. It is
> explicitly marked `"curation_status": "uncurated"`. M2 begins by downloading and classifying
> these, not by rediscovering them.

- Download mmCIF for all 617, parse with `MMCIFParser`, extract every rare-earth site with full
  first-shell geometry. (If you re-derive the list, use the **full ligand-code set in §4**.) Use
  BinaryCIF (`models.rcsb.org/{ID}.bcif`) for the bulk pull — much smaller than mmCIF over 617
  entries — and never the legacy `.pdb` endpoint, which 404s on large structures (§3.5).
- Compute per site: CN, protein-O/N/S donor counts, water count, bidentate carboxylate count,
  mean and spread of Ln–O distance, residue composition, B-factors/occupancy, solvent exposure.
- **Classify every site into the four classes of §4** — natural Ln biology, Ln-substituted Ca site,
  engineered LBT, phasing/surface artefact. Use deposition metadata and title text for a first
  pass, then hand-check. Site 11 of 8FNR (CN = 4, 2 carboxylates, no water) is a worked example of
  an artefact the classifier must reject; sites 1–3 of the same entry (CN = 9, 3 bidentate) are
  what it must keep.
- Build the matched Ca²⁺ contrast set from 1CLL and comparable EF-hand structures. Where a protein
  appears in both sets — troponin C with Ca and with Tb, calmodulin with Ca and with Tb — you have
  a *paired* same-protein comparison, which is the strongest evidence in the corpus. Extract these
  pairs explicitly.
- Ship as `data/lanthanide_sites.parquet` + a provenance manifest.

**Done when:** a single local query returns every known lanthanide protein site with geometry and a
curation label, and the CN distributions for biological Ln sites versus Ca sites separate visibly.

### M3 — A descriptor that actually discriminates (3–5 days)

- Implement the geometric descriptor from §3.1 — CN, bidentate carboxylate count, donor-atom
  composition, carboxylate-oxygen density, site burial — scored on structures, not sequences.
- Calibrate thresholds on M2's curated Ln sites versus the Ca contrast set. With ~tens of
  genuine biological Ln sites this is **threshold calibration and ROC reporting, not machine
  learning** — do not train a model on this sample size and do not call the output a probability.
- Version it (`score_version: "geometry-v1"`) and keep the sequence heuristic alongside, clearly
  labelled as triage only.
- Missing geometry must yield `not_scored`, never 0 and never an imputed mean.
- **Sanity gate:** the descriptor must rank engineered lanthanide-binding-tag sites (known
  high-affinity, from M2) above phasing-derivative surface sites. If it does not, stop and fix it
  before touching M4.

**Done when:** on held-out structures the descriptor separates biological lanthanide sites from
calcium sites with a reported ROC/AUC and an honest confidence interval, and LanM's margin over
calmodulin is large rather than the current 5.7 points of noise.

### M4 — Screen the 188 (2–3 days) ← *the headline result*

- Pull all 189 LanM-family sequences and their AlphaFold models.
- Run the M3 descriptor over predicted structures. Gate on local pLDDT: a low-confidence region
  yields `not_scored`, not a low score.
- Rank, and produce per-candidate evidence cards: identifiers, organism, predicted site residues,
  descriptor breakdown, AlphaFold confidence, and what experiment would test it.
- Position C5B164 as a positive control: if the pipeline does not rank the one characterized family
  member highly, the pipeline is wrong.

**Done when:** a ranked, evidence-backed shortlist of previously uncharacterized LanM homologs
exists, with the known binder recovered as a control. **This is the result the project is for.**

### M5 — Evidence ledger and honest selectivity (2–3 days)

- Hand-curate a literature table of measured lanthanide and Ca²⁺ affinities with assay conditions
  (pH, buffer, method, construct). Expect **tens of entries, not hundreds** — the matched-condition
  Ln-vs-Ca literature is small, which is itself a finding worth stating in the UI.
- Display `log10(Kd_Ca / Kd_REE)` **only** where both values exist for the same construct under
  comparable conditions; otherwise show "no matched measurement", distinct from "does not bind".
- Wire UniProt binding-site annotations (C5B164 already carries 20) as corroborating evidence.
  Filter on the **structured ChEBI identifier**, not the description text: `ft_binding` features
  carry `ligand.id` values such as `ChEBI:CHEBI:29108` (Ca²⁺), which is a stable key, whereas
  `ligand.name` is free text. Request it via `fields=ft_binding` — note that any invalid field name
  makes UniProt reject the **whole request** with HTTP 400, so validate field lists once up front.

**Done when:** every selectivity claim in the UI traces to a citation with conditions, or is
explicitly marked unmeasured.

### M6 — Real agent layer and UI (3–5 days)

- Now that tools return verified data, add the bounded planner: typed tool registry, argument
  validation, ≤8 steps, full audit trail. **Native function calling is available** — the gateway's
  OpenAPI spec declares `tools`, `tool_choice`, and `parallel_tool_calls` on the request, and
  `tool_calls`/`tool_call_id` on messages, so a real tool-calling loop is viable and no JSON-action
  fallback is needed. Two constraints: it works on non-streaming `/v1/chat/completions` only
  (the legacy `/streamchat/` path does not accept tools), and *runtime* behaviour per model is
  still unverified — the spec proves the schema is accepted, not that every one of the 37 models
  honours it. Probe two or three models at M6 entry and pin the one that works.
- The LLM narrates and selects among validated tools; it never writes a score or a citation.
- UI: candidate cards, 3D site inspector with donor atoms and distances labelled, evidence ledger,
  CSV/JSON export with versions and access dates.
- Self-host 3Dmol.js rather than CDN-loading it, so the demo survives a hostile network. Current
  release is **2.5.5**; `app.py:105` loads an unpinned `3Dmol.org/build/3Dmol-min.js`, which is
  both unversioned and a third-party origin. Vendor it from npm (`3dmol@2.5.5`), or pin
  `https://cdn.jsdelivr.net/npm/3dmol@2.5.5/build/3Dmol-min.js` as an interim step.

**Done when:** the agent completes a campaign end-to-end with an audit log mapping every claim to a
tool call and a source, and degrades to the deterministic pipeline when Argo is unreachable.

### Stretch — Corpus C

Broad EF-hand screen, homology-aware holdout to avoid leakage between close homologs, and only then
any discussion of generalization beyond the LanM family.

---

## 6. Sequencing and dependencies

```
M0 ──► M1 ──► M2 ──► M3 ──► M4  (the critical path to the headline result)
                      │
                      └────► M5 (parallelizable: curation, not code)
                                  │
M6 ────────────────────────────────┘  (needs M2–M5 to have something real to orchestrate)
```

Critical path to a defensible scientific result: **M0 → M1 → M2 → M3 → M4**, roughly 10–15
developer-days. M5 is curation work that can run in parallel with M2/M3. **M6 is last on purpose**:
an agent over broken tools produces confident nonsense, which is strictly worse than no agent.

If time is short, M0 + M1 + M4-with-sequence-scoring is a credible 3-day demo — but say plainly that
ranking is triage-grade until M3 lands.

---

## 7. What to retire from `IMPLEMENTATION_PLAN.md`

The existing plan is admirably careful about scientific honesty — keep that spirit and keep
`SCIENTIFIC_CONTRACT.md` as written. But it was composed before anyone measured the problem, and
parts are now contradicted by evidence:

- **"Verify KW-0254 before relying on it"** → verified; it is Endocytosis. Remove the query.
- **8FNR described as a "related Dy-binding reference"** → it is a *different organism*
  (*Hansschlegelia quercus*), a distinct LanM with a different site architecture (CN 9 with 3
  bidentate carboxylates and no coordinating water, versus 8FNS's CN 9 with 2 waters). That
  difference is scientifically interesting and should be surfaced, not flattened.
- **Sprint ordering** puts the agent framework (Sprint 3) before structural interpretation is
  trustworthy. Invert: tools first, agent last.
- **"Benchmark-calibrated ranking" and ML framing** → with ~tens of biological Ln sites, commit to
  calibrated thresholds with honest error bars. Promising a trained model oversells the data.
- **Argo section** assumed VPN-gated access, uncertain wire format, and a secret API key. Two of
  the three are resolved (§3.4): the wire format is OpenAI-shaped and auth is a username, not a
  key. **Keep the network caveat** — the gateway answers from this machine, but the hostname is an
  internal one and that may not generalize.
- **"Set a descriptive User-Agent for UniProt"** → not a documented UniProt requirement. Their REST
  docs ask for no custom header, and requests without one are served normally. Harmless to send,
  but do not present it as compliance. (NCBI E-utilities *does* require contact info — do not
  confuse the two services' policies.)
- The plan's instinct that **"neither a plausible AlphaFold structure nor an acidic sequence is
  evidence of REE-over-Ca selectivity"** was exactly right, and §3.1 now quantifies why. Promote
  that line from a caveat to the design principle it deserves to be.

---

## 8. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Curated biological Ln sites turn out to be ~20, not ~100 | M3 calibration is underpowered | Report confidence intervals; frame as hypothesis ranking, never prediction. Decide at M2 exit, where the real count is known. |
| AlphaFold apo models do not represent the metal-bound conformation | M4 descriptors misleading on predicted structures | Validate the descriptor on holo structures first; gate on pLDDT; label predicted sites hypothetical. The plan's existing warning here is correct. |
| Argo account not provisioned | No LLM layer | Everything through M5 is LLM-free by design. M6 degrades gracefully. |
| The 188 homologs are near-identical to C5B164 | "Discovery" is trivial | Measure sequence identity spread at M4 entry; if clustered, report it honestly and widen to Corpus C. |
| Lanthanide sites in the PDB are mostly artefacts | M2 yields little signal | This is why M2's curation step is the asset, not the download. |

---

## 9. Reproducing the measurements in this document

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                      # 5 passed

# §3.4 Argo: model list, the OpenAPI tool-calling schema, and the silent auth failure
curl -s https://apps.inside.anl.gov/argoapi/v1/models | python3 -m json.tool | head -40
curl -s https://apps.inside.anl.gov/argoapi/openapi.json \
  | python3 -c 'import json,sys; s=json.load(sys.stdin)["components"]["schemas"]; \
print(sorted(s["OpenAIRequest"]["properties"]))'      # includes tools, tool_choice, parallel_tool_calls
# A blocked reply is HTTP 200; the tells are id="chatcmpl-blocked-…" and usage.total_tokens==0.

# §3.5 legacy .pdb is not generated for large structures; mmCIF is
for id in 6EK0 7K00 3J3Q; do
  for ext in pdb cif; do
    printf '%s.%s -> ' "$id" "$ext"
    curl -s -o /dev/null -w '%{http_code}\n' "https://files.rcsb.org/download/$id.$ext"
  done
done                                                   # .pdb 404, .cif 200

# §3.2 KW-0254 is Endocytosis
curl -s https://rest.uniprot.org/keywords/KW-0254

# §5 M5: binding sites carry structured ChEBI ligand IDs, not just prose
curl -s 'https://rest.uniprot.org/uniprotkb/P0DP23.json?fields=ft_binding' \
  | python3 -c 'import json,sys; [print(f["ligand"]) for f in json.load(sys.stdin)["features"]]'

# §4 Corpus A, per ligand code (substitute each of the 18 codes listed in §4 — not just symbols)
curl -s -X POST https://search.rcsb.org/rcsbsearch/v2/query -H 'Content-Type: application/json' \
  -d '{"query":{"type":"terminal","service":"text","parameters":{
       "attribute":"rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id",
       "operator":"exact_match","value":"ND"}},
       "return_type":"entry","request_options":{"paginate":{"start":0,"rows":1}}}'

# §4 Corpus B, the 189 LanM-family proteins
curl -s 'https://www.ebi.ac.uk/interpro/api/protein/uniprot/entry/ncbifam/NF053806/?page_size=5' \
  -H 'Accept: application/json'
```

§3.1's coordination comparison and §3.3's demo-ranking table are reproduced by scoring the real
UniProt sequences and parsing 8FNS/8FNR/1CLL with the repo's own `structure.py`, filtered to O/N/S
donors within 3.2 Å.
