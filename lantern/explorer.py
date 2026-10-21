"""The Explorer: look at the data files directly, with no model in the loop.

Split the way viewer.py is. Everything that decides *which rows* a click or a
brush selects is a pure function here -- DataFrames in, DataFrames out, no
Streamlit -- so the selection logic is tested without a browser. `render_explorer`
is the thin page layer: it draws Altair charts, hands their selections to those
functions, and opens the existing binding-site viewer for a chosen site.

What this module will not do: score, rank by anything it computed, or say more
than the files say. Every number plotted is a count or a column read from
`data/*.parquet`, `data/paired_sites.csv`, the optional retrieval-hits file, or
the existing sequence screen. The captions state what those numbers cannot
support (a threshold chosen in-sample, pseudo-replicated sites, sequence leads
that are not binders), because a chart is read faster than its caption and the
caption is the only place the qualification can live.
"""
import json
import os
import zlib
from pathlib import Path

import altair as alt
import pandas as pd

from .geometry import CRITERIA, MAX_RESOLUTION_A
from .structure import ALL_METAL_CODES, binding_neighborhood, fetch_structure

DATA = Path(__file__).resolve().parent.parent / "data"
LN_SITES = DATA / "lanthanide_sites.parquet"
CA_SITES = DATA / "calcium_sites.parquet"
PAIRS = DATA / "paired_sites.csv"

# Loop-spacing hits of the sequence retrieval: a JSON list of
# {acc, len, gaps, strict, hdr, pro2} plus an optional `in_family` flag. The
# repo ships it; LANTERN_HITS_JSON points the Explorer at a different copy.
HITS_ENV = "LANTERN_HITS_JSON"
DEFAULT_HITS = str(DATA / "figures" / "retrieval_hits.json")

# The one coordination-number bar the geometry module scores against. Read from
# there rather than restated, so the line on the chart and the rule that makes
# a call cannot drift apart.
CN_THRESHOLD = next(minimum for name, minimum, _ in CRITERIA
                    if name == "coordination_number")

GROUP_LN = "Natural Ln"
GROUP_CA = "Ca"
GROUP_COLORS = {GROUP_LN: "#d98e04", GROUP_CA: "#4a7fb0"}

CAVEAT_THRESHOLD = (
    f"CN \u2265 {CN_THRESHOLD} was chosen on these same sites (in-sample), so it "
    "describes this corpus and says nothing about performance on new proteins.")


def entry_caveat(ln: pd.DataFrame, ca: pd.DataFrame) -> str:
    """Entry counts for the resampling caveat, computed from the rows shown."""
    return (f"The sampling unit is the PDB entry, not the site: {ln['pdb_id'].nunique()} "
            f"natural Ln entries and {ca['pdb_id'].nunique()} Ca entries stand behind "
            f"{len(ln)} and {len(ca)} sites, so any interval over sites is too narrow.")


CAVEAT_PSEUDOREPLICATES = (
    "Sites are pseudo-replicates: many copies per crystal, and the natural Ln "
    "entries come from a handful of protein families. Do not read a site count as a sample "
    "size or compute a p-value from it. Some rows come from asymmetric-unit "
    "coordinates, where a shell can be truncated.")
CAVEAT_LEADS = (
    "Candidates are sequence leads only. Nothing here shows binding, "
    "selectivity or stability, and no experiment backs any row.")


# ------------------------------------------------------------------ loading --

def load_sites(path: Path = LN_SITES) -> pd.DataFrame:
    return pd.read_parquet(path)


def curated_sites(df: pd.DataFrame, group: str) -> pd.DataFrame:
    """The sites the headline contrast is drawn from.

    Natural Ln: curated as natural biology, family lanthanide, resolution at
    most MAX_RESOLUTION_A, no chelator flag (136 rows). Ca: the same resolution
    and chelator filters (664 rows). `class_first_pass` is not applied to Ca
    because the Ca table has no natural_ln_biology rows -- its labels describe
    lanthanide-substituted sites -- so filtering on it would empty the arm.
    Both arms are held to one resolution cut on purpose; see geometry.py.
    """
    keep = (df["resolution_A"] <= MAX_RESOLUTION_A) & ~df["chelator_flagged"].astype(bool)
    if group == GROUP_LN:
        keep &= (df["class_first_pass"] == "natural_ln_biology") & (df["family"] == "lanthanide")
    elif group != GROUP_CA:
        raise ValueError(f"unknown group {group!r}")
    return df[keep].reset_index(drop=True)


