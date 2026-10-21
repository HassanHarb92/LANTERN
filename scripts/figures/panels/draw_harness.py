"""Figure 1, panel B: agentic harness, the models it can use and the literature critic. Axes ~3.45 x 2.5 in, data coords 0..100 x 0..100."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _shapes import *

ASPECT = (2.5 / 100) / (3.45 / 100)
CRIT_FC, CRIT_EC = "#f8e4f0", "#c2478f"


def _row(ax, x, yy, w, text, dashed=False):
    ax.add_patch(FancyBboxPatch((x, yy - 3.0), w, 6.2, boxstyle="round,pad=0,rounding_size=1.4", mutation_aspect=ASPECT,
                                fc="white" if dashed else NEUTRAL_LIGHT, ec=MUTED if dashed else NEUTRAL, lw=0.7, zorder=2,
                                ls=(0, (3, 2)) if dashed else "-"))
    ax.text(x + w / 2, yy + .2, text, ha="center", va="center", fontsize=FS_SMALL - .4, color=MUTED if dashed else INK, zorder=3)


def draw_harness(ax):
    ax.set_xlim(-1, 101); ax.set_ylim(-1, 101); ax.set_axis_off()
    BL = "#e8f0fb"
    # left column: the harness, top to bottom
    box(ax, 0, 89, 44, 11, "Typed question", "", ASPECT, tsize=FS - .5, pad_in=.03)
    ax.text(22, 91.1, "“proteins for capturing Ce³⁺”", fontsize=FS_SMALL - .6, color=INK2, ha="center", va="center", style="italic", zorder=3)
    box(ax, 0, 66, 44, 18, "plan.py", "intent only, allow-listed;\nelse deterministic parser", ASPECT, bsize=FS_SMALL - .5)
    box(ax, 0, 43, 44, 18, "discover.py", "rules → verify on structure\n→ record every number", ASPECT, fc=BL, ec=BLUE, lw=1.3, tcolor=BLUE, bsize=FS_SMALL - .5)
    box(ax, 0, 19, 44, 19, "critic", "retrieve → judge → policy\nflags only, never scores", ASPECT, fc=CRIT_FC, ec=CRIT_EC, lw=1.3, tcolor=CRIT_EC, bsize=FS_SMALL - .5)
    box(ax, 0, 0, 44, 13, "Planned", "tool-selecting planner", ASPECT, dashed=True, tcolor=MUTED, tsize=FS - .6, bsize=FS_SMALL - .6)
    for y0, y1 in ((89, 84), (66, 61), (43, 38)):
        arrow(ax, (22, y0), (22, y1))
    # right column, aligned with the stage that uses it
    box(ax, 54, 64, 46, 36, "Language models", "", ASPECT, tsize=FS - .5)
    for k, nm in enumerate(("Argo gateway (ANL)", "OpenAI (API)", "Anthropic (API)")):
        _row(ax, 57, 87.5 - k * 7.4, 40, nm)
    ax.text(77, 66.8, "parse, judge, narrate; never score", fontsize=FS_SMALL - .6, color=INK2, ha="center", style="italic", zorder=3)
    box(ax, 54, 30, 46, 31, "Structure sources", "", ASPECT, tsize=FS - .5)
    for k, (nm, dsh) in enumerate((("PDB (measured)", False), ("AlphaFold DB (retrieved)", False), ("ESMFold (planned)", True))):
        _row(ax, 57, 51 - k * 7.4, 40, nm, dsh)
    box(ax, 54, 0, 46, 27, "Literature", "", ASPECT, tsize=FS - .5, ec=CRIT_EC, lw=1.0)
    for k, nm in enumerate(("Crossref (abstracts)", "ChemRxiv (preprints)")):
        _row(ax, 57, 16.5 - k * 7.4, 40, nm)
    ax.text(77, 2.6, "abstract-level evidence only", fontsize=FS_SMALL - .6, color=INK2, ha="center", style="italic", zorder=3)
    arrow(ax, (44, 75), (54, 80), dashed=True, style="<|-|>")      # plan.py <-> LLM (intent)
    arrow(ax, (44, 52), (54, 47))                                    # discover -> structure sources
    arrow(ax, (44, 29), (54, 15), color=CRIT_EC)                     # critic -> literature
