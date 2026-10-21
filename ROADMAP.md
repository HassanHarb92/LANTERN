# LANTERN — Roadmap to a Working System

*Lanthanide-Aware Network for Targeted Exploration and Recognition in Nature*

**Status date:** 2026-10-20 (§3.20; everything above it dated 2026-10-19)
**Method:** every claim below was verified by running the code in this repo and querying the live
APIs it depends on. Commands are reproducible; numbers are not estimates.
**Companion docs:** `IMPLEMENTATION_PLAN.md` (prior aspirational plan — see §7 for what to retire),
`docs/SCIENTIFIC_CONTRACT.md` (claim boundaries — keep, it is sound).
**On the name:** the project was called REE-Finder until 2026-10-19; commits and cached fetch
provenance from before that date carry the old name. Everywhere else in this document "REE" means
*rare-earth element* and is not a reference to the old name — `REE_LIGAND_CODES`,
`CHELATED_REE_CODES`, `scripts/build_ree_corpus.py` and `data/ree_pdb_entries.json` are named for
the chemistry and keep their names.

---

## 1. The one-paragraph version

The project is currently framed as *"search a vast protein universe and rank candidates."* That
framing is why it feels unfinished: the search space looks infinite, so no amount of work closes it.
The real problem is **much smaller and already enumerable**, and that is good news:

- **636** PDB entries in the entire world contain a rare-earth ion. Not 636,000. You can download
  and curate all of them in an afternoon.
- **189** proteins in UniProt belong to the lanmodulin (LanM) family. **188 of them are
  uncharacterized.** That is the discovery space, and it fits on one screen.
- Every one of those 188 has an AlphaFold model already computed.

So LANTERN should stop being a search engine and become **a complete, curated, verified evidence
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
| `chemistry.py` | Ranks correctly since the §3.6 fix, but still measures a proxy (§3.1) | Real-sequence ranking, after the loop pattern was corrected against resolved donors: *M. extorquens* LanM 86.7 > *H. quercus* LanM 71.1 > TnC 69.0 > CaM 57.0 ≫ haemoglobin 23.4 > chymotrypsinogen 19.1. Both lanthanide binders now clear both calcium proteins — but by only 2.1 points, so this is triage, not a calibrated descriptor. |
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

The empirical consequence was worse than a narrow margin. Scoring the authentic M1 reference set
with the **calcium-consensus** loop pattern the prototype shipped with:

| Rank | Protein | Accession | Role | Score | Motifs |
|---|---|---|---|---|---|
| 1 | Lanmodulin, *M. extorquens* | C5B164 | **lanthanide binder** | 74.7 | 3 |
| 2 | Troponin C, human | P02585 | calcium protein | 69.0 | 2 |
| 3 | Calmodulin, human | P0DP23 | calcium protein | 57.0 | 1 |
| 4 | Lanmodulin, *H. quercus* | A0A4V2JDD3 | **lanthanide binder** | **35.1** | **0** |
| 5 | Haemoglobin α, human | P69905 | true negative | 23.4 | 0 |
| 6 | Chymotrypsinogen A, bovine | P00766 | true negative | 19.1 | 0 |

**The ranking did not merely fail to discriminate — it inverted.** A structurally confirmed Dy³⁺
binder with two deposited structures (8DQ2 La³⁺, 8FNR Dy³⁺) landed below both calcium proteins, one
rank above haemoglobin. The cause was a specific, reproducible motif-detection failure, §3.6.

So the claim "the heuristic is a competent EF-hand detector and not a REE detector" was too
generous: it was **not reliably an EF-hand detector either**. It detected one *sub-type* of
EF-hand, and the lanthanide protein outside that sub-type scored as a non-binder.

> **Resolved 2026-10-19 — and the fix was not a tuning exercise.** §3.6 traced the failure to two
> hard-coded positions. Relaxing both, each justified by resolved donors rather than by this table,
> turns the order the right way up:
>
> | Rank | Protein | Role | Score | Motifs | was |
> |---|---|---|---:|---:|---:|
> | 1 | Lanmodulin, *M. extorquens* (C5B164) | **lanthanide binder** | **86.7** | 4 | 74.7 |
> | 2 | Lanmodulin, *H. quercus* (A0A4V2JDD3) | **lanthanide binder** | **71.1** | 3 | 35.1 |
> | 3 | Troponin C, human (P02585) | calcium protein | 69.0 | 2 | 69.0 |
> | 4 | Calmodulin, human (P0DP23) | calcium protein | 57.0 | 1 | 57.0 |
> | 5 | Haemoglobin α, human (P69905) | true negative | 23.4 | 0 | 23.4 |
> | 6 | Chymotrypsinogen A, bovine (P00766) | true negative | 19.1 | 0 | 19.1 |
>
> **Read the margin before celebrating: 2.1 points.** Both lanthanide binders now outrank both
> calcium proteins, which is the criterion M1 was written to meet, but A0A4V2JDD3 clears troponin C
> by one motif's worth of nothing on a 100-point scale. `test_the_separation_is_thin_and_the_test_says_so`
> pins that explicitly. The ordering is correct; the descriptor is not calibrated, and M3 must not
> be closed on this.

> **Refinement, 2026-10-19.** §3.1 originally implied no sequence-only feature can separate Ln³⁺
> from Ca²⁺ proteins. That is true of *acidic fraction* and *EF-hand presence*, the two things the
> original score measured. It is **not** true in general: **loop position 9** is a published,
> structurally grounded, sequence-readable discriminator (§3.8), and EF-hand **spacing** is a second
> candidate. This changes M3 from "structure is mandatory" to "structure is mandatory for affinity;
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
searches for** — including the one labelled "lanmodulin". Real lanmodulin scores 86.7 with 4 motif
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

> **Fixed 2026-10-19.** `EF_HAND_HINT` is now `[DN].[DN].[DN]..[ILV][DE]..E`. Both changes are read
> off the table above rather than fitted to a desired ranking: Asn at position 1 is a resolved
> first-shell donor, and Gly at position 6 is a backbone-flexibility requirement of the 7-coordinate
> calcium geometry — it is not a donor in any of these structures, so constraining it only
> encodes the competitor's architecture. **Position 9 was left exactly as the calcium consensus
> already had it (`[DE]`)**, which matters: §3.8 shows that inherited constraint is the one doing
> the discriminating work, so the discrimination is not an artefact of this edit.
>
> Validated on 694 sequences, not on the 6-protein reference set
> (`python scripts/validate_motif.py`), against 505 reviewed calcium EF-hand proteins
> (calmodulin, troponin C, parvalbumin, calbindin, calretinin, S100):
>
> | Pattern | LanM family mean | Ca EF-hand mean | Sensitivity | Specificity | Balanced acc. |
> |---|---:|---:|---:|---:|---:|
> | Canonical (shipped) | 2.49 | 0.52 | 91.0% | 91.1% | 91.0% |
> | Structure-derived (now) | **2.95** | 0.58 | **96.8%** | 90.9% | **93.9%** |
>
> **Family members scoring zero motifs: 1.1% → 0.0%.** The 16% of invisible loops above is closed,
> and specificity against the competitor family is unchanged (−0.2 points). The pattern is still
> a *poor* detector of calcium EF-hands by design — it finds 1 of calmodulin's 4 — and that is now
> the intended behaviour rather than an accident, so it should be described as a lanthanide-like
> loop detector, never as an EF-hand detector.

**Remaining for M3:** the motif *count* is still a weak, saturating ranking term — it caps at 4 and
buys 12 points per hit. Separation licenses triage, not ranking. The calibrated descriptor still has
to come from structure (§3.9).

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

### 3.8 There *is* a sequence-only discriminator at loop position 9 — but it is Asp, not Glu

**The strongest one is a single residue.** The EF-loop ligates at positions 1, 3, 5, 7, 9, 12, and
position 9 is where lanmodulins and calcium proteins diverge. Loop sequences extracted from
deposited coordinates:

> **Read §3.8.1 before implementing anything from this section.** The structural evidence below is
> correct and invites a conclusion that is wrong at the sequence level. Every crystal structure
> here that reaches CN 10 does it with **Glu** at position 9, so Glu-at-9 looks like the lanthanide
> marker. Measured across 694 sequences it is the reverse: Glu at 9 is **27× more common in calcium
> EF-hands than in lanmodulins**. The transferable signal is that position 9 is a *carboxylate*,
> and **Asp carries essentially all of it**.

| Protein (PDB) | EF1 | EF2 | EF3 | EF4 | pos 9 |
|---|---|---|---|---|---|
| Mex-LanM (8FNS) | `DPDKDGTIDLKE` | `DPDKDGTLDAKE` | `DPDNDGTLDKKE` | `NPDNDGTIDARE` | **Asp ×4** |
| Hans-LanM (8DQ2/8FNR) | `NKDNDDSLEIAE` | `NPDGDTTLESGE` | `NKDGDQTLEMDE` | `DANKDGKLTAAE` | **Glu ×3**, Thr in EF4 |
| *A. lacus* LanM (9PI2) | `NKDGDQTLEIPE` | `NPDGDTTLEPDE` | `NKDGDQTLELDE` | `DKNKDGKLTAKE` | **Glu ×3**, Thr in EF4 |
| Calmodulin (1CLL) | `DKDGDGTITTKE` | `DADGNGTIDFPE` | `DKDGNGYISAAE` | `DIDGDGQVNYEE` | Thr/Asp/Ser/Asn |

What that residue does, measured from the coordinates (`binding_neighborhood`, chain A):

| Site | Ion | pos 9 | CN | Bidentate carboxylates | Waters |
|---|---|---|---:|---:|---:|
| 9PI2 EF1–3 | Nd³⁺ | **Glu** | **10** | **4** | **0** |
| 8DQ2 EF1–3 | La³⁺ | **Glu** | **10** | **4** | **0** |
| 8FNR EF1–3 | Dy³⁺ | **Glu** | **9** | 3 | 0 |
| 8FNS EF1–3 | Nd³⁺ | **Asp** | 9 | 2 | 2 |
| 9PI2 EF4 | **Ca²⁺** | **Thr** | **7** | **1** | **1** |
| 1CLL ×4 | Ca²⁺ | Thr/Asp/Ser/Asn | **7** | **1** | **1** |

**Glu at position 9 is a bidentate first-shell ligand that expels water entirely.** Asp at 9 is
too short to reach and works second-sphere through hydrogen bonds, giving CN 9 with two waters.
Thr at 9 is not a ligand at all and the −X vertex reverts to a bridging water — the canonical
calcium arrangement. Three published lines corroborate: D9 mutagenesis degrades Nd³⁺ affinity
monotonically (WT 21.3 pM → D9N 53 → D9A 397 → D9H 2150, a 101× loss, *Chem Sci* 2022); the
directed-evolution lanthanide-binding tag (1TJB) independently converged on bidentate carboxylates
at **both** 9 and 12; and position 9 is *not* a direct ligand in canonical calcium EF-hands at all
(4.45–5.07 Å from the metal in all four 1CLL sites).

> **⭐ 9PI2 is the cleanest control that exists for this project.** *A. lacus* LanM at 0.99 Å holds
> **Nd³⁺ and Ca²⁺ in the same protein, in the same crystal** — released 2026-08-19, after the
> prototype was written. Construct, conditions, refinement and resolution are all held fixed, so
> every difference in the table above is attributable to the ion and the loop. **The protein sorts
> the two ions by loop sequence**: the three loops with Glu at 9 take the lanthanide, the one with
> Thr at 9 takes the calcium. Verified independently with this repo's own code
> (`test_9pi2_sorts_two_ions_by_loop_chemistry_in_one_crystal`), reproducing the reported CN 10/7
> and water 0/1 split exactly. Any Ln-vs-Ca descriptor that cannot separate these four sites is not
> measuring selectivity.

This is also why the §3.6 fix works. The pattern `[DN].[DN].[DN]..[ILV][DE]..E` requires `[DE]` at
position 9 — a constraint **inherited unchanged from the calcium consensus**, not added. It finds
exactly Hans-LanM's three lanthanide loops and skips its calcium-like EF4, which is the behaviour
`test_hans_lanm_scores_its_three_lanthanide_loops_and_not_its_calcium_one` pins.

#### 3.8.1 The correction: at sequence scale the signal is Asp, and Glu points the other way

Everything above is structural, and three of the four structures are the same sub-architecture.
Before encoding position 9 as a feature I measured its composition across the family rather than
across five crystals, with position 9 **unconstrained** in the detector so the measurement does not
assume its own answer (`scripts/validate_motif.py`, 189 lanmodulins vs 505 reviewed calcium
EF-hand proteins):

| detector | set | loops | pos 9 = **Asp** | pos 9 = **Glu** | any carboxylate |
|---|---|---:|---:|---:|---:|
| `[DN].[DN].[DN]..[ILV]...E` (shipped pattern, pos 9 freed) | LanM family | 660 | **83.0%** | 1.4% | 84.4% |
| | calcium EF-hands | 990 | 26.2% | 3.3% | 29.5% |
| `D.{6}[ILVMFC].{3}E` (neutral, nothing LanM-specific) | LanM family | 609 | **82.1%** | **0.5%** | **82.6%** |
| | calcium EF-hands | 1247 | 26.4% | **13.3%** | **39.7%** |

Three things follow, and the third contradicts the obvious reading of the structural table:

1. **Position 9 does discriminate.** Carboxylate at 9 in 82.6% of LanM loops versus 39.7% of
   calcium loops — a real, sequence-readable, family-scale difference. The section title stands.
2. **Asp carries it.** 82.1 of those 82.6 points. The Asp column alone separates the families
   about as well as the carboxylate column does.
3. **Glu at 9 is a calcium signal, not a lanthanide one.** 0.5% in lanmodulins against 13.3% in
   calcium EF-hands under the neutral detector: **27× enriched in the wrong direction**. A
   descriptor keyed on Glu-at-9 would select *against* the target.

The structural claim and the sequence claim are both true and are about different things. Glu at 9
really is the tighter architecture *given that the protein is already a lanmodulin* — bidentate,
water-free, CN 10. It is just not what makes a sequence a lanmodulin, because almost no lanmodulins
have it. Hans-LanM and *A. lacus* LanM are the rare subtype; Mex-LanM's `Asp ×4` is the family.

> **The project's best structural positive control is its family's least representative member.**
> A0A4V2JDD3 (Hans-LanM, 8FNR/8DQ2) is the protein whose coordinates drove the §3.6 fix and whose
> three Dy³⁺ loops the ranking test pins — and it is `Glu ×3` at position 9, the 0.5% form. Tuning
> a sequence descriptor on it would miss the 189 family members that look like Mex-LanM, which are
> the entire point of M4. Pinned in `test_the_two_lanmodulins_do_not_share_a_position_9_residue`.
>
> **It is more unrepresentative than "atypical member" suggests: it is not a member at all.**
> A0A4V2JDD3 is **absent from the 189-protein NCBIfam NF053806 set**, and its closest sequence
> neighbour in that set is only ~42% similar. So the 0.5% Glu-at-9 figure does not include it —
> the three Glu loops in the family come from other proteins — and the 189/188 counts elsewhere in
> this document exclude it throughout. **This is the sharpest available evidence for §3.7: the
> family HMM fails to retrieve a lanmodulin whose lanthanide binding is confirmed in two
> deposited structures.** Retrieving by family label would never have found it.

