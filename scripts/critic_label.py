"""Hand-label the critic's claims, then score the judge against your labels (ROADMAP M7, step 4).

    python scripts/critic_label.py make  [--out docs/critic/CRITIC_LABELS.md] [--question Q]...
    python scripts/critic_label.py score [--labels docs/critic/CRITIC_LABELS.md] [--runs 5] [--provider argo]

TWO STEPS ON PURPOSE. `make` is offline: it builds the sheet from the cached Crossref
responses, needs no key, and costs nothing. Fill it in before running `score`, because a
label written after reading the judge's answer is not an independent label.

The sheet shows each claim with the passages the judge is given, truncated exactly the
way the judge truncates them (judge._shown), so you are reading what it reads -- not the
full abstract it never saw. That distinction is what the snippet bug in 04bbf50 was.

`score` runs the judge several times rather than once, because it does not give the same
answer twice: see docs/critic/CRITIC_JUDGE_STABILITY.md. An accuracy figure from a single
pass would be reporting a coin flip to two decimal places. The report separates the two
ways the judge can be wrong -- disagreeing with you consistently (bias, fixable in the
prompt) and disagreeing with itself (noise, not fixable there).

Both steps rebuild claims and retrieval the same deterministic way from the same cache,
so the claim ids in the sheet still mean the same thing at score time.
"""
import argparse
import pathlib
import re
import sys
from collections import Counter
from dataclasses import replace

from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from lantern.critic.claims import claims_from_record  # noqa: E402
from lantern.critic.judge import _shown, judge  # noqa: E402
from lantern.critic.lineage import load_lineage  # noqa: E402
from lantern.critic.retrieval import retrieve  # noqa: E402
from lantern.critic.types import LABELS  # noqa: E402
from lantern.discover import answer  # noqa: E402
from lantern.llm import make_client  # noqa: E402
from lantern.scholarbud import BM25Index, Library  # noqa: E402

from scripts.critic_live_trial import cached_search  # noqa: E402  (shares the polite Crossref cache)

DEFAULT_QUESTIONS = ["proteins for capturing Ce3+"]
DEFAULT_SHEET = "docs/critic/CRITIC_LABELS.md"
# [ \t] rather than \s: \s matches newlines, so `\s*(\S*)` on an unfilled `label:` line
# runs past the blank line and reads the next word in the file as the label.
HEAD_RE = re.compile(r"^##[ \t]+(\S+)[ \t]+label:[ \t]*(\S*)[ \t]*$", re.M)


def build(questions, rows, cache):
    """[(claim, evidence)] for every claim of every question, in sheet order.

    Deterministic given the cache, so `make` and `score` agree on what `q1:c3` is.
    Mirrors lantern/critic/pipeline.py: one retrieval per claim, evidence numbered
    continuously across every question, because judge() batches claims from the whole
    list into one prompt and two passages sharing the number [3] in it would make a
    citation ambiguous.

    Every claim is re-identified as `q<n>:<id>`. claims_from_record numbers from c1 per
    record, so two questions would otherwise both yield a `c1` and collide in the
    evidence dict keyed by claim id -- quietly judging one claim against another's
    passages.
    """
    lineage, out, nxt = load_lineage(), [], 1
    for qi, q in enumerate(questions, 1):
        claims = claims_from_record(answer(q))
        lib = Library()
        for c in claims:
            for prefix in (None, "10.26434"):
                for p in cached_search(c.query, rows, prefix, cache):
                    lib.upsert(p)
        index = BM25Index(lib.all())
        for c in claims:
            ev = retrieve(c, index, lineage, k=4, start=nxt)
            nxt += len(ev)
            out.append((replace(c, id=f"q{qi}:{c.id}"), ev))
    return out


def make(a):
    rows = build(a.question, a.rows, pathlib.Path(a.cache))
    L = ["# Critic hand labels\n",
         f"Questions: {', '.join('`' + q + '`' for q in a.question)}  \nClaims: {len(rows)}\n",
         "Put one of `supports` / `contradicts` / `no_evidence` after `label:` on each `##` line.",
         "Leave it blank to skip that claim. Judge its agreement with **the passages printed",
         "underneath it** -- that is all the judge is shown, so a claim the literature answers",
         "elsewhere is still `no_evidence` here. Then:\n",
         "```\npython scripts/critic_label.py score --labels " + (a.out or DEFAULT_SHEET) + " --runs 5 --provider argo\n```\n",
         "---\n"]
    for c, ev in rows:
        L += [f"## {c.id}  label:\n", "CLAIM", f"  {c.text}\n",
              f"EVIDENCE -- {len(ev)} passage(s), exactly as the judge sees them"]
        if not ev:
            L.append("  (none retrieved; the judge is shown nothing, so no_evidence is the only honest label)")
        for e in ev:
            title, snippet = _shown(e)
            flags = ", ".join(filter(None, ["preprint" if e.preprint else "", "lineage" if e.lineage else ""]))
            L += [f"  [{e.n}] {e.doi or e.cid} | {e.year or 'n.d.'} | {e.source or 'unknown'} | BM25 {e.score:.1f}"
                  + (f" | {flags}" if flags else ""),
                  f"      {title}", ""]
            L += [f"      {line}" for line in _wrap(snippet or "(no abstract)")] + [""]
        L.append("---\n")
    pathlib.Path(a.out).write_text("\n".join(L))
    print(f"wrote {a.out}: {len(rows)} claims to label")
    if len(rows) < 30:
        print(f"ROADMAP M7 asks for at least 30; this sheet has {len(rows)}. Add more with "
              f"repeated --question to reach it.", file=sys.stderr)


