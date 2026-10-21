"""Schematic caricature of LANTERN's final result (not data)."""
import sys, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import style
from matplotlib.patches import Polygon, Circle, FancyBboxPatch, FancyArrowPatch

OXY = "#f4a58a"


def _blob(cx, cy, R, tilt_deg):
    """Rounded protein blob with a small cleft notch on top, slightly tilted."""
    t = np.linspace(0, 2 * np.pi, 240, endpoint=False)
    r = R * (1 + 0.07 * np.sin(3 * t + 0.6) + 0.04 * np.cos(2 * t))
    r = r - 0.30 * R * np.exp(-((t - np.pi / 2) / 0.22) ** 2)   # cleft
    a = t + np.deg2rad(tilt_deg)
    return np.c_[cx + r * np.cos(a), cy + r * np.sin(a)]


def _pocket(ax, cx, cy, ion_color, cn, n_pairs, label):
    ax.add_patch(Polygon(_blob(cx, cy, 17.5, 8), closed=True, fc=style.NEUTRAL_LIGHT,
                         ec=style.NEUTRAL, lw=style.LW, joinstyle="round", zorder=1))
    ax.add_patch(Circle((cx, cy), 12.5, fc="white", ec=style.GRID, lw=0.6, zorder=2))
    # donor layout: n_pairs bidentate pairs + singles, spread around the ion
    n_sing = cn - 2 * n_pairs
    n_sites = n_pairs + n_sing
    base = np.deg2rad(90 + 12)
    sites = [base + 2 * np.pi * k / n_sites for k in range(n_sites)]
    rr = 9.3
    for k, ang in enumerate(sites):
        offs = [-0.20, 0.20] if k < n_pairs else [0.0]
        pts = []
        for o in offs:
            px, py = cx + rr * np.cos(ang + o), cy + rr * np.sin(ang + o)
            pts.append((px, py))
            ax.plot([cx, px], [cy, py], color=style.INK2, lw=0.7, zorder=3, solid_capstyle="round")
        if len(pts) == 2:
            ax.plot(*zip(*pts), color=OXY, lw=1.0, zorder=3)
        for px, py in pts:
            ax.add_patch(Circle((px, py), 1.6, fc=OXY, ec="white", lw=0.4, zorder=5))
    ax.add_patch(Circle((cx, cy), 3.8, fc=ion_color, ec="white", lw=0.6, zorder=6))
    return label


def draw_caricature(ax):
    ax.set_axis_off()
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("equal")

    _pocket(ax, 24, 73, style.BLUE, 9, 3, None)
    ax.text(24, 95.5, r"Ln$^{3+}$ CN 9", ha="center", va="center", fontsize=style.FS_SMALL,
            color=style.BLUE, fontweight="bold")
    _pocket(ax, 24, 29, style.ORANGE, 7, 2, None)
    ax.text(24, 51.5, r"Ca$^{2+}$ CN 7", ha="center", va="center", fontsize=style.FS_SMALL,
            color=style.ORANGE, fontweight="bold")

    # arrow pocket pair -> card
    ax.add_patch(FancyArrowPatch((43, 51), (55, 51), arrowstyle="-|>", mutation_scale=7,
                                 lw=0.8, color=style.INK2, zorder=4, shrinkA=0, shrinkB=0))

    # ranked shortlist card
    x0, x1, y0, y1 = 56, 98.5, 12, 86
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=3",
                                fc="white", ec=style.NEUTRAL, lw=style.LW, zorder=1))
    rows = [("candidate 1", 34, "measured site", style.NEUTRAL_LIGHT, style.INK2, style.MUTED),
            ("candidate 2", 26, "sequence lead", "#c9efe1", "#0c6a4a", style.AQUA),
            ("candidate 3", 18, "no structure", style.GRID, style.MUTED, style.NEUTRAL)]
    rh = 22.5
    for i, (lab, blen, chip, cf, ct, ce) in enumerate(rows):
        top = y1 - 3 - i * rh
        ax.text(x0 + 4, top - 2.6, lab, ha="left", va="center", fontsize=style.FS_SMALL, color=style.INK)
        ax.add_patch(FancyBboxPatch((x0 + 4, top - 10.5), blen, 3.8, boxstyle="round,pad=0,rounding_size=1.9",
                                    fc=style.BLUE if i == 0 else style.NEUTRAL, ec="none", zorder=2,
                                    alpha=1.0 if i == 0 else 0.8))
        cw = 35
        ax.add_patch(FancyBboxPatch((x0 + 4, top - 18.2), cw, 5.6, boxstyle="round,pad=0,rounding_size=2.8",
                                    fc=cf, ec=ce, lw=0.6, zorder=2))
        ax.text(x0 + 4 + cw / 2, top - 15.4, chip, ha="center", va="center", fontsize=style.FS_SMALL - 0.0,
                color=ct, zorder=3)
    # dashed outline around top row
    ax.add_patch(FancyBboxPatch((x0 + 1.5, y1 - 22.2), x1 - x0 - 3, 20.0,
                                boxstyle="round,pad=0,rounding_size=2.5", fc="none",
                                ec=style.INK, lw=0.9, ls=(0, (3, 2)), zorder=4))
    ax.text((x0 + x1) / 2, 94, "experiment next", ha="center", va="center", fontsize=style.FS_SMALL,
            color=style.INK, style="italic")
    ax.plot([(x0 + x1) / 2, (x0 + x1) / 2], [91, y1 + 0.3], color=style.INK, lw=0.6, zorder=4)

    ax.text(78.5, 5.5, "ranked shortlist", ha="center", va="center", fontsize=style.FS_SMALL, color=style.INK2)
    ax.text(50, -1.5, "schematic, not data", ha="center", va="center", fontsize=style.FS_SMALL,
            color=style.MUTED, style="italic")


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    style.apply()
    fig = plt.figure(figsize=(2.3, 2.3))
    ax = fig.add_axes([0.02, 0.04, 0.96, 0.94])
    draw_caricature(ax)
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "caricature_test")
    fig.savefig(str(out) + ".png", dpi=300)
    fig.savefig(str(out) + ".svg")