**What this means for the score.** Position 9 ∈ {Asp, Glu} stays — but for a corrected reason. The
earlier reason given here ("Glu alone would reject Mex-LanM") understated it: Glu-only is not
merely incomplete, it is inverted. Benchmarked balanced accuracy on the 694-sequence set:

| position-9 constraint | balanced accuracy |
|---|---:|
| canonical `D.[DN].[DN]G.[ILV][DE]..E` | 91.0% |
| **`[DE]` as shipped** | **93.9%** |
| `[D]` only (Asp) | 94.3% |
| `[E]` only (Glu) | 50.0% |

Asp-only scores 0.4 pp above the shipped form. **It was not adopted.** 0.4 pp on the single
benchmark being optimised against, chosen after seeing the benchmark, is fitting — and `[DE]` is
the form inherited from the calcium consensus rather than selected here, which is worth more than
0.4 pp. Revisit only against a held-out set (M4).

Position 9 is now reported as a named feature (`Candidate.position_9`, `ef_hand_loops()`) and
deliberately **not** added as a score term: the loops that matched already required `[DE]` there,
so scoring it again would double-count one piece of evidence.

#### Secondary: EF-hand spacing

Mattocks et al. 2023 (*Nature* **618**:87–93 — volume verified via Crossref; a secondary source
citing 615 is wrong) state three "hallmarks of a LanM", quoted verbatim:

> "First, LanMs possess four EF-hand motifs. … Second, adjacent EF hands in LanMs are separated by
> **12–13 residues** — rather than the typical ≈25 residues in Ca^II-responsive EF-hand proteins —
> resulting in an unusual three-helix bundle architecture with the metal-binding sites on the
> periphery. Third, at least one EF hand contains **proline at the second position**."

Hallmarks 2 and 3 are pure sequence features and require no structure. **Hallmark 2 is now the
third rule in `lantern/design.py`** (`MAX_ADJACENT_GAP_AA = 14`, strictly less); hallmark 3 is still
unused. The paper's "12–13 residue separation" is the inter-loop *linker* — loop-start period minus
the 12-residue loop — and that is the quantity `ef_hand_layout` returns, through
`EF_LOOP_INSTRUMENT` and never through `EF_HAND_HINT`. Re-measured on the reference set:

| Protein | Loop starts | Linkers | Rule 3 |
|---|---|---|---|
| `C5B164` Mex-LanM | 35, 59, 84, 108 | **12, 13, 12** | pass |
| `A0A4V2JDD3` Hans-LanM | 34, 58, 83, 107 | **12, 13, 12** | pass |
| `P0DP23` calmodulin-1 | 21, 57, 94, 130 | **24, 25, 24** | fail |
| `P02585` troponin C | 28, 64, 104, 140 | **24, 28, 24** | fail |
| `P69905`, `P00766` negatives | — | — | fail (no loops) |

Both lanmodulins land on **12–13** and both calcium proteins on **24–28**: the paper's own contrast
("12–13 … rather than the typical ≈25"), reproduced on this set with no threshold fitted to it.

**The detector swap is what earned this rule its place.** Under `EF_HAND_HINT` the table above was
measured in periods, calmodulin was absent from it entirely, and troponin C showed two loops instead
of four. The balanced instrument finds all four of calmodulin's — which means calmodulin now *passes*
the "at least four EF-hand loops" rule, and spacing is the only rule in the set that separates it
from a lanmodulin. A rule that was unmeasurable under the biased detector is load-bearing under the
neutral one.

So state the fragility plainly, in the form §3.19 forced on the geometry score: calmodulin and
troponin C both pass rules 1 and 2 and fail only rule 3, which means **the selector's entire ability
to reject a calcium EF-hand protein rests on one sequence rule measured at n = 6.** It reproduces a
published hallmark rather than being fitted here, which is why it is in the score at all; it is
still one rule, and a calcium protein with a short linker would walk straight through the shortlist.
Hallmark 3 corroborates but is not scored: Pro sits at position 2 in `NPDGDTTLESGE` and in all three
Mex-LanM loops. Across the 189 family members the median period is **24.0** (linker 12).

> **Still not validated at scale, unlike position 9.** The loop finder had deliberately poor recall
> on calcium EF-hands — 1 of calmodulin's 4 — which is a *feature* for position-9 discrimination
> (§3.6) but was a *problem* for spacing, because you cannot measure the period between loops you did
> not find. The n=6 result above and the published hallmark are what support spacing; measuring it
> against calcium proteins needed a balanced-recall detector, which now exists. **Spacing is scored
> through that detector and only that one; n is still 6, and the shortlist rule carries the
> disclaimer that passing it is an architecture match and not an affinity.** Position 9 did not need
> it: it is carried by the existing pattern
> and is validated on 694 sequences (§3.6). Its *composition* was still measured against a second,
> deliberately neutral loop definition (§3.8.1) — not a validated balanced detector, but enough to
> catch that the biased pattern was understating Glu in calcium loops by 4× (3.3% → 13.3%). Where
> the biased detector can be checked against a neutral one, it should be.
>
> **Unblocked, 2026-10-19.** The balanced detector now exists (§3.10, `EF_LOOP_INSTRUMENT`), so
> spacing and Pro-at-2 can be measured. Measure them through it, never through `EF_HAND_HINT`,
> which finds 1 of calmodulin's 4 loops where the instrument finds all 4.

### 3.9 Which structural features actually discriminate — and one that does not, here

The structural descriptor M3 owes is not a guess. A PDB-wide survey (283 lanthanide protein sites
from 642 entries vs 1602 calcium sites from 800, resolution ≤ 2.0 Å, median 1.80 Å in **both** sets)
gives a ranked feature list, with per-entry means and Mann-Whitney *p*:

| Feature | Ln³⁺ | Ca²⁺ | *p* | Direction |
|---|---:|---:|---:|---|
| **backbone carbonyl O count** | **0.39 ± 0.62** | **1.87 ± 0.88** | **1.6 × 10⁻⁴¹** | Ca ≫ Ln |
| **carboxylate O atoms** | **3.86 ± 1.52** | **2.54 ± 1.02** | **2.7 × 10⁻¹⁸** | Ln ≫ Ca |
| Glu carboxylate O | 2.27 ± 1.67 | 1.03 ± 1.01 | 9.5 × 10⁻¹⁴ | Ln ≫ Ca |
| coordination number | 6.99 ± 1.87 | 6.56 ± 0.80 | 1.2 × 10⁻³ | Ln > Ca |
| carboxylate-O : backbone-carbonyl-O | **9.86** | **1.36** | — | 7.2× |
| % of Asp/Glu bidentate | **55.8%** | **26.2%** | — | 2.1× |
| Glu-O : Asp-O | 1.42 | 0.68 | — | 2.1× |

CN distributions: Ln³⁺ 25% at CN 8, 33% at CN 9, **9% at CN 10**; Ca²⁺ 72% at CN 6–7 and
**CN 10 in zero of 1602 sites**. The mechanism is charge — a neutral backbone carbonyl contributes
nothing to pocket charge, and pocket charge is the published determinant of Ln/Ca selectivity
(Nikolova & Dudev, *IJMS* 2023, **24**:6297, DFT/PCM): *"buried active centers with net charge of
−4 or −3 are characterized by higher Ln³⁺ over Ca²⁺ selectivity, whereas it is the opposite for
sites with overall charge of −1."* That is directly implementable: count first-shell carboxylates,
compute net charge, weight by burial.

> **⚠ The best population-level feature is worthless inside the EF-hand family.** Backbone carbonyl
> count wins by 30 orders of magnitude in *p* across the PDB — and carries **zero** information for
> this project's actual question. The EF-hand loop grammar puts a backbone carbonyl at position 7
> of every loop regardless of which ion binds, so across all 19 cached EF-hand sites the count is
> **exactly 1, every time**. `test_backbone_carbonyl_does_not_discriminate_inside_the_ef_hand_family`
> pins this so nobody reaches for it expecting it to work.
>
> This is the general trap: features selected on a Ln-vs-*all-calcium* comparison are measuring
> "is this an EF-hand?" as much as "is this a lanthanide site?". The competitors that matter are
> calcium **EF-hand** proteins, so features must be selected against *that* set, not against all
> calcium sites. The same applies to the negative set in `scripts/validate_motif.py`, which is
> calcium EF-hand families for exactly this reason.

**What does survive the within-family test**, measured on the five cached structures (19 sites):

| Feature | Lanthanide-like sites | Calcium-like sites | Separation |
|---|---|---|---|
| bidentate carboxylates | 2–4 | 1 | **clean** |
| carboxylate O atoms | 6–8 | 4–5 | **clean** |
| coordination number | 9–10 | 7 | **clean** |
| waters | 0–2 | 1 | overlaps |
| backbone carbonyl O | 1 | 1 | **none** |

8FNR's EF4 is the useful case: it holds a **lanthanide** but is chemically a calcium site, and it
sorts with the calcium group on every feature. The descriptor follows the chemistry, not the
element label — which is what we want, and is also why site-level labels must come from geometry
rather than from "this entry contains Dy".

**Three descriptors not to build**, each ruled out by measurement rather than opinion:

- **Absolute M–O distance.** Pooled, Ln–O is +0.081 Å *longer* than Ca–O; at matched CN it is
  0.032 Å *shorter*. A clean Simpson's paradox — Ln sites concentrate at CN 8–10, Ca at CN 6–7.
  Every effect size is |Cohen *d*| ≤ 0.33, 3–6× smaller than within-bin scatter, and the CN-6 bin
  has the wrong sign. The §3.1 table's distance column should not become a scoring term.
- **Ionic radius.** Ca²⁺ (CN 8, 1.120 Å) is isosteric with the light lanthanides — Nd³⁺ 1.109,
  Pr³⁺ 1.126 — and every Ln from Sm onward is *smaller* than Ca²⁺. Size cannot separate them;
  charge at constant size is the discriminating variable.
- **Pearson hardness η and water-exchange kinetics.** η derived from ionization energies ranks
  Ca²⁺ (19.5) as *harder* than La³⁺ (15.4) — it measures the I–A gap, not oxophilicity. And Ca²⁺
  water exchange is at least as fast as Ln³⁺; the inertness associated with lanthanides comes from
  the chelate, not the ion.

**One scaling warning for whatever descriptor gets built.** Stability constants for the same ligand
show that a *single* carboxylate buys only ~1.6–1.9 log units of Ln-over-Ca selectivity
(acetate: Sm −1.92 vs Ca −3.83). The 6.5–11.9 log units seen for EDTA/DTPA/DOTA come from
denticity, preorganisation and total ligand charge. **A descriptor that sums per-donor terms will
badly underestimate real selectivity**; it has to reward multidentate, preorganised, high-net-charge
sites superlinearly. The physics behind this is desolvation: Ln³⁺ pays roughly twice Ca²⁺'s
hydration enthalpy (La 3283 vs Ca 1592 kJ/mol) and all Ln³⁺ 1:1 complexation is endothermic and
entropy-driven.

> **Calibration bar.** Ordinary EF-hand proteins bind lanthanides only **~100–1000× tighter** than
> Ca²⁺, essentially from the charge difference alone. That is the floor a candidate must clear to be
> interesting, and it is what makes lanmodulin's 10⁶–10⁸ remarkable. A screen that surfaces proteins
> at 10²–10³ has surfaced ordinary EF-hand proteins. See M5 for the matched-Kd data ceiling.

**Precedent check: there is an open niche here.** No PDB-wide Ln-vs-Ca site comparison has been
published since Pidcock & Moore 2001, whose dataset was **11 lanthanide sites**. No lanthanide-specific
binding-site predictor exists; MIB2 covers Sm³⁺ only, and every 2024–2026 deep-learning metal-site
predictor covers zero lanthanides. The 283-vs-1602 comparison above is, as far as can be verified,
the largest of its kind — which means **M2/M3 are not merely engineering tasks for this project,
they are a publishable result if the survey is re-run cleanly and the code released.** That is
worth weighing when sequencing the work. The survey above was produced by a research agent in this
session and has **not** been independently re-run; treat it as a strong prior and a specification
for M2, not as a verified repo artefact, until M2 reproduces it.

### 3.10 The classifier cannot be used as a measuring instrument, so there are now two

§3.8.1 exposed a methodological problem larger than the position-9 question it came from. Freeing
position 9 in the shipped pattern put Glu-at-9 in calcium loops at **3.3%**; a neutral loop
definition put the *same proteins* at **13.3%**. Same question, same data, 4× apart — the
difference was entirely the detector. Every loop property this project still needs to measure
(EF-hand period, Pro-at-position-2, per-position composition) was exposed to the same error.

**Ground truth, and the asymmetry in it.** UniProt annotates EF-hand domains from PROSITE PS50222.
Within an annotated domain the 12-residue loop sits at a fixed offset — **position 14**, recovered
from residue composition rather than assumed, and re-derived on every run by `validate_offset()`:

| offset | 10 | 11 | 12 | 13 | **14** | 15 | 16 | 17 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pos 1 = Asp | 0.7% | 6.8% | 4.3% | 1.3% | **91.3%** | 1.0% | 71.1% | 1.3% |
| pos 12 = Glu | 1.1% | 13.0% | 8.2% | 22.2% | **86.7%** | 0.6% | 2.1% | 6.6% |

That annotation is **not** usable as ground truth on the lanmodulin side, and the reason is the
same defect one level up: the profile is calcium-trained. It finds **2.82 domains per calcium
protein** but only **1.59 per lanmodulin**, where lanmodulins have four. So the calcium side uses
1421 curated loops, and the lanthanide side uses **12 distinct loops read off deposited
coordinates** — derived by `structural_loops()` from the lowest-numbered protein donor of each
metal site, not transcribed, and reproducing the §3.8 loop table exactly.

**What the curated loops say about which positions are structural** (n=1421):

| pos | 1 | 3 | 5 | 6 | 8 | 9 | 12 |
|---|---|---|---|---|---|---|---|
| | D 91% | D 71% N 15% | D 50% N 24% S 14% | **G 87%** | I 69% V 16% L 7% | D 24% S 19% T 15% E 13% N 13% | E 87% |

Two things fall out that were previously argued from four structures. **Gly at position 6 is 87%
conserved — in calcium loops.** §3.6 removed it because no lanmodulin has it; this confirms from
1421 curated loops that the canonical regex was encoding the competitor's architecture. And
**position 9 is the most variable of the six ligand positions**, independently reproducing
§3.8.1's 39.7% carboxylate figure by a completely different route.

**The instrument.** `EF_LOOP_INSTRUMENT = [DN].{6}[ILV].{3}E` keeps only the three positions
invariant in both families (1, 8, 12) and frees everything else, including position 9:

| detector | Ca recall | Ln recall | gap | matches/loop |
|---|---:|---:|---:|---:|
| `EF_HAND_HINT` (shipped classifier) | 20.4% | 83.3% | **+62.9** | 0.21 |
| PROSITE PS00018 | 82.2% | 0.0% | −82.2 | 0.83 |
| neutral `D.{6}[ILVMFC].{3}E` (§3.8.1) | 83.4% | 33.3% | −50.1 | 0.88 |
| **`EF_LOOP_INSTRUMENT`** | **83.0%** | **91.7%** | **+8.7** | **0.88** |
| same, position 1 tightened to `[D]` | 82.8% | 33.3% | −49.5 | 0.87 |

