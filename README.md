# 🧬 REE-Finder

**An Argo-powered, evidence-aware prototype for exploring naturally occurring rare-earth-binding proteins.**

This is a *prototype*, not a validated discovery pipeline. It includes a working web UI, synthetic offline demo, live sequence retrieval from UniProt and InterPro, deterministic exploratory sequence scores, a structure viewer, first-shell coordination analysis of deposited rare-earth sites, and Argo-based explanations. **It does not yet compute a calibrated selectivity descriptor, experimentally grounded metal selectivity, or autonomous multi-tool planning.** See `ROADMAP.md` for the measured state of the code and the path to those.

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
ARGO_USER=your_anl_domain_username
ARGO_MODEL=Claude Sonnet 5
```

`ARGO_USER` is an **ANL domain username, not a secret API key** — Argo authenticates a username.
(`ARGO_API_KEY`, the former name, is still read as a fallback.) Use a model name exactly as Argo
lists it: `curl -s https://apps.inside.anl.gov/argoapi/v1/models`. **Do not commit `.env`.** The app
sends only a bounded summary of screening results.

Argo reports a rejected credential as **HTTP 200 with a normal-looking chat completion** whose body
is an access-denied notice. The client detects this (blocked completion id, or zero billed tokens)
and raises instead of displaying it as analysis. The sidebar badge additionally checks that the
gateway answers and that `ARGO_MODEL` exists; note it cannot validate the username, since the model
list is served unauthenticated. Argo's host is an Argonne-internal name, so access may depend on
your network. Endpoints and models can change.

Start live discovery by selecting **Live database** in the sidebar. Available families:

| Topic | Route | Notes |
|---|---|---|
| `lanmodulin` | UniProt `protein_name` | The single reviewed entry, C5B164 |
| `calmodulin` | UniProt `protein_name` | Reviewed calcium comparators |
| `lanm-family` | InterPro NCBIfam NF053806 → UniProt | The 189-member lanmodulin family, 188 uncharacterized |

> **Known retrieval gap.** Neither route reaches `A0A4V2JDD3`, the *H. quercus* lanmodulin, even
> though its Dy³⁺ and La³⁺ complexes are in the PDB. It carries no lanmodulin family annotation —
> only generic EF-hand terms identical to calmodulin's — so family-label retrieval cannot see it.
> ROADMAP.md §3.7; this blocks the M4 screen and is tracked there.

`lanm-family` is a two-step retrieval because UniProt records **no** NCBIfam cross-reference for
lanmodulins — `xref:ncbifam-NF053806` returns zero hits. Membership comes from InterPro; sequences
are then fetched from UniProt by accession.

A former `ef-hand` option mapped to keyword KW-0254, which is the keyword for **Endocytosis**. It
returned 755 irrelevant proteins and has been withdrawn: no UniProt keyword denotes the EF-hand
domain.

## Project layout

