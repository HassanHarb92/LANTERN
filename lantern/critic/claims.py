"""Checkable claims derived from a discovery record, deterministically.

WHY NO MODEL HERE. A claim is the thing a verdict is about. If a model wrote the
claims, a confident "supports" could be a verdict on a sentence the pipeline never
said, and the trace from verdict back to number would run through prose. So every
claim is assembled from fields the deterministic pipeline already filled, and each
carries `source_field`, a path into the raw record (not the narration payload, which
renames fields and cuts each structure to 8 sites) that resolves to the number it
restates. A site missing a number yields no claim rather than a plausible one.

WHICH CLAIMS SURVIVE THE CAP. The canonical question measures 14 sites in 8FNR and 4
in 8FNS. Taken in record order, a cap of 12 would be all 8FNR and would drop the only
CN 10 site in the record. Sites are therefore interleaved across structures, and the
selection rules get reserved slots, because a rule is what a whole shortlist rests on.
"""
from __future__ import annotations

import re

from ..structure import DONOR_ELEMENTS, FIRST_SHELL_ANGSTROM
from .types import Claim

# Symbol -> name, so a query and a lexical check can meet a paper that writes
# "dysprosium" where the record writes "Dy". Lanthanides plus the two non-lanthanide
# metals that sit in this project's site tables.
ELEMENT_NAMES = {
    "LA": "lanthanum", "CE": "cerium", "PR": "praseodymium", "ND": "neodymium",
    "PM": "promethium", "SM": "samarium", "EU": "europium", "GD": "gadolinium",
    "TB": "terbium", "DY": "dysprosium", "HO": "holmium", "ER": "erbium",
    "TM": "thulium", "YB": "ytterbium", "LU": "lutetium", "Y": "yttrium",
    "CA": "calcium",
}
# Charges are stated only where the chemistry fixes them; any other metal is named
# bare rather than given an oxidation state the record does not carry.
TRIVALENT = frozenset(k for k in ELEMENT_NAMES if k != "CA")
CHARGE = {**{k: "3+" for k in TRIVALENT}, "CA": "2+"}

_DONOR_ORDER = "/".join(sorted(DONOR_ELEMENTS, key=lambda e: ("ONS" + e).index(e)))
DONOR_PHRASE = f"{_DONOR_ORDER} donors within {FIRST_SHELL_ANGSTROM:g} A"

# Citation markers like "[2]" or "[1, 3]" are evidence numbers, not measurements.
_CITATION = re.compile(r"\[\s*\d+(?:\s*[,;–-]\s*\d+)*\s*\]")
# A digit run glued to a preceding letter is part of an identifier (A201, Dy3+, 8FNR
# handled below), not a quantity. A leading minus is never read as a sign: "10-12" is
# a range, and a judge writing "-9" must still be caught as having written 9.
_NUMBER = re.compile(r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)(?!\.?\d)(?![A-Za-z]{2,})")


def numbers_in(text) -> list[float]:
    """Every non-negative quantity written in `text`, in order of appearance.

    Used to ask whether a model's rationale contains a number that came from
    nowhere, so it errs toward finding numbers: units ("3.2 A", "2.5A"), ranges
    ("10-12" gives 10 and 12) and "CN 9" all count. Citation brackets and digits
    inside identifiers (A201, 8FNR, Dy3+) do not, because they appear identically on
    both sides of the comparison and are not measurements.
    """
    if not isinstance(text, str) or not text:
        return []
    stripped = _CITATION.sub(" ", text)
    return [float(m.group(1)) for m in _NUMBER.finditer(stripped)]