Recall alone does not qualify a detector: matches-per-curated-loop must stay near 1, or spacing
measured between spurious hits looks like data. The last row is the §3.6 defect reconstructed from
curated annotations rather than from the four structures that first exposed it — tightening
position 1 from `[DN]` to `[D]` costs **58 points of lanthanide recall and 0.2 of calcium**.

> **These are two instruments with opposite objectives and they must never be swapped.** The
> classifier *wants* the 62.9-point gap; that gap is the discrimination. The instrument wants the
> gap at zero. The likely future mistake is someone noticing the classifier's 20.4% calcium recall,
> calling it a bug, and "fixing" it — which would look like an improvement and would destroy the
> score. `test_scoring_never_uses_the_measuring_instrument` inspects the source of
> `score_sequence` to prevent exactly that.

Reproduce: `python scripts/loop_detector.py`.

### 3.11 The two remaining hallmarks, measured — and the strongest one so far

With §3.10's instrument the other two Mattocks hallmarks can finally be measured rather than
cited. Both are reported under **both** detectors, so the cost of having used the biased one is
visible instead of asserted (`scripts/sequence_hallmarks.py`, 189 LanM vs 505 calcium):

**Hallmark 2 — EF-hand period.** Gap between consecutive loop starts:

| detector | set | gaps | median | IQR | in 20–28 |
|---|---|---:|---:|---:|---:|
| classifier | lanmodulin family | 368 | 24.0 | 24–49 | 61.4% |
| classifier | calcium EF-hands | **46** | **45.5** | 36–73 | 0.0% |
| **instrument** | lanmodulin family | 487 | **24.0** | **24–25** | **84.8%** |
| **instrument** | calcium EF-hands | 793 | **36.0** | **36–39** | **0.8%** |

The instrument reproduces the published 24–25 vs ~36 exactly. **The classifier does not**: it
measures the calcium period as 45.5 from 46 gaps where the instrument gets 36.0 from 793. That is
the predicted failure mode made concrete — period is measured *between* loops, so missing four
calcium loops in five both inflates the gaps and collapses the sample. Anyone who had measured
this through `EF_HAND_HINT` would have published 45.5 with conviction.

**Hallmark 3 — Pro at loop position 2**, and it is the cleanest sequence feature found so far:

| detector | set | loops | Pro at 2 | proteins with ≥1 |
|---|---|---:|---:|---:|
| classifier | lanmodulin family | 557 | 67.5% | 92.6% |
| classifier | calcium EF-hands | 292 | 0.0% | 0.0% |
| **instrument** | lanmodulin family | 676 | **71.2%** | **100.0%** |
| **instrument** | calcium EF-hands | 1249 | **0.1%** | **0.2%** |

Position 2 composition: lanmodulins `P 71% T 21%`, calcium EF-hands `K 31% A 16% Q 8% V 7% S 7%`.
Calcium EF-hands essentially never carry Pro there. This separates far better than position 9
(82.6% vs 39.7%) or motif count, and it is mechanistically coherent with the 4P2A result — Pro at
2 costs Ca²⁺ ~300× and Ln³⁺ only 5–10×, so it reads as Ca²⁺ *rejection* rather than Ln³⁺ affinity,
which is exactly the property a selectivity screen wants.

> **⚠️ Do not promote either hallmark to a score term on this evidence. The positive set is
> whatever NCBIfam NF053806 retrieves, so these are measured on precisely the set an HMM selected
> and cannot validate that HMM.** Two observations argue the signal is not purely definitional:
> per-protein Pro-at-2 runs 25–100% with median 67% rather than saturating, and **the HMM misses
> A0A4V2JDD3 entirely** — a lanmodulin with two deposited lanthanide structures, nearest family
> member ~42% similar. Neither settles it. The genuine test is M4: retrieve by these criteria and
> see what returns that the HMM did not already contain. Until then they are descriptions of a
> known family, not validated discovery features.

That last point cuts both ways and is worth stating plainly: **the family HMM failed to retrieve a
confirmed lanthanide binder.** §3.7 argued M4 must retrieve by sequence criteria rather than family
label; this is the measured instance of the failure it predicted.

Reproduce: `python scripts/sequence_hallmarks.py`.

### 3.12 Burial and net charge: implemented, measured, and deliberately not scored

M3.1 named these two as the descriptors not yet built, with the Dudev rule as the published form:
*"buried active centers with net charge of −4 or −3 are characterized by higher Ln³⁺ over Ca²⁺
selectivity, whereas it is the opposite for sites with overall charge of −1"* (Nikolova & Dudev,
*IJMS* 2023, **24**:6297). Both are now implemented in `lantern/structure.py` — `site_net_charge()`
counts first-shell charge, `_burial()` reports metal SASA plus a heavy-atom count — and attached to
every site dict. Measured across the 42 cached sites (36 lanthanide, 6 calcium):

| Descriptor | Lanthanide (median, IQR) | Calcium (median, IQR) | Balanced acc. | Ln recall | Ca recall |
|---|---|---|---:|---|---|
| net charge, first shell | −4.00 (−4.00 … −4.00) | −3.00 (−4.00 … −3.00) | 75.0% | 83% (30/36) | 67% (4/6) |
| metal SASA Å² | 0.00 (0.00 … 0.00) | 1.73 (0.00 … 3.46) | 77.8% | 89% (32/36) | 67% (4/6) |
| protein atoms <8 Å | 85.0 (83.3 … 98.3) | 86.5 (82.5 … 88.8) | 63.9% | 28% (10/36) | 100% (6/6) |
| shell net charge <8 Å | −3.00 (−4.00 … −3.00) | −1.50 (−4.00 … 0.00) | 73.6% | 81% (29/36) | 67% (4/6) |
| **coordination number** *(already shipped)* | 10.0 (9.0 … 10.0) | 7.0 (6.5 … 7.0) | **93.1%** | 86% (31/36) | 100% (6/6) |

Balanced accuracy — the mean of the two per-family recalls — is used because the sample is 36 against
6, so plain accuracy starts at 85.7% for a rule that reads nothing and calls everything lanthanide.
Thresholds are fitted on the same data they are scored on, so every figure is an upper bound.

**Neither new descriptor beats the coordination number already in the score**, and the reason is
structural rather than a shortcoming of the measurement:

> **Net charge is near-constant inside this fold, so it has nothing to rank with.** 97.6% of the 42
> sites carry −3 or −4 — 35 of 36 lanthanide sites and 6 of 6 calcium. An EF-hand loop places
> carboxylates at fixed loop positions, so its first-shell charge is a property of the twelve-residue
> grammar and not of the bound ion. The Dudev rule needs charge to *vary* before it can discriminate;
> within one fold it does not. This is the same lesson §3.9 recorded for backbone-carbonyl count —
> the second time a published PDB-wide discriminator has turned out to carry no information inside
> the EF-hand family, and the reason is identical both times: the loop grammar fixes it.

The cross-tabulation makes the failure concrete. The rule's Ln-selective condition — buried **and**
−3/−4 — is met by 32 of 42 sites, of which **30 are Ln-bound and 2 are Ca-bound**. Calmodulin's
calcium sites are buried −3/−4 centres too. The condition describes an EF-hand, not a lanthanide
preference.

> **What this sample can and cannot settle.** The Dudev rule is a claim about which ion a *given*
> site prefers. Every site here already has its preferred ion bound, so the sample cannot test the
> rule at all — only the weaker thing the score would need, whether the descriptors separate
> Ln-bound from Ca-bound sites. And **six calcium sites set the ceiling on all of it**: each Ca
> recall above is a count out of six, one site is 17 percentage points, and no threshold fitted
> against six points should ship. Both the positive and contrast sets are a single protein family
> each, so a descriptor that *did* separate here might be reading the fold rather than the chemistry.

**Neither descriptor enters the score.** They are implemented, attached to every site, and pinned by
tests — including one that pins the negative result itself, so that a future contributor who sees
charge "working" is prompted to suspect their contrast set first. Unblocking them is M2's corpus:
Ln sites outside the EF-hand fold, where charge actually varies, are the only sample that could
either calibrate these or retire them.

Reproduce: `python scripts/burial_and_charge.py`.

---

### 3.13 Corpus A, measured: charge does vary — and the corpus-wide contrast is a trap

§3.12 left a prediction on the table: if the EF-hand *fold* was holding first-shell charge constant,
then charge should vary once you leave that fold. Corpus A is now built and the prediction is
testable. All 636 entries are downloaded and parsed into **2795 sites — 2570 lanthanide, 225
calcium — in `data/lanthanide_sites.parquet`**, each carrying the full §3.9/§3.12 descriptor set.

**The parser was validated against MetalPDB before any of this was read.** Across Nd, La, Ce and Dy,
**65 of 65 metal ions agree with MetalPDB on every donor it reports**, atom for atom and distance
for distance; the 66th is an ion both sources give zero donors. The 26 donors this repo finds and
MetalPDB does not all lie between **3.00 and 3.18 Å** — precisely the band between this repo's 3.2 Å
cutoff and MetalPDB's ~3.0 Å, which is a documented convention difference and not a disagreement.
Nothing below 2.9 Å is in dispute. Six donors matched only after allowing for a PDB relabelling:
5KKB and 5KIJ have a mannose that MetalPDB calls `A/MAN709` and the current archive carries as
`C/MAN5`, because the carbohydrate remediation moved oligosaccharides into branched-entity chains.
Those are reported on their own line and counted separately, never folded into the agreement figure.

**Q1 — charge varies, and §3.12's explanation survives.** Only **10.0% of the 2570 corpus lanthanide
sites carry −3 or −4**, against 97.6% inside the EF-hand sample. The modal site is −1 (38.1%) and a
third are neutral.

| Net charge | −5 | −4 | −3 | −2 | −1 | 0 |
|---|---:|---:|---:|---:|---:|---:|
| Sites | 63 | 120 | 137 | 411 | 980 | 859 |
| Share | 2.5% | 4.7% | 5.3% | 16.0% | 38.1% | 33.4% |

It was the fold, not the descriptor. `test_charge_varies_outside_the_ef_hand_fold` pins this, so if
a future change makes charge look constant everywhere, §3.12's explanation gets re-opened rather
than quietly inherited.

**Q0 — what the corpus actually contains, which §4 flagged as a risk and nobody had sized.**
Geometry answers this with no labels at all: **69.8% of lanthanide sites have two protein donors or
fewer, and 29.5% have none**. A permissive sieve — ≥4 protein donors, CN ≥ 6, not chelator-flagged —
passes **374 of 2570 sites (14.6%), in 139 entries**. That is the realistic ceiling on curated
biology, and it is a sieve to point hand-curation at, not a classifier.

> **Q2 is a trap, and it is worth recording as one.** Corpus-wide, Ln-bound sites are *more* solvent
> exposed than the Ca-bound sites in the same entries (median SASA 68.3 vs 1.7 Å²) and have *fewer*
> protein atoms within 8 Å (37 vs 93). Read as chemistry that is absurd — it would say lanthanides
> prefer the surface. It is provenance: the lanthanide population of the PDB is mostly phasing
> soaks, while the calcium in those same entries is mostly structural calcium the protein evolved to
> hold. **A descriptor fitted on uncurated Ln-vs-Ca learns "was this ion soaked in?" and nothing
> about selectivity.** No Q2 figure may enter the score. This is the concrete reason M2's curation
> step is load-bearing rather than tidying.

**Q3 — and the reconciliation with §3.12.** Against the titled-biology subset (n=54 Ln sites) versus
everything untitled (n=2460):

| Descriptor | Titled biology (median, IQR) | Untitled (median, IQR) | Balanced acc. | at |
|---|---|---|---:|---|
| net charge, first shell | −4.00 (−4.00 … −3.00) | −1.00 (−2.00 … 0.00) | **94.1%** | < −2 |
| protein donor count | 8.50 (6.00 … 10.00) | 2.00 (0.00 … 3.00) | **94.1%** | ≥ 6 |
| metal SASA Å² | 0.00 (0.00 … 5.45) | 69.73 (39.22 … 92.97) | 93.4% | < 13.07 |
| protein atoms <8 Å | 87.0 (84.0 … 103.5) | 36.0 (24.0 … 57.0) | 91.9% | ≥ 80 |
| bidentate carboxylates | 3.00 (2.00 … 4.00) | 0.00 (0.00 … 1.00) | 90.6% | ≥ 2 |
| coordination number | 9.00 (9.00 … 10.00) | 4.00 (2.00 … 7.00) | 83.6% | ≥ 7 |
| shell net charge <8 Å | −3.00 (−4.00 … −3.00) | −1.00 (−3.00 … 0.00) | 79.3% | < −2 |

Net charge scores 94.1% here and scored 75.0% in §3.12. That is not a contradiction and the
difference is the whole point:

> **§3.12 asked which ion a genuine site holds. Q3 asks whether a site is genuine at all.** Those
> are different questions and net charge answers only the second. Within one fold, where every site
> is real and the loop grammar fixes the carboxylate count, charge has nothing to rank with. Across
> the corpus, where most sites are surface soaks with no carboxylates at all, charge separates real
> from artefactual almost perfectly. **Net charge is a good artefact filter and a useless
> selectivity descriptor** — which tells M3 exactly where to put it: in triage, never in the
> selectivity score.

Four caveats hold Q3 down, in decreasing order of how much they matter. The negative class is "no
keyword matched the title", not "artefact", so it contains every genuine site whose depositors did
not mention lanthanides — that biases every figure *downward*, which makes a strong result
meaningful and a weak one uninformative. Thresholds are fitted on the data they are scored on, so
each is an upper bound. The positive class is 54 sites. And Q3 is largely re-measuring Q0's
buried-versus-surface axis, so the seven rows are closer to one finding than to seven.

**Contamination is recorded, not dropped.** 522 sites (18.7%) have a first shell at least half
non-protein non-water, and 481 carry a *named* chelator — bis-tris 352, acetate 57, DO3A 45,
pyridine-2,6-dicarboxylate 16, citrate 9, DOTA 2. MetalPDB independently confirms PQQ and methanol
as genuine first-shell donors of the XoxF lanthanide site, which is why the flag records rather than
filters: the same column that catches a DO3A cage would throw away methanol dehydrogenase.

Reproduce: `python scripts/download_corpus.py`, then `python scripts/build_site_table.py`, then
`python scripts/corpus_descriptors.py`. Validate the parser with
`python scripts/crosscheck_metalpdb.py`.

### 3.14 The matched Ca²⁺ contrast, measured: Corpus A cannot supply one

§3.13's Q2 established that comparing the corpus's 2570 lanthanide sites against its 225 calcium
sites measures provenance, not chemistry — the lanthanides come out *more* exposed because most were
soaked in, and any descriptor fitted to that contrast learns the soak and inverts the preference.
The fix is to hold the protein fixed: compare the **same site** holding each ion.

**The mechanism.** `build_site_table.py` now emits two columns per site. `first_shell_protein_residues`
names the coordinating residues as `CHAIN:RESNAME:NUMBER`, which is what lets a curator recognise
`ASP20;ASP22;ASP24;THR26;GLU31` as an EF-hand loop where "5 protein donors" tells them nothing.
`site_signature` is the same string with the chain dropped, so two NCS copies — or two depositions of
one protein — compare equal. Two sites sharing a signature are the same site; if one holds a
lanthanide and the other a calcium, the only difference is the ion.