def _wrap(s, width=104):
    words, line, out = s.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    return out + [line] if line else out


def read_labels(path):
    text = pathlib.Path(path).read_text()
    labels, bad = {}, []
    for key, value in HEAD_RE.findall(text):
        if not value:
            continue
        if value in LABELS:
            labels[key] = value
        else:
            bad.append((key, value))
    if bad:
        sys.exit("Not a valid label (use one of %s):\n  %s" % (" / ".join(LABELS),
                 "\n  ".join(f"{k}: {v!r}" for k, v in bad)))
    return labels


def score(a):
    labels = read_labels(a.labels)
    if not labels:
        sys.exit(f"No labels filled in {a.labels}. Put a label after `label:` on the `##` lines first.")
    rows = build(a.question, a.rows, pathlib.Path(a.cache))
    known = {c.id for c, _ in rows}
    if missing := sorted(set(labels) - known):
        sys.exit(f"{a.labels} labels claims this run does not produce: {', '.join(missing)}. "
                 f"Regenerate the sheet with `make` using the same --question list.")
    rows = [r for r in rows if r[0].id in labels]

    client = make_client(a.provider)
    if not client.configured():
        sys.exit("The judge provider is not configured (missing key or username). Fill in .env (see .env.example).")
    claims, evidence = [c for c, _ in rows], {c.id: ev for c, ev in rows}
    runs = []
    for i in range(a.runs):
        runs.append({v.claim_id: v.label for v in judge(claims, evidence, client)})
        print(f"  run {i + 1}/{a.runs} done", file=sys.stderr, flush=True)

    L = [f"# Judge vs hand labels\n",
         f"Labels: `{a.labels}` ({len(rows)} of {len(known)} claims labelled)  \n"
         f"Judge: `{getattr(client, 'model', '?')}`, {a.runs} run{'s' if a.runs != 1 else ''} "
         f"on one fixed retrieval.\n",
         "| claim | your label | judge across runs | matched |", "|---|---|---|---|"]
    hits = total = modal_hits = 0
    never, confusion = [], Counter()
    for c, _ in rows:
        mine, got = labels[c.id], Counter(r[c.id] for r in runs)
        n = got[mine]
        hits, total = hits + n, total + a.runs
        modal_hits += got.most_common(1)[0][0] == mine
        never += [c.id] if n == 0 else []
        for label, count in got.items():
            confusion[(mine, label)] += count
        L.append(f"| {c.id} | {mine} | {', '.join(f'{k} x{v}' for k, v in got.most_common())} | "
                 f"{'**' if n == 0 else ''}{n}/{a.runs}{'**' if n == 0 else ''} |")
    L += [f"\n**Run-level agreement: {hits}/{total} ({hits / total:.0%}).** "
          f"Modal-label agreement: {modal_hits}/{len(rows)}.\n"]
    if never and a.runs >= 3:
        L.append(f"Never matched in any of {a.runs} runs -- consistently wrong rather than noisy, so this "
                 f"is the prompt's problem and not the temperature's: {', '.join(never)}.\n")
    elif never:
        L.append(f"Did not match: {', '.join(never)}. With {a.runs} run"
                 f"{'s' if a.runs != 1 else ''} there is no telling a wrong answer from an unstable one; "
                 f"use --runs 3 or more before reading anything into that.\n")
    L += ["## Confusion (your label down, judge across; counted over every run)\n",
          "| | " + " | ".join(LABELS) + " |", "|---|" + "---|" * len(LABELS)]
    for mine in LABELS:
        L.append(f"| **{mine}** | " + " | ".join(str(confusion[(mine, j)]) for j in LABELS) + " |")
    L.append("\nOff-diagonal mass in the `no_evidence` row is the judge reading support that is not there; "
             "in the `supports`/`contradicts` rows it is the judge missing what is.\n")
    text = "\n".join(L) + "\n"
    print(text)
    if a.out:
        pathlib.Path(a.out).write_text(text)
        print("wrote", a.out, file=sys.stderr)


def main():
    load_dotenv()  # same reason as critic_live_trial.py: the credential lives in .env
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("make", "score"))
    ap.add_argument("--question", action="append", default=None, help="repeatable; more questions, more claims")
    ap.add_argument("--rows", type=int, default=15)
    ap.add_argument("--cache", default=".critic_cache")
    ap.add_argument("--labels", default=DEFAULT_SHEET, help="score: the filled-in sheet")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--provider", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    a.question = a.question or DEFAULT_QUESTIONS
    pathlib.Path(a.cache).mkdir(parents=True, exist_ok=True)
    if a.mode == "make":
        a.out = a.out or DEFAULT_SHEET
        make(a)
    else:
        score(a)


if __name__ == "__main__":
    main()
