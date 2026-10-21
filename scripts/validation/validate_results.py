"""Independent validation of the headline LANTERN results. Read-only on the repo; downloads go to $LANTERN_ASSETS/validation/.

V1  independent re-count of coordination number from raw mmCIF with a different parser (gemmi) and different neighbour code
V2  statistics on the CN >= 9 contrast: Wilson CIs, Fisher exact, cluster (entry) bootstrap, per-family check, paired sign test
V3  M4 step 2 rerun from the cached UniProt FASTA, and sequence identity of the 49 outside-family hits to known lanmodulins
V4  'before' scores in figure F1 recomputed from the original calcium-consensus regex at commit 5e7491f
V5  LanD (9C8X) asymmetric unit vs biological assembly, recomputed with the repo parser on a freshly downloaded assembly file
V6  Corpus B hallmarks that can be checked without the calcium comparison set (period, Pro at position 2)
Writes data/validation/results.json and prints a summary.
"""
import gzip, io, json, math, os, pathlib, re, sys, collections
import numpy as np, pandas as pd
import gemmi
from scipy import stats

REPO = pathlib.Path(__file__).resolve().parents[2]
ASSETS = pathlib.Path(os.environ.get("LANTERN_ASSETS") or sys.exit("set LANTERN_ASSETS to the asset tree (downloaded mmCIFs, FASTA, AlphaFold models)"))
VAL = ASSETS / "validation"; VAL.mkdir(exist_ok=True)
OUT = REPO / "data/validation"; OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO))
R = {}

ln = pd.read_parquet(REPO / "data/lanthanide_sites.parquet")
ca = pd.read_parquet(REPO / "data/calcium_sites.parquet")
q = lambda d: d[(d.resolution_A <= 2.5) & (~d.chelator_flagged)]
nat = q(ln[(ln.class_first_pass == "natural_ln_biology") & (ln.family == "lanthanide")])
caq = q(ca)

# ---------------------------------------------------------------- V1
def independent_cn(cif_path, chain, resseq, resname, cutoff=3.2):
    st = gemmi.read_structure(str(cif_path)); st.setup_entities()
    model = st[0]
    ns = gemmi.NeighborSearch(model, st.cell, 5).populate()
    ion = None
    for ch in model:
        if ch.name != chain: continue
        for res in ch:
            if res.seqid.num == int(resseq) and res.name.strip().upper() == resname:
                ion = (ch, res); break
    if ion is None: return None
    ch, res = ion
    pos = res[0].pos
    seen = set()
    for m in ns.find_atoms(pos, "\0", radius=cutoff):
        cra = m.to_cra(model)
        a = cra.atom
        if a.element.name not in ("O", "N", "S"): continue
        if cra.residue is res: continue
        # symmetry mates are excluded on purpose: the repo counts the deposited asymmetric unit only
        if m.image_idx != 0: continue
        # find_atoms also returns lattice-translated copies under the identity operation (first run counted two such
        # atoms in 9VY9, 55 A away in the deposited frame); keep only atoms within the cutoff in the deposited coordinates
        if res[0].pos.dist(a.pos) > cutoff + 1e-3: continue
        seen.add((cra.chain.name, str(cra.residue.seqid), cra.residue.name, a.name))
    return len(seen)

asu = nat[nat.coordinate_source == "asu"]
rows = []
for _, r in asu.iterrows():
    p = ASSETS / "corpus_A_mmcif" / f"{r.pdb_id}.cif.gz"
    try:
        cn = independent_cn(p, str(r.chain), r.site, r.metal)
    except Exception as e:
        cn = None
    rows.append(dict(pdb=r.pdb_id, chain=r.chain, site=r.site, repo=int(r.coordination_number), indep=cn))
v1 = pd.DataFrame(rows)
ok = v1.dropna()
R["V1"] = dict(asu_natural_sites=len(asu), matched=len(ok), exact_agree=int((ok.repo == ok.indep).sum()),
               within_1=int(((ok.repo - ok.indep).abs() <= 1).sum()),
               disagreements=ok[ok.repo != ok.indep].to_dict("records")[:12],
               unmatched=len(v1) - len(ok),
               cn9_repo=int((ok.repo >= 9).sum()), cn9_indep=int((ok.indep >= 9).sum()))