**What a matched pair can and cannot show.** Same signature means the same residues, so the charge
descriptors are identical *by construction*. Net charge cannot discriminate inside a pair and should
not be expected to — this is §3.13's reconciliation seen in a mirror, and the charge columns are kept
in the output precisely as a control that must read zero. What is free to move is geometry: Ln³⁺ is
more charge-dense than Ca²⁺, so the testable prediction is higher coordination number and more
bidentate carboxylates on the lanthanide side.

**The measured answer is that this corpus cannot run the test.** At ≥3 signature residues:

| Tier | Matched signatures | Usable |
|---|---:|---|
| Within-entry (same deposition, same site, different ion) | 3 | 5G6U ×1, 9R0Q ×2 |
| Cross-entry (same signature, any deposition) | 4 | adds the 1AK8/2K0J/2K61 EF-hand |

**475 of 481 lanthanide sites (98.8%) have no calcium partner at all**, and every descriptor delta
across the pairs that do exist is 0.00. This is not a weak result; it is a structural property of
Corpus A, which is *defined* as entries containing a rare earth and therefore excludes by
construction the Ca-only depositions that would make the contrast.

> **A near miss worth recording.** Run without the residue-count filter, the cross-entry tier showed
> 10 matched signatures and a coordination-number delta of **+0.75 with 6 of 7 pairs in the predicted
> direction** — exactly the result the hypothesis wants. It was an artefact. Those matches were
> one-residue signatures: `GLU113` recurring across 2V15, 4LL7, 6FRM and 6FRN, four unrelated
> proteins sharing a string. A single residue is not a site. `--min-residues 3` removes them and the
> delta collapses to 0.00. The lesson generalises past this script — the looser the matching key, the
> more confidently a corpus this size will hand back the answer you were hoping for.

**So the contrast set has to be fetched, and by sequence rather than by name.** `matched_calcium.py`
resolves each Corpus A entry holding a plausible lanthanide site to its UniProt accession through the
SIFTS mapping, asks RCSB for the other entries on that accession containing `CA`, and subtracts
Corpus A. Accession, not title: a title cannot tell a point mutant from a different protein.

Two selection rules, and the first is chemistry rather than bandwidth. Counterparts refined worse
than **2.5 Å are dropped**, because coordination number and donor distance are exactly what a matched
pair measures and both are refinement artefacts below that — a "7-coordinate" site may be an
8-coordinate one with a missing density peak. NMR entries go too: their metal–donor distances come
from a restraint set, not from density. Second, at most **five counterparts per accession**, best
resolution first; human calmodulin alone offers 229 and the 229th adds nothing the best five did not.

The manifest is a manifest, not a conclusion. Same accession means same sequence, not same construct,
ligand state or oligomeric form, and `curation_status` in the output says so. Downloads land in
`.cache/calcium/`, their own empty directory, and are parsed by path.

Reproduce: `python scripts/paired_sites.py` for the in-corpus tiers, then
`python scripts/matched_calcium.py`, `python scripts/download_corpus.py --out .cache/calcium
--enumeration data/calcium_counterparts.json`, and `python scripts/build_site_table.py --corpus
.cache/calcium --enumeration data/calcium_counterparts.json --out data/calcium_sites.parquet`.

### 3.15 The matched contrast, measured: a null result, and why it is the only possible one

The fetch returned **172 Ca-only entries across 67 accessions** (739 candidates before the 2.5 Å and
five-per-accession cuts), parsed to **645 calcium sites in 172 entries**. Against Corpus A that gives
**31 cross-corpus matched signatures** — against 4 from Corpus A alone.

**First, an artefact I manufactured myself.** The first run looked like a result: donor distances
+0.08 Å longer on the lanthanide side, and `protein_donor_count` higher in 7 of 7 pairs (sign test
p=0.016). It was the filter. I had capped the contrast set at 2.5 Å and left Corpus A unfiltered, so
the lanthanide sides ran **0.17 Å worse-resolved than their calcium partners (20/26 pairs, p=0.0094)**
— a stronger effect than any chemistry in the table. The resolution gap correlated with the distance
delta (r=+0.40). Holding both sides to the same cutoff collapses the distance difference to +0.010 Å
at p=1.0 and the donor-count effect to 2/2, p=0.50. Resolution is now a column in both tables and the
cutoff is applied to both or to neither.

**With that fixed, nothing separates.** 19 fold- and resolution-matched pairs:

| descriptor | Ln median | Ca median | Ln>Ca | sign test |
|---|---:|---:|---:|---:|
| coordination_number | 7.00 | 7.00 | 6/11 | 1.00 |
| mean_donor_distance_A | 2.40 | 2.41 | 10/19 | 1.00 |
| protein_donor_count | 5.00 | 5.00 | 2/2 | 0.50 |
| water_donor_count | 1.00 | 1.00 | 6/10 | 0.75 |
| bidentate_carboxylates | 1.00 | 1.00 | 1/1 | 1.00 |
| **net_charge** | −3.00 | −3.00 | **0/0** | — |
| **carboxylate_residues** | 3.00 | 3.00 | **0/0** | — |

The last two rows are the control working: same signature means same residues, so the charge
descriptors are identical *by construction* and must read exactly zero. They do, in all 19 pairs,
which is what certifies that the matching is sound and the nulls above are real nulls.

> **The null is structural, not disappointing.** A matched pair is by construction a site observed
> holding *both* ions — which is to say, a site that is **not selective**. The design selects for
> promiscuity, so there is no selectivity left in it to measure. The decisive evidence is what is
> missing: **not one natural-lanthanide-biology site has a calcium partner anywhere in the data.**
> Lanmodulin cannot appear in this set, because not binding calcium is the entire point of it. All
> 19 pairs are calcium proteins with a lanthanide soaked in — troponin C, mannose-binding protein,
> langerin, psoriasin, calexcitin, α-lactalbumin, proteinase K. (The title pass labels only 3 of them
> `ln_substituted_ca`; its keyword list is EF-hand-centric and misses the lectins and the hydrolases.
> That is a gap in the hint, not in the geometry.)
>
> So the matched design answers a different question than the one it was built for, and answers it
> cleanly: **a pre-formed calcium site does not measurably deform when it accepts a lanthanide
> instead.** Same coordination number, same donor distances, same denticity, at PDB resolution. That
> is worth knowing, and it rules out first-shell geometry *alone* as the thing that distinguishes the
> two ions in a fixed fold.

### 3.16 The comparison that does work: native against native

Three contrasts exist in this data and two of them cannot answer the selectivity question — §3.13's
Q2 measures provenance, §3.15's matched pairs measure promiscuity. The third is sites that bind
lanthanide **and not** calcium against sites that bind calcium in their own Ca-only depositions. It
does not control the fold, but unlike Q2 both sides are native: every protein crystallised with the
ion it actually uses.

Entry-level medians, both sides ≤2.5 Å and chelator-free, **10 lanthanide entries vs 171 calcium
entries**, two-sided permutation test on the difference of medians:

| descriptor | Ln | Ca | balanced acc. | split | perm *p* |
|---|---:|---:|---:|---|---:|
| **coordination_number** | 9.50 | 7.00 | **1.000** | ≥8.5 | **0.0016** |
| **bidentate_carboxylates** | 2.50 | 1.00 | **0.988** | ≥1.5 | **<0.0001** |
| mean_donor_distance_A | 2.62 | 2.44 | 0.835 | ≥2.53 | 0.0008 |
| protein_donor_count | 7.00 | 5.00 | 0.816 | ≥5.5 | 0.0139 |
| protein_atoms_within_8A | 100.0 | 87.0 | 0.715 | ≥100 | 0.0365 |
| net_charge | −3.00 | −2.00 | 0.825 | <−3 | 0.168 *(n.s.)* |
| carboxylate_residues | 3.00 | 2.00 | 0.825 | ≥3 | 0.167 *(n.s.)* |
| shell_net_charge | −3.00 | −2.00 | 0.807 | <−3 | 0.248 *(n.s.)* |
| metal_sasa_A2 | 6.54 | 10.38 | 0.763 | <9.4 | 0.659 *(n.s.)* |

**Coordination number and bidentate carboxylate count separate, and they are exactly what Ln³⁺
coordination chemistry predicts** — a larger ion preferring CN 8–10 where Ca²⁺ sits at 6–8, and a
higher charge density pulling carboxylates into bidentate contact. Neither is the Dudev charge rule.

**Net charge is not significant (p=0.168).** That is now the third independent route to the same
conclusion: it scored 94% at telling a real site from an artefact (§3.13 Q3), 75% at telling which
ion a genuine site prefers (§3.12), and here it fails outright. Net charge is a triage filter and
must stay out of the selectivity score. **SASA fails too** (p=0.659), and the per-family table says
why — lanmodulin's sites are fully buried (median 0.00 Å²) while the dehydrogenase sites are not
(8.72 Å²), so burial is a property of those two folds rather than of lanthanide selectivity.

> **The honest *n* is two, not ten.** The ten lanthanide entries are six methanol/alcohol
> dehydrogenases and four lanmodulins. Collapsing sites to entry medians already prevents 8FNR's
> fourteen lanmodulin sites from counting as fourteen observations, but two families is still the
> real limit, and the thresholds above are fitted and scored on the same points — the balanced
> accuracies are descriptive, not validated. A coordination number of 1.000 separation on 10 vs 171
> means "these two families are cleanly different from calcium proteins", not "this classifier
> works". Both families agree on the direction of CN and bidentate count, which is the strongest
> statement two families support.

**What this fixes in M3.1.** The geometry score should be built on **coordination number and
bidentate carboxylate count**, with donor distance and protein donor count as weaker support. Net
charge, shell charge and SASA come out of the selectivity term — net charge stays, but in triage.
This is still not machine learning at *n*=2 families; it is two thresholds with a mechanistic
rationale and a stated validation gap.

Reproduce: `python scripts/paired_sites.py --contrast data/calcium_sites.parquet` for §3.15 and
`python scripts/selectivity_contrast.py` for §3.16.

> **The numbers in the table above are superseded by §3.17.** They were computed from deposited
> asymmetric units, and for sites on a symmetry axis that is half the coordination sphere. The
> *conclusion* survives the correction and gets a third family; the per-descriptor figures change.

---

### 3.17 The asymmetric unit is not the site: a third family, and two statistical traps

§3.16 ended with a stated weakness — *n* = 2 families — so the next move was to search the 600
unclassified Corpus A entries for more natural lanthanide biology. That search found a family, and
the family found a parsing bug underneath it.

**A third family: LanD.** Four entries (9C8X/Y/Z/90) titled *"Methylorubrum extorquens La(III)-bound
LanD"* were unclassified because `"lanm"` does not match "LanD" and `"methylotroph"` does not match
"Methylorubrum". The entity is **landiscernin**, a **lanthanide chaperone** (PNAS 2024, PMID
39467132), and the paper is titled *"Modulating metal-centered dimerization of a lanthanide
chaperone protein for separation of light lanthanides."* A protein whose published function is
telling lanthanides apart from each other is the most on-target entry in the corpus, and it was
sitting in the unclassified pile.

**Why it looked like junk.** Parsed from the deposited coordinates, its site read coordination
number 5, net charge −3, and SASA 47.9 Å² — an exposed, unremarkable surface metal. The ASU holds
**one chain**; the biological assembly is a **homo-2-mer with C2 symmetry**, and the metal sits on
the interface. The deposited coordinates contain half the site:

| descriptor | asymmetric unit | biological assembly |
|---|---:|---:|
| coordination_number | 5 | **10** |
| carboxylate_residues | 3 | **6** — GLU70/73/75 from *both* protomers |
| bidentate_carboxylates | 1 | **2** |
| net_charge | −3 | **−6** — as anionic as any site in the corpus (11 sites reach −6) |
| metal_sasa_A2 | 47.94 | **0.00** — buried, not exposed |

Every descriptor was wrong, and all of them in the direction that makes a real site look
adventitious. **This is a general defect, not one entry**: `scripts/assembly_audit.py` finds
**99 of 636 Corpus A entries (15.6%)** and **20 of 172 calcium entries (11.6%)** — 119 of 808 —
whose biological assembly is larger than their deposited coordinates. Being larger does not prove
any site is truncated, which is why `data/assembly_counts.json` records itself as uncurated and
re-parsing is what decides. The fix fetches assembly 1 for exactly those
entries, and every row now records a `coordinate_source` of `asu` or `assembly1` — because applying
this correction to one arm and not the other would have been §3.15's resolution bug a second time.

**Burial was checked and cleared.** Coordination number does partly measure burial: it correlates
with solvent exposure at −0.521 across the lanthanide family sites and −0.572 across calcium sites,
and in the calcium set alone median CN falls 7.0 → 5.5 from the buried to the exposed tertile.
Since the corrected LanD and lanmodulin sites are at SASA 0.00, "lanthanide sites are buried, buried
sites are high-CN" is the obvious alternative explanation. Stratifying kills it. Holding both sides
to SASA ≤ 10 Å² leaves the two arms **indistinguishable on burial** — median 0.00 Å² each,
permutation *p* = 1.0 — while the lanthanide side still carries **median CN 10 against 7**, and
tightening to ≤ 5 Å² gives CN 9.5 against 7 on the same null burial difference. All three families
survive both strata, so this is not lanmodulin carrying the result. These are site-level counts
(53 and 46 lanthanide sites) and therefore pseudo-replicated — the claim is not the *p*-value but
the fact that **matching on burial does not shrink the CN gap**.

> **Two statistical traps, both of which briefly reversed the conclusion.**
>
> **Pseudo-replication at the entry level.** With 14 entries, net charge reaches *p* < 0.0001 —
> ahead of coordination number at 0.0001 and far ahead of bidentate carboxylates at 0.0134, so on
> the entry-level table it is the descriptor to pick. Four of those entries are LanD — one protein
> crystallised with four different lanthanides, which are technical replicates — and they drag the
> median to −4. At the family level net charge is still significant but **17 of 55 calcium
> accessions overlap it**. Pseudo-replication did not merely inflate confidence; it changed which
> descriptor ranked first.
>
> **The wrong test at small *n*.** A two-sided permutation test on the difference of medians also
> counts random triples whose median falls far *below* the pooled median, and the calcium lower
> tail is fat. Coordination number — which **no** calcium accession in the set reaches — scored
> *p* = 0.148, and bidentate carboxylates, also with zero overlap, scored *p* = 0.298; net charge,
> with 17 of 55 accessions overlapping, scored *p* = 0.029. **Perfect separation came out five to
> ten times worse than partial separation.** Since Ln³⁺ coordination chemistry fixes the expected
> direction in advance, the honest statistic is a **one-sided exact rank test**, and at *n* = 3 the
> null can be enumerated rather than sampled.

**The corrected result.** Three lanthanide families against 55 calcium accessions, both sides
≤2.5 Å, chelator-free, assembly-corrected by one rule; exact one-sided rank test over all
C(58,3) = 30 856 assignments:

