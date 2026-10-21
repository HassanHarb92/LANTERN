"""Talk figures F1-F5, F7, F8 for LANTERN (slide-scale versions of the paper's Figure 2 data; F6 is a 3D view, F9 a slide).

Reads ONLY files inside the repo: data/*.parquet, data/paired_sites.csv, data/reference_proteins.json and
data/figures/{retrieval_hits,controls_plddt,corpusb_coverage}.json (same loading approach as panels/draw_results.py).
Quoted, not recomputed (as in the original talk script):
  - F1 "before fix" scores: ROADMAP.md s3.1 (before the s3.6 fix); "after" is computed with lantern.chemistry.
  - F5 left panel (LanD asymmetric unit vs assembly counts): ROADMAP.md s3.17.
Everything else is computed from repo data. F8 coverage counts come from data/figures/corpusb_coverage.json and the pLDDT
traces/sequences from controls_plddt.json (the original read AlphaFold model files from an external asset tree).
Style: scripts/figures/style.py (DejaVu Sans, white background, shared palette; Ln = blue, Ca = orange) at slide scale
(13 pt base, 15 pt titles). Unlike the paper figures these keep titles and an explanatory footnote.
Outputs: docs/figures/talk/F<n>_<name>.png (200 dpi) and .svg; override with --out DIR.
Run: python scripts/figures/talk/make_talk_figures.py [--out DIR]
"""
import argparse, json, pathlib, re, sys, textwrap
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = pathlib.Path(__file__).resolve().parents[3]
FIGDATA = REPO / "data/figures"
for p in (REPO, REPO / "scripts/figures"):
    if str(p) not in sys.path: sys.path.insert(0, str(p))
import style
from style import BLUE, ORANGE, AQUA, YELLOW, VIOLET, INK, INK2, MUTED, GRID, NEUTRAL
from lantern.chemistry import EF_LOOP_INSTRUMENT, LOOP_LENGTH, score_sequence
from lantern.models import Protein

WHITE = "white"
OUT = REPO / "docs/figures/talk"


def setup():
    style.apply()
    plt.rcParams.update({
        "font.size": 13, "axes.titlesize": 15, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 13, "xtick.labelsize": 13, "ytick.labelsize": 13, "legend.fontsize": 11,
        "axes.edgecolor": GRID, "axes.linewidth": 0.8, "xtick.major.size": 3, "ytick.major.size": 3,
        "lines.linewidth": 1.5,
    })


def finish(fig, name, note=None, manual=False):
    if note:
        wrapped = textwrap.fill(note, width=int(fig.get_figwidth() * 10.5))
        lines = wrapped.count("\n") + 1
        pad = 0.035 + 0.032 * lines * 5.4 / fig.get_figheight()
        if not manual:
            fig.tight_layout(rect=(0, pad, 1, 1))
        fig.text(0.01, 0.012, wrapped, fontsize=10, color=MUTED, ha="left", va="bottom")
    elif not manual:
        fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / f"{name}.png")


def yaxis_grid(ax):
    ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0)


def xaxis_grid(ax):
    ax.xaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0)


