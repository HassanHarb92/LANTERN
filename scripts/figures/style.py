"""Shared style for the publication figures. Physical sizes in inches, fonts in pt.
Every panel is a function draw_X(ax) in scripts/figures/panels/; build_figure1.py / build_figure2.py call each function twice
(standalone panel file, and into the composite figure). One look everywhere: DejaVu Sans, white background, this palette. No titles, no figure-level notes: panel letters only; explanations go in captions."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# dataviz reference palette (light). Ln = blue, Ca = orange, third = aqua; neutrals for context.
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
VIOLET, RED = "#6250d6", "#e34948"
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8b8a85", "#e6e5e1", "#fcfcfb"
NEUTRAL, NEUTRAL_LIGHT = "#b9b8b2", "#ecebe6"
FULL_W = 7.0      # double-column width, inches
COL_W = 3.4       # single-column width, inches
FONT = "DejaVu Sans"
FS, FS_SMALL, FS_TICK = 7.5, 6.5, 6.5   # base, annotations, tick labels (pt)
LW = 1.0

def apply():
    plt.rcParams.update({
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "font.family": FONT, "font.size": FS, "text.color": INK, "axes.labelcolor": INK2,
        "axes.labelsize": FS, "xtick.labelsize": FS_TICK, "ytick.labelsize": FS_TICK,
        "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": MUTED, "axes.linewidth": 0.7,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
        "legend.frameon": False, "legend.fontsize": FS_SMALL, "lines.linewidth": LW,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
        "svg.fonttype": "none", "pdf.fonttype": 42, "savefig.dpi": 300,
    })

def panel_letter(ax, letter, dx=-0.02, dy=1.02):
    ax.text(dx, dy, letter, transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom", ha="right", color=INK)
