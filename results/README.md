# Results

Every question this platform can be asked, answered offline and written out so it can be read, checked and diffed without running anything.

`runs/` is the **run archive**. Every question answered in the app is saved there automatically and can be reopened from its *Saved runs* page -- the proteins the design rules selected, the structures that were measured, and the 3D view of each metal site. The runs listed below are the fifteen seeded by `scripts/export_results.py` so the page is not empty in a fresh clone; anything asked in the app joins them.

**Generated. Do not edit by hand** -- rerun the script. Each run's JSON is the artifact to cite; this table is only its headline.

- code: `e968f1a` on `rag_dev`
- geometry: `geometry-v2`
- generated: 2026-10-21T21:31:21Z

## What each column means

| column | meaning |
| --- | --- |
| **Structure shown** | the deposited entry on the page that holds the ion asked about, if any |
| **How** | why that structure is there -- the design rules reached it, or an element lookup did |
| **Sites** | measured metal sites holding that element, in the structure(s) named beside them |
| **Res / Protein** | of the sharpest structure shown |

All 15 share the same 2 of 6 design-rule candidates: the rules are sequence rules and fire identically for every trivalent lanthanide. That column is therefore not a result about the ion, and is left out below. Only the structure columns differ.

## Answers

| Ion | Structure shown | How | Sites | Res (Å) | Protein |
| --- | --- | --- | --- | --- | --- |
| **La3+** | 8DQ2 | in the screened corpus | 12 | 1.8 | Lanmodulin (Hansschlegelia quercus) |
| **Ce3+** | 4MAE | found by element lookup, not a candidate | 2 | 1.6 | Methanol dehydrogenase from Methylacidiphilum fumariol |
| **Pr3+** | 3MVC | found by element lookup, not a candidate | 4 | 1.4 | High resolution crystal structure of the heme domain o |
| **Nd3+** | 8FNS | in the screened corpus | 4 | 1.01 | Lanmodulin |
| **Pm3+** | -- | nothing holding it is deposited | 0 |  |  |
| **Sm3+** | 1UZP | found by element lookup, not a candidate | 3 | 1.78 | Integrin binding cbEGF22-TB4-cbEGF33 fragment of human |
| **Eu3+** | 6FKW | found by element lookup, not a candidate | 4 | 1.4 | Europium-containing methanol dehydrogenase |
| **Gd3+** | 9VY9 | found by element lookup, not a candidate | 27 | 1.41 | Structure of MIF binding with Gadolinium ions |
| **Tb3+** | 6Y0E | found by element lookup, not a candidate | 2 | 1.5 | Nbe LBM |
| **Dy3+** | 8FNR | in the screened corpus | 14 | 1.4 | Lanmodulin (Hansschlegelia quercus) |
| **Ho3+** | -- | all 16 deposited entries measured, none is a protein site | 0 |  |  |
| **Er3+** | -- | all 6 deposited entries measured, none is a protein site | 0 |  |  |
| **Tm3+** | -- | nothing holding it is deposited | 0 |  |  |
| **Yb3+** | 9VY4 | found by element lookup, not a candidate | 10 | 1.21 | Structure of MIF binding with Ytterbium ions |
| **Lu3+** | 5F8A | found by element lookup, not a candidate | 2 | 1.76 | Crystal structure of the ternary EcoRV-DNA-Lu complex  |

11 of 15 show a deposited structure holding the ion asked about. The rest say which kind of nothing they are: an element with no deposited structure anywhere is a different answer from one whose every deposited entry was measured and turned out to be a soaked chelate the protein never coordinates.

## Reproducing

```sh
.venv/bin/python scripts/export_results.py --check
```

`--check` re-answers every seeded question in memory and fails if the result differs from what is archived here. It needs no network: the answers read bundled data and the cached coordinates under `data/structures/`. A difference means the platform's claims changed, and the diff says how.

A seeded run whose measurements have not changed is left on disk untouched, timestamps included, so rerunning the script on unchanged code produces no diff at all.