def loops(seq):
    st = []
    for m in re.finditer("(?=(%s))" % EF_LOOP_INSTRUMENT.pattern, seq):
        if not st or m.start() - st[-1] >= LOOP_LENGTH: st.append(m.start())
    return st


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="output directory (default docs/figures/talk)")
    args = ap.parse_args()
    if args.out: OUT = pathlib.Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)
    setup()

    ln = pd.read_parquet(REPO / "data/lanthanide_sites.parquet")
    ca = pd.read_parquet(REPO / "data/calcium_sites.parquet")
    ln_rare = ln[ln.family == "lanthanide"]

    # ------------------------------------------------------------ F1 reference ranking before/after the fix
    refs = json.load(open(REPO / "data/reference_proteins.json"))["proteins"]
    after = {r["accession"]: score_sequence(Protein(accession=r["accession"], name=r["name"], organism=r["organism"],
                                                    sequence=r["sequence"])).score for r in refs}
    before = {"C5B164": 74.7, "P02585": 69.0, "P0DP23": 57.0, "A0A4V2JDD3": 35.1, "P69905": 23.4, "P00766": 19.1}
    role = {"C5B164": "L", "A0A4V2JDD3": "L", "P02585": "C", "P0DP23": "C", "P69905": "N", "P00766": "N"}
    label = {"C5B164": "Mex-LanM", "A0A4V2JDD3": "Hans-LanM", "P02585": "Troponin C", "P0DP23": "Calmodulin",
             "P69905": "Haemoglobin α", "P00766": "Chymotrypsinogen A"}
    order = sorted(after, key=lambda a: after[a])
    fig, ax = plt.subplots(figsize=(10, 5.4))
    colour = {"L": BLUE, "C": ORANGE, "N": NEUTRAL}
    for i, a in enumerate(order):
        ax.plot([before[a], after[a]], [i, i], color=colour[role[a]], lw=2, alpha=.45, zorder=1)
        ax.scatter(before[a], i, s=70, facecolor=WHITE, edgecolor=colour[role[a]], lw=2, zorder=3)
        ax.scatter(after[a], i, s=90, color=colour[role[a]], edgecolor=WHITE, lw=2, zorder=4)
        ax.text(after[a] + 2.2, i, f"{after[a]:.1f}", va="center", fontsize=12, color=INK)
        if abs(after[a] - before[a]) > 1:
            ax.text(before[a] - 2.2, i, f"{before[a]:.1f}", va="center", ha="right", fontsize=11, color=INK2)
    ax.set_yticks(range(len(order)), [label[a] for a in order])
    ax.set_xlim(0, 100); ax.set_xlabel("Sequence heuristic score (0–100)"); xaxis_grid(ax)
    ax.set_title("A plausible score ranked a confirmed binder below calcium proteins")
    ax.scatter([], [], s=70, facecolor=WHITE, edgecolor=INK2, lw=2, label="before: calcium-consensus loop pattern")
    ax.scatter([], [], s=90, color=INK2, label="after: pattern re-derived from coordinates")
    ax.scatter([], [], s=60, color=BLUE, label="lanthanide binder")
    ax.scatter([], [], s=60, color=ORANGE, label="calcium protein")
    ax.scatter([], [], s=60, color=NEUTRAL, label="negative control")
    ax.legend(loc="lower right", fontsize=10.5, labelcolor=INK2)
    finish(fig, "F1_reference_ranking",
           "After: computed here from data/reference_proteins.json. Before: quoted from ROADMAP §3.1. "
           "Margin of Hans-LanM over troponin C after the fix is 2.1 points.")

    # ------------------------------------------------------------ F2 corpus composition
    cls = {"natural_ln_biology": "Natural lanthanide biology", "phasing_artefact": "Phasing / soaking artefact",
           "engineered_lbt": "Engineered LBT", "unclassified": "Unclassified"}
    ln_rare = ln_rare.assign(cls=ln_rare.class_first_pass.map(cls).fillna("Other curated"))
    cats = ["Natural lanthanide biology", "Phasing / soaking artefact", "Engineered LBT", "Other curated", "Unclassified"]
    cols = [BLUE, ORANGE, AQUA, YELLOW, NEUTRAL]
    tab = ln_rare.groupby(["element", "cls"]).size().unstack(fill_value=0).reindex(columns=cats, fill_value=0)
    tab = tab.loc[tab.sum(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(10, 6))
    left = np.zeros(len(tab))
    for c_, col in zip(cats, cols):
        ax.barh(range(len(tab)), tab[c_], left=left, color=col, edgecolor=WHITE, linewidth=2, height=.72, label=c_)
        left += tab[c_].values
    for i, tot in enumerate(tab.sum(axis=1)):
        ax.text(tot + 12, i, f"{int(tot)}", va="center", fontsize=11, color=INK2)
    ax.set_yticks(range(len(tab)), tab.index); ax.set_xlabel("Rare-earth sites in the 636 PDB entries"); xaxis_grid(ax)
    nat_pct = 100 * (ln_rare.cls == cats[0]).mean()
    ax.set_title(f"Only {nat_pct:.0f}% of rare-earth sites are curated natural biology; most are unclassified")
    ax.legend(loc="lower right", fontsize=10.5, labelcolor=INK2)
    nat_n = int((ln_rare.cls == cats[0]).sum()); unc_n = int((ln_rare.cls == "Unclassified").sum())
    finish(fig, "F2_corpus_composition",
           f"{len(ln_rare)} rare-earth sites ({nat_n} natural, {unc_n} unclassified); first-pass class + hand curation "
           f"(class_first_pass). Entry-level labels propagate to incidental sites. Y = yttrium; Nd has 22 sites, Dy 40.")

    # ------------------------------------------------------------ F3 CN distribution, natural Ln vs Ca
    q = lambda d: d[(d.resolution_A <= 2.5) & (~d.chelator_flagged)]
    nat = q(ln_rare[ln_rare.class_first_pass == "natural_ln_biology"])
    caq = q(ca)
    cn_vals = np.arange(0, 11)
    fl = np.array([(nat.coordination_number.round() == k).mean() for k in cn_vals]) * 100
    fc = np.array([(caq.coordination_number.round() == k).mean() for k in cn_vals]) * 100
    fig, ax = plt.subplots(figsize=(10, 5.4))
    w = .38
    ax.bar(cn_vals - w / 2 - .02, fc, width=w, color=ORANGE, edgecolor=WHITE, linewidth=2, label=f"Ca²⁺ sites (n = {len(caq)})")
    ax.bar(cn_vals + w / 2 + .02, fl, width=w, color=BLUE, edgecolor=WHITE, linewidth=2, label=f"Natural Ln³⁺ sites (n = {len(nat)})")
    ax.axvline(8.5, color=INK2, lw=1.5, ls=(0, (4, 3)))
    ax.set_ylim(0, 58)
    ax.text(8.62, 56, "CN ≥ 9: threshold chosen\non these data", fontsize=10.5, color=INK2, va="top")
    n_ln9, n_ca9 = int((nat.coordination_number >= 9).sum()), int((caq.coordination_number >= 9).sum())
    ax.set_xticks(cn_vals); ax.set_xlabel("First-shell coordination number (O/N/S within 3.2 Å)")
    ax.set_ylabel("% of sites"); yaxis_grid(ax)
    ax.set_title("Coordination number separates curated Ln sites from Ca sites, in-sample")
    ax.legend(loc="upper left", fontsize=11, labelcolor=INK2)
    finish(fig, "F3_cn_distribution",
           f"CN ≥ 9: {n_ln9}/{len(nat)} Ln sites ({100*n_ln9/len(nat):.1f}%) vs {n_ca9}/{len(caq)} Ca sites "
           f"({100*n_ca9/len(caq):.1f}%). Filters: resolution ≤ 2.5 Å, no chelator flag. Descriptive counts, not "
           f"validated performance; Ca sites are not independent replicates.")

    # ------------------------------------------------------------ F4 paired Ln/Ca sites
    pr = pd.read_csv(REPO / "data/paired_sites.csv")
    fig, ax = plt.subplots(figsize=(6.4, 5.6))
    for _, r in pr.iterrows():
        ax.plot([0, 1], [r.coordination_number_ln, r.coordination_number_ca], color=INK2, lw=1.4, alpha=.45)
    ax.scatter(np.zeros(len(pr)), pr.coordination_number_ln, s=46, color=BLUE, edgecolor=WHITE, lw=1.5, zorder=3)
    ax.scatter(np.ones(len(pr)), pr.coordination_number_ca, s=46, color=ORANGE, edgecolor=WHITE, lw=1.5, zorder=3)
    ax.set_xticks([0, 1], ["Lanthanide\nin the site", "Calcium\nin the same site"])
    ax.set_xlim(-.3, 1.3); ax.set_ylabel("Coordination number"); yaxis_grid(ax)
    med = (pr.coordination_number_ln - pr.coordination_number_ca).median()
    ax.set_title(f"Same site, either ion: median ΔCN = {med:g}", fontsize=14)
    finish(fig, "F4_paired_sites",
           f"{len(pr)} same-site pairs (data/paired_sites.csv). Sign-test p = 1.0 per PDF p5. Half-integers are averages "
           f"over copies. A site seen with each ion shows compatibility, not equal affinity.")

    # ------------------------------------------------------------ F5 artefacts: LanD asymmetric unit vs assembly; chelator flags
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [1.15, 1]})
    desc = ["Coordination\nnumber", "Carboxylate\nresidues", "Bidentate\ncarboxylates"]
    asu, asm = [5, 3, 1], [10, 6, 2]   # quoted from ROADMAP.md s3.17 (LanD, 9C8X)
    x = np.arange(len(desc))
    a1.bar(x - .2, asu, width=.38, color=NEUTRAL, edgecolor=WHITE, linewidth=2, label="Asymmetric unit (half the site)")
    a1.bar(x + .2, asm, width=.38, color=BLUE, edgecolor=WHITE, linewidth=2, label="Biological assembly (homodimer)")
    for xi, (u, m) in enumerate(zip(asu, asm)):
        a1.text(xi - .2, u + .2, str(u), ha="center", fontsize=11, color=INK2)
        a1.text(xi + .2, m + .2, str(m), ha="center", fontsize=11, color=INK)
    a1.set_xticks(x, desc); yaxis_grid(a1); a1.set_ylim(0, 12.5)
    a1.legend(loc="upper right", fontsize=10, labelcolor=INK2)
    a1.set_title("LanD: the deposited coordinates hold half the site", fontsize=13)
    flag = ln_rare.groupby("cls").chelator_flagged.agg(["mean", "size"]).reindex(cats)
    a2.barh(range(len(flag)), flag["mean"] * 100, color=cols, edgecolor=WHITE, linewidth=2, height=.7)
    for i, (m_, n_) in enumerate(zip(flag["mean"], flag["size"])):
        a2.text(m_ * 100 + 1, i, f"{m_*100:.0f}%  (n={n_})", va="center", fontsize=10.5, color=INK2)
    a2.set_yticks(range(len(flag)), [c_.replace(" / ", " /\n") for c_ in flag.index]); a2.invert_yaxis()
    a2.set_xlabel("% of sites, chelator-dominated shell"); a2.set_xlim(0, 100); xaxis_grid(a2)
    a2.set_title("Chelator contamination by class", fontsize=13)
    n_asm = int((ln.coordinate_source == "assembly1").sum())
    finish(fig, "F5_artefacts",
           f"Left: quoted from ROADMAP §3.17. Right: computed from lanthanide_sites.parquet "
           f"({n_asm} of {len(ln)} sites re-parsed from assembly 1). Flagged sites are kept, not dropped.")

    # ------------------------------------------------------------ F7 loop spacing vs Pro at position 2
    hits = json.load(open(FIGDATA / "retrieval_hits.json"))
    rng = np.random.default_rng(7)
    fig, ax = plt.subplots(figsize=(10, 5.6))
    groups = [("4 loops, wider spacing (rule too loose)", [h for h in hits if not h["strict"]], NEUTRAL, 18, .5),
              ("Strict hit, in LanM family set", [h for h in hits if h["strict"] and h["in_family"]], BLUE, 46, .85),
              ("Strict hit, outside family set", [h for h in hits if h["strict"] and not h["in_family"]], ORANGE, 62, .95)]
    for name, hs, col, s, al in groups:
        xs = [min(max(h["gaps"]), 40) + rng.uniform(-.25, .25) for h in hs]
        ys = [h["pro2"] + rng.uniform(-.14, .14) for h in hs]
        ax.scatter(xs, ys, s=s, color=col, alpha=al, edgecolor=WHITE, lw=1, label=f"{name} (n = {len(hs)})", zorder=3)
    for acc, nm, dy in (("C5B164", "Mex-LanM", -.55), ("A0A4V2JDD3", "Hans-LanM", -.7)):
        h = next(h for h in hits if h["acc"] == acc)
        ax.annotate(nm, (max(h["gaps"]), h["pro2"]), xytext=(max(h["gaps"]) + 3.2, h["pro2"] + dy), fontsize=11, color=INK,
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=1))
    ax.axvspan(11.6, 13.6, color=BLUE, alpha=.07, zorder=0)
    ax.set_xlabel("Largest gap between adjacent EF loops (residues; capped at 40)")
    ax.set_ylabel("Loops with Pro at position 2 (of 4)")
    ax.set_yticks(range(5)); yaxis_grid(ax)
    ax.set_title("Searching by loop spacing finds candidates outside the family")
    ax.set_xlim(11, 41); ax.set_ylim(-.4, 4.5)
    ax.legend(loc="upper right", fontsize=10.5, labelcolor=INK2)
    n_out = sum(1 for h in hits if h["strict"] and not h["in_family"])
    n_out_p = sum(1 for h in hits if h["strict"] and not h["in_family"] and h["pro2"] > 0)
    finish(fig, "F7_retrieval_beyond_family",
           f"Query: UniProt IPR011992 (generic EF-hand pair) AND length < 200, no lanmodulin term; 4 loops by "
           f"EF_LOOP_INSTRUMENT. {n_out} outside-family strict hits ({n_out_p} with Pro at ≥1 loop). Candidates only, unchecked.")

    # ------------------------------------------------------------ F8 pLDDT of the controls + AlphaFold coverage
    ctrl = json.load(open(FIGDATA / "controls_plddt.json"))
    cov = json.load(open(FIGDATA / "corpusb_coverage.json"))
    fig = plt.figure(figsize=(11, 5.6)); gs = fig.add_gridspec(2, 2, width_ratios=[1.7, 1], hspace=.55, wspace=.28)
    for k, (acc, nm) in enumerate((("C5B164", "Mex-LanM (C5B164)"), ("A0A4V2JDD3", "Hans-LanM (A0A4V2JDD3)"))):
        ax = fig.add_subplot(gs[k, 0]); pl = ctrl[acc]["plddt"]
        ax.axhspan(90, 100, color=BLUE, alpha=.06); ax.axhspan(70, 90, color=BLUE, alpha=.025)
        ax.plot(range(1, len(pl) + 1), pl, color=BLUE, lw=2)
        for st0 in loops(ctrl[acc]["sequence"]):
            ax.axvspan(st0 + 1, st0 + LOOP_LENGTH, color=ORANGE, alpha=.35, lw=0)
        ax.set_ylim(20, 100); ax.set_xlim(1, len(pl)); ax.set_ylabel("pLDDT"); yaxis_grid(ax)
        ax.set_title(f"{nm}   mean {np.mean(pl):.1f}", fontsize=12.5)
        if k == 1: ax.set_xlabel("Residue")
    ax.text(.995, .05, "orange = EF loop (12 residues)", transform=ax.transAxes, ha="right", fontsize=10, color=INK2)
    ax = fig.add_subplot(gs[:, 1])
    bl = cov["by_loops"]
    yes = [bl["4_loops"]["with_model"], bl["3_loops"]["with_model"]]
    no = [bl["4_loops"]["without_model"], bl["3_loops"]["without_model"]]
    ax.bar(range(2), yes, color=BLUE, edgecolor=WHITE, linewidth=2, width=.55, label="AlphaFold model exists")
    ax.bar(range(2), no, bottom=yes, color=NEUTRAL, edgecolor=WHITE, linewidth=2, width=.55, label="no model (404)")
    for i in range(2):
        ax.text(i, yes[i] / 2, str(yes[i]), ha="center", va="center", color="white", fontsize=12, fontweight="bold")
        ax.text(i, yes[i] + no[i] / 2, str(no[i]), ha="center", va="center", color=INK, fontsize=12)
    ax.set_xticks(range(2), ["4 EF loops", "3 EF loops"]); ax.set_ylabel("Corpus B accessions"); yaxis_grid(ax)
    ax.legend(loc="upper right", fontsize=9.5, labelcolor=INK2)
    ax.set_title("Model coverage", fontsize=12.5)
    fig.suptitle("AlphaFold: confident where it exists, absent for 42% of the family", x=.01, ha="left", fontsize=15, fontweight="bold")
    fig.subplots_adjust(top=.86, bottom=.17, left=.07, right=.98)
    ax.set_ylim(0, 150)
    finish(fig, "F8_alphafold",
           f"{cov['n_with_model']} of {cov['n_accessions']} Corpus B accessions have a model (AlphaFold v6). pLDDT read from the model B-factor column. "
           f"Model confidence is not evidence of metal binding.", manual=True)
    print("done")


if __name__ == "__main__":
    main()