# ---------------------------------------------------------------- V2
def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - h), 2), round(100 * (c + h), 2)
n1, k1 = len(nat), int((nat.coordination_number >= 9).sum())
n2, k2 = len(caq), int((caq.coordination_number >= 9).sum())
odds, pf = stats.fisher_exact([[k1, n1 - k1], [k2, n2 - k2]])
rng = np.random.default_rng(11)
def boot(df, B=5000):
    ids = df.pdb_id.unique(); g = {i: (d.coordination_number >= 9).values for i, d in df.groupby("pdb_id")}
    out = []
    for _ in range(B):
        pick = rng.choice(ids, size=len(ids), replace=True)
        v = np.concatenate([g[i] for i in pick]); out.append(v.mean())
    return [round(100 * x, 2) for x in np.percentile(out, [2.5, 97.5])]
per_entry_nat = nat.groupby("pdb_id").coordination_number.apply(lambda s: (s >= 9).mean())
pairs = pd.read_csv(REPO / "data/paired_sites.csv")
dcn = (pairs.coordination_number_ln - pairs.coordination_number_ca)
pos, neg = int((dcn > 0).sum()), int((dcn < 0).sum())
sign_p = stats.binomtest(pos, pos + neg, .5).pvalue if pos + neg else 1.0
# per-family: assign natural sites to the four families by the roadmap's entry lists
fam_of = {}
for e in ("8FNS", "8FNR", "8DQ2", "9PI2"): fam_of[e] = "lanmodulin"
for e in ("9C8X", "9C8Y", "9C8Z", "9C90"): fam_of[e] = "LanD"
for e in ("9VY4", "9VY5", "9VY7", "9VY8", "9VY9", "9VYA"): fam_of[e] = "PepSY"
for e in ("4MAE", "6DAM", "6FKW", "6ZCV", "6ZCW", "7O6Z"): fam_of[e] = "MDH/XoxF"
nat = nat.assign(fam=nat.pdb_id.map(fam_of).fillna("unassigned"))
perfam = {f: dict(sites=int(len(d)), cn_ge9=int((d.coordination_number >= 9).sum()), median=float(d.coordination_number.median()))
          for f, d in nat.groupby("fam")}
R["V2"] = dict(nat=dict(k=k1, n=n1, wilson95=wilson(k1, n1), entry_cluster_bootstrap95=boot(nat), entries=int(nat.pdb_id.nunique())),
               ca=dict(k=k2, n=n2, wilson95=wilson(k2, n2), entry_cluster_bootstrap95=boot(caq), entries=int(caq.pdb_id.nunique())),
               fisher_p=float(pf), odds_ratio=float(odds),
               per_entry_fraction_cn9_natural=dict(entries_with_any=int((per_entry_nat > 0).sum()), entries=int(len(per_entry_nat))),
               per_family=perfam,
               paired=dict(n=len(pairs), up=pos, down=neg, ties=int((dcn == 0).sum()), sign_p=float(sign_p), median=float(dcn.median())))

# ---------------------------------------------------------------- V3
from lantern.chemistry import EF_LOOP_INSTRUMENT, LOOP_LENGTH
from Bio import Align
from Bio.Align import substitution_matrices
D3 = ASSETS / "uniprot_efhand_short"
fam = {a for v in json.load(open(ASSETS / "corpus_B_alphafold/family_accessions.json")).values() for a in v}
seqs, hdr, a_ = {}, {}, None
with gzip.open(D3 / "efhand_IPR011992_len_lt200.fasta.gz", "rt") as fh:
    for line in fh:
        if line.startswith(">"):
            a_ = line.split("|")[1]; seqs[a_] = ""; hdr[a_] = line.strip()
        else: seqs[a_] += line.strip()
def loops(s):
    st = []
    for m in re.finditer("(?=(%s))" % EF_LOOP_INSTRUMENT.pattern, s):
        if not st or m.start() - st[-1] >= LOOP_LENGTH: st.append(m.start())
    return st
n4 = strict = 0; strict_hits = []
for a, s in seqs.items():
    st = loops(s)
    if len(st) != 4: continue
    gaps = [b - c - LOOP_LENGTH for c, b in zip(st, st[1:])]
    if any(g < 14 for g in gaps): n4 += 1
    if all(12 <= g <= 13 for g in gaps): strict_hits.append(a)