def _number(value) -> float | None:
    """A finite real number from the record, or None. Bools are not numbers here."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if value == value and abs(value) != float("inf") else None


def _fmt(value: float) -> str:
    return f"{value:g}"


def _name_words(name) -> str:
    """Protein name as lowercase query words: "Lanmodulin (Hansschlegelia quercus)"."""
    return " ".join(re.findall(r"[a-z0-9]+", str(name or "").lower()))


def _ion_label(element: str) -> str:
    sym = element.upper()
    return element[:1].upper() + element[1:].lower() + CHARGE.get(sym, "")


def _site_claims(record: dict, ef_hand: bool) -> tuple[list[list[Claim]], list[list[Claim]]]:
    """Per-structure lists of coordination-number and donor-distance claims."""
    cn_lists, dist_lists = [], []
    for i, ev in enumerate(record.get("evidence") or []):
        if not isinstance(ev, dict) or ev.get("structure_kind") != "deposited":
            continue
        pdb = str(ev.get("pdb_id") or "").upper()
        if not pdb:
            continue
        cns, dists = [], []
        for j, site in enumerate(ev.get("sites") or []):
            element = str(site.get("deposited_element") or "").strip()
            if not element:
                continue
            sym = element.upper()
            ion = _ion_label(element)
            label = f"{site.get('chain', '')}{site.get('site', '')}"
            words = " ".join(w for w in (
                "lanthanide" if sym in TRIVALENT else "", sym.capitalize(),
                ELEMENT_NAMES.get(sym, ""), _name_words(ev.get("name")),
                "EF-hand" if ef_hand else "") if w)
            where = f"evidence[{i}].sites[{j}]"
            cn = _number(site.get("coordination_number"))
            if cn is not None:
                cns.append(Claim(
                    id="", kind="number", value=cn,
                    text=(f"Site {label} of {pdb} holds {ion} with coordination "
                          f"number {_fmt(cn)} ({DONOR_PHRASE})"),
                    query=f"{words} coordination number {_fmt(cn)}",
                    source_field=f"{where}.coordination_number"))
            dist = _number(site.get("mean_donor_distance_A"))
            if dist is not None:
                dists.append(Claim(
                    id="", kind="number", value=dist,
                    text=(f"Site {label} of {pdb} holds {ion} with a mean "
                          f"{ion}-donor distance of {_fmt(dist)} A"),
                    query=f"{words} metal oxygen bond distance {_fmt(dist)} A",
                    source_field=f"{where}.mean_donor_distance_A"))
        cn_lists.append(cns)
        dist_lists.append(dists)
    return cn_lists, dist_lists


def _interleave(lists: list[list[Claim]]) -> list[Claim]:
    """Round-robin across structures so no single structure fills the cap."""
    out, depth = [], max((len(x) for x in lists), default=0)
    for k in range(depth):
        out += [x[k] for x in lists if k < len(x)]
    return out


def _rule_claims(record: dict) -> list[Claim]:
    """One claim per selection rule that every selected candidate passed.

    The claim restates the rule's own question and the values the record measured
    for the selected proteins; it adds no interpretation of what the rule means.
    """
    shortlist = record.get("shortlist") or {}
    selected = [c for c in shortlist.get("candidates") or []
                if isinstance(c, dict) and c.get("selected")]
    claims = []
    for r_idx, rule in enumerate(shortlist.get("rules") or []):
        rid, question = rule.get("id"), str(rule.get("question") or "").strip()
        if not rid or not question:
            continue
        measured = []
        for c in selected:
            row = next((x for x in c.get("rules") or [] if x.get("id") == rid), None)
            if row is None or row.get("verdict") != "pass":
                measured = []
                break
            value = _number(row.get("measured"))
            if value is not None:
                measured.append(f"{_fmt(value)} in {c.get('accession')}")
        if not measured:
            continue
        content = " ".join(w for w in re.findall(r"[a-z0-9-]+", question.lower())
                           if w not in _QUESTION_WORDS)
        claims.append(Claim(
            id="", kind="qualitative",
            text=(f"Lanthanide-binding proteins of the lanmodulin architecture answer "
                  f"yes to the design rule '{question}' (measured "
                  f"{', '.join(measured)})"),
            query=f"lanmodulin lanthanide {content}",
            source_field=f"shortlist.rules[{r_idx}]"))
    return claims


_QUESTION_WORDS = frozenset(
    "is it does are do the a an of than at least two carry".split())


def claims_from_record(record: dict, max_claims: int = 12) -> list[Claim]:
    """Deterministic claims for the critic, ids "c1".."cN" in a fixed order.

    Order: coordination numbers (interleaved across structures), then rule claims,
    then mean donor distances. Rule claims keep their slots under the cap; the rest
    is filled by coordination numbers first, because those are the numbers the
    page leads with. A record that was not answered, or has neither evidence nor a
    shortlist, gives [].
    """
    if not isinstance(record, dict) or max_claims < 1:
        return []
    rules_text = " ".join(str(r.get("question", "")) for r in
                          ((record.get("shortlist") or {}).get("rules") or []))
    cn_lists, dist_lists = _site_claims(record, "EF-hand" in rules_text)
    rules = _rule_claims(record)
    sites = _interleave(cn_lists) + _interleave(dist_lists)

    def unique(items):
        seen, out = set(), []
        for c in items:
            if c.text not in seen:
                seen.add(c.text)
                out.append(c)
        return out

    rules = unique(rules)[:max_claims]
    sites = [c for c in unique(sites) if c.text not in {r.text for r in rules}]
    budget = max_claims - len(rules)
    chosen_sites = sites[:budget]
    cn_part = [c for c in chosen_sites if c.source_field.endswith("coordination_number")]
    dist_part = [c for c in chosen_sites if not c.source_field.endswith("coordination_number")]
    ordered = cn_part + rules + dist_part
    return [Claim(id=f"c{k}", text=c.text, kind=c.kind, query=c.query,
                  source_field=c.source_field, value=c.value)
            for k, c in enumerate(ordered, start=1)]
