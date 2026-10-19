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

The empirical consequence is worse than a narrow margin. Scoring the authentic M1 reference set:

| Rank | Protein | Accession | Role | Score | Motifs |
|---|---|---|---|---|---|
| 1 | Lanmodulin, *M. extorquens* | C5B164 | **lanthanide binder** | 74.7 | 3 |
| 2 | Troponin C, human | P02585 | calcium protein | 69.0 | 2 |
| 3 | Calmodulin, human | P0DP23 | calcium protein | 57.0 | 1 |
| 4 | Lanmodulin, *H. quercus* | A0A4V2JDD3 | **lanthanide binder** | **35.1** | **0** |
| 5 | Haemoglobin α, human | P69905 | true negative | 23.4 | 0 |
| 6 | Chymotrypsinogen A, bovine | P00766 | true negative | 19.1 | 0 |

**The ranking does not merely fail to discriminate — it inverts.** A structurally confirmed Dy³⁺
binder with two deposited structures (8DQ2 La³⁺, 8FNR Dy³⁺) lands below both calcium proteins, one
rank above haemoglobin. The cause is a specific, reproducible motif-detection failure, §3.6.

So the claim "the heuristic is a competent EF-hand detector and not a REE detector" was too
generous: it is **not reliably an EF-hand detector either**. It is a detector for one *sub-type* of
EF-hand, and the lanthanide protein that falls outside that sub-type is scored as a non-binder.

> **Refinement, 2026-10-19.** §3.1 originally implied no sequence-only feature can separate Ln³⁺
> from Ca²⁺ proteins. That is true of *acidic fraction* and *EF-hand presence*, the two things the
> current score measures. It is **not** true in general: EF-hand **spacing** is a published,
> sequence-only discriminator, and it works on the reference set where the current score fails. See
> §3.8. This changes M3 from "structure is mandatory" to "structure is mandatory for affinity;
> sequence can do useful triage first."

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

### 3.6 The EF-hand regex is structurally blind to a confirmed lanthanide site

`EF_HAND_HINT = D.[DN].[DN]G.[ILV][DE]..E` hard-codes **Asp at loop position 1** and **Gly at
position 6**. I took the three Dy³⁺-coordinating loops of *H. quercus* lanmodulin — not predicted
loops, the residue ranges whose donors are resolved in **8FNR** — and checked them position by
position against the equivalent *M. extorquens* loops from **8FNS**:

| Protein | Loop | Sequence | Pos 1 | Pos 6 | Regex |
|---|---|---|---|---|---|
| Hans-LanM `A0A4V2JDD3` | 34–45 | `NKDNDDSLEIAE` | **N** | **D** | ✗ |
| | 58–69 | `NPDGDTTLESGE` | **N** | **T** | ✗ |
| | 83–94 | `NKDGDQTLEMDE` | **N** | **Q** | ✗ |
| Mex-LanM `C5B164` | 35–46 | `DPDKDGTIDLKE` | D | G | ✓ |
| | 59–70 | `DPDKDGTLDAKE` | D | G | ✓ |
| | 84–95 | `DPDNDGTLDKKE` | D | G | ✓ |

**Two independent violations, both in every Hans-LanM site.** The Asn is not a degraded Asp: Asn34,
Asn58 and Asn83 are confirmed first-shell Dy³⁺ donors in 8FNR, contributing one monodentate amide
oxygen each. The pattern cannot express a site that nature uses.

Scale, measured over the 189 LanM-family sequences (`.cache/lanm_family.json`):

| Pattern | Loops found |
|---|---|
| Canonical `D.[DN].[DN]G.[ILV][DE]..E` | 470 |
| …allowing Asn at position 1 | 525 (+55) |
| …also allowing non-Gly at position 6 | 557 (+32) |

**87 of 557 metal-binding loops — 16% — are invisible to the canonical pattern.** Position 1 is Asp
488× and Asn 69×; position 6 is Gly 525× and something else 32× (D 9, A 8, K 6, S 4, N 3, R 1, Q 1).