outside = [a for a in strict_hits if a not in fam]
al = Align.PairwiseAligner(); al.substitution_matrix = substitution_matrices.load("BLOSUM62"); al.open_gap_score = -10; al.extend_gap_score = -0.5
al.mode = "global"
def ident(a, b):
    aln = al.align(a, b)[0]; cols = sum(1 for x, y in zip(*[aln[0], aln[1]]) if x != "-" and y != "-")
    same = sum(1 for x, y in zip(aln[0], aln[1]) if x == y and x != "-")
    return same / max(min(len(a), len(b)), 1)
refs = {"C5B164": seqs["C5B164"], "A0A4V2JDD3": seqs["A0A4V2JDD3"]}
idn = {}
for a in outside:
    idn[a] = max(ident(seqs[a], r) for r in refs.values())
vals = np.array(list(idn.values()))
in_fam_strict = [a for a in strict_hits if a in fam]
idn_in = [max(ident(seqs[a], r) for r in refs.values()) for a in in_fam_strict[:40]]
ann = collections.Counter(re.sub(r"^.*?\s", "", hdr[a]).split(" OS=")[0] for a in outside)
R["V3"] = dict(scanned=len(seqs), four_loops_any_gap_lt14=n4, strict=len(strict_hits), strict_in_family=len(in_fam_strict),
               strict_outside=len(outside), outside_with_pro2=sum(1 for a in outside if sum(seqs[a][i + 1] == "P" for i in loops(seqs[a])) > 0),
               ctrl_recovered=[a in strict_hits for a in refs],
               outside_identity_to_nearest_known_LanM=dict(min=round(float(vals.min()), 3), median=round(float(np.median(vals)), 3), max=round(float(vals.max()), 3),
                                                           n_ge_0_40=int((vals >= .40).sum()), n_lt_0_25=int((vals < .25).sum())),
               in_family_identity_sample=dict(median=round(float(np.median(idn_in)), 3), n=len(idn_in)),
               outside_annotation_top=ann.most_common(5))

# ---------------------------------------------------------------- V4
refjson = json.load(open(REPO / "data/reference_proteins.json"))["proteins"]
old = re.compile(r"D.[DN].[DN]G.[ILV][DE]..E")
def old_score(s):
    s = s.upper(); ac = (s.count("D") + s.count("E")) / len(s); m = len(old.findall(s))
    return round(min(100., 10 + min(ac / .22, 1.) * 35 + min(m, 4) * 12), 1), m
R["V4"] = {r["accession"]: dict(zip(("score", "motifs"), old_score(r["sequence"]))) for r in refjson}

# ---------------------------------------------------------------- V5
import requests
from lantern.structure import binding_neighborhood, donor_chemistry, site_net_charge
land = {}
for label, url in (("asu", "https://files.rcsb.org/download/9C8X.cif.gz"), ("assembly1", "https://files.rcsb.org/download/9C8X-assembly1.cif.gz")):
    f = VAL / pathlib.Path(url).name
    if not f.exists():
        f.write_bytes(requests.get(url, timeout=60).content)
    text = gzip.open(f, "rt").read()
    sites = binding_neighborhood(text, fmt="cif")
    def _desc(s):
        ch = donor_chemistry(s["donors"])
        return dict(cn=s["coordination_number"], carboxylate_residues=ch.get("carboxylate_residues"),
                    bidentate=ch.get("bidentate_carboxylates"), net_charge=site_net_charge(ch).get("net_charge"), metal=s["metal"])
    land[label] = [_desc(s) for s in sites]
R["V5"] = land

# ---------------------------------------------------------------- V6
fam4 = [a for a in fam if a in seqs and len(loops(seqs[a])) == 4]
periods = [b - c for a in fam4 for c, b in zip(loops(seqs[a]), loops(seqs[a])[1:])]
pro2 = [seqs[a][i + 1] == "P" for a in fam4 for i in loops(seqs[a])]
R["V6"] = dict(family_four_loop_seqs=len(fam4), median_period=float(np.median(periods)),
               iqr_period=[float(x) for x in np.percentile(periods, [25, 75])], pro_at_2_fraction=round(float(np.mean(pro2)), 3))

json.dump(R, open(OUT / "results.json", "w"), indent=1, default=str)
print(json.dumps(R, indent=1, default=str))