| descriptor | Ln | Ca | Ca accessions reaching it | exact *p* |
|---|---:|---:|---:|---:|
| **coordination_number** | 9.00 | 7.00 | **0 / 55** | **0.00003** |
| **bidentate_carboxylates** | 2.00 | 1.00 | **0 / 55** | **0.00003** |
| protein_donor_count | 8.00 | 4.00 | 16 / 55 | 0.00107 |
| net_charge | −4.00 | −2.00 | 17 / 55 | 0.00240 |
| carboxylate_residues | 4.00 | 2.00 | 17 / 55 | 0.00240 |
| shell_net_charge | −4.00 | −2.00 | 26 / 55 | 0.04589 |
| mean_donor_distance_A | 2.54 | 2.45 | 15 / 54 | 0.04925 |
| metal_sasa_A2 | 0.00 | 12.11 | 25 / 55 | 0.063 *(n.s.)* |
| protein_atoms_within_8A | 100.0 | 87.0 | 30 / 55 | 0.083 *(n.s.)* |

Per family, on the two descriptors that separate cleanly — every family above every calcium
accession, which is what "0 / 55" means:

| family | CN | bidentate carboxylates | net charge | SASA Å² |
|---|---:|---:|---:|---:|
| LanD (lanthanide chaperone) | 9.00 | 2.00 | −6.00 | 0.00 |
| MDH/XoxF (dehydrogenases) | 9.00 | 2.00 | −3.00 | 8.72 |
| lanmodulin | 10.00 | 3.50 | −4.00 | 0.00 |

**§3.16's recommendation survives, on better evidence.** Coordination number and bidentate
carboxylate count are the only two descriptors with **no overlap at all** — all three lanthanide
families rank above all 55 calcium accessions, which is the smallest *p* attainable at *n* = 3.
The honest *n* rose from two families to three, and the third was found by fixing a bug rather than
by relaxing a filter.

**Net charge fails for the fourth time**, and this is the most informative of the four. It is
significant (*p* = 0.0024) and it is the Dudev prediction, so the temptation to promote it is real
— but 17 of 55 calcium accessions are as anionic as the lanthanide families. A descriptor that a
third of the negative class satisfies is a triage filter, not a selectivity term. **SASA fails for
the fifth time** (*p* = 0.063, 25/55 overlapping).

**A keyword trap worth recording.** The obvious fix for the LanD miss — matching the substring
`"land"` — also matches *"Ignicoccus **island**icus"* (6QSS), a malate dehydrogenase co-crystallised
with Tb-Xo4, which is a phasing experiment and not lanthanide biology. `"methylo"` catches all four
LanD entries without that cost. Both halves are pinned by
`test_land_is_natural_biology_without_matching_islandicus`, because fixing the miss by reintroducing
the trap is the likely regression. The widened rules take `natural_ln_biology` from 13 to **17
entries (65 sites)** and `engineered_lbt` from 27 to **111 sites**, the latter mostly LBT peptides,
tagging constructs and designed coiled coils that the tag-centric wording had missed. Recall is
still the limiting problem: **590 of 636 Corpus A entries remain unclassified**, which is why M2
hand-curation stays on the list rather than being declared solved by keywords.

**What this changes in M3.1.** Nothing in the recommendation — coordination number and bidentate
carboxylate count, with donor distance and protein donor count as weaker support, and net charge in
triage. What changed is the confidence behind it: three families rather than two, a defect in the
coordinates corrected, burial excluded as the cause, and the two tests that would have told a
different story identified and discarded on their merits rather than on their answers.

Reproduce: `python scripts/assembly_audit.py`, then
`python -I scripts/download_corpus.py --assembly --enumeration data/assembly_counts.json --out .cache/assembly`,
rebuild both site tables with `--assembly-dir .cache/assembly`, then
`python scripts/selectivity_contrast.py`.

---

### 3.18 geometry-v1, and what it refuses to do

> **Superseded in part by §3.19.** A fourth family removed the second of the two criteria below.
> The *n* = 3 numbers, the 9PI2 control and every refusal in this section still stand; the
> two-criterion conjunction and the 75.9%/99.5% site calibration are v1's and are kept here so the
> change has something to be read against. The shipped score is **geometry-v2**.

M3.1 is implemented as `lantern/geometry.py`. It is the smallest thing §3.17 supports: the two
descriptors that separated with zero overlap, no weights, and a set of refusals.

**No weights.** A weighted sum of two descriptors fitted on three families would be three numbers
fitted to three points. The score is the **count of criteria met** (0, 1 or 2) and ties break on the
raw descriptors, so the ordering inside a band is transparently "more donors, more bidentate
carboxylates" rather than a fitted combination presented as one number. Thresholds are the
**weakest of the three lanthanide families** — CN ≥ 9, bidentate carboxylates ≥ 2 — not a midpoint
between the classes, because a midpoint is tuned to the calcium set's upper tail and the family
minimum is a statement about the positive class, which is the thing being generalised from. CN ≥ 9
is exactly the zero-overlap boundary: at CN ≥ 8 one calcium accession passes.

**It reproduces the result it came from**, re-derived through the shipped scorer rather than the
analysis script: 3 of 3 lanthanide families pass, **0 of 55 calcium accessions** do. Pinned by
`test_geometry_v1_reproduces_the_separation_it_was_derived_from`, which fails if a threshold is
loosened.

**The single-crystal control.** 9PI2 holds Nd³⁺ *and* Ca²⁺ in one 0.99 Å crystal, so fold,
resolution, crystal form, refinement and depositor are identical across the two ions and none of
the usual confounders can explain a split. All **6 Nd sites** are called lanthanide-like (CN 10,
4 bidentate); both **Ca sites** are called calcium-like (CN 7 and 5, 1 bidentate). This is the
strongest control the project has and it runs offline from the cached coordinates.

**Site-level calibration — pseudo-replicated, quoted for calibration only.** Across the §3.17
filters: sensitivity **44/58 (75.9%)**, specificity **661/664 (99.5%)**. (§3.19 corrects that
denominator: three of the 58 are calcium ions inside lanthanide-family entries, so the sensitivity
is **44/55 = 80.0%**.) The three calcium sites
that pass are worth naming rather than burying: 2YGG (a calmodulin complex, CN 9, 3 bidentate,
SASA 3.46 Å²) is simply a lanthanide-like calcium site, and two calsequestrin sites in 7F05 are
CN 9 with 2 bidentate but **SASA 53.6 and 65.7 Å²**, where all three lanthanide families sit
between 0.00 and 8.72. So solvent accessibility, which fails as a *selectivity* term (25 of 55
overlapping), might work as a *negative triage* filter. That observation is **post-hoc on three
false positives and is not adopted** — it is written down so it can be tested on data that did not
suggest it.

**What it refuses to do**, each refusal pinned by a test:

- **A chelated site is not callable.** Half the first shell non-protein means the geometry
  describes the ligand, not the protein — the same flag the corpus filters on.
- **Worse than 2.5 Å is not callable**, the cutoff both arms of the contrast were held to.
  Resolution is read from the coordinates; an entry that states none (NMR) is scored with an
  explicit caveat rather than assigned a number.
- **A negative call from an asymmetric unit is marked unreliable.** Both criteria are counts a
  truncated parse can only *understate*, so an ASU can turn a real site into a negative but never
  into a false positive — §3.17's bug, encoded as an asymmetry. Unstated provenance is treated as
  an ASU rather than given the benefit of the doubt.
- **Net charge and SASA are reported and never scored.** They appear under `triage_only`, and
  `test_net_charge_and_sasa_are_reported_but_never_scored` makes promoting them loud, because net
  charge is the published Dudev prediction and the pressure to let it in is recurring.
- **No call returns a bare number.** Every output carries the *n* = 3 caveat, the fitted-and-scored-
  on-the-same-points caveat, and "not an affinity, not a selectivity constant, not a probability."

Reproduce: `pytest tests/test_geometry.py -v`, or open the Structure tab for 9PI2.

---

### 3.19 The fourth family, and the criterion it took with it

§3.18 closed by saying the honest *n* was three families and that raising it was worth more than
any refinement of the score. Raising it to four cost the score one of its two criteria. This
section is what that looked like.

**Why the search had to stop using titles.** `title_first_pass` left 590 of 636 Corpus A entries
unclassified, and `data/ree_pdb_entries.json` carries only elements, method, resolution and title —
no organism, no accession. Titles are written by depositors for humans and the fixes are worse than
the misses: `land` as a substring matches *Ignicoccus islandicus* and *Switzerland*.
`scripts/curate_corpus.py` goes to the RCSB GraphQL API for four structured signals per entry —
entity **description**, **struct_keywords**, Pfam/InterPro/GO **annotation**, and source
**organism** — matches whole words only, and emits a *ranked shortlist for hand curation*, never a
label. An organism match alone can only reach the `supporting` tier, because a methylotroph can
deposit an unrelated protein with a lanthanide soaked into it.

The first run used description, annotation and organism, and recovered all 11 known positives:
**30 strong, 2 family, 9 supporting**. The entry that mattered was in the *supporting* tier, on
organism alone.

**9VY4–9VYA.** Seven entries, one protein, seven different lanthanides — Yb, Tb, Ho, La, Sm, Gd,
Nd — at 1.21–3.05 Å. Nothing in the usual places says so. The titles say *"Structure of MIF binding
with Ytterbium ions"*; the entity description says *"Propeptide, PepSY amd peptidase M4"*. Only
`struct_keywords` names it: **"Rare earth, Metalloprotein, METAL BINDING PROTEIN"**. Adding keywords
as a fourth signal is what promotes the series to `strong`, and that is now a regression test —
the 9VY* entries are in `KNOWN_POSITIVES` precisely because the first rule set under-ranked them.

> Element names are deliberately **not** in any vocabulary. "ytterbium" in a title means a
> lanthanide is present, which is true of all 636 entries by construction.

**It is a natural protein, checked before it was used.** The construct is UniProt **Q1H2G7**
residues 23–175 — the mature wild-type chain after the annotated signal peptide, one initiator Met
the only difference — from *Methylobacillus flagellatus* KT, a methylotroph. `pdbx_mutation` is
empty, the host organism is *E. coli* (expression only), and UniProt annotates **two PepSY domains**
in tandem, which the sequence repeat confirms. A designed binder was the thing to rule out and it
is ruled out. The citation, *"Adjacent Rare Earth Separation by a protein atomic ruler"*, is **To Be
Published**: the structures are evidence, the function is so far a title, and that caveat travels
with the data in `FAMILIES`.

**It is a real site, not a soak.** 159 sites across the seven entries carry **24 distinct site
signatures**. Sixteen appear in exactly one entry — that is the soak background. **Five appear in
all seven**, which is the same five residue sets binding seven different metals in seven
independent crystals. Every one is carboxylate-dominated — four are carboxylate-only, the fifth
carries a single Gln:

| signature | in | geometry-v1 call |
|---|---|---|
| GLU31; GLU104; ASP120; GLU128; GLU146; GLN149 | 7/7 | Ln-like in 4 |
| ASP44; GLU70; GLU106; GLU153 | 7/7 | Ln-like in 4 |
| GLU66; GLU68; GLU110; GLU132; GLU142 | 7/7 | Ln-like in 1 |
| GLU42; ASP54; GLU106; GLU108; GLU118 | 7/7 | Ln-like in 0 |
| ASP54; GLU68; GLU108; GLU118; GLU132 | 7/7 | Ln-like in 0 |

**The family fails geometry-v1, on exactly one criterion.** Under §3.17's filters, six of seven
entries survive (9VY6 is 3.05 Å) giving 81 sites. Family medians: **CN 9**, **bidentate 1**,
carboxylate residues 5, net charge −5, SASA 1.45 Å². CN clears the threshold; bidentate count does
not, so v1 called the family `partial`. Restricting to the five conserved signatures changes
nothing — identical medians on all five descriptors — so the conclusion does not rest on the
post-hoc filter. **The fourth family reaches CN 9 through five monodentate carboxylates instead of
two bidentate ones.** Same coordination number, different route to it.

**What that does to the descriptor table.** §3.17's nine-descriptor sweep, re-run with four
families against the same 55 calcium accessions, ordered by overlap:

Medians are listed **weakest family first**, since the overlap count is taken against the weakest
— so for the descriptors whose lanthanide-like direction is *downward* (net charge, SASA) the
weakest value is the largest.

| overlap | exact one-sided *p* | descriptor | Ln family medians |
|---:|---:|---|---|
| **0/55** | **0.000002** | **coordination_number** | 9, 9, 9, 10 |
| 16/55 | 0.00085 | protein_donor_count | 6, 6, 8, 9.5 |
| 17/55 | 0.00023 | carboxylate_residues | 3, 4, 5, 6 |
| 17/55 | 0.00023 | net_charge | −3, −4, −5, −6 |
| 25/55 | 0.04088 | metal_sasa_A2 | 8.72, 1.45, 0.00, 0.00 |
| 26/55 | 0.00805 | shell_net_charge | −3, −4, −6, −10 |
| **30/55** | **0.00007** | **bidentate_carboxylates** | **1**, 2, 2, 3.5 |
| 30/55 | 0.04666 | protein_atoms_within_8A | 85, 94, 100, 110 |
| 35/54 | 0.12230 | mean_donor_distance_A | 2.43, 2.54, 2.54, 2.72 |

At *n* = 3 these two were indistinguishable: both 0/55, both *p* = 0.000032. One fourth family
separates them completely. Coordination number holds its zero overlap and its *p* improves by more
than an order of magnitude; bidentate count falls to **30 of 55**.

> **A correction, made while turning this analysis into a script.** The table above was first
> computed inline, selecting the lanthanide arm by entry rather than by ion — which quietly put
> **three calcium ions sitting inside lanthanide-family entries** (two in 9PI2, one in 6ZCV) into
> the lanthanide arm. They are correctly called calcium-like by both score versions, so they were
> *successes* being counted as failures. Every *p*-value in the first version of this table was
> slightly off and every overlap count was exactly right, which is the §3.17 rule arriving a
> fourth time from a direction nobody was watching. The numbers above now come from
> `scripts/selectivity_contrast.py`, whose lanthanide arm has always filtered on
> `family == "lanthanide"`; the same correction raises §3.18's site-level sensitivity from
> 44/58 (75.9%) to 44/55 (**80.0%**).

> **The third instance of the same trap, and the first against something already shipped.**
> Ranked by *p*-value, bidentate carboxylates is still the **second-best descriptor of the nine**.
> Ranked by overlap it is seventh. The *p*-value stays small because three of four families sit
> high — it cannot see that the fourth is sitting in the calcium bulk. §3.17 derived the rule
> *overlap count beats p-value at small n* from two near-misses; here it overturns a criterion
> that was shipped in `lantern/geometry.py` and passing its own reproduction test.

**What dropping it costs, measured both ways.** The second criterion was never buying specificity —
CN ≥ 9 alone already admitted 0 of 55 calcium accessions, measured before this family existed. It
was only costing sensitivity. All three rows below are on four families, 136 Ln sites and 664 Ca
sites, and are printed by `scripts/selectivity_contrast.py` at the foot of the contrast they come
from, so they cannot drift from it again:

| rule | Ln families | Ca accessions | site sensitivity | site specificity |
|---|---:|---:|---:|---:|
| CN ≥ 9 **and** bidentate ≥ 2 (v1) | 3 of 4 | 0 of 55 | 72/136 = 52.9% | 661/664 = 99.55% |
| **CN ≥ 9 alone (v2)** | **4 of 4** | **0 of 55** | **89/136 = 65.4%** | 659/664 = 99.25% |
| bidentate ≥ 2 alone | 3 of 4 | 1 of 55 | 83/136 = 61.0% | 623/664 = 93.83% |

