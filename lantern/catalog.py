"""Bundled protein sets loaded from data/.

Two sets, kept apart on purpose. The reference set holds authentic sequences
and is what the offline view screens. The synthetic set is fixture data for
tests and must never be presented as real proteins.
"""
import json
from dataclasses import fields
from functools import lru_cache
from pathlib import Path
from .models import Protein

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REFERENCE_PATH = DATA_DIR / "reference_proteins.json"
SYNTHETIC_PATH = DATA_DIR / "synthetic_examples.json"
REE_ENTRIES_PATH = DATA_DIR / "ree_pdb_entries.json"

_PROTEIN_FIELDS = {f.name for f in fields(Protein)}


def _load(path: Path) -> list[Protein]:
    payload = json.loads(Path(path).read_text())
    # Files carry a _provenance block alongside the records; older bare-list
    # files are still accepted.
    records = payload["proteins"] if isinstance(payload, dict) else payload
    # Records keep provenance keys the dataclass does not model, such as
    # uniprot_name; drop them here rather than widening Protein.
    return [Protein(**{k: v for k, v in r.items() if k in _PROTEIN_FIELDS})
            for r in records]


def provenance(path: Path = REFERENCE_PATH) -> dict:
    payload = json.loads(Path(path).read_text())
    return payload.get("_provenance", {}) if isinstance(payload, dict) else {}


def load_reference(path: Path = REFERENCE_PATH) -> list[Protein]:
    """Authentic sequences: two lanmodulins, two calcium proteins, two negatives."""
    return _load(path)


def load_synthetic(path: Path = SYNTHETIC_PATH) -> list[Protein]:
    """Synthetic fixtures. Never report a score over these as a finding."""
    return _load(path)


def load_demo(path: Path = REFERENCE_PATH) -> list[Protein]:
    """Default offline set. Authentic since M1; previously synthetic."""
    return load_reference(path)


# Which element is in which deposited file -- the fact a UniProt cross-reference
# does not carry, and whose absence uniprot.RESOLUTION_IS_THE_RULE apologises for
# in so many words. Without it "measure the sharpest structure" is the only rule
# available, and a user asking about one lanthanide is shown another with no way
# to tell that the swap happened.
#
# The enumeration is a snapshot, so a miss has two meanings and they are not the
# same: an entry present in it with no rare earth really holds none, while an
# entry absent from it is simply unknown to the snapshot -- a structure deposited
# after `retrieved_at_utc` reads the same as one holding nothing. Callers that act
# on a negative must say which of the two they saw, which is why known_entry() is
# public alongside the lookup itself.
@lru_cache(maxsize=1)
def _ree_entries() -> dict:
    payload = json.loads(REE_ENTRIES_PATH.read_text())
    return payload.get("entries", {})


def known_entry(pdb_id: str) -> bool:
    """Whether the rare-earth enumeration has heard of this PDB id at all."""
    return str(pdb_id).strip().upper() in _ree_entries()


def deposited_rare_earths(pdb_id: str) -> tuple[str, ...]:
    """Rare-earth element symbols deposited in one PDB entry, sorted.

    () for an entry the enumeration lists with no rare earth -- a true answer
    for a calcium structure -- and also for an entry it has never heard of,
    which is not the same thing. Ask known_entry() to tell those apart before
    reporting either as a fact about the protein.
    """
    entry = _ree_entries().get(str(pdb_id).strip().upper(), {})
    return tuple(sorted(entry.get("elements", [])))


# One structure per lanthanide that is measurably holding it, built by
# scripts/build_ion_structures.py. Separate from the enumeration above because
# it answers a different question: not "which entries contain this element"
# -- most of those contain it as a soaked phasing chelate the protein never
# touches -- but "which entry can this platform show a user as their own ion,
# held by a protein". The admission test is geometry-v2's own call, so the
# file records a measurement rather than somebody's shortlist.
ION_STRUCTURES_PATH = DATA_DIR / "ion_structures.json"


@lru_cache(maxsize=1)
def _ion_structures() -> dict:
    payload = json.loads(ION_STRUCTURES_PATH.read_text())
    return payload.get("ions", {})


def structure_search(ion: str) -> dict | None:
    """What the build script found for `ion`, whether or not it found one.

    None only when the ion was never searched. Everything else -- how many
    entries the index held, how many were measured, and what each rejection
    measured -- is here even on a failed search, because "no promethium
    structure has ever been deposited" and "every holmium entry turned out to
    be a soaked chelate" are both failures and are not the same failure.
    """
    record = _ion_structures().get(str(ion).strip())
    return dict(record) if record else None


def structure_holding(ion: str) -> dict | None:
    """The structure measured as holding `ion`, with how it was chosen.

    None when the search found nothing to admit, which is a real answer for
    Pm3+ -- no promethium structure has ever been deposited -- and a different
    real answer for an element whose every indexed entry turned out to be a
    chelate soak. The counts that tell those apart travel with the result.
    """
    record = _ion_structures().get(str(ion).strip())
    if not record or not record.get("chosen"):
        return None
    return dict(record["chosen"],
                entries_in_index=record.get("entries_in_index"),
                entries_tried=record.get("entries_tried"),
                rejected=record.get("rejected", []))


def entries_holding(element: str) -> list[dict]:
    """Every enumerated PDB entry containing `element`, sharpest first.

    Each row is the enumeration's own record plus its `id`. Entries stating no
    resolution sort last rather than first: None is not sharper than 1.4 A.
    """
    wanted = str(element).strip().capitalize()
    rows = [dict(record, id=pdb) for pdb, record in _ree_entries().items()
            if wanted in record.get("elements", [])]
    return sorted(rows, key=lambda r: (r["resolution_A"] is None,
                                       r["resolution_A"] or 0.0, r["id"]))
