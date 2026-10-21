"""Build Figure 1 (overview): panels saved alone, then the composite. A flow, B harness, C caricature (schematic), D/E UI screenshots.
D/E are composites of real UI crops (made by capture_ui.py), images read from docs/figures/paper/screens/ui_shortlist.png and ui_explorer.png (made by capture_ui.py); the build
fails with a clear message if they are missing.
Usage: python scripts/figures/build_figure1.py [--out DIR] [--screens DIR]    (or env LANTERN_FIG_OUT)
Outputs: DIR/panels/*.{png,svg}, DIR/Figure1.{png,svg}; DIR defaults to docs/figures/paper/fig1."""
import sys, os, pathlib, argparse
HERE = pathlib.Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "panels"))
import matplotlib.pyplot as plt, matplotlib.image as mpimg
import style; style.apply()
from draw_flow import draw_flow, draw_flow_detailed; from draw_harness import draw_harness; from draw_caricature import draw_caricature
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=os.environ.get("LANTERN_FIG_OUT") or str(REPO / "docs/figures/paper/fig1"))
ap.add_argument("--screens", default=str(REPO / "docs/figures/paper/screens"))
args = ap.parse_args()
OUT = pathlib.Path(args.out); (OUT / "panels").mkdir(parents=True, exist_ok=True); SCREENS = pathlib.Path(args.screens)

def draw_shot(name):
    def f(ax):
        p = SCREENS / name
        if not p.exists():
            raise SystemExit(f"missing UI screenshot {p}; run scripts/figures/capture_ui.py (or restore docs/figures/paper/screens/)")
        ax.imshow(mpimg.imread(p), aspect="auto", interpolation="lanczos")
        ax.set_axis_on(); ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values(): sp.set_visible(True); sp.set_edgecolor(style.NEUTRAL); sp.set_linewidth(.6)
    return f

W, H = 7.0, 6.59   # H grew by 0.39 in when D/E went from 3.25x1.45 to 3.3x1.84 in (legible UI text); A/B/C unchanged, only shifted up
# layout in inches: (left, bottom, width, height) measured from the figure bottom-left
L = {"A": (0.20, 4.65, 6.80, 1.80), "B": (0.20, 2.00, 3.45, 2.50),
     "C": (4.20, 2.12, 2.30, 2.30), "D": (0.20, 0.00, 3.30, 1.84), "E": (3.70, 0.00, 3.30, 1.84)}
FN = {"A": draw_flow, "B": draw_harness, "C": draw_caricature, "D": draw_shot("ui_shortlist.png"), "E": draw_shot("ui_explorer.png")}
NAME = {"A": "flow", "B": "harness", "C": "caricature", "D": "ui_shortlist", "E": "ui_explorer"}
LET = {"A": (-.002, 1.0), "B": (-.002, 1.0), "C": (-.0, 1.02), "D": (-.0, 1.02), "E": (-.0, 1.02)}
for k, (x, y, w, h) in L.items():
    fig = plt.figure(figsize=(w + .25, h + .22)); ax = fig.add_axes([.2 / (w + .25), .04 / (h + .22), w / (w + .25), h / (h + .22)])
    FN[k](ax); style.panel_letter(ax, k, dx=-.015, dy=0.995)
    for ext in ("png", "svg"): fig.savefig(OUT / "panels" / f"Fig1{k}_{NAME[k]}.{ext}")
    plt.close(fig)
# the original, text-heavy panel A is kept as an alternative
_w, _h = L["A"][2], L["A"][3]
_f = plt.figure(figsize=(_w + .25, _h + .22)); _ax = _f.add_axes([.2 / (_w + .25), .04 / (_h + .22), _w / (_w + .25), _h / (_h + .22)])
draw_flow_detailed(_ax); style.panel_letter(_ax, "A", dx=-.015, dy=0.995)
for ext in ("png", "svg"): _f.savefig(OUT / "panels" / f"Fig1A_flow_detailed.{ext}")
plt.close(_f)
fig = plt.figure(figsize=(W, H))
for k, (x, y, w, h) in L.items():
    ax = fig.add_axes([x / W, y / H, w / W, h / H]); FN[k](ax)
    style.panel_letter(ax, k, dx=-.015, dy=0.995)
for ext in ("png", "svg"): fig.savefig(OUT / f"Figure1.{ext}")
print("wrote", OUT)