Twelve points of sensitivity and a whole family, against 0.3 points of site-level specificity —
two additional false-positive sites out of 664. There is no threshold that keeps four families
*and* separates: at bidentate ≥ 1, which is what keeping the family requires, 30 of 55 calcium
accessions pass. `test_the_v1_conjunction_would_still_lose_the_fourth_family` pins that, so the
argument for the removal stays executable rather than only written down.

**A second negative control, orthogonal to calcium.** The keyword sweep also turned up the
**Tb-Xo4 "crystallophore"** series — 4BAD, 4BAF, 4BAP, 4BAR, 4BS7, 5MF2, 6F2F, 6F2I, 6F2M, 6HF6,
6HF7, 6HK1 — twelve entries where a lanthanide complex was added purely as a nucleating and
phasing agent, plus two antibody–DOTA complexes (1NC2, 1NC4). Here the element is right and the
site is certainly not biology, which is the converse of the calcium contrast. Of their 126 sites,
98 are removed by the resolution and chelator filters; **of the 28 that survive, none reaches
CN 9** — they run CN 0–4 with `other_ligand_donor_count` 0, i.e. bare surface ions that the
chelator flag correctly declined to fire on. Both DOTA entries are caught 4/4 by the chelator flag.
**0 false positives on 12 entries of known-artefact ground truth.**

**No fifth family has turned up in Corpus A.** With keywords added the shortlist is **60 strong, 0
family, 2 supporting, 574 none** — double the first run — and all 62 have now been read
individually. The entries outside the four known families return no new natural biology. What they
return is the non-biology classes, now identifiable rather than merely unclassified: twelve
crystallophore entries, two antibody–DOTA conjugates, the LBT and de-novo designed binders (1TJB,
7CCN, 7CCO, 7P3H, 9CEQ, 6ZV9, 2OJR, 3VDZ, 5XBO, 3LTQ, 5OBB, and — missed by the title pass because
it writes the abbreviation rather than the phrase — 2RPV "GB1 with LBT probe" and 9L6D
"Azurin-LBT"), a paramagnetic-NMR tag (2RSE), lanthanide-substituted calbindin used as a PCS system
(1KSM), lanthanide substituted into a **non**-calcium site (1FCK and 1QJM, Ce into lactoferrin's
Fe³⁺ site), and soaks.
**Raising *n* beyond four requires enlarging the corpus, not re-reading it** — the PDB contains
four natural lanthanide protein families and a great deal of lanthanide reagent.

> **How far that claim actually reaches, measured.** "No fifth family in Corpus A" is a statement
> about the corpus; the evidence is that every *shortlisted* entry was read. Those are not the same
> thing unless the shortlist recalls everything worth reading, which was never checked. It can be
> checked, because geometry-v2 shares none of the shortlist's four signals — it is coordination
> geometry, they are depositor vocabulary — so the two disagreeing is informative. Of the 1667
> scoreable lanthanide sites, **174 reach CN ≥ 9, and 81 of them, in 38 entries, sit in entries the
> shortlist tiered `none`.** `scripts/curate_corpus.py` prints this as a recall audit and
> `tests/test_corpus.py` pins the three counts, so improving the signals forces this number to be
> restated rather than quietly dropped.
>
> The case that exposed it: **5HLK** is EcoRV–DNA–Lu with *cleaved* substrate, the same experiment
> and the same Lu site as the shortlisted 5F8A, and **not one of the four signals fired on it** —
> 5F8A reached the shortlist only because its depositors happened to put the word "Lanthanide" in
> the title. A whole category is invisible this way: lanthanides substituted into the catalytic
> Mg²⁺ sites of nucleases and ribozymes, which depositors describe as "Lutetium", "two metal ions",
> "di- and trivalent metal ions". None of the 38 looks like a fifth natural family on its title —
> they are Dps/Dpr iron-storage proteins, aldehyde dehydrogenases, an LBT nanobody fusion (6Y1R
> "Nb22-LBT"), a surface gadolinium cluster (4AHX) — so the conclusion survives. **The confidence
> behind it does not: it rests on a shortlist with measured imperfect recall, and the honest
> statement is that no fifth family has been found by either of two independent probes.** Reading
> those 38 is the next curation step, and a better-ordered one than the unclassified tail, because
> the score chose them.

The last six were the ones whose titles promised least, and they are worth naming because reading
them is what turns "no fifth family" from an inference into a check. **4IRW** co-crystallizes
streptavidin with a Tb–dipicolinate complex; **7O9P** is an adhesin A-domain whose own keywords say
"gadolinium cluster"; **6THE** is a copper nitrite reductase carrying four different rare earths
(Er, Tb, Yb and Y) at CN 0–1, a phasing screen, and the only entry here admitted on an organism
match alone; **9WE9** lists its lanthanide between a buffer and a cryoprotectant; **5F8A** is Lu³⁺
in EcoRV's catalytic Mg²⁺ site, inhibiting cleavage; and **7QB3** is not a protein at all but a
selected DNA aptamer, which the scheme could not express either, even after lactoferrin had already
pushed it from four classes to five — hence a sixth, `not_protein`. The parse agrees with the
metadata there from the coordinates alone: that site's signature is `DC15;DG17;DC18`. It also
exposes a parser limitation worth naming, since those three nucleotides are counted in
`protein_donor_count` — the count keys on polymer residues without asking which polymer. Scope
measured and pinned by a test: **22 sites in 10 entries**, all of them lanthanide, **none in the
four families and none in the 55 calcium accessions**, so the contrast and everything derived from
it are untouched. One site changes if the nucleotide is excluded — 5HLK's Lu, CN 9 → 8 — and that
entry turns out not to have been shortlisted at all, which is what led to the recall audit above.

Two findings came out of those six that the four families could not have produced:

- **The chelator filter is load-bearing, and only 4IRW proves it.** All 20 of its Tb sites are
  chelator-flagged, every one has `protein_donor_count` **0** — the protein contributes nothing to
  any of them — and yet **8 reach CN ≥ 9** through the dipicolinate cage alone. Without the filter
  those 8 are false positives for the v2 criterion. The Tb-Xo4 series never tested this: its 28
  surviving sites run CN 0–4, so for the crystallophores CN alone would have sufficed. A negative
  control only exercises the component that would have failed on it.
- **geometry-v2, applied out of sample to these 98 sites, fires once — on 5F8A.** That site is CN 9
  with four protein donors and two bidentate carboxylates, not chelator-flagged, and its signature
  is `GLU45;ASP74`: EcoRV's PD…D/ExK catalytic carboxylates themselves, not surface acid. The score
  is right and the label is also right. **geometry-v2 ranks sites that suit a lanthanide, not
  proteins that evolved to use one** — a catalytic metal site qualifies on chemistry whether or not
  the organism ever meets a lanthanide. For a screen whose output is a shortlist for experimental
  testing that distinction is the difference between a hit and a candidate, and it is the reason
  the class label is carried alongside the score rather than folded into it.

> One gap this exposes in the four-class scheme: `ln_substituted_ca` does not cover lactoferrin,
> where the lanthanide replaces **Fe³⁺**, not Ca²⁺. The class is now
> `ln_substituted_native_site`, with the displaced metal recorded in the basis.

**The verdicts are in the table, not only in this section.** `data/curation_verdicts.json` carries
all 33 of them with their evidence, and `scripts/build_site_table.py` applies them over the title
pass, writing `class_basis` as `curated:<reason>` so that machine guesses and human judgements stay
distinguishable in the data. A further 29 entries are recorded in `confirmed_by_title_pass`: read,
title rule already correct, no override written — so that *not in verdicts* cannot be misread as
*not looked at*. This is the M2 hand-curation step, started on the entries this section had to read
anyway. Two consequences are worth stating:

- **`scripts/selectivity_contrast.py` now reproduces this section by itself.** Before the verdicts
  existed it still printed the superseded *n* = 3 result, because the fourth family was sitting in
  the `unclassified` pile that its positive-class filter excludes — the analysis behind the shipped
  score and the script that was supposed to regenerate it had silently diverged.
- **The positive-class verdicts are deliberately non-geometric.** `natural_ln_biology` is the
  positive class of this very contrast, so an entry admitted to it *because of its coordination
  number* would make the contrast circular. The evidence recorded for the PepSY family is construct
  provenance, an empty mutation record, cross-crystal signature conservation and a citation; its
  geometry is what the contrast then measures, not what let it in.

**geometry-v2** is therefore one criterion: **CN ≥ 9**, the single descriptor of nine that
separates four families from 55 calcium accessions and 28 crystallophore sites with no overlap.
Bidentate carboxylates joins net charge and SASA under `triage_only` — reported on every call,
never scored. The `partial` band is gone, since with one criterion a call is a pass or a fail and
there is no half-passing bucket to file a failing family into. The ASU asymmetry gets *cleaner*,
not messier: the one thing scored is exactly the quantity a truncated parse understates, so a
passing call is trustworthy whatever the provenance and a failing one from an ASU is not. Ranking
orders on CN and then stops — using bidentate count as a tiebreak would reinstate the removed
descriptor silently, in the ordering instead of in the call, which is the weighted-score mistake in
miniature (`test_ranking_does_not_demote_a_monodentate_site_below_a_bidentate_one`).

Every call now also carries a fourth caveat naming what would break it: *a fifth family may do to
coordination number what the fourth did to bidentate carboxylates.* One descriptor surviving four
families is the current state of the evidence, not a result.

Reproduce: `pytest tests/test_geometry.py -v`; refresh the shortlist with
`python -I scripts/curate_corpus.py`.

### 3.20 Live search threw away the structures, so turning it on cost you the measurement

**Found 2026-10-20, fixed the same day.** `uniprot.FIELDS` requested
`accession,protein_name,organism_name,sequence`. UniProt returns
`uniProtKBCrossReferences` only when `xref_pdb` is among the requested fields, so every live hit
arrived with `pdb_id=None`. `discover._evidence_for` reads exactly that attribute, so every live
candidate fell through to:

> No deposited structure and no prediction, so the coordination number is unknown. The design
> rules above are sequence-only.

Measured before the fix, on the canonical question with the sidebar toggle on:

| | shortlist | structures measured | sites |
|---|---|---|---|
| Offline (bundled set) | 2 of 6 | 2 | 18 |
| **Live search on** | 1 of 1 | **0** | **0** |

The protein the live search returns is C5B164 — lanmodulin, the right answer. UniProt's own record
for it cross-references **8FNS at 1.01 Å**, the same file `data/structures/` already holds and the
offline path already measures. The platform had the protein, had the structure, and said the
coordination number was unknown. Not a false claim — a false *unknown*, which is the same fault
pointing the other way: the toggle that advertises more proteins silently removed the half of the
loop that measures anything.

**Fix.** `xref_pdb` is requested, `pdb_cross_references` parses the id, method and resolution out
of each cross-reference, and `choose_structure` picks one. Method and resolution come from the
cross-reference itself, so this costs no extra request per hit.

**The choice is the part that needed care.** An entry can list several structures and the page
shows one. The rule is highest-resolution X-ray, because geometry-v2 weighs how far to trust a
call against the resolution of the entry it measured — so the sharpest coordinates make the
measurement downstream worth the most. That is *not* a relevance judgement: a cross-reference does
not say which metal is in which file, and a 2.5 Å entry holding the user's lanthanide beats a
1.0 Å apo one for the question actually being asked. Entries stating no resolution (NMR, 6MI5
here) are not ranked against those that do — treating `None` as a number sorts them either first
or last and neither is a measurement — so they are the fallback, taken in PDB-id order, and the
reason string says that choice is arbitrary. Every unmeasured structure stays in the record and is
listed on the page under what was not measured.

After the fix, same question, toggle on: **8FNS measured, 4 Nd sites, all CN 9–10, all called
lanthanide-like**, with "chose 1 of 2 deposited" disclosed. Reproduce:
`pytest tests/test_uniprot.py tests/test_discover.py -v`, or drive the page with
`python scripts/drive_app.py --live`.

**What this does not fix.** The default live corpus is `lanmodulin`, which is one UniProt record
(§3.2) — so live search still returns *fewer* candidates than the bundled six, and `lanm-family`
remains the only route to the other 188. Retrieval breadth is M4's problem; this entry is only
about not discarding what retrieval already found.

---

## 4. The strategic reframe: three finite corpora

Everything below follows from sizing the problem honestly.

**Corpus A — the global rare-earth structure set: 636 entries.** Complete per-element counts, from
the RCSB Search API:

| Element | Entries | | Element | Entries | | Element | Entries |
|---|---:|---|---|---:|---|---|---:|
| Gd | 179 | | Sm | 52 | | Ho | 16 |
| Yb | 119 | | Y | **68** | | Ce | 6 |
| Tb | 64 | | Eu | 28 | | Er | 6 |
| Pr | 57 | | La | 23 | | **Nd** | **4** |
| | | | Lu | 17 | | **Dy** | **2** |

Of the 636, **570 contain a true lanthanide** (La–Lu) and 66 are yttrium-only. Sc, Pm, Tm: **zero**.
For contrast, Ca²⁺ appears in **16,658** entries.

> **Implementation gotcha, found the hard way — twice.** There is no single ligand code per element.
> Erbium is `ER3` (plain `ER` does not exist), and Eu, Gd, Ho, Yb each have *two* codes
> (`EU`/`EU3`, `GD`/`GD3`, `HO`/`HO3`, `YB`/`YB2`) that must be merged. Querying the obvious
> two-letter symbols alone undercounts the corpus by ~15% and reports zero erbium structures. Beware
> also that `SC`, `TM3`, `ND3`, `LA3` are codes for unrelated *organic* molecules — matching on
> element symbol alone will silently poison the corpus.
>
> **The second time was ours.** The hand-written code list above originally said "yttrium is `YT3`".
> Yttrium is `YT3` *and* `Y1`, both bare Y³⁺ ions. `Y1` was missing from both the corpus query and
> `REE_LIGAND_CODES`, costing 19 entries (617 → 636, Y 49 → 68) and leaving `binding_neighborhood()`
> silently blind to every one of them — it would have returned "no rare-earth sites found" rather
> than an error. The fix is not a longer hand-written list; it is **not hand-writing the list at
> all**. `scripts/build_ree_corpus.py` now asks RCSB which chemical components have a rare earth in
> their *formula* (`chemical` service, `type: formula`, `match_subset`), and fails loudly on any
> component it cannot classify.

That enumeration returns **27 components**. Nineteen are bare ions and make up the corpus above. The
other eight are excluded on chemical grounds, recorded in `CHELATED_REE_CODES`:

| Code | What it is | Entries |
|---|---|---:|
| `7MT` | Tb-Xo4 "crystallophore" (nucleating/phasing agent) | 20 |
| `7PR` | praseodymium triacetate | 4 |
| `YBT` | yttrium **bis-tris** — a buffer component | 4 |
| `WRT` | TbXo4-OH, same crystallophore family | 1 |
| `JGH` | Ce-substituted Keggin polyoxometalate (W₂₂!) | 1 |
| `K93` | Lu(III) macrocyclic cage | 1 |
| `T7K` | Yb(III) caged complex | 1 |
| `SFL` | scandium tetrafluoride | 1 |

