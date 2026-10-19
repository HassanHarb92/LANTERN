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
│   ├── prefetch_structures.py    # Cache 8FNS/8FNR/1CLL for an offline demo
│   └── analyze_motifs.py         # Reproduce the ROADMAP §3.6 / §3.8 findings
├── data/reference_proteins.json  # 6 authentic UniProt sequences, checksummed
├── data/synthetic_examples.json  # Synthetic fixtures, used only by tests
├── data/structures/              # Prefetched coordinates + manifest
├── data/ree_pdb_entries.json     # All 617 rare-earth PDB entries, uncurated
├── tests/                        # Offline regression tests (62, no network)
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
- **Offline structure demo.** `python scripts/prefetch_structures.py` caches 8FNS, 8FNR and 1CLL
  under `data/structures/`; `fetch_structure()` reads the cache before touching the network.
- Live retrieval for three families, including the full lanmodulin family via InterPro.
- Sequence acid fraction and limited EF-hand-like motif hints.
- Transparent, deterministic score (not metal-specific and not selectivity).
- Interactive result table, workflow trace, downloadable JSON.
- Structure retrieval with automatic mmCIF fallback (RCSB publishes no legacy `.pdb` for large
  entries such as 6EK0, 7K00, 3J3Q); pinned 3Dmol.js viewer, which still needs CDN connectivity.
- **First-shell coordination analysis** of *experimentally deposited* rare-earth ions: O/N/S donors
  within 3.2 Å, waters included and labelled, reported as coordination number with a protein/water
  split. Verified against 8FNS (4 Nd sites, CN 9–10) and 8FNR (Dy).
- Argo text explanations constrained to screening output, with rejected credentials failing closed.

## Measured baseline

Coordination descriptors computed by this repo on real structures:

| Structure | Ion | Coordination number | Protein donors | Waters |
|---|---|---:|---:|---:|
| 8FNS lanmodulin | Nd³⁺ (×3) | 9 | 7 | 2 |
| 8FNS lanmodulin | Nd³⁺ (site 204) | 10 | 8 | 2 |
| 8FNR lanmodulin | Dy³⁺ (biological) | 9 | 9 | 0 |
| 1CLL calmodulin | Ca²⁺ (×4) | 7 | 6 | 1 |

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

### The sequence score currently inverts

Scoring the reference set exposes the defect the roadmap's M3 exists to fix:

| Protein | Role | Score | Motifs |
|---|---|---:|---:|
| Lanmodulin, *M. extorquens* (C5B164) | **lanthanide binder** | 74.7 | 3 |
| Troponin C, human (P02585) | calcium protein | 69.0 | 2 |
| Calmodulin, human (P0DP23) | calcium protein | 57.0 | 1 |
| Lanmodulin, *H. quercus* (A0A4V2JDD3) | **lanthanide binder** | **35.1** | **0** |
| Haemoglobin α (P69905) | true negative | 23.4 | 0 |
| Chymotrypsinogen A (P00766) | true negative | 19.1 | 0 |

A structurally confirmed Dy³⁺ binder ranks below both calcium proteins. The cause is specific and
reproducible: the EF-hand regex requires Asp at loop position 1 and Gly at position 6, and all three
of this protein's Dy-binding loops have Asn and a non-Gly — so it scores zero motifs. The same blind
spot hides 16% of all metal-binding loops in the lanmodulin family. Reproduce with
`python scripts/analyze_motifs.py`; full analysis in ROADMAP.md §3.6–§3.8.

**This is published in the README on purpose.** The ranking is pinned by test
(`tests/test_reference_data.py`) so that fixing it is a visible event rather than a quiet one.

## What remains for a credible discovery claim

- ~~Verified real positive/negative reference sequences~~ — done; see *Measured baseline*.
- A motif descriptor derived from lanthanide structures rather than a calcium consensus, and
  retrieval that does not depend on family labels (both block the headline screen).
- Experimental protein–metal binding constants. Note the ceiling: matched-condition Kd values for
  both a lanthanide **and** Ca²⁺ on the same construct exist for only **four** proteins, so this is
  a validation set, never a training set.
- PDB↔UniProt residue mapping and accessible metal-site detection for structures without deposited ions.
- A curated corpus of all 617 rare-earth PDB entries, classified by site provenance.
- A calibrated geometric descriptor replacing the sequence heuristic for ranking.
- Sequence homology and redundancy controls; hold-out evaluation.
- A planner with bounded dynamic tool selection, provenance and source citation aggregation.
- Robust security, UI and automated integration tests.

**Read `ROADMAP.md`** for the verified state of the code, the five defects found by measurement,
the three finite corpora the project actually spans, and milestones M0–M6. `IMPLEMENTATION_PLAN.md`
is the earlier aspirational plan, retained for reference; `ROADMAP.md` §7 lists which parts of it
evidence has since contradicted.
