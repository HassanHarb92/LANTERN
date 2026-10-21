"""Small drawing helpers shared by the diagram panels. Data coords 0..100 on both axes; `aspect` = (inches per y-unit)/(inches per x-unit)
keeps rounded corners circular on anisotropic axes."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from style import *


def _units(ax):
    """inches per x-unit and per y-unit for an Axes drawn in 0..100 data coords"""
    fw, fh = ax.figure.get_size_inches(); pos = ax.get_position()
    return fw * pos.width / 100.0, fh * pos.height / 100.0


def box(ax, x, y, w, h, title, body="", aspect=None, fc="white", ec=INK2, dashed=False, tcolor=INK, lw=0.8, tsize=None, bsize=None,
        align="center", pad_in=0.04):
    xin, yin = _units(ax)
    asp = yin / xin
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.6", mutation_aspect=asp,
                                fc=fc, ec=ec, lw=lw, ls=(0, (3, 2)) if dashed else "-", zorder=2))
    cx = x + w / 2 if align == "center" else x + 1.8
    ha = "center" if align == "center" else "left"
    ts = tsize or FS
    top = y + h - pad_in / yin
    ax.text(cx, top, title, ha=ha, va="top", fontsize=ts, fontweight="bold", color=tcolor, zorder=3)
    if body:
        ax.text(cx, top - (ts / 72.0 * 1.35) / yin, body, ha=ha, va="top", fontsize=bsize or FS_SMALL - .3,
                color=INK2, zorder=3, linespacing=1.25)


def arrow(ax, p0, p1, color=INK2, dashed=False, lw=0.9, style="-|>", conn="arc3", scale=6, zorder=1):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=scale, lw=lw, color=color, zorder=zorder,
                                 ls=(0, (3, 2)) if dashed else "-", connectionstyle=conn, shrinkA=0, shrinkB=0))


def line(ax, pts, color=INK2, lw=0.9, dashed=False, zorder=1):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=color, lw=lw, ls=(0, (3, 2)) if dashed else "-", solid_capstyle="butt", zorder=zorder)
