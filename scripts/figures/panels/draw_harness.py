"""Figure 1, panel B: agentic harness and the models it can use. Axes ~3.45 x 2.5 in, data coords 0..100 x 0..100."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _shapes import *

ASPECT = (2.5 / 100) / (3.45 / 100)

def draw_harness(ax):
    ax.set_xlim(-1, 101); ax.set_ylim(-1, 101); ax.set_axis_off()
    BL = "#e8f0fb"
    box(ax, 0, 87, 44, 13, "Typed question", "", ASPECT, tsize=FS - .5, pad_in=.03)
    ax.text(22, 89.6, "“proteins for capturing Ce³⁺”", fontsize=FS_SMALL - .4, color=INK2, ha="center", va="center", style="italic", zorder=3)
    box(ax, 0, 52, 44, 30, "plan.py", "LLM extracts intent only\nchecked against allow-lists\nand the question text;\nelse deterministic parser", ASPECT)
    box(ax, 0, 24, 44, 24, "discover.py", "select by stated rules\n→ verify on structure\n→ record every number", ASPECT, fc=BL, ec=BLUE, lw=1.1, tcolor=BLUE)
    box(ax, 0, 0, 44, 18, "Planned", "tool-selecting planner,\n≤ 8 steps, audit log", ASPECT, dashed=True, tcolor=MUTED, tsize=FS - .5)
    arrow(ax, (22, 87), (22, 82)); arrow(ax, (22, 52), (22, 48))
    # language models
    box(ax, 54, 58, 46, 40, "Language models", "", ASPECT, tsize=FS - .5)
    for k, (nm, sub) in enumerate((("Argo gateway", "ANL"), ("OpenAI", "API"), ("Anthropic", "API"))):
        yy = 84 - k * 8.6
        ax.add_patch(FancyBboxPatch((57, yy - 3.2), 40, 7.0, boxstyle="round,pad=0,rounding_size=1.4", mutation_aspect=ASPECT,
                                    fc=NEUTRAL_LIGHT, ec=NEUTRAL, lw=0.6, zorder=2))
        ax.text(77, yy + .3, f"{nm}  ({sub})", ha="center", va="center", fontsize=FS_SMALL - .3, color=INK, zorder=3)
    ax.text(77, 60.4, "parse and narrate only", fontsize=FS_SMALL - .5, color=INK2, ha="center", style="italic", zorder=3)
    # structure sources
    box(ax, 54, 14, 46, 38, "Structure sources", "", ASPECT, tsize=FS - .5)
    for k, (nm, sub, dsh) in enumerate((("PDB", "measured", False), ("AlphaFold DB", "retrieved", False), ("ESMFold", "planned", True))):
        yy = 35 - k * 8.6
        ax.add_patch(FancyBboxPatch((57, yy - 3.2), 40, 7.0, boxstyle="round,pad=0,rounding_size=1.4", mutation_aspect=ASPECT,
                                    fc="white" if dsh else NEUTRAL_LIGHT, ec=MUTED if dsh else NEUTRAL, lw=0.7, zorder=2,
                                    ls=(0, (3, 2)) if dsh else "-"))
        ax.text(77, yy + .3, f"{nm}  ({sub})", ha="center", va="center", fontsize=FS_SMALL - .3, color=MUTED if dsh else INK, zorder=3)
    arrow(ax, (44, 68), (54, 80), dashed=True, style="<|-|>")          # plan.py <-> LLM (intent)
    arrow(ax, (44, 34), (54, 34))                                          # discover -> structure sources
    arrow(ax, (44, 44), (54, 61), dashed=True)      # record -> LLM narration
