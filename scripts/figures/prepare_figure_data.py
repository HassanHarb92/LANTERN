"""Regenerate data/figures/*.json from external (non-repo) assets. Only needed to refresh the data; the figure
build scripts read the committed JSON files and need nothing outside the repo.

Usage: python scripts/figures/prepare_figure_data.py [--assets DIR]
  --assets defaults to $LANTERN_ASSETS, else /work/as1296/LANTERN_assets
Inputs under DIR: uniprot_efhand_short/criteria_hits.json, corpus_B_alphafold/{family_accessions.json,
uniprot_sequences.fasta,models/<acc>.cif}
"""
import argparse, json, os, pathlib, re, sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from lantern.chemistry import EF_LOOP_INSTRUMENT, LOOP_LENGTH  # noqa: E402

DEFAULT_ASSETS = "/work/as1296/LANTERN_assets"
CONTROLS = ("C5B164", "A0A4V2JDD3")


def count_loops(seq):
    st = []
    for m in re.finditer("(?=(%s))" % EF_LOOP_INSTRUMENT.pattern, seq):
        if not st or m.start() - st[-1] >= LOOP_LENGTH:
            st.append(m.start())
    return len(st)


def read_fasta(path):
    seqs, a = {}, None
    for line in open(path):
        if line.startswith(">"):
            a = line.split("|")[1]; seqs[a] = ""
        else:
            seqs[a] += line.strip()
    return seqs


def plddt(cif):
    import gemmi
    st = gemmi.read_structure(str(cif))
    return [round(res.find_atom("CA", "*").b_iso, 2) for res in st[0][0] if res.find_atom("CA", "*")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", default=os.environ.get("LANTERN_ASSETS", DEFAULT_ASSETS))
    ap.add_argument("--out", default=str(REPO / "data/figures"))
    a = ap.parse_args()
    A, out = pathlib.Path(a.assets), pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    B = A / "corpus_B_alphafold"

    fam_lists = json.load(open(B / "family_accessions.json"))
    fam = {x for v in fam_lists.values() for x in v}
    hits = json.load(open(A / "uniprot_efhand_short/criteria_hits.json"))
    rows = [{"acc": h["acc"], "len": h["len"], "gaps": h["gaps"], "strict": h["strict"],
             "hdr": h.get("hdr", "")[:80], "pro2": h["pro2"], "in_family": h["acc"] in fam} for h in hits]
    json.dump(rows, open(out / "retrieval_hits.json", "w"), separators=(",", ":"))

    seqs = read_fasta(B / "uniprot_sequences.fasta")
    ctrl = {}
    for acc in CONTROLS:
        pl = plddt(B / "models" / f"{acc}.cif")
        ctrl[acc] = {"sequence": seqs[acc], "plddt": pl}
    json.dump(ctrl, open(out / "controls_plddt.json", "w"), separators=(",", ":"))

    accs = sorted(seqs)   # the 190 corpus-B accessions (fasta = manifest); `fam` also lists 5 retrieved ones outside it
    cov = {"n_accessions": len(accs), "n_with_model": 0,
           "by_loops": {"4_loops": {"with_model": 0, "without_model": 0},
                        "3_loops": {"with_model": 0, "without_model": 0},
                        "other": {"with_model": 0, "without_model": 0}}}
    for acc in accs:
        has = (B / "models" / f"{acc}.cif").exists()
        n = count_loops(seqs.get(acc, ""))
        key = "4_loops" if n >= 4 else "3_loops" if n == 3 else "other"
        cov["by_loops"][key]["with_model" if has else "without_model"] += 1
        cov["n_with_model"] += has
    json.dump(cov, open(out / "corpusb_coverage.json", "w"), indent=1)
    print("wrote", out, "| accessions", len(accs), "with model", cov["n_with_model"], cov["by_loops"])


if __name__ == "__main__":
    main()
