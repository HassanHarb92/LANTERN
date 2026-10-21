"""Build Figure 2 (results): each panel saved alone, then the composite. PNG (300 dpi) and SVG for all.
Reads only repo files (data/*.parquet, data/paired_sites.csv, data/reference_proteins.json, data/figures/*.json, lantern.chemistry).
Usage: python scripts/figures/build_figure2.py [--out DIR]    (or env LANTERN_FIG_OUT)
Outputs: DIR/panels/*.{png,svg} and DIR/Figure2.{png,svg}; DIR defaults to docs/figures/paper/fig2."""
import sys, os, pathlib, argparse
HERE = pathlib.Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "panels"))
import matplotlib.pyplot as plt
import style; style.apply()
from draw_results import *
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=os.environ.get("LANTERN_FIG_OUT") or str(REPO / "docs/figures/paper/fig2"))
OUT = pathlib.Path(ap.parse_args().out); (OUT / "panels").mkdir(parents=True, exist_ok=True)
PANELS = [("A", "ranking", draw_ranking), ("B", "composition", draw_composition), ("C", "cn_distribution", draw_cn),
          ("D", "paired_sites", draw_pairs), ("E", "retrieval", draw_retrieval), ("F", "alphafold", draw_alphafold)]
W, H = 7.0, 4.15
# standalone panels at the size each occupies in the composite
for letter, name, fn in PANELS:
    fig, ax = plt.subplots(figsize=(W / 3 - .1, H / 2 - .15))
    fn(ax); style.panel_letter(ax, letter, dx=-.16)
    fig.subplots_adjust(left=.24, right=.97, bottom=.2, top=.9)
    for ext in ("png", "svg"): fig.savefig(OUT / "panels" / f"Fig2{letter}_{name}.{ext}")
    plt.close(fig)
fig = plt.figure(figsize=(W, H))
gs = fig.add_gridspec(2, 3, left=.13, right=.985, bottom=.095, top=.945, wspace=.5, hspace=.52)
for k, (letter, name, fn) in enumerate(PANELS):
    ax = fig.add_subplot(gs[k // 3, k % 3]); fn(ax); style.panel_letter(ax, letter, dx=-.2)
for ext in ("png", "svg"): fig.savefig(OUT / f"Figure2.{ext}")
print("wrote", OUT)
