"""Run the literature critic on a real discovery record and write a stage-by-stage markdown table.

    python scripts/critic_live_trial.py --out TRIAL.md [--provider argo|openai|anthropic] [--no-judge] [--question Q]
                                        [--rows 15] [--cache DIR]

Stages recorded: input question -> parsed plan -> claims derived from the measured record -> live Crossref/ChemRxiv retrieval
-> judge verdicts -> policy decision -> final shortlist order. Retrieval is live (Crossref, no key). The judge needs a
configured provider; with --no-judge (or no provider) the judge columns read "not run" and every decision stays keep.
Crossref responses are cached under --cache so a rerun is reproducible and polite.
"""
import argparse
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from lantern.critic.claims import claims_from_record  # noqa: E402
from lantern.critic.pipeline import critique  # noqa: E402
from lantern.critic.retrieval import retrieve  # noqa: E402
from lantern.discover import answer  # noqa: E402
from lantern.llm import make_client  # noqa: E402
from lantern.scholarbud import BM25Index, Library  # noqa: E402
from lantern.scholarbud.crossref import search  # noqa: E402
from lantern.scholarbud.types import Paper  # noqa: E402


def cached_search(query, rows, prefix, cache):
    key = hashlib.sha1(f"{query}|{rows}|{prefix}".encode()).hexdigest()[:16]
    f = cache / f"{key}.json"
    if f.exists():
        return [Paper(**d) for d in json.loads(f.read_text())]
    papers = search(query, rows=rows, prefix=prefix)
    f.write_text(json.dumps([{k: v for k, v in p.as_dict().items() if k != "cid"} for p in papers]))
    return papers


def cell(s, n=140):
    s = " ".join(str(s).split()).replace("|", "/")
    return s if len(s) <= n else s[: n - 1] + "…"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--question", default="proteins for capturing Ce3+")
    ap.add_argument("--provider", default=None)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--rows", type=int, default=15)
    ap.add_argument("--cache", default=".critic_cache")
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
    index = BM25Index(lib.all())

    client = None
    if not a.no_judge:
        try:
            client = make_client(a.provider)
        except Exception as e:
            sys.exit(f"Cannot build a judge client ({e}). Set LLM_PROVIDER and its key in .env, or pass --no-judge.")
        if not client.configured():
            sys.exit("The judge provider is not configured (missing key or username). Fill in .env (see .env.example), "
                     "or pass --no-judge to run retrieval only.")
        ok, detail = client.health()
        print(f"judge health: {ok} - {detail}")
        if not ok:
            sys.exit("The judge provider failed its health check; fix that first (network, key, model id).")
    out = critique(record, client, index, lineage=None)
    crit = out["critic"]
    verdicts = {v["claim_id"]: v for v in crit["verdicts"]}

    L = [f"# Critic live trial\n", f"Question: `{a.question}`  \nJudge: `{getattr(client, 'model', None) or 'NOT RUN (no configured provider)'}`  "
         f"\nLibrary: {len(lib)} records from live Crossref/ChemRxiv; evidence per claim: top 4 by BM25.\n",
         "## 1. Input and parsed plan\n", f"| field | value |\n|---|---|\n| target | {record['plan'].get('target')} |\n"
         f"| parsed_by | {record['plan'].get('parsed_by')} |\n| answered | {record['answered']} |\n",
         "## 2. Claims, retrieved evidence, judge and critic response\n",
         "| claim | measured source | retrieved evidence (top 3: DOI, year, score, lineage) | judge verdict | critic note |",
         "|---|---|---|---|---|"]
    for c in crit["claims"]:
        evs = crit["evidence"].get(c["id"], [])
        ev_txt = "; ".join(f"{e['doi'] or e['cid']} ({e['year']}, {e['score']:.1f}{', lineage' if e['lineage'] else ''}) {cell(e['title'], 60)}"
                           for e in evs[:3]) or "none"
        v = verdicts.get(c["id"])
        vt = f"{v['label']} (conf {v['confidence']:.2f}, cites {v['cited']})" if v else "not run"
        note = cell(v["rationale"], 100) if v and v["rationale"] else (v["downgraded"] if v else "")
        L.append(f"| {c['id']}: {cell(c['text'], 110)} | `{c['source_field']}` | {ev_txt} | {vt} | {cell(note, 100)} |")
    L += ["\n## 3. Policy decision per protein\n", "| accession | action | net | contradict | reason |", "|---|---|---|---|---|"]
    for acc, d in crit["decisions"].items():
        L.append(f"| {acc} | {d['action']} | {d['net']:.2f} | {d['details']['contradict']:.2f} | {cell(d['reason'], 130)} |")
    L += ["\n## 4. Final shortlist order (selected first)\n", "| rank | accession | name | rules | critic_action |", "|---|---|---|---|---|"]
    for i, c in enumerate(out["shortlist"]["candidates"], 1):
        L.append(f"| {i} | {c['accession']} | {cell(c['name'], 50)} | {c['passed']}/{c['of']} | {c.get('critic_action', 'keep')} |")
    L.append(f"\n_Numbers unchanged by the critic: {_unchanged(record, out)}_\n")
    pathlib.Path(a.out).write_text("\n".join(L))
    pathlib.Path(a.out).with_suffix(".json").write_text(json.dumps(crit, indent=1, default=str))
    labels = {}
    for v in crit["verdicts"]:
        labels[v["label"]] = labels.get(v["label"], 0) + 1
    print("verdicts:", labels, "| downgraded by post-check:", sum(1 for v in crit["verdicts"] if v["downgraded"]),
          "| actions:", {d["action"] for d in crit["decisions"].values()} or "none")
    print("wrote", a.out, "| judge:", getattr(client, "model", "not run"), "| claims:", len(claims), "| library:", len(lib))


def _unchanged(a, b):
    f = lambda r: [(e["accession"], s["site"], s["coordination_number"], s["mean_donor_distance_A"]) for e in r["evidence"] for s in e["sites"]]
    return f(a) == f(b)


if __name__ == "__main__":
    main()
