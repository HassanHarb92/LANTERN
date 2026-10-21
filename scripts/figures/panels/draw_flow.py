"""Figure 1, panel A: data-processing flow. Axes ~7.0 x 2.5 in, data coords 0..100 x 0..100."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _shapes import *

ASPECT = (2.5 / 100) / (7.0 / 100)

def draw_flow(ax):
    ax.set_xlim(-1, 101); ax.set_ylim(0, 100); ax.set_axis_off()
    W, G = 17.6, 3.0
    xs = [i * (W + G) for i in range(5)]
    H = 31
    yt, yb = 63, 12
    BL = "#e8f0fb"   # light blue tint for the evidence-bearing stages
    ax.text(0, 98.5, "structure evidence", fontsize=FS_SMALL, style="italic", color=MUTED, va="top")
    ax.text(0, 49.0, "sequence evidence", fontsize=FS_SMALL, style="italic", color=MUTED, va="top")
    top = [("RCSB PDB", "636 entries with bare\nrare-earth ions\n(Gd, Yb, Tb, … Nd, Dy)"),
           ("Parse sites", "first-shell O/N/S ≤ 3.2 Å\nassembly-aware\n3,375 site records"),
           ("Curate", "62 entries read by hand\n4 natural families;\nartefact classes"),
           ("Descriptor", "coordination number ≥ 9\nrefuses chelated or\nlow-resolution sites")]
    bot = [("UniProt / InterPro", "165,902 EF-hand\nsequences, < 200 aa\nno family label used"),
           ("Retrieve by spacing", "4 EF loops, adjacent\ngaps 12–13 residues\n(EF_LOOP_INSTRUMENT)"),
           ("Candidates", "156 strict hits\n107 in family, 49 outside\nboth controls recovered"),
           ("Structures", "PDB (measured)\nAlphaFold DB (retrieved)\nESMFold: planned")]
    for i, (t, b) in enumerate(top):
        box(ax, xs[i], yt, W, H, t, b, ASPECT)
    for i, (t, b) in enumerate(bot):
        box(ax, xs[i], yb, W, H, t, b, ASPECT, dashed=False)
    box(ax, xs[4], yt, W, H, "Verify", "coordination measured\non a structure; models\nlabelled hypothetical", ASPECT, fc=BL, ec=BLUE, lw=1.2, tcolor=BLUE)
    box(ax, xs[4], yb, W, H, "Shortlist + UI", "evidence cards in a\nquestion box, Explorer\nand 3D site viewer", ASPECT, fc=BL, ec=BLUE, lw=1.2, tcolor=BLUE)
    ym_t, ym_b = yt + H / 2 - 4, yb + H / 2 - 4
    for i in range(3):
        arrow(ax, (xs[i] + W, ym_t), (xs[i + 1], ym_t)); arrow(ax, (xs[i] + W, ym_b), (xs[i + 1], ym_b))
    arrow(ax, (xs[3] + W, ym_t), (xs[4], ym_t))
    # structures also feed Verify, through a small bus in the gap
    bx = xs[3] + W + G / 2
    line(ax, [(xs[3] + W, ym_b + 6), (bx, ym_b + 6), (bx, ym_t)])
    arrow(ax, (xs[4] + W / 2, yt), (xs[4] + W / 2, yb + H))
