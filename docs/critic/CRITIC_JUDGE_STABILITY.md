# Critic judge stability

Question: `proteins for capturing Ce3+`  
Judge: `claudeopus5`  
Runs: 5, one retrieval reused by all of them.

Reproducibility only. A claim can be stably wrong; accuracy needs hand labels.

## Label across runs

| claim | labels | confidence min/median/max | stable |
|---|---|---|---|
| c1 | no_evidence x3, supports x2 | 0.35 / 0.75 / 0.75 | **no** |
| c2 | no_evidence x5 | 0.00 / 0.75 / 0.75 | yes |
| c3 | no_evidence x5 | 0.00 / 0.75 / 0.75 | yes |
| c4 | no_evidence x5 | 0.00 / 0.75 / 0.75 | yes |
| c5 | no_evidence x5 | 0.00 / 0.75 / 0.75 | yes |
| c6 | no_evidence x5 | 0.00 / 0.70 / 0.70 | yes |
| c7 | supports x4, no_evidence x1 | 0.00 / 0.75 / 0.78 | **no** |
| c8 | no_evidence x4, supports x1 | 0.45 / 0.55 / 0.60 | **no** |
| c9 | no_evidence x5 | 0.80 / 0.85 / 0.90 | yes |
| c10 | no_evidence x5 | 0.80 / 0.85 / 0.90 | yes |
| c11 | no_evidence x5 | 0.80 / 0.85 / 0.90 | yes |
| c12 | no_evidence x5 | 0.80 / 0.85 / 0.90 | yes |

3 of 12 claims changed label across 5 identical runs.

## Policy action across runs (tau_review=0.5, tau_badge=0.5)

| run | A0A4V2JDD3 | C5B164 |
|---|---|---|
| 1 | keep (contradict 0.00, net +0.00) | keep (contradict 0.00, net +0.00) |
| 2 | badge (contradict 0.00, net +1.45) | badge (contradict 0.00, net +1.05) |
| 3 | badge (contradict 0.00, net +0.62) | badge (contradict 0.00, net +0.62) |
| 4 | badge (contradict 0.00, net +0.60) | badge (contradict 0.00, net +0.60) |
| 5 | badge (contradict 0.00, net +1.02) | badge (contradict 0.00, net +0.68) |

<!-- keep below: written by hand, preserved across reruns of the script above -->

## What two batches of five runs show

The table above is the second batch of five. An earlier batch of five — same code, same
question, same cached retrieval, run by this same probe before it was promoted into
`scripts/` — gave a different answer, and not merely different verdicts: a different set
of unstable claims.

| claim | batch A (5 runs) | batch B (5 runs, table above) |
|---|---|---|
| c1 | supports x4, no_evidence x1 | no_evidence x3, supports x2 |
| c2 | no_evidence x3, **contradicts x2** | no_evidence x5 |
| c4 | no_evidence x3, supports x2 | no_evidence x5 |
| c7 | supports x5 | supports x4, no_evidence x1 |
| c8 | supports x3, no_evidence x2 | no_evidence x4, supports x1 |

Four of twelve claims moved in batch A, three in batch B, and only c1 and c8 moved in
both. *Which* claims are unreliable is itself not reproducible, so one stability run
understates the problem: across ten runs the judge has disagreed with itself about five
of the twelve claims.

**The one informative verdict is the least reproducible.** c2 — "Dy3+ in lanmodulin
EF-hand sites has coordination number 7" — is the critic's only true positive. 8FNR
really does contain sites at CN 7 and CN 4, below the 8–9 the literature reports, and
surfacing that disagreement is the entire purpose of a `contradicts`. It contradicted in
2 of 5 runs in batch A and in 0 of 5 in batch B. The claims the judge is *stable* on are
the ones it has nothing to say about.

**The veto is being decided by noise, not by signal.** `tau_review` is 0.50, and the
contradiction mass for A0A4V2JDD3 on this one fixed input has now been measured at 0.00,
0.40, 0.45, and — in the live run that exposed the policy bug fixed in `14e4178` — above
0.50. The same protein on the same evidence has come out `keep` (batch B, run 1), `badge`
(ten runs, one of them at contradict 0.45, five hundredths short of the veto) and
`review` (once). A threshold the quantity straddles is not thresholding anything.

Temperature is not the cause. The request body was checked live and carries
`{'max_tokens': 1000, 'temperature': 0.2}`, sent and accepted, not silently dropped.

## What this blocks

Step 5 of the handoff — passing verdicts into the narration. A sentence whose label
changes between identical runs would make the user-visible output irreproducible, which
is the one property the rest of the spine exists to guarantee: every number on the page
traces to a measurement that can be recomputed. The critic is contained today only
because nothing downstream reads it.

Step 4 (hand labels) has to come first, and the measurement above changes how it should
be done: labels need to be collected per claim *over repeated runs*, not once. A single
run cannot score a judge that disagrees with itself, and an accuracy number computed from
one pass would be reporting a coin flip to two decimal places.

## Reproducing

```
python scripts/critic_judge_stability.py --runs 5 --provider argo --out docs/critic/CRITIC_JUDGE_STABILITY.md
```

Crossref responses come from `.critic_cache/`, so retrieval is fixed and only the judge
varies. The generated tables above are replaced on each run; everything below the marker
is carried through.
