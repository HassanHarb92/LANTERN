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
CN 10 site in the record. Coordination numbers are therefore grouped by (element, CN),
which keeps a rare CN as its own claim however late its site appears; donor distances
are still per site and interleaved across structures; and the selection rules get
reserved slots, because a rule is what a whole shortlist rests on.
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


def _site_rows(record: dict) -> list[dict]:
    """One row per measured site of a deposited structure, in record order.

    A site identical to one already seen in the same entry is dropped. Chain and
    number identify a site, so the repeat is the same site recorded twice, and a
    claim that counts it would overstate how often a coordination number was
    measured.
    """
    rows, seen = [], set()
    for i, ev in enumerate(record.get("evidence") or []):
        if not isinstance(ev, dict) or ev.get("structure_kind") != "deposited":
            continue
        pdb = str(ev.get("pdb_id") or "").upper()
        if not pdb:
            continue
        for j, site in enumerate(ev.get("sites") or []):
            element = str(site.get("deposited_element") or "").strip()
            if not element:
                continue
            row = {
                "where": f"evidence[{i}].sites[{j}]", "pdb": pdb, "name": ev.get("name"),
                "element": element, "cn": _number(site.get("coordination_number")),
                "label": f"{site.get('chain', '')}{site.get('site', '')}",
                "dist": _number(site.get("mean_donor_distance_A"))}
            key = (pdb, row["label"], element, row["cn"], row["dist"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows


def _query_words(element: str, name, ef_hand: bool) -> str:
    sym = element.upper()
    return " ".join(w for w in (
        "lanthanide" if sym in TRIVALENT else "", sym.capitalize(),
        ELEMENT_NAMES.get(sym, ""), _name_words(name),
        "EF-hand" if ef_hand else "") if w)


def _setting(name, ef_hand: bool) -> str:
    """How a claim names its setting ("lanmodulin EF-hand"), from record fields only."""
    word = next(iter(re.findall(r"[A-Za-z][A-Za-z-]+", str(name or ""))), "")
    return " ".join(w for w in (word.lower(), "EF-hand" if ef_hand else "") if w) or "protein"


def _cn_claims(rows: list[dict], ef_hand: bool) -> list[Claim]:
    """One claim per distinct (element, coordination number), not one per site.

    The first live judge run answered "no_evidence" to all nine per-site claims and was
    right to: no abstract states the coordination number of a named site in a named PDB
    entry. Several of the nine also restated the same (element, CN) pair, so the judge
    was asked one question repeatedly and no answerable question at all. Grouping drops
    the repeats and makes the ion and its coordination number the subject, which a paper
    can address; the trailing clause keeps the provenance and `source_field` still
    resolves to one measured site. Nothing is generalised beyond the record: the setting
    words come from the structure's own name and the rule text.

    Grouping also subsumes what `_interleave` protected coordination numbers from. A
    rare CN is now its own group rather than a late site of a long structure, so the cap
    can no longer drop it for being behind fourteen sites of 8FNR.
    """
    groups: dict = {}
    for row in rows:
        if row["cn"] is not None:
            groups.setdefault((row["element"].upper(), row["cn"]), []).append(row)
    claims = []
    for (_sym, cn), members in groups.items():
        first = members[0]
        count = len(members)
        claims.append(Claim(
            id="", kind="number", value=cn,
            text=(f"{_ion_label(first['element'])} in {_setting(first['name'], ef_hand)} "
                  f"sites has coordination number {_fmt(cn)} ({DONOR_PHRASE}), measured "
                  f"at {count} such site{'s' if count != 1 else ''} in "
                  f"{', '.join(sorted({m['pdb'] for m in members}))}"),
            query=f"{_query_words(first['element'], first['name'], ef_hand)} "
                  f"coordination number {_fmt(cn)}",
            source_field=f"{first['where']}.coordination_number"))
    return claims


def _dist_lists(rows: list[dict], ef_hand: bool) -> list[list[Claim]]:
    """Per-structure donor-distance claims, still one per site so they can interleave."""
    by_pdb: dict = {}
    for row in rows:
        if row["dist"] is None:
            continue
        ion = _ion_label(row["element"])
        by_pdb.setdefault(row["pdb"], []).append(Claim(
            id="", kind="number", value=row["dist"],
            text=(f"Site {row['label']} of {row['pdb']} holds {ion} with a mean "
                  f"{ion}-donor distance of {_fmt(row['dist'])} A"),
            query=f"{_query_words(row['element'], row['name'], ef_hand)} "
                  f"metal oxygen bond distance {_fmt(row['dist'])} A",
            source_field=f"{row['where']}.mean_donor_distance_A"))
    return list(by_pdb.values())


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

    Order: coordination numbers (one per distinct element and CN), then rule claims,
    then mean donor distances (one per site, interleaved across structures). Rule
    claims keep their slots under the cap; the rest is filled by coordination numbers
    first, because those are the numbers the page leads with. A record that was not
    answered, or has neither evidence nor a shortlist, gives [].
    """
    if not isinstance(record, dict) or max_claims < 1:
        return []
    rules_text = " ".join(str(r.get("question", "")) for r in
                          ((record.get("shortlist") or {}).get("rules") or []))
    ef_hand = "EF-hand" in rules_text
    rows = _site_rows(record)
    rules = _rule_claims(record)
    sites = _cn_claims(rows, ef_hand) + _interleave(_dist_lists(rows, ef_hand))

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