# ----------------------------------------------------------------------- V1 --

def cn_distribution(ln: pd.DataFrame, ca: pd.DataFrame) -> pd.DataFrame:
    """Per group, the share of sites at each coordination number.

    Normalised within a group because the arms differ in size (136 vs 664);
    raw counts would let the larger arm look more important. `n` and `total`
    ride along so a tooltip can show the counts the percentage came from.
    Every CN between the smallest and largest observed appears in both groups,
    with n = 0 where nothing was seen, so the bars align on one axis.
    """
    frames = {GROUP_LN: ln, GROUP_CA: ca}
    values = pd.concat([f["coordination_number"] for f in frames.values()])
    if values.empty:
        return pd.DataFrame(columns=["group", "cn", "n", "total", "percent"])
    axis = range(int(values.min()), int(values.max()) + 1)
    rows = []
    for group, frame in frames.items():
        counts = frame["coordination_number"].value_counts()
        total = int(counts.sum())
        for cn in axis:
            n = int(counts.get(cn, 0))
            rows.append({"group": group, "cn": cn, "n": n, "total": total,
                         "percent": round(100.0 * n / total, 2) if total else 0.0})
    return pd.DataFrame(rows)


def threshold_summary(frame: pd.DataFrame) -> dict:
    """Sites at or above the bar, as counts and a share of the group."""
    total = len(frame)
    above = int((frame["coordination_number"] >= CN_THRESHOLD).sum())
    return {"above": above, "total": total,
            "percent": round(100.0 * above / total, 1) if total else None}


def sites_for_selection(ln: pd.DataFrame, ca: pd.DataFrame, selection) -> pd.DataFrame:
    """Rows behind the bars a user clicked.

    `selection` is what Vega-Lite hands back for a point selection on
    (group, cn): a list of {"group": ..., "cn": ...}. Vega returns field
    values, not row indices, so the match is on those two fields. An empty or
    malformed selection returns an empty frame rather than every site, because
    "nothing clicked" must not look like "everything selected".
    """
    columns = ["group", "pdb_id", "element", "chain", "site", "coordination_number",
               "water_donor_count", "protein_donor_count", "resolution_A",
               "coordinate_source", "class_first_pass", "title"]
    empty = pd.DataFrame(columns=columns)
    if not selection:
        return empty
    wanted = set()
    for item in selection:
        try:
            wanted.add((str(item["group"]), int(item["cn"])))
        except (KeyError, TypeError, ValueError):
            continue
    parts = []
    for group, frame in ((GROUP_LN, ln), (GROUP_CA, ca)):
        cns = {cn for g, cn in wanted if g == group}
        if cns:
            hit = frame[frame["coordination_number"].isin(cns)].copy()
            hit.insert(0, "group", group)
            parts.append(hit)
    if not parts:
        return empty
    out = pd.concat(parts, ignore_index=True)
    return out[columns].sort_values(["group", "coordination_number", "pdb_id", "chain", "site"],
                                    kind="stable").reset_index(drop=True)