Recall is poor on calcium proteins too: the regex finds **1 of calmodulin's 4** known EF-hands
(`P0DP23`, motif count 1) and 2 of troponin C's. So the motif term is not a precision instrument
pointed at the wrong target — it is a low-recall instrument in both directions, and the small score
differences it produces between proteins are not meaningful.

> **The curated pattern is worse — it selects against the sites we want.** PROSITE **PS00018**, the
> pattern InterPro actually uses to annotate these proteins, fires on Hans-LanM at **exactly one
> position: 107**, covering **0 of the 3** confirmed Dy³⁺ loops. Parsing 8FNR shows what sits at
> 107. All four Dy sites in chain A, with their protein donor residues:
>
> | Site | Donor residues | CN | Water | PS00018 |
> |---|---|---|---|---|
> | Dy 201 (EF1) | 34, 36, 38, 40, 42, 45 | **9** | 0 | ✗ |
> | Dy 202 (EF2) | 58, 60, 62, 64, 66, 69 | **9** | 0 | ✗ |
> | Dy 203 (EF3) | 83, 85, 87, 89, 91, 94 | **9** | 0 | ✗ |
> | Dy 204 (EF4) | 107, 109, 111, 113, 118 | **7** | **1** | **✓** |
>
> **PS00018 detects exactly the one EF-hand with calcium-like coordination — CN 7 with a water — and
> misses all three with lanthanide-like coordination.** The pattern is named "EF-hand *calcium*-binding
> domain" and it does precisely what the name says. Its single hit is also why InterPro annotates
> this protein at all (§3.7): the evidence that makes Hans-LanM look like an EF-hand protein comes
> from its least lanthanide-like site. On Mex-LanM it fires at 59 and 84, covering 2 of 3.
>
> **Do not treat PS00018, or any calcium-derived consensus, as ground truth here.** This is the
> clearest single piece of evidence in the document that the project needs a lanthanide-derived
> descriptor rather than a borrowed one.

The same four sites are also the sharpest available statement of §3.1: **one protein, one metal, one
crystal, and coordination number still separates the three real lanthanide sites (CN 9, no water)
from the one that behaves like a calcium site (CN 7, one water)** — which is consistent with the
*Nature* 2023 authors modelling the equivalent position as Na⁺ in the La³⁺ structure. CN is doing
real work at a resolution no sequence feature can reach.

**Fix (M3):** derive the pattern from the structures in Corpus A rather than importing a
calcium-derived consensus. Until then the motif count is not a usable ranking term.

### 3.7 Both retrieval routes miss the best-characterised non-prototype lanthanide binder

Hans-LanM is not merely mis-scored — **it cannot be retrieved at all.** Both shipped routes, tested
directly:

| Route | Returns | Contains `A0A4V2JDD3`? |
|---|---|---|
| `protein_name:lanmodulin` | 1 accession | **No** |
| InterPro NCBIfam `NF053806` → UniProt | 189 accessions | **No** |

The cause is in the annotation. Hans-LanM's complete InterPro entry list contains **no lanmodulin
family term** — no `NF053806`, no Pfam `PF13202`, no PANTHER family:

```
A0A4V2JDD3   IPR002048 EF-hand domain · IPR011992 EF-hand domain pair
             IPR018247 EF-Hand 1, calcium-binding site · PS00018 · PS50222 · SSF47473 · G3DSA:1.10.238.10
C5B164       (all of the above) + NF053806 "lanmodulin LanM" + PF13202 + PTHR23050 + IPR050145
```

Every term Hans-LanM carries is a **generic EF-hand term that calmodulin carries too**, and the one
binding-site term it has is named *"EF-Hand 1, **calcium**-binding site."* A protein whose Dy³⁺
complex is in the PDB is annotated in the databases as a calcium protein.

**This compounds with §3.6 into the central risk for M4.** The pipeline misses this protein twice:
retrieval cannot reach it, and if handed it directly the score ranks it below haemoglobin. Any claim
that the system "discovers REE-binding proteins" is untestable until at least one of these is fixed,
because the one available held-out positive control is invisible to both ends.

> Consistent with Mattocks et al. 2023, which describes a remote **"Hans cluster"** separate from the
> main 642-member group at 65% identity. Family-annotation-based retrieval is structurally biased
> toward the prototype. **M4 must retrieve by sequence criteria, not by family label** (§3.8).

