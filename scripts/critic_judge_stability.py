"""Repeat the judge pass on one fixed retrieval and report how much the verdicts move.

    python scripts/critic_judge_stability.py [--runs 5] [--provider argo] [--question Q] [--cache DIR]

WHY THIS EXISTS. A single live table shows what the judge said once. It cannot show
whether it would say the same thing again, and the policy thresholds a verdict's
confidence, so a claim sitting near a threshold decides a candidate's fate on noise.
The first run after the snippet fix demoted a candidate to review; the next badged it,
on identical input.

Retrieval runs once and every repetition is judged against exactly those passages, so
the only thing varying is the model. This measures reproducibility, not accuracy:
a claim can be stably wrong. Accuracy needs hand labels (ROADMAP M7, step 4).
"""
import argparse
import pathlib
import statistics
import sys
from collections import Counter

from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from lantern.critic.claims import claims_from_record  # noqa: E402
from lantern.critic.judge import judge  # noqa: E402
from lantern.critic.lineage import load_lineage  # noqa: E402
from lantern.critic.policy import FROZEN, decide  # noqa: E402
from lantern.critic.retrieval import retrieve  # noqa: E402
from lantern.discover import answer  # noqa: E402
from lantern.llm import make_client  # noqa: E402
from lantern.scholarbud import BM25Index, Library  # noqa: E402

from critic_live_trial import cached_search  # noqa: E402  (same directory; shares the polite Crossref cache)

# The table below this line is generated; the reading of it underneath is written by hand
# and is the part worth keeping. Rerunning with --out replaces the table and carries the
# tail through, so a second batch does not silently delete the conclusions drawn from the first.
KEEP_MARKER = "<!-- keep below: written by hand, preserved across reruns of the script above -->"


def group_by_accession(record, claims, verdicts, evidence):
    """The pipeline's attribution, reused: a site claim belongs to its structure's accession,
    a rule claim to every selected candidate. Kept in step with lantern.critic.pipeline."""
    selected = [c["accession"] for c in (record.get("shortlist") or {}).get("candidates", []) if c.get("selected")]
    structures = [e.get("accession", "") for e in record.get("evidence", [])]
    groups = {}
    for c in claims:
        field = c.source_field or ""
        idx = field.split("[", 1)[1].split("]", 1)[0] if field.startswith("evidence[") else None
        accs = [structures[int(idx)]] if idx is not None and int(idx) < len(structures) else selected
        for acc in filter(None, accs):
            vs, es = groups.setdefault(acc, ([], []))
            vs.append(verdicts[c.id])
            es.extend(evidence[c.id])
    return groups


def main():
    load_dotenv()  # same reason as critic_live_trial.py: the credential lives in .env
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--provider", default=None)
    ap.add_argument("--question", default="proteins for capturing Ce3+")
    ap.add_argument("--rows", type=int, default=15)
    ap.add_argument("--cache", default=".critic_cache")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cache = pathlib.Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)

    record = answer(a.question)
    claims = claims_from_record(record)
    lib = Library()
    for c in claims:
        for prefix in (None, "10.26434"):
            for p in cached_search(c.query, a.rows, prefix, cache):
                lib.upsert(p)
    index, lineage, evidence, nxt = BM25Index(lib.all()), load_lineage(), {}, 1
    for c in claims:
        evidence[c.id] = retrieve(c, index, lineage, k=4, start=nxt)
        nxt += len(evidence[c.id])

    client = make_client(a.provider)
    if not client.configured():
        sys.exit("The judge provider is not configured (missing key or username). Fill in .env (see .env.example).")
    runs = []
    for i in range(a.runs):
        runs.append({v.claim_id: v for v in judge(claims, evidence, client)})
        print(f"  run {i + 1}/{a.runs} done", file=sys.stderr, flush=True)

    accessions = sorted({e.get("accession", "") for e in record.get("evidence", [])} - {""})
    L = [f"# Critic judge stability\n",
         f"Question: `{a.question}`  \nJudge: `{getattr(client, 'model', '?')}`  \nRuns: {a.runs}, "
         f"one retrieval reused by all of them.\n",
         "Reproducibility only. A claim can be stably wrong; accuracy needs hand labels.\n",
         "## Label across runs\n",
         "| claim | labels | confidence min/median/max | stable |", "|---|---|---|---|"]
    unstable = 0
    for c in claims:
        labels = Counter(r[c.id].label for r in runs)
        confs = sorted(r[c.id].confidence for r in runs)
        ok = len(labels) == 1
        unstable += not ok
        L.append(f"| {c.id} | {', '.join(f'{k} x{v}' for k, v in labels.most_common())} | "
                 f"{confs[0]:.2f} / {statistics.median(confs):.2f} / {confs[-1]:.2f} | {'yes' if ok else '**no**'} |")
    L += [f"\n{unstable} of {len(claims)} claims changed label across {a.runs} identical runs.\n",
          f"## Policy action across runs (tau_review={FROZEN.tau_review:g}, tau_badge={FROZEN.tau_badge:g})\n",
          "| run | " + " | ".join(accessions) + " |", "|---|" + "---|" * len(accessions)]
    for i, r in enumerate(runs, 1):
        groups = group_by_accession(record, claims, r, evidence)
        cells = []
        for acc in accessions:
            d = decide(*groups.get(acc, ([], [])), FROZEN)
            cells.append(f"{d['action']} (contradict {d['details']['contradict']:.2f}, net {d['net']:+.2f})")
        L.append(f"| {i} | " + " | ".join(cells) + " |")
    text = "\n".join(L) + "\n"
    print(text)
    if a.out:
        p = pathlib.Path(a.out)
        old = p.read_text() if p.exists() else ""
        tail = "\n" + KEEP_MARKER + old.split(KEEP_MARKER, 1)[1] if KEEP_MARKER in old else ""
        p.write_text(text + tail)
        print("wrote", a.out, "(kept hand-written tail)" if tail else "", file=sys.stderr)


if __name__ == "__main__":
    main()