In every one the metal arrives **pre-chelated**: its first shell is the reagent's donors, not the
protein's, so these sites teach the opposite of what the project is looking for. Including them
would add 14 entries and a systematic bias. This is also why scandium shows zero — the PDB has no
bare Sc code at all, which is a fact about the ion's chemistry here rather than a gap in the list.

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

> **Doing it took six, not four** (§3.19). Two of the additions came from entries the four-way
> split simply could not name: `ln_substituted_native_site`, because lactoferrin and EcoRV hold
> their lanthanide in a site evolved for Fe³⁺ and Mg²⁺ rather than Ca²⁺, and `not_protein`, for a
> lanthanide-binding DNA aptamer. The survey above was written from what the PDB was expected to
> contain; the extra classes are what reading it actually returned.

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

### M1 — Real reference data (1–2 days) — ✅ **DONE 2026-10-19**

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

> **And then it was achievable after all — later the same day.** The reasoning above was right to
> refuse the test *at the time*: with a known-broken descriptor, the only way to pass it was to tune
> the descriptor against it. What changed was not the test but the evidence. Auditing the resolved
> donors of 8FNR, and then 8DQ2 and 9PI2 (§3.8), showed the two offending regex positions encode
> **calcium** architecture — Asn at position 1 is a real first-shell donor, Gly at position 6 is not
> a donor at all. Removing them is justified by structure, and the ranking inverted back on its own.
>
> The distinction worth preserving: **the fix was derived from coordinates and validated on 694
> sequences before the acceptance test was consulted** (§3.6). Had the test been written first, the
> same code change would have been indistinguishable from fitting. The strict `xfail` is what made
> this safe — it failed loudly the moment the behaviour changed, forcing the milestone to be closed
> deliberately rather than drifting shut.
>
> The inversion-pinning test is now replaced, not deleted, by three that pin the corrected state:
> the ordering, the **2.1-point margin** (`test_the_separation_is_thin_and_the_test_says_so`), and
> the mechanism (`test_hans_lanm_scores_its_three_lanthanide_loops_and_not_its_calcium_one`).

**Done when:** ~~the default demo runs offline on authentic sequences, every record carries a
verified checksum and provenance, and the ranking — including its known inversion — is pinned by
test.~~ — ✅ **DONE 2026-10-19.** All of that, plus the inversion resolved rather than merely
pinned: 88 tests at M1 close, no xfail, five structures cached (8FNS, 8FNR, 8DQ2, 9PI2, 1CLL), both lanthanide
binders above both calcium proteins.

### M2 — The lanthanide structure corpus (3–5 days) ← *the core asset*

Build Corpus A as a versioned local database.

> **Head start:** `data/ree_pdb_entries.json` already ships the verified enumeration — all 636
> entry IDs with their rare-earth elements and structure titles, plus a provenance block. It is
> explicitly marked `"curation_status": "uncurated"`. M2 begins by downloading and classifying
> these, not by rediscovering them.

> **Second head start: do not parse 636 structures from scratch.** **MetalPDB**
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

- ✅ **Download all 636 and extract every rare-earth site.** **Done 2026-10-19.** All 636 entries
  fetched, zero failures, 186 MB into gitignored `.cache/corpus/`; parsed to **2795 sites from 636
  entries** (2570 Ln, 225 Ca) in `data/lanthanide_sites.parquet` (93 KB). §3.13 has the results.

  **The format recommendation above was wrong, and it was measured rather than assumed.** BinaryCIF
  is smaller than *uncompressed* mmCIF, which is not the comparison that matters: gzipped mmCIF is
  **5× smaller than bcif**, bcif gains only ~15% even with `--compressed`, it needs msgpack (not
  installed), and `models.rcsb.org` 404s on 6EK0. The corpus is gzipped mmCIF. The legacy `.pdb`
  warning stands (§3.5).
- ✅ **Per-site measurements.** **Done 2026-10-19.** 33 columns: CN, protein/water/other donor
  counts, bidentate and monodentate carboxylates, Glu/Asp carboxylate O, backbone carbonyl,
  sidechain amide, hydroxyl, mean donor distance, first-shell net charge, metal SASA, protein atoms
  within 8 Å, shell charge, chelator evidence, title class and its basis.
- ✅ **The parser is validated against an independent implementation.** **Done 2026-10-19.** 65 of
  65 metal ions agree with MetalPDB on every donor it reports, atom for atom and distance for
  distance; the 26 extras all fall in the 3.00–3.18 Å band between the two cutoffs (§3.13).
  `scripts/crosscheck_metalpdb.py`.
- **Filter chelator-dominated sites, which are a second contamination class.** §4's
  `CHELATED_REE_CODES` catches entries where the metal *is* a pre-chelated component. It does not
  catch the commoner case: a bare `GD`/`TB`/`YB` ion in an entry that also contains a separate
  chelator molecule — bis-tris (`BTB`), DOTA/DO3A-type macrocycles (`DO3`), pyridine-2,6-
  dicarboxylate (`PDC`), citrate, EDTA — which is what actually coordinates it. The site passes the
  bare-ion filter and is still not protein-coordinated.

  This needs no new chemistry: `binding_neighborhood()` already returns `other_ligand_donor_count`
  per site, counting first-shell donors that are neither protein nor water. A site where those
  dominate is a chelator complex that happens to sit near a protein. Suggested rule, to be
  hand-checked rather than trusted: flag any site where `other_ligand_donor_count` is at least half
  of `coordination_number`. Record the flag; do not silently drop, since a few genuine sites have a
  bound carbonate or acetate. Checked against the 42 cached biological sites: **zero** are flagged,
  so the rule costs nothing on the positive class. Its false-*negative* rate is untested and needs
  a chelator-containing entry to measure — pick one from the `BTB` list below.

  **The scale of the problem, measured over all 636 corpus entries** (RCSB Data API, 2026-10-19):
  **207 entries — 32.5% — contain at least one known metal-chelating co-solute.**

  | Component | What it is | Entries |
  |---|---|---:|
  | `BTB` | bis-tris | 96 |
  | `ACT` | acetate | 93 |
  | `DO3` | DO3A macrocycle | 21 |
  | `PDC` | pyridine-2,6-dicarboxylate | 6 |
  | `CIT` / `FLC` | citrate | 7 |
  | `DOT` | DOTA | 1 |
  | `TLA` | L-tartrate | 1 |

  **Do not read that 32.5% as "207 entries to drop."** Bis-tris in the crystallization buffer
  usually sits nowhere near the metal, and acetate is often an innocent surface passenger. Presence
  is a reason to *check the geometry*, which is why the filter is a first-shell measurement and not
  a component-presence lookup. The 21 `DO3` and 1 `DOT` entries are the ones to inspect first:
  DOTA-type macrocycles are purpose-built lanthanide cages, and in those entries the metal is
  almost certainly theirs rather than the protein's.

  ✅ **Measured over the real first shells, 2026-10-19, and the caution above was right.** The
  component-presence survey flagged 32.5% of *entries*; the first-shell measurement flags **522 of
  2795 sites (18.7%)**, and **481 sites carry a named chelator** — bis-tris 352, acetate 57, DO3A
  45, pyridine-2,6-dicarboxylate 16, citrate 9, DOTA 2. The flag is recorded in two columns
  (`chelator_flagged`, plus the chelator names themselves) and nothing is dropped: MetalPDB
  independently confirms PQQ and methanol as genuine first-shell donors of the XoxF lanthanide
  site, so a filter that discarded non-protein donors would discard methanol dehydrogenase.
- 🟡 **Classify every site into the classes of §4** — natural Ln biology, Ln-substituted Ca site,
  engineered LBT, phasing/surface artefact, and the two the hand-check had to add: Ln substituted
  into a native **non**-Ca site, and not-a-protein. **First pass done, shortlist hand-checked, the
  unclassified tail outstanding.** The
  title pass ships as `class_first_pass` with `class_basis` naming the keyword that fired, because
  a label whose provenance is not recorded cannot be audited later: **2655 unclassified, 57 natural
  Ln biology, 56 Ln-substituted Ca, 27 engineered LBT**. It is a *hint*. A title cannot tell a
  phasing derivative from biology, and "STRUCTURE OF X" is the commonest title in the corpus.

  Two things now make the hand-check tractable rather than open-ended. Geometry sieves 2570 Ln
  sites down to **374 worth looking at** (§3.13, Q0), in 139 entries. And the keyword list is
  already known to be brittle in a specific way: 9PI2 is titled *"Ancylobacter lacus LanM"*, so the
  keyword "lanmodulin" dropped a structurally confirmed lanthanide binder into the unclassified
  pile — the same failure mode as §3.11's HMM miss, reached by a different route. The shortened
  key is pinned by a test. Site 11 of 8FNR (CN = 4, 2 carboxylates, no water) remains the worked
  example of an artefact the classifier must reject; sites 1–3 of the same entry (CN = 9, 3
  bidentate) are what it must keep.

  ✅ **The hand-check is done for the whole shortlist: 33 verdicts in the table, 29 more entries
  confirmed as already-correct (§3.19, 2026-10-19).** `scripts/curate_corpus.py` shortlists entries
  on four *structured* RCSB signals — entity description, struct_keywords, Pfam/InterPro/GO
  annotation, source organism — instead of titles, and never auto-labels;
  `data/curation_verdicts.json` holds what reading the shortlist concluded, with the evidence, and
  `scripts/build_site_table.py` applies it over the title pass as `class_basis = curated:<reason>`.
  Progress is **60 of 60 strong-tier and 2 of 2 supporting-tier entries read, 0 outstanding**. The
  counts are now **2739 unclassified, 224 natural Ln biology, 224 phasing artefact, 125 engineered
  LBT, 56 Ln-substituted Ca, 6 Ln-substituted non-Ca site, 1 not protein**. Three of those classes
  could not previously be reached at all: `phasing_artefact` had no keyword rule,
  `ln_substituted_native_site` did not exist until lactoferrin showed that `ln_substituted_ca`
  cannot express a lanthanide displacing Fe³⁺ (EcoRV then gave it a second displaced metal, Mg²⁺),
  and `not_protein` had to be added for a DNA aptamer that the site parser was happy to describe
  and the class scheme could not name. What the verdicts bought immediately was the fourth natural
  family and, through it, the removal of a criterion from the shipped score.
- Build the matched Ca²⁺ contrast set from 1CLL and comparable EF-hand structures. Where a protein
  appears in both sets — troponin C with Ca and with Tb, calmodulin with Ca and with Tb — you have
  a *paired* same-protein comparison, which is the strongest evidence in the corpus. Extract these
  pairs explicitly. **§3.13's Q2 is the argument for doing this properly:** the 225 calcium sites
  already in the table are Ca in entries that also contain a rare earth, which is not a matched
  contrast, and using them as one inverts the chemistry.
- ✅ **Ship as `data/lanthanide_sites.parquet` + a provenance manifest.** **Done 2026-10-19.**
  `.cache/corpus/_manifest.json` records source, fetch date and a per-entry sha256.

**Done when:** a single local query returns every known lanthanide protein site with geometry and a
curation label, and the CN distributions for biological Ln sites versus Ca sites separate visibly.
**Status: geometry and provenance done, the shortlist fully curated (33 entries hand-verdicted and
29 confirmed, §3.19), and the long tail of 2739 unclassified sites outstanding.** The CN
distributions do separate — 9.00 (9.00–10.00) for titled biology against 4.00 (2.00–7.00) for everything untitled,
83.6% balanced accuracy — but §3.13 shows that comparison is mostly real-site-versus-surface-soak,
not Ln-versus-Ca, and the Ln-versus-Ca split on this uncurated corpus runs backwards for the reason
given there. The curation step is what the rest of M2's claim rests on.

### M3 — A descriptor that actually discriminates (3–5 days)

**M3.0 — the sequence-level fixes, first, because M4's retrieval depends on them (§3.6, §3.8).**
These are cheap, they are what unblocks the headline screen, and none of them needs M2:

- ✅ **Re-derive the motif from structure, not from a calcium consensus.** **Done 2026-10-19.**
  Positions 1 and 6 now admit what the structures show (Asn at 1; non-Gly at 6). Validated on 694
  sequences: sensitivity 91.0% → 96.8%, specificity held at ~91%, family zero-motif rate 1.1% → 0.0%
  (§3.6, `scripts/validate_motif.py`). PS00018 is documented as a *negative* example.
- ✅ **Gate: `A0A4V2JDD3` must rank above both calcium proteins.** **Met** — 71.1 vs 69.0 and 57.0.
  **But the margin is 2.1 points and the gate should not be read as more than it is.** It confirms
  the ordering is no longer inverted; it does not establish a calibrated descriptor.
- ✅ **Build a loop detector with balanced recall.** **Done** — `EF_LOOP_INSTRUMENT`,
  `[DN].{6}[ILV].{3}E`, built and validated against external ground truth in §3.10. The shipped
  classifier recovers **20.4%** of 1421 curated calcium EF-loops against **83.3%** of lanthanide
  loops read off coordinates; the instrument gets **83.0% / 91.7%**, cutting the family gap from
  **62.9 to 8.7 points** at 0.88 matches per curated loop. The two are kept separate in code and
  the separation is pinned by `test_scoring_never_uses_the_measuring_instrument` — swapping the
  instrument into the score would look like a recall improvement and would silently destroy the
  discrimination the score depends on. One is a classifier, the other is an instrument.
- ✅ **Measure the remaining sequence hallmarks** from Mattocks et al. 2023. **Done** (§3.11,
  `scripts/sequence_hallmarks.py`), through `EF_LOOP_INSTRUMENT`. Period: **24.0 (IQR 24–25) for
  lanmodulins vs 36.0 (IQR 36–39)** for calcium EF-hands, reproducing the published figures — the
  classifier gets 45.5 from 46 gaps for the same calcium set, which is what the instrument was
  built to prevent. Pro at loop position 2: **71.2% of lanmodulin loops vs 0.1%** of calcium
  loops, the cleanest sequence feature found so far.
- **Neither hallmark may enter the score yet, and the blocker is not implementation.** Both are
  measured on exactly the set NCBIfam NF053806 retrieves, so they describe a known family rather
  than predicting membership in it (§3.11). Promoting them now would fit the score to an HMM.
  **The unblocking step is M4 retrieval**: search by period + Pro-at-2 and see what returns that
  the HMM did not contain. If that set is non-empty and survives structural checks, the features
  have earned their place; if it is empty, they were definitional and the score is better without
  them.
- ✅ **Encode position 9 explicitly** rather than leaving it implicit in the regex (§3.8). **Done**
  — `ef_hand_loops()` returns every matched loop with all six ligand positions named, and
  `Candidate.position_9` reports the composition. It is *not* a score term: the matched loops
  already required `[DE]` there, so scoring it again would double-count.
  **The reason previously given in this bullet for keeping the {Asp, Glu} form was wrong and has
  been corrected in §3.8.1.** It said Glu-only "would reject Mex-LanM, the founding family member".
  True, but far too weak: measured over 694 sequences, Glu at position 9 occurs in **0.5% of
  lanmodulin loops and 13.3% of calcium EF-hand loops**. Glu-only is not an incomplete lanthanide
  feature, it is a calcium feature — 50.0% balanced accuracy, i.e. no better than a coin. Asp
  carries the signal (82.1% vs 26.4%). Asp-only benchmarks 0.4 pp above `[DE]` and was deliberately
  **not** adopted: that is fitting to the one set being measured against.

