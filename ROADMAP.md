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

- **636** PDB entries in the entire world contain a rare-earth ion. Not 636,000. You can download
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

> **Still not validated at scale, unlike position 9.** The loop finder has deliberately poor recall
> on calcium EF-hands — 1 of calmodulin's 4 — which is a *feature* for position-9 discrimination
> (§3.6) but a *problem* for spacing, because you cannot measure the period between loops you did
> not find. The n=6 result above and the published hallmark are what support spacing; measuring it
> against calcium proteins needs a balanced-recall detector that does not yet exist. **Spacing stays
> out of the score until then.** Position 9 did not need it: it is carried by the existing pattern
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
pinned: 82 tests, no xfail, five structures cached (8FNS, 8FNR, 8DQ2, 9PI2, 1CLL), both lanthanide
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

- Download mmCIF for all 636, parse with `MMCIFParser`, extract every rare-earth site with full
  first-shell geometry. (Do not re-derive the list by hand; rerun `scripts/build_ree_corpus.py`, which enumerates the
  codes from RCSB — see §4.) Use
  BinaryCIF (`models.rcsb.org/{ID}.bcif`) for the bulk pull — much smaller than mmCIF over 636
  entries — and never the legacy `.pdb` endpoint, which 404s on large structures (§3.5).
- Compute per site: CN, protein-O/N/S donor counts, water count, bidentate carboxylate count,
  mean and spread of Ln–O distance, residue composition, B-factors/occupancy, solvent exposure.
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
  survivors: bidentate carboxylate count, carboxylate O count, Glu/Asp split. Burial and net charge
  are the two not yet implemented, and the Dudev rule (buried, −3/−4 ⇒ Ln-selective) is the
  published form to implement.
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
.venv/bin/python -m pytest -q                      # 73 passed

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
# rare-earth component that reefinder/structure.py does not yet classify.
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

§3.9's donor-chemistry comparison, including the 9PI2 internal control and the finding that
backbone-carbonyl count carries zero information *within* the EF-hand family, is reproduced by the
structure tests: `.venv/bin/python -m pytest tests/test_structure.py -q`. They run against the five
cached structures and need no network. `scripts/prefetch_structures.py` refreshes that cache.

§3.1's coordination comparison and §3.3's demo-ranking table are reproduced by scoring the real
UniProt sequences and parsing the five cached structures (8FNS, 8FNR, 8DQ2, 9PI2, 1CLL) with the
repo's own `structure.py`, filtered to O/N/S donors within 3.2 Å. Pass `metals=ALL_METAL_CODES` to
include the Ca²⁺ contrast sites — without it `binding_neighborhood()` returns rare earths only, and
9PI2's calcium site disappears.