def site_view(row: dict, fetch=fetch_structure, measure=binding_neighborhood) -> dict:
    """Locate one table row in its structure so the viewer can draw it.

    Never raises. Returns {"status": "ok", "text", "fmt", "site", "note"} or
    {"status": "unavailable", "message"}. The reasons a site cannot be drawn
    are ordinary and each gets its own message: the entry is not cached and
    cannot be fetched; the row is a symmetry copy from the biological assembly
    (chain ids like "A-2" do not exist in the deposited file); the ion is not
    found under that chain and residue number.

    A site is matched on (chain, residue number, element). The table's
    coordination number may come from assembly 1 while the file drawn is the
    deposited asymmetric unit, so when they differ the note says so rather than
    letting the picture contradict the number beside it.
    """
    pdb_id = str(row.get("pdb_id", ""))
    chain, number = str(row.get("chain", "")), str(row.get("site", ""))
    element = str(row.get("element", "")).strip().upper()
    try:
        text, fmt = fetch(pdb_id)
    except Exception as exc:  # no cache, no network, bad id: all the same to a reader
        return {"status": "unavailable",
                "message": f"{pdb_id or 'This entry'} is not cached in data/structures/ and "
                           f"could not be fetched ({type(exc).__name__}), so there is no "
                           "structure to draw. The table row is unaffected."}
    if "-" in chain:
        return {"status": "unavailable",
                "message": f"{pdb_id} chain {chain} is a symmetry copy generated for the "
                           "biological assembly. It is not in the deposited coordinate file, "
                           "so it cannot be drawn from it."}
    try:
        sites = measure(text, fmt, metals=ALL_METAL_CODES)
    except Exception as exc:
        return {"status": "unavailable",
                "message": f"{pdb_id} could not be parsed ({type(exc).__name__})."}
    match = next((s for s in sites if s["chain"] == chain and s["site"] == number
                  and s["element"].upper() == element), None)
    if match is None:
        return {"status": "unavailable",
                "message": f"{element} {number} chain {chain} was not found in the "
                           f"deposited coordinates of {pdb_id}."}
    note = ""
    want = row.get("coordination_number")
    if want is not None and match["coordination_number"] != int(want):
        note = (f"The table lists CN {int(want)} for this site; the deposited file drawn "
                f"here gives CN {match['coordination_number']}, because the table row was "
                f"measured on {row.get('coordinate_source', 'a different parse')}.")
    return {"status": "ok", "text": text, "fmt": fmt, "site": match, "note": note}


# ----------------------------------------------------------------------- V3 --

def pair_table(pairs: pd.DataFrame) -> pd.DataFrame:
    """The paired Ln/Ca sites in long form: two rows per pair, one per ion.

    Long form is what a slope chart wants (one line per `pair`, x = ion). The
    delta and donor counts are carried so a tooltip shows what changed besides
    CN. The delta is copied from the file's `*_delta` column untouched; the
    chart itself only draws the two CNs.
    """
    rows = []
    for i, p in enumerate(pairs.to_dict("records"), start=1):
        for ion, suffix in (("Ln", "_ln"), ("Ca", "_ca")):
            rows.append({
                "pair": i, "site_signature": p["site_signature"], "ion": ion,
                "cn": float(p["coordination_number" + suffix]),
                "water_donors": float(p["water_donor_count" + suffix]),
                "protein_donors": float(p["protein_donor_count" + suffix]),
                "metals": p["metals"], "cn_delta": float(p["coordination_number_delta"]),
            })
    return pd.DataFrame(rows)


def pair_signs(pairs: pd.DataFrame) -> dict:
    """Up / down / tie counts of the CN delta, from the file's own column."""
    delta = pairs["coordination_number_delta"]
    return {"up": int((delta > 0).sum()), "down": int((delta < 0).sum()),
            "tie": int((delta == 0).sum())}


# ----------------------------------------------------------------------- V4 --

def load_hits(path: str | os.PathLike | None = None) -> tuple[pd.DataFrame | None, str]:
    """(hits, message). Absent or malformed input gives (None, why), not an exception.

    Reads data/figures/retrieval_hits.json unless `path` or LANTERN_HITS_JSON
    says otherwise. A missing file is a normal case (the view is optional), not
    an error.

    `in_family` is optional per row. The returned frame always has the column:
    True / False when the file states it, None when it does not. A frame with
    no stated value anywhere is how `family_split` knows not to draw a split.
    """
    path = Path(path or os.environ.get(HITS_ENV) or DEFAULT_HITS)
    if not path.is_file():
        return None, (f"The retrieval-hits file was not found at {path}. Set "
                      f"{HITS_ENV} to its location to enable this view; the rest of "
                      "the Explorer does not need it.")
    try:
        raw = json.loads(path.read_text())
        rows = []
        for h in raw:
            gaps = [int(g) for g in h["gaps"]]
            if not gaps:
                continue
            rows.append({"acc": str(h["acc"]), "len": int(h["len"]),
                         "max_gap": max(gaps), "n_loops": len(gaps) + 1,
                         "pro2": int(h["pro2"]), "strict": bool(h["strict"]),
                         "in_family": (None if h.get("in_family") is None
                                       else bool(h["in_family"])),
                         "name": _hit_name(str(h.get("hdr", "")), str(h["acc"]))})
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return None, f"{path} could not be read as retrieval hits ({type(exc).__name__}: {exc})."
    if not rows:
        return None, f"{path} holds no hits with measurable loop gaps."
    return pd.DataFrame(rows), ""