### 3.8 There *is* a sequence-only discriminator: EF-hand spacing

Mattocks et al. 2023 (*Nature* **618**:87–93) state three "hallmarks of a LanM", quoted verbatim:

> "First, LanMs possess four EF-hand motifs. … Second, adjacent EF hands in LanMs are separated by
> **12–13 residues** — rather than the typical ≈25 residues in Ca^II-responsive EF-hand proteins —
> resulting in an unusual three-helix bundle architecture with the metal-binding sites on the
> periphery. Third, at least one EF hand contains **proline at the second position**."

Hallmarks 2 and 3 are pure sequence features, require no structure, and the current score uses
neither. Measured on the reference set (loop-start period; the paper's "12–13 residue separation" is
the inter-loop linker, i.e. period minus the 12-residue loop):

| Protein | Loop starts | Periods | Verdict |
|---|---|---|---|
| `C5B164` Mex-LanM | 35, 59, 84, 108 | **24, 25, 24** | LanM-like |
| `A0A4V2JDD3` Hans-LanM | 34, 58, 83 | **24, 25** | LanM-like |
| `P02585` troponin C | 104, 140 | **36** | Ca-like |
| `P69905`, `P00766` negatives | — | — | no loops |

**This separates both lanmodulins from the calcium protein, including the one the current score
ranks 4th of 6.** Hallmark 3 corroborates: Pro sits at position 2 in `NPDGDTTLESGE` and in all three
Mex-LanM loops. Across the 189 family members the median period is **24.0**.

> **Not yet validated, and I will not claim it is.** The permissive loop finder used above has poor
> recall on calcium EF-hands — it fired only 5 times across 300 reviewed calmodulins, and catches
> just 1 of calmodulin's 4 known loops, because its positions 8–9 constraints are too tight. The
> LanM-vs-CaM comparison at scale is therefore **not a valid test yet**. The n=6 reference-set result
> and the published hallmark are what support this; a detector with balanced recall must be built and
> re-tested before the spacing term enters the score. That is the first task of M3.

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
- Tests: sequence checksums, provenance labelling, reference/synthetic separation, and a
  **regression test pinning the measured ranking including the inversion** (§3.1) so that M3 can
  demonstrate it has fixed it.

> **Acceptance criterion corrected, 2026-10-19.** This milestone originally said "an acceptance test
> asserting real LanM outranks both calcium proteins and both negatives." **That test is not
> achievable and should not be written.** Measured: `A0A4V2JDD3`, a confirmed Dy³⁺ binder, scores
> **35.1** against troponin C's 69.0 and calmodulin's 57.0, because the motif regex cannot see any
> of its three metal sites (§3.6). Writing the test as originally specified would mean either
> failing M1 on a defect that belongs to M3, or tuning the heuristic until a known-broken descriptor
> produced the desired answer — fitting the metric to the conclusion. **M1 pins the honest ranking;
> M3 owns fixing it.** The "LanM outranks calcium proteins" assertion moves to M3's done-when.

**Done when:** the default demo runs offline on authentic sequences, every record carries a verified
checksum and provenance, and the ranking — including its known inversion — is pinned by test.

### M2 — The lanthanide structure corpus (3–5 days) ← *the core asset*

Build Corpus A as a versioned local database.

> **Head start:** `data/ree_pdb_entries.json` already ships the verified enumeration — all 617
> entry IDs with their rare-earth elements and structure titles, plus a provenance block. It is
> explicitly marked `"curation_status": "uncurated"`. M2 begins by downloading and classifying
> these, not by rediscovering them.

