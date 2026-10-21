"""Figure 2 panels (results). Each draw_* function draws into the Axes it is given; no titles, no notes.
Data are read from repo files at first use (data/*.parquet, data/paired_sites.csv, data/reference_proteins.json,
data/figures/*.json; regenerate the latter with scripts/figures/prepare_figure_data.py). The 'before fix' scores in panel A are
hard-coded constants (quoted from ROADMAP.md s3.1, as the caption says); 'after fix' is computed live with lantern.chemistry."""
import sys, json, pathlib, functools
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
import style
from style import *

REPO = pathlib.Path(__file__).resolve().parents[3]
FIGDATA = REPO / "data/figures"
if str(REPO) not in sys.path: sys.path.insert(0, str(REPO))


@functools.lru_cache(None)
def tables():
    ln = pd.read_parquet(REPO / "data/lanthanide_sites.parquet"); ca = pd.read_parquet(REPO / "data/calcium_sites.parquet")
    q = lambda d: d[(d.resolution_A <= 2.5) & (~d.chelator_flagged)]
    rare = ln[ln.family == "lanthanide"]
    nat = q(rare[rare.class_first_pass == "natural_ln_biology"])
    return rare, nat, q(ca), pd.read_csv(REPO / "data/paired_sites.csv")


def _yg(ax):
    ax.yaxis.grid(True, color=GRID, lw=0.5); ax.set_axisbelow(True); ax.tick_params(length=2)


# ------------------------------------------------------------------ A  score before / after the fix
def draw_ranking(ax):
    from lantern.chemistry import score_sequence
    from lantern.models import Protein
    refs = json.load(open(REPO / "data/reference_proteins.json"))["proteins"]
    after = {r["accession"]: score_sequence(Protein(accession=r["accession"], name=r["name"], organism=r["organism"],
                                                    sequence=r["sequence"])).score for r in refs}
    before = {"C5B164": 74.7, "P02585": 69.0, "P0DP23": 57.0, "A0A4V2JDD3": 35.1, "P69905": 23.4, "P00766": 19.1}
    role = {"C5B164": BLUE, "A0A4V2JDD3": BLUE, "P02585": ORANGE, "P0DP23": ORANGE, "P69905": NEUTRAL, "P00766": NEUTRAL}
    name = {"C5B164": "Mex-LanM", "A0A4V2JDD3": "Hans-LanM", "P02585": "Troponin C", "P0DP23": "Calmodulin",
            "P69905": "Hemoglobin α", "P00766": "Chymotrypsin"}
    order = sorted(after, key=lambda a: after[a])
    for i, a in enumerate(order):
        c = role[a]
        ax.plot([before[a], after[a]], [i, i], color=c, lw=1.6, alpha=.4, zorder=1)
        ax.scatter(before[a], i, s=18, facecolor="white", edgecolor=c, lw=1.0, zorder=3)
        ax.scatter(after[a], i, s=22, color=c, zorder=4)
        ax.text(after[a] + 2.5, i, f"{after[a]:.1f}", va="center", fontsize=FS_SMALL, color=INK)
    ax.set_yticks(range(len(order)), [name[a] for a in order]); ax.set_xlim(0, 100); ax.set_ylim(-.6, len(order) - .4)
    ax.set_xlabel("Sequence score (0–100)"); ax.xaxis.grid(True, color=GRID, lw=0.5); ax.set_axisbelow(True)
    ax.scatter([], [], s=18, facecolor="white", edgecolor=INK2, lw=1, label="before fix")
    ax.scatter([], [], s=22, color=INK2, label="after fix")
    ax.legend(loc="lower right", handletextpad=.2, borderaxespad=.2)


# ------------------------------------------------------------------ B  corpus composition by class
def draw_composition(ax):
    rare, nat, caq, pairs = tables()
    cls = {"natural_ln_biology": "Natural biology", "phasing_artefact": "Phasing/soak", "engineered_lbt": "Engineered tag"}
    rare = rare.assign(c=rare.class_first_pass.map(cls).fillna("Other curated"))
    rare.loc[rare.class_first_pass == "unclassified", "c"] = "Unclassified"
    cats = ["Natural biology", "Phasing/soak", "Engineered tag", "Other curated", "Unclassified"]
    cols = [BLUE, ORANGE, AQUA, YELLOW, NEUTRAL]
    tab = rare.groupby(["element", "c"]).size().unstack(fill_value=0).reindex(columns=cats, fill_value=0)
    tab = tab.loc[tab.sum(axis=1).sort_values().index]
    tab = tab.iloc[-9:]
    left = np.zeros(len(tab))
    for c_, col in zip(cats, cols):
        ax.barh(range(len(tab)), tab[c_], left=left, color=col, edgecolor="white", linewidth=.8, height=.78, label=c_)
        left += tab[c_].values
    ax.set_yticks(range(len(tab)), tab.index); ax.set_xlabel("Rare-earth sites (top 9 elements)")
    ax.xaxis.grid(True, color=GRID, lw=.5); ax.set_axisbelow(True)
    ax.legend(loc="lower right", handlelength=.9, handletextpad=.3, labelspacing=.25, borderaxespad=.1)


