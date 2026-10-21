"""Sensitivity of the CN >= 9 contrast to the first-shell cutoff (2.8/3.0/3.2/3.4 A), recomputed independently with gemmi
on the asymmetric-unit rows (assembly-1 rows cannot be recomputed from the downloaded ASU files). Ca-entry files are fetched to
$LANTERN_ASSETS/validation/ca_mmcif/. Output: data/validation/cutoff_sensitivity.json"""
import gzip, json, os, pathlib, time, sys
import pandas as pd, requests, gemmi
REPO = pathlib.Path(__file__).resolve().parents[2]
ASSETS = pathlib.Path(os.environ.get("LANTERN_ASSETS") or sys.exit("set LANTERN_ASSETS to the asset tree (downloaded mmCIFs, FASTA, AlphaFold models)"))
CA = ASSETS / "validation/ca_mmcif"; CA.mkdir(parents=True, exist_ok=True)
ln = pd.read_parquet(REPO / "data/lanthanide_sites.parquet"); ca = pd.read_parquet(REPO / "data/calcium_sites.parquet")
q = lambda d: d[(d.resolution_A <= 2.5) & (~d.chelator_flagged)]
nat = q(ln[(ln.class_first_pass == "natural_ln_biology") & (ln.family == "lanthanide")]); caq = q(ca)
nat_asu, ca_asu = nat[nat.coordinate_source == "asu"], caq[caq.coordinate_source == "asu"]
for pid in sorted(ca_asu.pdb_id.unique()):
    f = CA / f"{pid}.cif.gz"
    if not f.exists():
        r = requests.get(f"https://files.rcsb.org/download/{pid}.cif.gz", timeout=60); r.raise_for_status(); f.write_bytes(r.content); time.sleep(.15)
cache = {}
def cns(path, rows, cutoffs):
    key = str(path)
    if key not in cache:
        st = gemmi.read_structure(str(path)); st.setup_entities(); cache[key] = (st, gemmi.NeighborSearch(st[0], st.cell, 6).populate())
    st, ns = cache[key]; model = st[0]; out = {}
    for _, r in rows.iterrows():
        res = next((x for ch in model if ch.name == str(r.chain) for x in ch if x.seqid.num == int(r.site) and x.name.strip().upper() == r.metal), None)
        if res is None: continue
        pos = res[0].pos
        for c in cutoffs:
            seen = set()
            for m in ns.find_atoms(pos, "\0", radius=c):
                cra = m.to_cra(model); a = cra.atom
                if cra.residue is res or m.image_idx != 0 or pos.dist(a.pos) > c + 1e-3: continue
                if a.element.name in ("O", "N", "S"): seen.add((cra.chain.name, str(cra.residue.seqid), cra.residue.name, a.name))
            out[(r.pdb_id, r.chain, r.site, c)] = len(seen)
    return out
cut = [2.8, 3.0, 3.2, 3.4]
def run(df, base):
    res = {}
    for pid, g in df.groupby("pdb_id"):
        res.update(cns(base / f"{pid}.cif.gz", g, cut))
    return res
rn, rc = run(nat_asu, ASSETS / "corpus_A_mmcif"), run(ca_asu, CA)
out = {"natural_asu_sites": len(nat_asu), "ca_asu_sites": len(ca_asu), "by_cutoff": {}}
for c in cut:
    a = [v for (p, ch, s, cc), v in rn.items() if cc == c]; b = [v for (p, ch, s, cc), v in rc.items() if cc == c]
    out["by_cutoff"][str(c)] = dict(ln_ge9=sum(v >= 9 for v in a), ln_n=len(a), ca_ge9=sum(v >= 9 for v in b), ca_n=len(b),
                                    ln_median=float(pd.Series(a).median()), ca_median=float(pd.Series(b).median()))
json.dump(out, open("data/validation/cutoff_sensitivity.json", "w"), indent=1)
print(json.dumps(out, indent=1))