> **Second head start: do not parse 617 structures from scratch.** **MetalPDB**
> (`metalpdb.cerm.unifi.it`, *NAR* 2018, 10.1093/nar/gkx989) has already decomposed every PDB metal
> site into donors, coordination number and geometry — 399,625 sites as of 2026-09-16 — and it
> indexes all 15 lanthanides *and* Ca²⁺ in one schema, which is exactly the matched contrast M2
> needs. Working REST API: `/api?query=metal:Nd&columns=donors,coordination,geometry,ligands`,
> returning per-donor distances. Bulk: `/download?t=cspheres`. Two cautions: the API returns ~86–90%
> of the sites `/stats` reports (it appears to expose only protein-chain sites — Nd via API 2 sites,
> via stats 6), so **never mix the two sources in one table**; and no terms-of-use statement exists
> anywhere on the site, so check licensing before redistributing derived data.
>
> Companion **MetalS3** ranks sites by 3D similarity of the coordinating-residue arrangement,
> fold- and sequence-independent — i.e. "find proteins whose site geometry resembles a known Ln
> site", which is M4's question asked structurally. HTML form only, results emailed; no API.
>
> **Validate every site you keep.** The *Nature* 2023 Hans-LanM paper used **CheckMyMetal**
> (`cmm.minorlab.org`) to decide whether an EF4 site was Na⁺ or Ca²⁺. If a *Nature* paper needs CMM
> to assign a metal, so does this project — lanthanide sites are frequently low-occupancy soaks.
>
> Scale check, from MetalPDB, which sharpens §4's artefact problem: **Nd has 6 sites in 2 entries
> and zero non-redundant representative sites; Dy has 38 sites in 2 entries.** Ca²⁺ has 39,686 sites
> in 13,274 entries. The two commercially critical REEs are essentially absent from structural
> biology, and most of the lanthanide set that does exist is phasing apparatus (Gd 179, Yb 118,
> Tb 64 entries are classic MAD/SAD heavy atoms).

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

**M3.0 — the sequence-level fixes, first, because M4's retrieval depends on them (§3.6, §3.8).**
These are cheap, they are what unblocks the headline screen, and none of them needs M2:

- **Build a loop detector with balanced recall.** The current regex misses 16% of LanM-family loops
  and 100% of Hans-LanM's; the permissive variant used in §3.8 misses 3 of calmodulin's 4. A
  detector biased toward either family invalidates every comparison built on it. Calibrate recall on
  both families *before* using it, and report per-family recall as a test.
- **Re-derive the motif from structure, not from a calcium consensus.** Positions 1 and 6 must admit
  what Corpus A actually shows (Asn at 1; non-Gly at 6). Treat PS00018 as a *negative* example —
  §3.6 shows it annotates the one Hans-LanM loop that is not a lanthanide site.
- **Implement the two sequence hallmarks** from Mattocks et al. 2023: EF-hand period (24–25 vs ~36)
  and Pro at loop position 2. Validate on the reference set, then on the 189 against a matched
  calmodulin-family control set. **Only then** may the spacing term enter the score.
- Gate: `A0A4V2JDD3` must rank above both calcium proteins. It currently ranks below both.

**M3.1 — the geometric descriptor.**

- Implement the geometric descriptor from §3.1 — CN, bidentate carboxylate count, donor-atom
  composition, carboxylate-oxygen density, site burial — scored on structures, not sequences.
- Calibrate thresholds on M2's curated Ln sites versus the Ca contrast set. With ~tens of
  genuine biological Ln sites this is **threshold calibration and ROC reporting, not machine
  learning** — do not train a model on this sample size and do not call the output a probability.
- Version it (`score_version: "geometry-v1"`) and keep the sequence heuristic alongside, clearly
  labelled as triage only.