# ------------------------------------------------------------------ C  CN distribution
def draw_cn(ax):
    rare, nat, caq, pairs = tables()
    v = np.arange(0, 11)
    fl = np.array([(nat.coordination_number.round() == k).mean() for k in v]) * 100
    fc = np.array([(caq.coordination_number.round() == k).mean() for k in v]) * 100
    w = .4
    ax.bar(v - w / 2, fc, width=w, color=ORANGE, edgecolor="white", linewidth=.6, label=f"Ca (n = {len(caq)})")
    ax.bar(v + w / 2, fl, width=w, color=BLUE, edgecolor="white", linewidth=.6, label=f"Natural Ln (n = {len(nat)})")
    ax.axvline(8.5, color=INK2, lw=.8, ls=(0, (3, 2)))
    ax.set_xticks(v); ax.set_xlabel("First-shell coordination number"); ax.set_ylabel("% of sites"); _yg(ax)
    ax.set_ylim(0, 56); ax.legend(loc="upper left", handlelength=.9, handletextpad=.3, borderaxespad=.1)
    ax.text(8.6, 52, "CN ≥ 9", fontsize=FS_SMALL, color=INK2, va="top")


# ------------------------------------------------------------------ D  paired sites
def draw_pairs(ax):
    rare, nat, caq, pr = tables()
    for _, r in pr.iterrows():
        ax.plot([0, 1], [r.coordination_number_ln, r.coordination_number_ca], color=INK2, lw=.8, alpha=.4)
    ax.scatter(np.zeros(len(pr)), pr.coordination_number_ln, s=14, color=BLUE, zorder=3, edgecolor="white", lw=.4)
    ax.scatter(np.ones(len(pr)), pr.coordination_number_ca, s=14, color=ORANGE, zorder=3, edgecolor="white", lw=.4)
    ax.set_xticks([0, 1], ["Ln in site", "Ca in same site"]); ax.set_xlim(-.35, 1.35)
    ax.set_ylabel("Coordination number"); _yg(ax)
    ax.set_ylim(3.6, 10); ax.text(.5, 9.6, "n = 19, median Δ = 0", ha="center", fontsize=FS_SMALL, color=INK2)


# ------------------------------------------------------------------ E  retrieval by loop spacing
def draw_retrieval(ax):
    hits = json.load(open(FIGDATA / "retrieval_hits.json"))
    rng = np.random.default_rng(7)
    groups = [("wider spacing", [h for h in hits if not h["strict"]], NEUTRAL, 3, .5),
              ("strict, in family", [h for h in hits if h["strict"] and h["in_family"]], BLUE, 9, .9),
              ("strict, outside family", [h for h in hits if h["strict"] and not h["in_family"]], ORANGE, 11, .95)]
    for nm, hs, col, s, al in groups:
        ax.scatter([min(max(h["gaps"]), 40) + rng.uniform(-.3, .3) for h in hs], [h["pro2"] + rng.uniform(-.13, .13) for h in hs],
                   s=s, color=col, alpha=al, edgecolor="white", lw=.3, label=f"{nm} ({len(hs)})", zorder=3)
    ax.axvspan(11.6, 13.6, color=BLUE, alpha=.08, zorder=0)
    ax.set_xlim(11, 41); ax.set_ylim(-.4, 4.6); ax.set_yticks(range(5)); _yg(ax)
    ax.set_xlabel("Largest gap between EF loops (residues)"); ax.set_ylabel("Loops with Pro at position 2")
    ax.legend(loc="upper right", handletextpad=.1, borderaxespad=.1, markerscale=1)


# ------------------------------------------------------------------ F  AlphaFold confidence + coverage
def draw_alphafold(ax):
    import re
    from lantern.chemistry import EF_LOOP_INSTRUMENT, LOOP_LENGTH
    ctrl = json.load(open(FIGDATA / "controls_plddt.json"))
    def loops(seq):
        st = []
        for m in re.finditer("(?=(%s))" % EF_LOOP_INSTRUMENT.pattern, seq):
            if not st or m.start() - st[-1] >= LOOP_LENGTH: st.append(m.start())
        return st
    for st0 in loops(ctrl["C5B164"]["sequence"]):
        ax.axvspan(st0 + 1, st0 + LOOP_LENGTH, color=ORANGE, alpha=.18, lw=0)
    for acc, col, nm in (("C5B164", BLUE, "Mex-LanM"), ("A0A4V2JDD3", VIOLET, "Hans-LanM")):
        pl = ctrl[acc]["plddt"]; ax.plot(range(1, len(pl) + 1), pl, color=col, lw=1.0, label=f"{nm} (mean {np.mean(pl):.0f})")
    ax.set_ylim(20, 105); ax.set_xlim(1, 133); ax.set_xlabel("Residue"); ax.set_ylabel("pLDDT"); _yg(ax)
    ax.legend(loc="lower right", handlelength=1.2, borderaxespad=.1)
