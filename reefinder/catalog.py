"""Bundled protein sets loaded from data/.

Two sets, kept apart on purpose. The reference set holds authentic sequences
and is what the offline view screens. The synthetic set is fixture data for
tests and must never be presented as real proteins.
"""
import json
from dataclasses import fields
from pathlib import Path
from .models import Protein

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REFERENCE_PATH = DATA_DIR / "reference_proteins.json"
SYNTHETIC_PATH = DATA_DIR / "synthetic_examples.json"

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
