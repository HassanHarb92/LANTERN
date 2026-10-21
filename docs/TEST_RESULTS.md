# Test results, tested versions, and confounds found

Independent test pass by A. Sabath, 2026-10-20, on a Duke compute cluster (Linux 5.14, RHEL 9). Everything here was run, not
inferred, unless marked *not verified*. Companion to `ROADMAP.md` section 3.

## 1. Tested versions

| Component | Version |
|---|---|
| LANTERN commit | `b8c229e` ("pre hackathon"); earlier pass on `d73fd28` |
| Python | 3.10.22 (the code needs >= 3.10; 3.7 and 3.9 fail at import on `X \| None` annotations) |
| streamlit | 1.65.0 |
| pandas / numpy / pyarrow | 2.3.3 / 2.2.6 / 25.0.1 |
| biopython | 1.88 |
| requests / python-dotenv | 2.34.2 / 1.2.4 |
| pytest | 9.1.1 |
| UniProt release used for retrieval checks | 2026_03 (2026-09-02) |
| AlphaFold DB models | v6 |

## 2. Results

| Run | Commit | Result |
|---|---|---|
| `pytest -q` | `d73fd28` | 229 passed, 16 skipped, 14.5 s |
| `pytest -q` | `b8c229e` | 713 passed, 16 skipped, 39 s |
| Demo, Reference set, headless (Streamlit `AppTest`) | `d73fd28` | no exceptions, errors or warnings; C5B164 86.7, A0A4V2JDD3 71.1, troponin C 69.0, calmodulin-1 57.0, haemoglobin alpha 23.4, chymotrypsinogen A 19.1 |
| Explorer, 9PI2 | `d73fd28` | opens; views such as "Nd 201 chain A, CN 10" |

The 16 skips are data-presence conditions (site table, shortlist, cached 9PI2 / 1CLL / 8DQ2). A skip means *not checked*.
Not exercised: live database mode, the language-model tab (no credentials), real-browser 3D rendering (`AppTest` runs no JavaScript).

### Roadmap section 3 defects against the tests

| Defect | Status | Evidence |
|---|---|---|
| 3.1 score inverted | fixed | lanmodulins above calcium proteins in the demo; margin 2.1 points is thin |
| 3.2 endocytosis keyword query | fixed | keyword absent from `ALLOWED_QUERIES` |
| 3.3 synthetic default demo | fixed | demo uses six authentic sequences |
| 3.4 Argo auth failure shown as analysis | fixed in tests only | no live Argo credentials |
| 3.5 proximity reported as coordination | fixed | 9PI2 sites report CN 10 |
| 3.6 regex blind to a lanthanide site | fixed | Hans-LanM's three loops scored |
| 3.7 retrieval cannot reach A0A4V2JDD3 | **not fixed in the repo** | topics are still family-label routes; see section 3 below |
| 3.20 live search dropped structures | fixed | `xref_pdb` requested |

Sections 3.8 to 3.19 are measurements, not defects, and were not re-run.

## 3. Additional confounds found

1. **AlphaFold coverage is incomplete.** 80 of 190 LanM-family accessions (the 189 family members plus A0A4V2JDD3) have no
   AlphaFold DB entry (404, confirmed on retry); 110 do. 44 of the 80 have four detectable EF loops. `ROADMAP.md` says every one has a model.
2. **Family-label retrieval is circular.** 109 of the 189 family members pass the design rules, which agrees with the family
   assignment more than it finds anything (see `lantern/discover.py`). A generic EF-hand query (UniProt `xref:interpro-IPR011992`,
   length < 200, 165,902 sequences) recovers A0A4V2JDD3 and C5B164 without any family term.
3. **The loose spacing rule is not selective on its own.** Over those 165,902 sequences: 4 loops and at least one gap < 14 gives 2,266 hits
   (mostly other EF-hand families); every gap 12-13 gives 156, of which 49 lie outside the NF053806 family and are unvalidated candidates.
4. **The 696 sequences in Mattocks et al. 2023 are homology-seeded.** Methods: PSI-BLAST from Mex-LanM against nr and env_nr (3,047
   sequences), curated to < 200 aa, four EF hands, at least one pair separated by < 14 residues. UniProt alone cannot reproduce that count.
5. **The calcium-rejection rule rests on spacing alone, at n = 6** (`ROADMAP.md` 3.8): calmodulin and troponin C pass the other two rules.
6. **Site counts disagree.** `ROADMAP.md` says 2,795 sites (asymmetric unit); README and a separate results report say 3,375
   (3,116 rare-earth, 259 calcium) after assembly-1 re-parsing. The parquet itself was *not verified*.
7. **Predicted structures are apo.** Neither AlphaFold DB nor ESMFold models contain the metal, so loop geometry is hypothetical.
8. **ESMFold pLDDT is not on AlphaFold's scale.** On 12 test sequences ESMFold loop pLDDT was 89-93 throughout, up to about 15 points above
   AlphaFold DB where the latter was lowest; the AlphaFold gate threshold must not be reused. Loop RMSD to the crystal structures was
   comparable (A0A4V2JDD3 vs 8DQ2: 0.92 vs 0.96 A; C5B164 vs 8FNS: 0.42 vs 0.60 A).
9. **The three-loop family members (80) are untreated** by the strict four-loop criterion; the loop detector's recall is imperfect, so some may be real.
10. **Environment:** the default `python3` in many HPC setups is < 3.10; pytest writes to `/tmp` by default (set `--basetemp`).
11. **An external results report (REE-Finder) disagrees with the roadmap** on: MetalPDB validation (report: not rechecked; roadmap: 65 of 65
    ions agree), the geometric queue (report: 54 leads in 23 entries; roadmap: 38 flagged entries), and whether AlphaFold lookups were done.
    Not resolved.
12. **The sequence score is ion-independent.** Changing the target-ion dropdown cannot change the sequence score; ion identity enters only
    at the structure step (`lantern/ions.py`).