def _hit_name(header: str, acc: str) -> str:
    """The protein name out of a UniProt FASTA header, for display only."""
    parts = header.split(" ", 1)
    if len(parts) < 2:
        return acc
    return parts[1].split(" OS=")[0] or acc


def family_split(hits: pd.DataFrame) -> dict | None:
    """Hits inside vs outside the reference family, or None when not stated.

    Counted only over rows that carry `in_family`; `unknown` is the rest. None
    (no row states it) tells the page to say nothing about family membership
    rather than imply every hit is outside it.
    """
    stated = hits["in_family"].dropna()
    if stated.empty:
        return None
    return {"inside": int(stated.astype(bool).sum()),
            "outside": int((~stated.astype(bool)).sum()),
            "unknown": int(hits["in_family"].isna().sum())}


def hit_cells(hits: pd.DataFrame) -> pd.DataFrame:
    """Hits counted per (largest gap, Pro-at-position-2 count, strict).

    Both axes are small integers, so plotting one dot per hit stacks
    thousands of points on a few dozen positions. Counting per cell and sizing
    the bubble by the count keeps every hit represented and lets a brush
    select by the same two fields the chart is drawn on.
    """
    cells = (hits.groupby(["max_gap", "pro2", "strict"]).size()
             .reset_index(name="hits"))
    cells["rule"] = cells["strict"].map({True: "strict (all gaps 12–13)",
                                         False: "other spacing"})
    return cells


def filter_by_brush(frame: pd.DataFrame, brush, x: str, y: str) -> pd.DataFrame:
    """Rows inside a Vega-Lite interval brush, {field: [low, high]}.

    No brush (or a malformed one) returns the whole frame: an unbrushed chart
    is an unfiltered table, the opposite convention to sites_for_selection,
    because a brush narrows a list that is already showing.
    """
    try:
        (xl, xh), (yl, yh) = sorted(brush[x]), sorted(brush[y])
    except (KeyError, TypeError, ValueError):
        return frame
    return frame[frame[x].between(xl, xh) & frame[y].between(yl, yh)]


def uniprot_url(accession: str) -> str:
    return f"https://rest.uniprot.org/uniprotkb/{accession}"


# ----------------------------------------------------------------------- V5 --

