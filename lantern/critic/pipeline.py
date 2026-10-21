"""The critic step, end to end: claims -> retrieval -> judge -> frozen policy -> annotated record.

Degrades to "keep" at every failure (no index, no client, judge error): a critic that cannot run must not change a result.
The record's shortlist, evidence and numbers are never edited. The only effect on ranking is `policy.apply_to_ranking`,
which can move a contradicted candidate behind the others and can never promote one.
"""
from __future__ import annotations

import copy
from dataclasses import asdict

from .claims import claims_from_record
from .judge import judge
from .lineage import load_lineage
from .policy import FROZEN, Params, apply_to_ranking, decide
from .retrieval import retrieve
from .types import Verdict

CRITIC_VERSION = "critic-0.1"
COMMENTARY_IS_NOT_VALIDATION = (
    "Literature commentary from an automated critic. Evidence is abstract-level and often preprint; absence of a paper "
    "is not evidence; sources the rules were derived from count at a reduced weight. It can flag a candidate for review "
    "and never raises a rank or changes a number.")


def critique(record: dict, client, index, *, params: Params = FROZEN, lineage: set[str] | None = None,
             k: int = 4, max_claims: int = 12) -> dict:
    """Return a deep copy of `record` with a `critic` section and critic_* fields on shortlist candidates."""
    out = copy.deepcopy(record)
    lineage = load_lineage() if lineage is None else lineage
    claims = claims_from_record(record, max_claims=max_claims)
    section = {"version": CRITIC_VERSION, "note": COMMENTARY_IS_NOT_VALIDATION, "params": asdict(params),
               "claims": [c.as_dict() for c in claims], "verdicts": [], "evidence": {}, "decisions": {}, "ran": False}
    if not claims or index is None or client is None:
        section["skipped"] = ("no claims" if not claims else "no literature index" if index is None else "no judge client")
        out["critic"] = section
        return out
    ev, nxt = {}, 1
    for c in claims:
        ev[c.id] = retrieve(c, index, lineage, k=k, start=nxt)
        nxt += len(ev[c.id])
    verdicts = judge(claims, ev, client)
    section.update(ran=True, verdicts=[v.as_dict() for v in verdicts],
                   evidence={cid: [e.as_dict() for e in es] for cid, es in ev.items()})
    by_acc = _group_by_accession(record, claims, verdicts, ev)
    decisions = {acc: decide(vs, es, params) for acc, (vs, es) in by_acc.items()}
    section["decisions"] = decisions
    sl = out.get("shortlist") or {}
    if sl.get("candidates"):
        sl["candidates"] = apply_to_ranking(sl["candidates"], decisions)
    out["critic"] = section
    return out


def _group_by_accession(record: dict, claims, verdicts: list[Verdict], ev: dict) -> dict:
    """Attribute each claim to the proteins it is about.

    A site claim belongs to the structure it was measured on (the index in its source_field points into
    record["evidence"], whose entries carry the accession). A rule claim describes every selected candidate, so it is
    attached to all of them. Claims that map to no protein are dropped from the per-candidate decision but stay in the
    record's `verdicts` for reading.
    """
    import re
    vmap = {v.claim_id: v for v in verdicts}
    selected = [c["accession"] for c in (record.get("shortlist") or {}).get("candidates", []) if c.get("selected")]
    structures = [e.get("accession", "") for e in record.get("evidence", [])]
    groups: dict[str, tuple[list, list]] = {}
    for c in claims:
        m = re.match(r"evidence\[(\d+)\]", c.source_field or "")
        accs = [structures[int(m.group(1))]] if m and int(m.group(1)) < len(structures) else selected
        for acc in filter(None, accs):
            vs, es = groups.setdefault(acc, ([], []))
            if c.id in vmap:
                vs.append(vmap[c.id])
                es.extend(ev.get(c.id, []))
    return groups