> **Two external baselines to beat, both verified to exist.** A descriptor that cannot outperform
> these is not worth shipping.
>
> - **MIB2** (`bioinfo.cmu.edu.tw/MIB2/`, *Bioinformatics* 2022) is the **only** published
>   metal-site predictor with any lanthanide support — its 18 metals include **Sm³⁺** *and* Ca²⁺.
>   That makes a **Sm³⁺-score minus Ca²⁺-score differential an immediately available, zero-training
>   baseline discriminator.** Compute it first; it costs nothing and it is the honest comparator.
>   Web form only, no API, and it serves a certificate for `combio.life.nctu.edu.tw`, so HTTPS
>   clients need `verify=False`.
> - **Metal1D** (`github.com/lcbc-epfl/metal-site-prediction`, MIT) is a residue-propensity map
>   mined from PDB `LINK` records plus geometric scoring. It ships Zn²⁺-only maps, but it is
>   **trivially re-parameterisable for Ln³⁺** from M2's coordination statistics — and that is far
>   more defensible than training a CNN on 29 entries.
>
> **Do not plan on transfer learning from Zn models.** Surveyed 2024–2026 predictors — PrOMet,
> PRIME, BiteNetI, MetalBind, SuperMetal, ZincSight, AllMetal3D — **none covers lanthanides**, and
> ZincSight's own out-of-distribution tests show Zn-trained models generalise to transition metals,
> weakly to alkaline-earth, and fail on alkali. Ln³⁺ are hard, oxophilic and trivalent; every
> natural Ln first shell examined is **100% oxygen**, with no N or S donors at all. The His/Cys/Met
> chemistry those models are built on is simply not present here.
- Missing geometry must yield `not_scored`, never 0 and never an imputed mean.
- **Sanity gate:** the descriptor must rank engineered lanthanide-binding-tag sites (known
  high-affinity, from M2) above phasing-derivative surface sites. If it does not, stop and fix it
  before touching M4.

**Done when:** on held-out structures the descriptor separates biological lanthanide sites from
calcium sites with a reported ROC/AUC and an honest confidence interval; **both** lanmodulins
outrank **both** calcium proteins on the M1 reference set, with `A0A4V2JDD3` no longer inverted; and
LanM's margin over calmodulin is large rather than the current 5.7 points of noise.

### M4 — Screen the 188 (2–3 days) ← *the headline result*

> **Blocker found 2026-10-19, read §3.7 before starting.** "The 188" is the wrong corpus. Retrieval
> by family label cannot reach `A0A4V2JDD3` — it carries no lanmodulin annotation, only generic
> EF-hand terms identical to calmodulin's — so the one available held-out positive control is
> outside the set being screened. A screen that cannot recover a known binder it never saw is not
> evidence of discovery. **Fix retrieval before running the screen:**
>
> - Reproduce the Nature 2023 selection criteria — four EF-hands, 12–13 residue separation, length
>   < 200 aa — which recovered **696** putative LanMs, against this project's 189. The gap is the
>   measure of how much family-label retrieval misses.
> - Hold out `A0A4V2JDD3` as the validation target: a correct pipeline retrieves it *and* ranks it
>   highly, having been given only its sequence.
> - Keep `C5B164` as the positive control, but note it is the prototype the family profile was built
>   from, so recovering it is necessary and **not sufficient**.

- Pull all LanM-family sequences and their AlphaFold models.
- Run the M3 descriptor over predicted structures. Gate on local pLDDT: a low-confidence region
  yields `not_scored`, not a low score.
- Rank, and produce per-candidate evidence cards: identifiers, organism, predicted site residues,
  descriptor breakdown, AlphaFold confidence, and what experiment would test it.
- Position C5B164 as a positive control: if the pipeline does not rank the one characterized family
  member highly, the pipeline is wrong.

**Done when:** a ranked, evidence-backed shortlist of previously uncharacterized LanM homologs
exists, with the known binder recovered as a control. **This is the result the project is for.**

### M5 — Evidence ledger and honest selectivity (2–3 days)