def candidate_table(candidates) -> pd.DataFrame:
    """The existing sequence screen, flattened. No new score is computed here.

    `candidates` is chemistry.screen()'s output, already sorted by its score,
    and `rank` is that order. Position 9 is shown as counts, as the screen
    reports it, not folded into anything.
    """
    rows = []
    for rank, c in enumerate(candidates, start=1):
        p9 = ", ".join(f"{k}×{v}" for k, v in sorted(c.position_9.items())) or "—"
        rows.append({"rank": rank, "name": c.protein.name, "accession": c.protein.accession,
                     "organism": c.protein.organism, "score": c.score,
                     "motifs": c.motif_count, "acidic_fraction": c.acidic_fraction,
                     "position_9": p9, "evidence": c.protein.evidence,
                     "rationale": c.rationale, "flags": "; ".join(c.flags)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------- charts --

def cn_chart(dist: pd.DataFrame, selection_name: str = "cn_pick"):
    """Normalised CN bars, one per (group, CN), with the CN bar drawn as a rule."""
    pick = alt.selection_point(name=selection_name, fields=["group", "cn"])
    domain = sorted(GROUP_COLORS)
    bars = (alt.Chart(dist).mark_bar()
            .encode(x=alt.X("cn:O", title="First-shell coordination number (O/N/S within 3.2 Å)"),
                    xOffset=alt.XOffset("group:N", sort=domain),
                    y=alt.Y("percent:Q", title="% of sites in group"),
                    color=alt.Color("group:N", title=None, sort=domain,
                                    scale=alt.Scale(domain=domain,
                                                    range=[GROUP_COLORS[g] for g in domain])),
                    opacity=alt.condition(pick, alt.value(1.0), alt.value(0.55)),
                    tooltip=[alt.Tooltip("group:N"), alt.Tooltip("cn:O", title="CN"),
                             alt.Tooltip("n:Q", title="sites"),
                             alt.Tooltip("total:Q", title="sites in group"),
                             alt.Tooltip("percent:Q", title="%", format=".1f")])
            .add_params(pick))
    rule_data = pd.DataFrame({"cn": [CN_THRESHOLD],
                              "label": [f"CN ≥ {CN_THRESHOLD} rule (in-sample)"]})
    rule = alt.Chart(rule_data).mark_rule(strokeDash=[5, 4], color="#c0392b", size=2,
                                          xOffset=-12).encode(x="cn:O")
    text = alt.Chart(rule_data).mark_text(align="left", dx=-10, dy=-4, baseline="bottom",
                                          color="#c0392b", fontSize=12,
                                          xOffset=-12).encode(x="cn:O", y=alt.value(0),
                                                              text="label:N")
    return (bars + rule + text).properties(height=320)


def pair_chart(long: pd.DataFrame):
    """Slope chart: one line per Ln/Ca pair from its Ln CN to its Ca CN."""
    base = alt.Chart(long).encode(
        x=alt.X("ion:N", sort=["Ln", "Ca"], title=None, scale=alt.Scale(padding=0.4)),
        y=alt.Y("cn:Q", title="Coordination number"),
        detail="pair:N",
        tooltip=[alt.Tooltip("pair:N", title="pair"),
                 alt.Tooltip("site_signature:N", title="site (residues)"),
                 alt.Tooltip("metals:N", title="Ln metal"),
                 alt.Tooltip("ion:N"), alt.Tooltip("cn:Q", title="CN"),
                 alt.Tooltip("water_donors:Q", title="water donors"),
                 alt.Tooltip("protein_donors:Q", title="protein donors"),
                 alt.Tooltip("cn_delta:Q", title="CN delta (file column)")])
    lines = base.mark_line(color="#7a8691", opacity=0.55, strokeWidth=2)
    points = base.mark_point(filled=True, size=70, opacity=0.9).encode(
        color=alt.Color("ion:N", legend=None,
                        scale=alt.Scale(domain=["Ln", "Ca"],
                                        range=[GROUP_COLORS[GROUP_LN], GROUP_COLORS[GROUP_CA]])))
    return (lines + points).properties(height=340)


def loop_chart(cells: pd.DataFrame, selection_name: str = "loop_brush"):
    brush = alt.selection_interval(name=selection_name, encodings=["x", "y"])
    return (alt.Chart(cells).mark_circle(opacity=0.6)
            .encode(x=alt.X("max_gap:Q", title="Largest gap between EF loops (residues)"),
                    y=alt.Y("pro2:Q", title="Loops with Pro at position 2 (of 4)",
                            scale=alt.Scale(domain=[-0.5, 4.5])),
                    size=alt.Size("hits:Q", title="hits", scale=alt.Scale(range=[40, 900])),
                    color=alt.Color("rule:N", title="spacing rule",
                                    scale=alt.Scale(range=["#1f8a8a", "#b0742c"])),
                    tooltip=[alt.Tooltip("hits:Q"), alt.Tooltip("max_gap:Q", title="largest gap"),
                             alt.Tooltip("pro2:Q", title="Pro-2 loops"), alt.Tooltip("rule:N")])
            .add_params(brush).properties(height=340))


def candidate_chart(table: pd.DataFrame, selection_name: str = "cand_brush"):
    brush = alt.selection_interval(name=selection_name, encodings=["x", "y"])
    return (alt.Chart(table).mark_circle(size=180)
            .encode(x=alt.X("acidic_fraction:Q", title="Acidic-residue fraction (D+E)"),
                    y=alt.Y("score:Q", title="Sequence-screen score (0–100)",
                            scale=alt.Scale(domain=[0, 100])),
                    color=alt.condition(brush, alt.value("#1f8a8a"), alt.value("#9aa5b1")),
                    tooltip=["name:N", "accession:N", "score:Q", "motifs:Q",
                             alt.Tooltip("acidic_fraction:Q", format=".3f")])
            .add_params(brush).properties(height=300))


# --------------------------------------------------------------------- page --

def render_explorer(embed) -> None:
    """Draw the Explorer. `embed` is app.embed, passed in to avoid a cycle."""
    import streamlit as st

    from .chemistry import screen
    from .catalog import load_reference
    from .viewer import site_viewer_html, theme_control, tmol_sources, viewer_spec

    script_src, fallback_src = tmol_sources()

    @st.cache_data(show_spinner=False)
    def sites():
        return curated_sites(load_sites(LN_SITES), GROUP_LN), \
            curated_sites(load_sites(CA_SITES), GROUP_CA)

    @st.cache_data(show_spinner=False)
    def pairs():
        return pd.read_csv(PAIRS)

    @st.cache_data(show_spinner=False, ttl=600)
    def hits(path: str):
        return load_hits(path)

    @st.cache_data(show_spinner=False)
    def candidates():
        return candidate_table(screen(load_reference()))

    @st.cache_data(show_spinner="Reading structure…", ttl=3600)
    def structure_site(pdb_id, chain, site, element, cn, source):
        view = site_view({"pdb_id": pdb_id, "chain": chain, "site": site, "element": element,
                          "coordination_number": cn, "coordinate_source": source},
                         fetch=lambda i: fetch_structure(i, timeout=10))
        return view

    st.subheader("Explorer")
    st.caption("The data files, plotted. Nothing here is computed by a language model, and "
               "no view adds a score the files do not contain.")

    # ---- V1
    st.markdown("#### 1 · Coordination number: natural Ln vs Ca sites")
    ln, ca = sites()
    s_ln, s_ca = threshold_summary(ln), threshold_summary(ca)
    a, b, c = st.columns(3)
    a.metric("Natural Ln sites", s_ln["total"],
             help="class natural_ln_biology, family lanthanide, ≤ 2.5 Å, no chelator flag")
    b.metric(f"Natural Ln at CN ≥ {CN_THRESHOLD}", f"{s_ln['above']} ({s_ln['percent']}%)")
    c.metric(f"Ca at CN ≥ {CN_THRESHOLD}",
             f"{s_ca['above']} of {s_ca['total']} ({s_ca['percent']}%)")
    event = st.altair_chart(cn_chart(cn_distribution(ln, ca)), on_select="rerun",
                            key="viz_cn", width="stretch")
    st.caption(CAVEAT_THRESHOLD + " " + entry_caveat(ln, ca))
    st.caption(CAVEAT_PSEUDOREPLICATES)
    picked = sites_for_selection(ln, ca, (event.selection or {}).get("cn_pick", []))
    if picked.empty:
        st.info("Click a bar to list the sites behind it.")
    else:
        key = zlib.crc32(picked[["group", "coordination_number"]].drop_duplicates()
                         .to_json().encode())
        table = st.dataframe(picked, width="stretch", hide_index=True, on_select="rerun",
                             selection_mode="single-row", key=f"viz_cn_rows_{key}")
        st.caption(f"{len(picked)} site(s). Select a row to open it in the binding-site viewer.")
        rows = table.selection.rows
        if rows:
            row = picked.iloc[rows[0]]
            view = structure_site(row["pdb_id"], row["chain"], row["site"], row["element"],
                                  int(row["coordination_number"]), row["coordinate_source"])
            if view["status"] != "ok":
                st.warning(view["message"])
            else:
                theme = theme_control()
                embed(site_viewer_html(view["text"], view["fmt"], view["site"],
                                       script_src=script_src, fallback_src=fallback_src,
                                       theme=theme), 620)
                st.caption(f"**{row['element']} {row['site']}, chain {row['chain']}** of "
                           f"{row['pdb_id']} — {viewer_spec(view['site'])['summary']}. "
                           "Drawn from the deposited coordinates; no call is shown here.")
                if view["note"]:
                    st.caption(view["note"])

    # ---- V3
    st.divider()
    st.markdown("#### 3 · The 19 paired Ln/Ca sites")
    pairs_df = pairs()
    signs = pair_signs(pairs_df)
    st.altair_chart(pair_chart(pair_table(pairs_df)), width="stretch")
    st.caption(f"Same-site pairs: CN higher for Ln in {signs['up']}, lower in {signs['down']}, "
               f"unchanged in {signs['tie']}. Counts are read from the "
               "file's CN delta column.")
    st.caption("n = 19 pairs, each a different protein site; hover for residues and donors. "
               + CAVEAT_PSEUDOREPLICATES)

    # ---- V4
    st.divider()
    st.markdown("#### 4 · Loop spacing of the sequence-retrieval hits")
    hits_df, message = hits(os.environ.get(HITS_ENV) or DEFAULT_HITS)
    if hits_df is None:
        st.info(message)
    else:
        event = st.altair_chart(loop_chart(hit_cells(hits_df)), on_select="rerun",
                                key="viz_loops", width="stretch")
        brushed = filter_by_brush(hits_df, (event.selection or {}).get("loop_brush", {}),
                                  "max_gap", "pro2")
        split = family_split(hits_df)
        st.caption(f"{len(hits_df)} sequences with four EF-hand-like loops and at least one "
                   f"short gap; {int(hits_df['strict'].sum())} meet the strict rule. Bubble size "
                   "is the number of hits at that position. Drag a box to list them.")
        if split is None:
            st.caption("These are matches to a sequence-spacing rule, candidates only, "
                       "unchecked: not verified binders, and not joined here to any "
                       "family-membership list. " + CAVEAT_LEADS)
        else:
            st.metric("In the reference family / outside it",
                      f"{split['inside']} / {split['outside']}")
            st.caption(f"{split['inside']} of these hits are in the reference family and "
                       f"{split['outside']} are outside it"
                       + (f" ({split['unknown']} not classified)" if split["unknown"] else "")
                       + ". All are matches to a sequence-spacing rule, candidates only, "
                       "unchecked: being outside the family does not make a hit a binder. "
                       + CAVEAT_LEADS)
        if len(brushed) < len(hits_df):
            shown = brushed.assign(uniprot=brushed["acc"].map(uniprot_url))
            columns = ["acc", "name", "len", "max_gap", "pro2", "strict"]
            columns += ["in_family"] if split is not None else []
            st.dataframe(shown[columns + ["uniprot"]],
                         width="stretch", hide_index=True,
                         column_config={"uniprot": st.column_config.LinkColumn("UniProt")})

    # ---- V5
    st.divider()
    st.markdown("#### 5 · Ranked candidates (reference set)")
    cand = candidates()
    event = st.altair_chart(candidate_chart(cand), on_select="rerun", key="viz_cand",
                            width="stretch")
    shown = filter_by_brush(cand, (event.selection or {}).get("cand_brush", {}),
                            "acidic_fraction", "score")
    key = zlib.crc32(",".join(shown["accession"]).encode())
    table = st.dataframe(shown[["rank", "name", "accession", "score", "motifs",
                                "acidic_fraction", "position_9"]],
                         width="stretch", hide_index=True, on_select="rerun",
                         selection_mode="single-row", key=f"viz_cand_rows_{key}")
    rows = table.selection.rows
    if rows:
        pick = shown.iloc[rows[0]]
        st.markdown(f"**{pick['name']}** · {pick['accession']} · {pick['organism']}")
        st.write(pick["rationale"])
        st.caption(f"Evidence: {pick['evidence']}. Flags: {pick['flags']}.")
    else:
        st.caption("Brush the plot to filter the table; select a row for its detail.")
    st.caption("Six bundled reference sequences ranked by the existing sequence screen. The "
               "score cannot tell lanthanide binding from calcium binding. " + CAVEAT_LEADS)
