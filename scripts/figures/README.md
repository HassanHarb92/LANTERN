# Publication figures

Everything needed to rebuild Figures 1 and 2 lives in the repo; nothing outside it is read.

## Build
    pip install -r requirements-figures.txt
    python scripts/figures/build_figure2.py [--out DIR]   # default docs/figures/paper/fig2
    python scripts/figures/build_figure1.py [--out DIR]   # default docs/figures/paper/fig1
(`LANTERN_FIG_OUT` may replace `--out`.) Each writes every panel alone (`panels/`) and the composite, as SVG and 300-dpi PNG.
`pytest tests/test_figures.py` builds both into a temp directory.

## Inputs (all in the repo)
- `data/lanthanide_sites.parquet`, `data/calcium_sites.parquet`, `data/paired_sites.csv`: panels 2B, 2C, 2D
- `data/reference_proteins.json` + `lantern.chemistry.score_sequence`: panel 2A ("after fix" is computed; "before fix" values are constants quoted from ROADMAP.md 3.1)
- `data/figures/retrieval_hits.json`: panel 2E (EF-hand retrieval hits, `in_family` flag)
- `data/figures/controls_plddt.json`: panel 2F (sequence and per-residue pLDDT of the two lanmodulin controls)
- `data/figures/corpusb_coverage.json`: corpus B counts (190 accessions, 110 with an AlphaFold model, by 4 vs 3 loops); used in the paper text, not drawn
- `docs/figures/paper/screens/ui_shortlist.png`, `ui_explorer.png`: Figure 1D/E (images; the build stops with a clear message if missing)

## Data vs schematic
Figure 2 panels are data. Figure 1A/B are diagrams whose numbers are typed text (counts from the pipeline); 1C is a labelled
schematic, not data; 1D/E are UI screenshots.

## Regenerating data and screenshots (optional, needs external assets)
- `prepare_figure_data.py [--assets DIR]` rebuilds `data/figures/*.json` from the asset tree (default `$LANTERN_ASSETS`, else the default documented in the script).
- `capture_ui.py --out SCRATCH_DIR [--repo R] [--port 8790] [--stage 1|2|both] [--publish]` starts `streamlit run app.py` with the light theme (no LLM credentials needed), injects CSS (DejaVu Sans, white background, narrowed layout), captures the real UI with Playwright (swiftshader WebGL, mouse-wheel zoom of the viewer, `Viewer background` radio Light/Dark) and composes the 1D/E panels (3.4 x 1.9 in at 600 dpi, composites of real crops). Raw captures go to `--out` (keep it outside the repo); `--publish` copies `ui_shortlist.png` and `ui_explorer.png` into `docs/figures/paper/screens/`. Needs `playwright` + chromium and the DejaVu Sans font. Emoji glyphs render as tofu in headless chromium, so those columns are cropped out, never edited.

## Style
`style.py` is the single source: DejaVu Sans, white background, fixed palette (Ln blue, Ca orange). Panels are functions `draw_X(ax)`; no titles, panel letters only.
