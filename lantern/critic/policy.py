"""Decision policy of the literature critic: verdicts in, one of keep / badge / review out.

THE CONTRACT. The critic is commentary. This module may BADGE a candidate (the literature supports it) or DEMOTE it to
"review" (the literature contradicts it). It never raises a rank and never changes a number; `apply_to_ranking` can only
push review candidates behind the rest, and the order among everything else is left exactly as the pipeline produced it.

WHY A VETO AND NOT A BOOST. Absence of papers is not evidence: a candidate nobody has written about is unstudied, not
wrong, so "no_evidence" never moves anything. And the literature is biased toward reported successes, so agreement is
cheap and a clean contradiction is the rarer, more informative signal. Support is therefore only allowed to attach a
badge (extra information shown next to the score), while contradiction is allowed to ask a human to look.

WHY LINEAGE IS DISCOUNTED. A rule such as "CN >= 9" or the loop-spacing rule was derived from particular papers. Retrieving
those papers and finding that they agree with the rule is circular, so a record flagged `Evidence.lineage` counts with
weight alpha_lineage (0.3) of an external record (w_external = 1.0). Discounting alone is not enough, because enough
lineage papers would still add up to a badge; so a badge additionally requires `min_independent` distinct non-lineage
supporting sources, and lineage-only support can never badge. Lineage evidence can still count against a candidate, at
the same reduced weight.

TRAINABLE LATER. Every number is a field of `Params`, frozen at the defaults in `FROZEN` for now. `net_evidence`,
`decide` and `objective` are pure functions of a parameter vector, so a Gaussian-process / Bayesian optimiser (skopt,
GPyOpt, BoTorch) can minimise `objective(vec, cases)` over the box `PARAM_BOUNDS` without touching anything else here.
No optimiser is imported. The loss counts false negatives once and false positives twice, because wrongly demoting a
good candidate costs more than missing a bad one, plus a small L2 pull toward the defaults so a sparse case set cannot
drive the parameters to extremes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from .types import Evidence, Verdict

ACTIONS = ("keep", "badge", "review")

_SIGN = {"supports": 1.0, "contradicts": -1.0, "no_evidence": 0.0}

# Continuous, tunable parameters. w_external is fixed at 1.0 (it only sets the unit), min_independent is an integer.
PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "alpha_lineage": (0.0, 1.0),
    "preprint_discount": (0.05, 1.0),
    "conf_floor": (0.0, 0.95),
    "tau_review": (0.05, 5.0),
    "tau_badge": (0.05, 5.0),
    "relevance_floor": (0.0, 1.0),
}


@dataclass(frozen=True)
class Params:
    alpha_lineage: float = 0.3        # weight of lineage evidence relative to external
    w_external: float = 1.0           # unit weight of an external record
    preprint_discount: float = 0.8    # multiplier on a preprint's weight
    conf_floor: float = 0.3           # verdicts below this confidence are ignored
    relevance_floor: float = 0.0      # cited evidence scoring below this is ignored
    tau_review: float = 0.5           # net <= -tau_review -> review
    tau_badge: float = 0.5            # net >= +tau_badge (and independent support) -> badge
    min_independent: int = 1          # distinct non-lineage supporting sources needed to badge

    def __post_init__(self):
        if not 0.0 <= self.alpha_lineage <= 1.0:
            raise ValueError("alpha_lineage must be in [0, 1]")
        if self.w_external < 0:
            raise ValueError("w_external must be >= 0")
        if not 0.0 < self.preprint_discount <= 1.0:
            raise ValueError("preprint_discount must be in (0, 1]")
        if not 0.0 <= self.conf_floor <= 1.0:
            raise ValueError("conf_floor must be in [0, 1]")
        if self.relevance_floor < 0:
            raise ValueError("relevance_floor must be >= 0")
        if self.tau_review <= 0 or self.tau_badge <= 0:
            raise ValueError("tau_review and tau_badge must be > 0")
        if isinstance(self.min_independent, bool) or not isinstance(self.min_independent, int) \
                or self.min_independent < 0:
            raise ValueError("min_independent must be an int >= 0")

    @staticmethod
    def names() -> list[str]:
        return list(PARAM_BOUNDS)

    def to_vector(self) -> list[float]:
        return [float(getattr(self, n)) for n in PARAM_BOUNDS]

    @classmethod
    def from_vector(cls, vec) -> "Params":
        """Build Params from a vector ordered as `names()`. Values are clipped to PARAM_BOUNDS; non-tunable fields
        keep their defaults."""
        vec = list(vec)
        if len(vec) != len(PARAM_BOUNDS):
            raise ValueError(f"expected a vector of length {len(PARAM_BOUNDS)}, got {len(vec)}")
        kw = {n: min(max(float(v), lo), hi) for (n, (lo, hi)), v in zip(PARAM_BOUNDS.items(), vec)}
        return cls(**kw)


FROZEN = Params()


def _evidence_weight(ev: Evidence, p: Params) -> float:
    w = p.alpha_lineage * p.w_external if ev.lineage else p.w_external
    return w * (p.preprint_discount if ev.preprint else 1.0)


def net_evidence(verdicts: list[Verdict], evidence: list[Evidence], params: Params = FROZEN) -> dict:
    """Weighted net of the verdicts for ONE candidate. Positive means literature supports, negative contradicts."""
    by_n: dict[int, Evidence] = {}
    for e in evidence:
        by_n.setdefault(e.n, e)
    parts = []
    support = contradict = 0.0
    independent: set[str] = set()
    lineage_support = False
    for v in verdicts:
        part = {"claim_id": v.claim_id, "label": v.label, "confidence": v.confidence, "contribution": 0.0,
                "weights": [], "used": [], "ignored": ""}
        parts.append(part)
        if v.confidence < params.conf_floor:
            part["ignored"] = "confidence below conf_floor"
            continue
        sign = _SIGN[v.label]
        if sign == 0.0:
            part["ignored"] = "no_evidence"
            continue
        used = []
        for n in v.cited:
            ev = by_n.get(n)
            if ev is None or ev.score < params.relevance_floor:
                continue
            used.append(ev)
        if not used:
            part["ignored"] = "cites no valid evidence"
            continue
        weights = [_evidence_weight(e, params) for e in used]
        contribution = sign * v.confidence * (sum(weights) / len(weights))
        part["contribution"] = contribution
        part["weights"] = weights
        part["used"] = [e.n for e in used]
        if sign > 0:
            support += contribution
            for e in used:
                if e.lineage:
                    lineage_support = True
                else:
                    independent.add(e.cid)
        else:
            contradict += -contribution
    return {
        "net": support - contradict,
        "support": support,
        "contradict": contradict,
        "independent_support": len(independent),
        "lineage_only_support": lineage_support and not independent,
        "parts": parts,
    }


def _reason(action: str, d: dict, p: Params) -> str:
    net = d["net"]
    note = ""
    if d.get("_lineage"):
        note = (f" Lineage sources (papers the rule was derived from) count at {p.alpha_lineage:g} of an external "
                f"source's weight.")
    if action == "review":
        # Report the quantity the veto actually tested. The veto reads contradiction
        # mass, so a candidate with more support than contradiction still crosses it,
        # and explaining it with the net rule prints an inequality that is false: the
        # first live review read "net evidence +0.52 <= -0.5".
        return (f"Literature contradicts this candidate (contradiction weight "
                f"{d['contradict']:.2f} >= {p.tau_review:g}, net evidence {net:+.2f}); "
                f"demoted to human review, numbers unchanged.{note}")
    if action == "badge":
        return (f"Literature supports this candidate (net evidence {net:+.2f} >= {p.tau_badge:g}) with "
                f"{d['independent_support']} independent source(s); badge only, rank unchanged.{note}")
    if net >= p.tau_badge:
        if d["lineage_only_support"]:
            return (f"Support (net {net:+.2f}) comes only from lineage sources, which cannot confirm the rule they "
                    f"were derived from; not badged.{note}")
        return (f"Support (net {net:+.2f}) has {d['independent_support']} independent source(s), below the "
                f"{p.min_independent} required to badge; kept.{note}")
    if all(part["contribution"] == 0.0 for part in d["parts"]):
        return ("No usable evidence either way. Absence of papers is not evidence, so the candidate is kept "
                "unchanged.")
    return f"Net evidence {net:+.2f} is within the thresholds (-{p.tau_review:g}, {p.tau_badge:g}); kept.{note}"


def decide(verdicts: list[Verdict], evidence: list[Evidence], params: Params = FROZEN) -> dict:
    """Turn verdicts into one action: keep, badge or review. Never anything else."""
    d = net_evidence(verdicts, evidence, params)
    # A veto reads the contradiction mass, not the net: summed over many claims a net lets nine agreeing verdicts
    # drown one confident contradiction, which is exactly the claim a human should look at.
    if d["contradict"] >= params.tau_review:
        action = "review"
    elif d["net"] >= params.tau_badge and d["independent_support"] >= params.min_independent \
            and not d["lineage_only_support"]:
        action = "badge"
    else:
        action = "keep"
    # Lineage is mentioned in the reason only when a lineage record actually carried weight.
    by_n = {e.n: e for e in evidence}
    d_for_reason = dict(d)
    d_for_reason["_lineage"] = any(
        by_n[n].lineage for part in d["parts"] if part["contribution"] != 0.0 for n in part["used"])
    reason = _reason(action, d_for_reason, params)
    return {"action": action, "net": d["net"], "reason": reason, "details": d, "params": asdict(params)}


def apply_to_ranking(candidates: list[dict], decisions: dict[str, dict]) -> list[dict]:
    """Same order as given, except review candidates move behind all others (stable within each group).

    Returns copies with `critic_action` and `critic_reason` added. Matching key is candidate["accession"]; a candidate
    without a decision is kept. Nothing is ever promoted: non-review candidates keep their relative order.
    """
    kept, demoted = [], []
    for c in candidates:
        dec = decisions.get(c.get("accession"))
        action = dec["action"] if dec else "keep"
        if action not in ACTIONS:
            action = "keep"
        out = dict(c)
        out["critic_action"] = action
        out["critic_reason"] = dec.get("reason", "") if dec else "No critic decision for this candidate; kept."
        (demoted if action == "review" else kept).append(out)
    return kept + demoted


def evaluate(params: Params, cases: list[dict]) -> dict:
    """Confusion counts treating "review" as the positive class (should_flag True = literature contradicts)."""
    tp = fp = fn = tn = 0
    for c in cases:
        flagged = decide(c["verdicts"], c["evidence"], params)["action"] == "review"
        if c["should_flag"]:
            tp, fn = (tp + 1, fn) if flagged else (tp, fn + 1)
        else:
            fp, tn = (fp + 1, tn) if flagged else (fp, tn + 1)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0}


def objective(vec, cases: list[dict]) -> float:
    """Loss to minimise: (FN + 2 FP) / n plus 0.01 * squared distance from the defaults, each axis scaled by its
    bound range. Lower is better. Suitable for skopt / GPyOpt / BoTorch over PARAM_BOUNDS."""
    if not cases:
        raise ValueError("objective needs at least one case")
    params = Params.from_vector(vec)
    m = evaluate(params, cases)
    loss = (m["fn"] + 2 * m["fp"]) / len(cases)
    default = FROZEN.to_vector()
    penalty = sum(((x - d) / (hi - lo)) ** 2
                  for x, d, (lo, hi) in zip(params.to_vector(), default, PARAM_BOUNDS.values()))
    return loss + 0.01 * penalty