**M3.1 — the geometric descriptor.**

- Implement the geometric descriptor from §3.1 — CN, bidentate carboxylate count, donor-atom
  composition, carboxylate-oxygen density, site burial — scored on structures, not sequences.
  **Use the §3.9 feature ranking, and select features against calcium EF-hands rather than against
  all calcium sites** — the strongest PDB-wide feature (backbone carbonyl count) carries exactly
  zero information inside this family. `donor_chemistry()` already computes the within-family
  survivors: bidentate carboxylate count, carboxylate O count, Glu/Asp split. ✅ **Burial and net
  charge are now implemented and measured** (§3.12) — `site_net_charge()` and `_burial()`, attached
  to every site dict. **Neither is scored.** The Dudev condition (buried, −3/−4) is met by 30 of 36
  Ln sites *and 2 of 6 Ca sites*, because an EF-hand loop is a −3/−4 buried centre whichever ion it
  holds: 97.6% of cached sites fall in that class. Coordination number, already shipped, separates
  better than either (93.1% vs 77.8% and 75.0% balanced accuracy). Calibrating them needs Ln sites
  from **outside** this fold, where charge varies — i.e. M2's corpus.
- ✅ **Which descriptors go in is now settled (§3.17, revised by §3.19).** Against **four** natural
  Ln families and 55 Ca accessions, **coordination number** is the only one of nine with **zero
  overlap** — no calcium accession reaches CN 9. Bidentate carboxylate count tied it at *n* = 3 and
  broke at *n* = 4 (30/55). Net charge is significant and is the Dudev prediction, but 17 of 55 Ca
  accessions are as anionic, so it stays in **triage** for the fifth time; SASA is out for the
  sixth. Build the score on coordination number alone.
- Calibrate thresholds on M2's curated Ln sites versus the Ca contrast set. With ~tens of
  genuine biological Ln sites this is **threshold calibration and ROC reporting, not machine
  learning** — do not train a model on this sample size and do not call the output a probability.
  At *n* = 3 families, **report the overlap count beside every threshold**: it is the number that
  survives a small sample, where a *p*-value is mostly a statement about *n* (§3.17).
- ✅ Version it (`score_version`) and keep the sequence heuristic alongside, clearly labelled as
  triage only. **Shipped** as `lantern/geometry.py` and wired into the Structure tab, with
  refusals for chelated sites, resolution worse than 2.5 Å, and negative calls made on an
  asymmetric unit. 9PI2's six Nd and two Ca sites split correctly inside one 0.99 Å crystal.
- ✅ **Raising *n* to four removed a criterion (§3.19).** The honest *n* was three; `curate_corpus.py`
  made it four by going to RCSB `struct_keywords` instead of titles, and the fourth family —
  wild-type tandem-PepSY, UniProt Q1H2G7, seven lanthanides, five sites conserved across all seven
  crystals — reaches CN 9 with *monodentate* carboxylates. **`geometry-v2` is one criterion,
  CN ≥ 9**: 4/4 families, 0/55 Ca accessions, 0/28 crystallophore artefact sites. Bidentate count
  joins net charge and SASA in triage. It would have been kept on its *p*-value, which is still
  second-best of nine; its overlap went 0/55 → 30/55.
- ✅ **First out-of-sample test of v2, on the 98 sites of the six hand-read entries that were
  nobody's family (§3.19).** One site fires: 5F8A, Lu³⁺ on EcoRV's catalytic `GLU45;ASP74`. Correct
  as chemistry and correctly *not* natural biology — **v2 ranks sites that suit a lanthanide, not
  proteins that evolved to use one**, which is why the class label travels beside the score instead
  of inside it. The same six showed the chelator filter is load-bearing: 4IRW has 8 CN ≥ 9 sites
  with zero protein donors, all cage, all filtered — a failure the 28 crystallophore sites (CN 0–4)
  could never have caught.
- **Still open:** *n* = 4 and no fifth family has been found by either of two independent probes —
  all 62 shortlisted entries are read (phasing reagents, designed binders, NMR tags, a
  metal-substituted catalytic site, one DNA aptamer), and a recall audit of the shortlist against
  geometry-v2 turned up **38 further entries the signals never proposed and the score flags**, none
  of which looks like natural lanthanide biology either (§3.19). Reading those 38 is the next
  curation step. Raising *n* further still means **enlarging the corpus**.

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
>    implying otherwise.** n=4 is a validation set, never a training set. LANTERN is a
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
- **3D site inspector — done.** `lantern/viewer.py` draws one site at a time: the ion, a dashed
  bond to each first-shell donor, the measured distance on every bond, donors coloured by the
  class `structure.donor_class` assigns, and toggles for residue labels, distances, waters and
  cartoon. Two design decisions are load-bearing rather than cosmetic.
  - *Every shape is placed from coordinates the analysis already measured*, not re-derived in
    the browser. `binding_neighborhood()` now carries `xyz` for the ion and for each donor, so
    the bond count equals the coordination number by construction and the distance on a bond is
    the float geometry-v2 scored. A viewer that re-found its own neighbours could show CN 8
    under a table saying CN 9, and the picture is the more persuasive of the two.
  - *One ion radius for every element.* Ln³⁺ and Ca²⁺ ionic radii differ by hundredths of an
    ångström — that near-identity is the selectivity problem — so drawing them to scale would
    imply a distinction the chemistry does not offer. Colour carries identity instead.
  Coverage: `tests/test_viewer.py` (51 tests) pins the spec, and, where `node` is installed,
  executes the generated JavaScript against a stubbed `$3Dmol` and asserts on the shapes drawn
  — a blank viewer raises nothing on the Python side, so it is the only layer that can catch it.
- **Self-hosted 3Dmol.js — done.** `static/3Dmol-min.js` is `3dmol@2.5.5` from the npm tarball,
  verified byte-for-byte against the registry's published sha512 and against what the CDN serves,
  BSD-3-Clause with the licence alongside it. `.streamlit/config.toml` enables static serving and
  `viewer.tmol_sources()` makes the local copy the primary source, so the last externally-hosted
  asset is gone and the whole core workflow — reference set, cached structures, coordination
  analysis, viewer — runs with no network at all. The CDN is kept as a *browser-side* fallback
  rather than deleted: static serving is a config option, and someone running `streamlit run`
  from another directory will not pick up our config, so trying local first and the CDN second
  means the viewer works if either is available instead of swapping one single point of failure
  for another. `tests/test_viewer.py` runs the fallback for real — denies the page `$3Dmol`,
  lets it request the CDN, then supplies the library the way a late script would and asserts the
  full scene appears — because a fallback that silently fails to draw looks exactly like one
  that was never needed.
- **Provider independence — done.** `lantern/llm.py` adds OpenAI and Anthropic clients beside Argo,
  selected by `LLM_PROVIDER` or in the sidebar, so the project is no longer gated on an
  Argonne-internal host. This closes the "Argo account not provisioned" risk in §8 for the
  narration layer. Two translation hazards were found and are covered by tests: Anthropic has **no
  `system` role**, so the system prompt — the instruction forbidding invented affinities — must be
  hoisted to the top-level `system` parameter or it is silently dropped; and OpenAI reports a
  refusal as `content: null` with a sibling `refusal` field, which reads as an empty response
  unless handled. Each client raises `LLMError` rather than returning a provider's error text as
  prose, matching the Argo guard in §3.4.

**Done when:** the agent completes a campaign end-to-end with an audit log mapping every claim to a
tool call and a source, and degrades to the deterministic pipeline when no provider is reachable.

### M7 — Literature critic (retrieval + LLM judge + frozen policy) — 🟡 retrieval verified live, judge not yet run

Branch `arxiv_rag`. Code: `lantern/scholarbud/` (Crossref/ChemRxiv search, dedup library, BM25; adapted from the ScholarMap project),
`lantern/critic/` (claims, judge with post-check, retrieval, policy, lineage, pipeline), optional hook `discover.answer(critic=...)`.
Docs: `lantern/critic/README.md`. Tests: `tests/test_scholarbud.py`, `tests/test_critic_{policy,judge,pipeline}.py` (offline, scripted judge).

Design: the critic comments on numbers the deterministic pipeline already produced. A confident `contradicts` moves a protein behind
the others and marks it `review`; `supports` only adds a badge; neither changes a number or promotes a candidate. Evidence from
lineage sources (papers the rules came from) counts at alpha = 0.3 of an external source; lineage-only support never badges. The
policy is a pure function of a parameter vector (frozen now; `PARAM_BOUNDS` and `objective` are the hooks for later GP tuning).

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

**Exit criteria for M7:** (1) one full live run on the canonical question with a real judge, table committed; (2) a hand-labelled set of
at least 30 claims with the judge scored against it; (3) lineage list populated; (4) with and without the critic on the two lanmodulin
controls and the known negatives, correct calls unchanged; (5) only then, push.

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
| Argo account not provisioned | No LLM layer | **Closed.** Everything through M5 is LLM-free by design, and M6's narration now runs on Argo, OpenAI or Anthropic (`lantern/llm.py`), so an unprovisioned Argonne account no longer removes the layer. |
| The 188 homologs are near-identical to C5B164 | "Discovery" is trivial | Measure sequence identity spread at M4 entry; if clustered, report it honestly and widen to Corpus C. |
| Lanthanide sites in the PDB are mostly artefacts | M2 yields little signal | This is why M2's curation step is the asset, not the download. |
| The literature critic confirms the rules by construction (same papers) or cites the data under test | Looks like validation, is not | Lineage discount (0.3), PDB depositions excluded, verdicts treated as commentary; measure against a labelled set before relying on it (M7). |
| No judge model reachable from the cluster | M7 untested live | Needs a provider key from a collaborator or the Argonne network; see `Agent_handoff.md`. |

---

## 9. Reproducing the measurements in this document

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                      # 100 passed

# §3.13 Corpus A end to end: download, parse to one table, then measure.
# The parquet is committed, so steps 1-2 are only needed to rebuild it.
.venv/bin/python -I scripts/download_corpus.py     # 636 entries -> .cache/corpus/, 186 MB
.venv/bin/python -I scripts/build_site_table.py    # -> data/lanthanide_sites.parquet, 2795 sites
.venv/bin/python -I scripts/corpus_descriptors.py  # Q0-Q3 tables

# §3.13 the independent check on the parser (needs network)
.venv/bin/python -I scripts/crosscheck_metalpdb.py # 65/65 ions agree with MetalPDB

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

# §4 Corpus A, rebuilt end to end: discovers the ligand codes, then the entries.
# Writes data/ree_pdb_entries.json and refuses to run if RCSB has added a
# rare-earth component that lantern/structure.py does not yet classify.
.venv/bin/python scripts/build_ree_corpus.py          # 27 components -> 636 entries

# §4 the component discovery step on its own -- this is what found the missing Y1
curl -s -X POST https://search.rcsb.org/rcsbsearch/v2/query -H 'Content-Type: application/json' \
  -d '{"query":{"type":"terminal","service":"chemical","parameters":{
       "value":"Y","type":"formula","match_subset":true}},
       "return_type":"mol_definition","request_options":{"return_all_hits":true}}' \
  | python3 -c 'import json,sys; print([h["identifier"] for h in json.load(sys.stdin)["result_set"]])'
                                                      # ['Y1', 'YBT', 'YT3'] -- not just YT3

# §4 entry count for a single ligand code
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

§3.6's 694-sequence validation of the loop pattern — the evidence that the M1 fix generalises
beyond the six demo proteins — is reproduced by `scripts/validate_motif.py`. It scores the
189-member LanM family against 505 reviewed calcium EF-hand proteins under both the canonical and
the structure-derived pattern, and prints sensitivity, specificity and balanced accuracy at the
best threshold for each. Both sets cache under `.cache/`, so reruns are offline.

The same script also prints **§3.8.1's position-9 composition table** — the measurement that shows
Glu-at-9 is a calcium signal rather than a lanthanide one. It reports the composition under two
detectors, the shipped pattern with position 9 freed and a neutral `D.{6}[ILVMFC].{3}E`, because
the headline number (Glu 0.5% vs 13.3%) depends on not letting the biased pattern define the loop
population it is being measured on.

§3.10's detector comparison — the loop-offset derivation, the PROSITE annotation asymmetry, the
per-position composition of 1421 curated calcium loops, and the recall table — is reproduced by
`scripts/loop_detector.py`. It fetches EF-hand domain annotations for both sets (cached under
`.cache/`), re-derives the loop offset from composition on every run and asserts it, and reads the
lanthanide loops off the five cached structures with this repo's own `binding_neighborhood()`
rather than transcribing them. The classifier/instrument separation itself is pinned by
`tests/test_chemistry.py`, which does not need the network.

§3.11's two hallmark tables are reproduced by `scripts/sequence_hallmarks.py`, which reports each
hallmark under both detectors so the classifier's error is visible rather than described. The
parts that can be checked without the network — calmodulin's ~36-residue period, Pro-at-2 on the
coordinate-derived loops — are also pinned in `tests/test_chemistry.py`.

§3.12's burial and net-charge tables are reproduced by `scripts/burial_and_charge.py`, which reads
the five cached structures and needs no network. Every figure in its closing paragraph is computed
on each run rather than transcribed, so the prose cannot drift from the table above it. The negative
result is pinned by `tests/test_structure.py` — charge near-constant across the fold, both families
in the same classes — so that it has to be argued with rather than quietly overturned.

§3.13's corpus measurements run in three steps, each resumable and each writing its own provenance:
`scripts/download_corpus.py` fetches all 636 entries as gzipped mmCIF into `.cache/corpus/` (186 MB,
gitignored, with a sha256 per entry), `scripts/build_site_table.py` parses them into
`data/lanthanide_sites.parquet`, and `scripts/corpus_descriptors.py` prints the Q0–Q3 tables. The
parquet is small enough to commit, so the tables can be re-derived without the 186 MB download.
`scripts/crosscheck_metalpdb.py` is the independent check on the parser and is the one script here
that needs the network; it compares per metal ion rather than per MetalPDB site, since MetalPDB
groups nearby ions into one polymetallic site while this repo emits one site per ion, and it
anchors each ion on its own element and residue number so that site matching never depends on the
distances under test. `tests/test_corpus.py` pins the parts that are pure logic, including the
corpus-wide charge variance that §3.12's explanation predicted.

§3.9's donor-chemistry comparison, including the 9PI2 internal control and the finding that
backbone-carbonyl count carries zero information *within* the EF-hand family, is reproduced by the
structure tests: `.venv/bin/python -m pytest tests/test_structure.py -q`. They run against the five
cached structures and need no network. `scripts/prefetch_structures.py` refreshes that cache.

§3.1's coordination comparison and §3.3's demo-ranking table are reproduced by scoring the real
UniProt sequences and parsing the five cached structures (8FNS, 8FNR, 8DQ2, 9PI2, 1CLL) with the
repo's own `structure.py`, filtered to O/N/S donors within 3.2 Å. Pass `metals=ALL_METAL_CODES` to
include the Ca²⁺ contrast sites — without it `binding_neighborhood()` returns rare earths only, and
9PI2's calcium site disappears.
