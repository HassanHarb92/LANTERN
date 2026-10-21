"""Figure 1, panel A: data-processing flow. Axes ~7.0 x 2.5 in, data coords 0..100 x 0..100."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _shapes import *

ASPECT = (2.5 / 100) / (7.0 / 100)

def draw_flow_detailed(ax):
    """The original, text-heavy version (kept; saved as Fig1A_flow_detailed)."""
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


# Rough category of action -> (tinted fill, saturated border). Chosen to avoid orange (= Ca elsewhere in the figures).
CATS = {"Acquire": ("#dff3ec", AQUA), "Process": ("#e9e5fa", VIOLET), "Select": ("#fbf0d3", YELLOW),
        "Verify and present": ("#dce9fa", BLUE)}


def draw_flow(ax):
    """Panel A, simplified: short labels, thick coloured boxes; colour = the kind of action the stage performs."""
    ax.set_xlim(-1, 101); ax.set_ylim(0, 100); ax.set_axis_off()
    W, G, H = 17.6, 3.0, 22
    xs = [i * (W + G) for i in range(5)]
    yt, yb = 66, 30
    ax.text(0, 99, "structures", fontsize=FS_SMALL, style="italic", color=MUTED, va="top")
    ax.text(0, 60, "sequences", fontsize=FS_SMALL, style="italic", color=MUTED, va="top")
    top = [("PDB", "636 entries", "Acquire"), ("Parse", "3,375 sites", "Process"), ("Curate", "62 by hand", "Process"),
           ("Descriptor", "CN \u2265 9", "Select"), ("Verify", "measured", "Verify and present")]
    bot = [("UniProt", "165,902 seqs", "Acquire"), ("Spacing rule", "EF loops", "Select"), ("Candidates", "156 hits", "Select"),
           ("Structures", "PDB, AlphaFold", "Verify and present"), ("Shortlist + UI", "cards, 3D viewer", "Verify and present")]
    for row, y in ((top, yt), (bot, yb)):
        for i, (t, b, cat) in enumerate(row):
            fc, ec = CATS[cat]
            box(ax, xs[i], y, W, H, t, b, ASPECT, fc=fc, ec=ec, lw=2.4, tsize=FS + 1.2, bsize=FS_SMALL + .4)
    ym_t, ym_b = yt + H / 2 - 5, yb + H / 2 - 5
    for i in range(4):
        arrow(ax, (xs[i] + W, ym_t), (xs[i + 1], ym_t), lw=1.3, scale=8)
        arrow(ax, (xs[i] + W, ym_b), (xs[i + 1], ym_b), lw=1.3, scale=8)
    bx = xs[3] + W + G / 2   # structures also feed Verify, through a bus in the gap
    line(ax, [(xs[3] + W, ym_b + 5), (bx, ym_b + 5), (bx, ym_t)], lw=1.3)
    arrow(ax, (xs[4] + W / 2, yt), (xs[4] + W / 2, yb + H), lw=1.3, scale=8)
    # legend: one swatch per category, along the bottom
    x = 0.0
    for name, (fc, ec) in CATS.items():
        ax.add_patch(plt.Rectangle((x, 5), 3.2, 8, fc=fc, ec=ec, lw=1.8, zorder=2))
        ax.text(x + 4.6, 9, name, fontsize=FS_SMALL, va="center", color=INK2)
        x += 4.6 + 1.05 * len(name) * 0.95 + 5.5