> **The corpus is smaller than "tens". It is four.** A literature sweep (Europe PMC full text, 2026-10-19)
> found that matched-condition Kd values for **both a lanthanide and Ca²⁺ on the same construct**
> exist for exactly **four** proteins:
>
> | Protein | Ln Kd | Ca²⁺ Kd | Ratio | Method |
> |---|---|---|---|---|
> | Hans-LanM `A0A4V2JDD3` | La 68 pM · Nd 91 pM · Dy 2.6 nM | 60 µM | **8.8×10⁵** (La) | CD 222 nm, chelator-buffered, pH 5.0 |
> | Lanpepsy `Q1H2G7` | La ≈1 µM; La/Nd/Eu 5±1 µM | 14±11 µM | ~3–14× (error swamps it) | ITC, pH 7.2 |
> | SPL2 `E3 ligase` | La 0.945 µM | 1.21 µM | **1.3×** — Ca²⁺ binds *tighter* in the MBP fusion | CD, Hill fit |
> | Al-LanM (PDB 9PI2) | Nd and Ca in one 0.99 Å structure | — | Kd table paywalled (JACS 2026) | X-ray |
>
> Three consequences, each of which changes a design decision:
>
> 1. **Mex-LanM's Ca²⁺ Kd is not publicly available as a number.** Cotruvo 2018 (*JACS*
>    10.1021/jacs.8b09842) is paywalled with no repository copy; every open-access source describes
>    it only as "millimolar". Do not put a figure in the ledger for it.
> 2. **The famous 10⁸ selectivity is not an affinity ratio.** Cotruvo's own 2019 review states
>    "only 10⁶ derives from affinity differences; the rest appears to derive from a conformational
>    effect." A binding-site descriptor predicts *binding*, so **calibrate against 10⁶**. The
>    independently measured Hans-LanM La/Ca ratio of 8.8×10⁵ lands on exactly that figure — a real
>    consistency check and the single best calibration anchor available.
> 3. **A calibrated Ln-vs-Ca regressor is not feasible on public data, and the roadmap should stop
>    implying otherwise.** n=4 is a validation set, never a training set. REE-Finder is a
>    *ranked-hypothesis generator* with a physics/propensity score. The 621-ortholog SpyCI-LAMBS
>    dataset (*Nat Chem Biol* 2026) does not rescue this: it measures RE-vs-RE, calcium is never
>    assayed, and all 621 are one 133-residue family. It is excellent for a *different* question —
>    given a LanM, which REE does it prefer.
>
> **Highest-leverage experimental gap in the field, worth stating in the write-up:** the SpyCI-LAMBS
> assay already exists; measuring Ca²⁺ across even 50 of its 621 orthologs would take n from 4 to 50
> and make calibrated regression plausible. Nobody has done it.

- Hand-curate a literature table of measured lanthanide and Ca²⁺ affinities with assay conditions
  (pH, buffer, method, construct). **Four matched-condition entries, not tens** — state the number
  in the UI; the scarcity is itself a finding.
- **Never pool Kd values across methods.** CD-derived lanmodulin values are *apparent* constants for
  a metal-dependent conformational change; ITC, UV-vis dye competition and CD do not measure the
  same quantity. Record method and pH as required fields, and refuse to display a ratio across two
  methods. Mex-LanM's quoted affinity moves from ~21 pM at pH 5 to low pM at pH 7 — a scraped Kd
  without its pH is unusable.
- **Do not build a size-matching term.** Ca²⁺ at CN 8 is 1.12 Å, sitting *mid-series* among Ln³⁺
  (La 1.16 → Lu 0.98 Å), so radius cannot separate them; and *Chem Sci* 2022 reports LanM's affinity
  trend "does not follow the lanthanide contraction", so a radius-driven score will also get the
  intra-series order wrong. Charge density and coordination number do the work (§3.1).
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

# §3.7 Hans-LanM carries NO lanmodulin family term -- only generic EF-hand terms.
# Compare the two entry lists; NF053806 and PF13202 appear for C5B164 and not for A0A4V2JDD3.
for ACC in A0A4V2JDD3 C5B164; do echo "== $ACC"; curl -s \
  "https://www.ebi.ac.uk/interpro/api/entry/all/protein/uniprot/$ACC/?page_size=100" \
  -H 'Accept: application/json' | python3 -c \
  'import json,sys; [print(" ", e["metadata"]["source_database"], e["metadata"]["accession"]) \
   for e in json.load(sys.stdin)["results"]]'; done

# §3.7 and neither retrieval route returns it
curl -s 'https://rest.uniprot.org/uniprotkb/search?query=protein_name:lanmodulin&fields=accession' \
  | python3 -c 'import json,sys; print([r["primaryAccession"] for r in json.load(sys.stdin)["results"]])'
```

§3.6's motif audit and §3.8's spacing table are reproduced by
`scripts/analyze_motifs.py`, which caches the 189 family sequences under `.cache/`
(gitignored) and prints every table in those two sections.

§3.1's coordination comparison and §3.3's demo-ranking table are reproduced by scoring the real
UniProt sequences and parsing 8FNS/8FNR/1CLL with the repo's own `structure.py`, filtered to O/N/S
donors within 3.2 Å.