```text
REE-Finder/
├── app.py                        # Streamlit user experience
├── reefinder/
│   ├── __init__.py
│   ├── models.py                 # Typed data records
│   ├── chemistry.py              # Unvalidated transparent sequence heuristic
│   ├── catalog.py                # Loads the authentic reference set and the test fixtures
│   ├── uniprot.py                # UniProt search + InterPro family retrieval
│   ├── structure.py              # Structure fetch + first-shell coordination analysis
│   ├── argo.py                   # Argo chat client, fails closed on rejected credentials
│   └── agent.py                  # Fixed retrieve-then-score pipeline (not a planner)
├── scripts/
│   ├── build_reference_data.py   # Rebuild the reference set from UniProt
│   ├── build_ree_corpus.py       # Rebuild Corpus A; discovers ligand codes, never guesses them
│   ├── prefetch_structures.py    # Cache 8FNS/8FNR/8DQ2/9PI2/1CLL for an offline demo
│   ├── analyze_motifs.py         # Reproduce the ROADMAP §3.6 / §3.8 findings
│   └── validate_motif.py         # Validate the loop pattern on 694 sequences, not six
├── data/reference_proteins.json  # 6 authentic UniProt sequences, checksummed
├── data/synthetic_examples.json  # Synthetic fixtures, used only by tests
├── data/structures/              # Prefetched coordinates + manifest
├── data/ree_pdb_entries.json     # All 636 rare-earth PDB entries, uncurated
├── tests/                        # Offline regression tests (73, no network)
├── docs/SCIENTIFIC_CONTRACT.md   # Scientific claims and evidence gates
├── ROADMAP.md                    # Verified state, defects, milestones M0-M6
├── IMPLEMENTATION_PLAN.md        # Earlier aspirational plan, superseded in part
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

- Offline screening over **six authentic UniProt sequences** (two lanmodulins, two calcium proteins,
  two true negatives), each carrying an accession, a SHA-256 checksum and a retrieval date. Rebuild
  with `python scripts/build_reference_data.py`. Synthetic records are kept in a separate file used
  only by tests.
- **Offline structure demo.** `python scripts/prefetch_structures.py` caches 8FNS, 8FNR, 8DQ2,
  9PI2 and 1CLL under `data/structures/`; `fetch_structure()` reads the cache before the network.
  9PI2 is the key one: Nd³⁺ and Ca²⁺ in a single 0.99 Å crystal.
- Live retrieval for three families, including the full lanmodulin family via InterPro.
- Sequence acid fraction and limited EF-hand-like motif hints.
- Transparent, deterministic score (not metal-specific and not selectivity).
- Interactive result table, workflow trace, downloadable JSON.
- Structure retrieval with automatic mmCIF fallback (RCSB publishes no legacy `.pdb` for large
  entries such as 6EK0, 7K00, 3J3Q); pinned 3Dmol.js viewer, which still needs CDN connectivity.
- **First-shell coordination analysis** of *experimentally deposited* rare-earth ions: O/N/S donors
  within 3.2 Å, waters included and labelled, reported as coordination number with a protein/water
  split. Verified against 8FNS (4 Nd sites, CN 9–10), 8FNR (Dy), 8DQ2 (La) and 9PI2 (Nd + Ca).
- **Donor-chemistry classification** per site — carboxylate, backbone carbonyl, side-chain amide,
  hydroxyl and water oxygens, with bidentate/monodentate and Glu/Asp splits. Bidentate carboxylate
  count separates lanthanide from calcium EF-hand sites; backbone carbonyl count does not (above).
- Argo text explanations constrained to screening output, with rejected credentials failing closed.

## Measured baseline

Coordination descriptors computed by this repo on real structures:

| Structure | Ion | CN | Protein donors | Waters | Bidentate carboxylates |
|---|---|---:|---:|---:|---:|
| 8DQ2 lanmodulin | La³⁺ (×12) | 10 | 10 | 0 | 4 |
| 8FNS lanmodulin | Nd³⁺ (×3) | 9 | 7 | 2 | 2 |
| 8FNS lanmodulin | Nd³⁺ (site 204) | 10 | 8 | 2 | 3 |
| 8FNR lanmodulin | Dy³⁺ (biological) | 9 | 9 | 0 | 3 |
| 1CLL calmodulin | Ca²⁺ (×4) | 7 | 6 | 1 | 1 |

This is the discriminating signal: biological lanthanide sites sit at CN 9–10, calcium sites at
CN 7. **Acidic-residue content, which the sequence score measures, is identical between them** —
which is why the score is labelled triage-only throughout the UI.

Sharper still, inside a single structure. All four Dy³⁺ sites of 8FNR chain A:

| Site | Donor residues | CN | Waters |
|---|---|---:|---:|
| EF1 | 34, 36, 38, 40, 42, 45 | **9** | 0 |
| EF2 | 58, 60, 62, 64, 66, 69 | **9** | 0 |
| EF3 | 83, 85, 87, 89, 91, 94 | **9** | 0 |
| EF4 | 107, 109, 111, 113, 118 | **7** | 1 |

One protein, one metal, one crystal — and coordination number still separates the three genuine
lanthanide sites from the one that behaves like a calcium site.

**Sharpest of all: 9PI2**, *A. lacus* lanmodulin at 0.99 Å, which resolves Nd³⁺ **and** Ca²⁺ in the
same crystal — the cleanest internal control this project could ask for, since every variable
except the ion is held fixed:

| Chain A site | Ion | CN | Protein donors | Waters | Bidentate carboxylates |
|---|---|---:|---:|---:|---:|
| 201, 202, 203 | **Nd³⁺** | **10** | 10 | **0** | **4** |
| 204 | **Ca²⁺** | **7** | 6 | **1** | **1** |

One crystal, one protein, two ions, and the split is total. The 0.99 Å resolution means this is
measured, not modelled.

> **A negative result worth more than the positives.** Across all **42** metal sites in the five
> cached structures — three lanthanide elements and calcium, CN 4 to 10 — the backbone-carbonyl
> donor count is **exactly 1, every time**. In a PDB-wide survey, carboxylate-vs-backbone-carbonyl
> ratio is the single strongest Ln/Ca discriminator (p = 1.6×10⁻⁴¹). *Inside the EF-hand family it
> carries zero information*, because the loop grammar fixes position 7 as a backbone carbonyl
> regardless of which ion binds. Features for M3 must be selected against calcium **EF-hand**
> proteins, not against all calcium sites, or they will encode the fold and not the ion.
> ROADMAP.md §3.9.

### The sequence score used to invert. It no longer does.

Until 2026-10-19 this section reported a defect: *Lanmodulin, H. quercus* (A0A4V2JDD3) — a
structurally confirmed Dy³⁺ binder — scored **zero** EF-hand motifs and ranked **below both calcium
proteins**, at 35.1. The ranking is pinned by test precisely so that fixing it would be a visible
event rather than a quiet one. Here is the event.

| Protein | Role | Score | Motifs | |
|---|---|---:|---:|---|
| Lanmodulin, *M. extorquens* (C5B164) | **lanthanide binder** | 86.7 | 4 | ↑ from 74.7 / 3 |
| Lanmodulin, *H. quercus* (A0A4V2JDD3) | **lanthanide binder** | **71.1** | **3** | ↑ from 35.1 / 0 |
| Troponin C, human (P02585) | calcium protein | 69.0 | 2 | — |
| Calmodulin-1, human (P0DP23) | calcium protein | 57.0 | 1 | — |
| Haemoglobin α (P69905) | true negative | 23.4 | 0 | — |
| Chymotrypsinogen A (P00766) | true negative | 19.1 | 0 | — |

The cause of the inversion was that the EF-hand regex encoded the **calcium** consensus: it demanded
Asp at loop position 1 and Gly at position 6. Reading resolved coordinates in 8FNR, 8DQ2 and 9PI2
shows both demands are wrong for lanthanide loops — Asn Oδ1 at position 1 is a genuine first-shell
donor, and Gly at 6 is a backbone-flexibility requirement of the 7-coordinate *calcium* geometry,
not a donor at all. Relaxing exactly those two positions makes the three Dy³⁺ loops visible.

**The fix is not a tuning exercise, and three things keep it honest:**

1. **The discriminating constraint was inherited, not added.** Position 9's `[DE]` was already in
   the calcium consensus and was left untouched. It turns out to be the position doing the work —
   Glu at 9 is a bidentate first-shell ligand that expels water, Asp at 9 works second-sphere.
2. **It was validated before it shipped, on 694 sequences, not six.** Against 505 reviewed calcium
   EF-hand proteins, sensitivity for the 189-member lanmodulin family rises **91.0% → 96.8%** while
   specificity holds at ~91% (balanced accuracy 91.0% → 93.9%), and the share of family members
   scoring zero motifs falls from 1.1% to **0.0%**. Reproduce: `python scripts/validate_motif.py`.
3. **It still discriminates.** A0A4V2JDD3 scores **3** motifs, not 4 — the pattern finds its three
   genuine lanthanide loops and correctly skips EF4, which is CN 7 with a bound water and behaves
   like a calcium site. Calmodulin, with four EF-hands, still scores 1.

**What this does *not* mean.** A0A4V2JDD3 clears troponin C by **2.1 points on a 100-point scale** —
one motif's worth of nothing. The ordering is now right; the margin is not evidence of a calibrated
descriptor, and `test_the_separation_is_thin_and_the_test_says_so` pins it as thin on purpose. A
motif count is a triage filter, not an affinity. M3 remains open. Full analysis in ROADMAP.md
§3.6–§3.9.

## What remains for a credible discovery claim

- ~~Verified real positive/negative reference sequences~~ — done; see *Measured baseline*.
- ~~A motif descriptor derived from lanthanide structures rather than a calcium consensus~~ —
  done, and validated on 694 sequences; see *The sequence score used to invert*. It is a triage
  filter, not a calibrated descriptor, so M3 remains open.
- Retrieval that does not depend on family labels (still blocks the headline screen — see the
  known retrieval gap above).
- Experimental protein–metal binding constants. Note the ceiling: matched-condition Kd values for
  both a lanthanide **and** Ca²⁺ on the same construct exist for only **four** proteins, so this is
  a validation set, never a training set.
- PDB↔UniProt residue mapping and accessible metal-site detection for structures without deposited ions.
- A curated corpus of all 636 rare-earth PDB entries, classified by site provenance.
- A calibrated geometric descriptor replacing the sequence heuristic for ranking.
- Sequence homology and redundancy controls; hold-out evaluation.
- A planner with bounded dynamic tool selection, provenance and source citation aggregation.
- Robust security, UI and automated integration tests.

**Read `ROADMAP.md`** for the verified state of the code, the nine defects found by measurement,
the three finite corpora the project actually spans, and milestones M0–M6. `IMPLEMENTATION_PLAN.md`
is the earlier aspirational plan, retained for reference; `ROADMAP.md` §7 lists which parts of it
evidence has since contradicted.
