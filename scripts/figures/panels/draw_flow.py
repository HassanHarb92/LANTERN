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
        "Verify and present": ("#dce9fa", BLUE), "Critique": ("#f8e4f0", "#c2478f")}


def draw_flow(ax):
    """Panel A: short labels, thick coloured boxes; colour = the kind of action the stage performs.
    Six columns. The literature critic follows Verify and feeds the shortlist; it comments, it never scores."""
    ax.set_xlim(-1, 101); ax.set_ylim(10, 100); ax.set_axis_off()
    W, G, H = 14.2, 3.0, 22
    xs = [i * (W + G) for i in range(6)]
    yt, yb = 66, 30
    ax.text(0, 99, "structures", fontsize=FS_SMALL, style="italic", color=MUTED, va="top")
    ax.text(0, 60, "sequences", fontsize=FS_SMALL, style="italic", color=MUTED, va="top")
    top = [(0, "PDB", "636 entries", "Acquire"), (1, "Parse", "3,375 sites", "Process"), (2, "Curate", "62 entries", "Process"),
           (3, "Descriptor", "CN \u2265 9", "Select"), (4, "Verify", "measured", "Verify and present"),
           (5, "Critic", "literature flags", "Critique")]
    bot = [(0, "UniProt", "165,902 seqs", "Acquire"), (1, "Spacing rule", "EF loops", "Select"), (2, "Candidates", "156 hits", "Select"),
           (4, "Structures", "PDB, AlphaFold", "Verify and present"), (5, "Shortlist + UI", "cards, 3D viewer", "Verify and present")]
    for row, y in ((top, yt), (bot, yb)):
        for c, t, b, cat in row:
            fc, ec = CATS[cat]
            box(ax, xs[c], y, W, H, t, b, ASPECT, fc=fc, ec=ec, lw=2.4, tsize=FS + .5, bsize=FS_SMALL + .1)
    ym_t, ym_b = yt + H / 2 - 5, yb + H / 2 - 5
    for i in (0, 1, 2, 3, 4):                       # top row, left to right
        arrow(ax, (xs[i] + W, ym_t), (xs[i + 1], ym_t), lw=1.3, scale=8)
    for a, b in ((0, 1), (1, 2), (2, 4), (4, 5)):   # bottom row; Candidates -> Structures spans the empty column
        arrow(ax, (xs[a] + W, ym_b), (xs[b], ym_b), lw=1.3, scale=8)
    arrow(ax, (xs[4] + W / 2, yb + H), (xs[4] + W / 2, yt), lw=1.3, scale=8)    # structures feed Verify
    arrow(ax, (xs[5] + W / 2, yt), (xs[5] + W / 2, yb + H), lw=1.3, scale=8)    # critic -> shortlist
    x = 0.0   # legend, one swatch per category, along the bottom
    for name, (fc, ec) in CATS.items():
        ax.add_patch(plt.Rectangle((x, 14.5), 3.2, 7.5, fc=fc, ec=ec, lw=1.8, zorder=2))
        ax.text(x + 4.6, 18.25, name, fontsize=FS_SMALL, va="center", color=INK2)
        x += 4.6 + 1.05 * len(name) * 0.95 + 5.5
