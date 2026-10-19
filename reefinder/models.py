from dataclasses import dataclass, asdict, field
from typing import Optional

@dataclass
class Protein:
    accession: str
    name: str
    organism: str
    sequence: str = ""
    pdb_id: Optional[str] = None
    source: str = "curated"
    evidence: str = "unreviewed hypothesis"
    source_url: str = ""
    notes: str = ""

@dataclass
class Candidate:
    protein: Protein
    score: float
    motif_count: int
    acidic_fraction: float
    flags: list[str] = field(default_factory=list)
    rationale: str = ""
    score_type: str = "sequence heuristic (unvalidated)"

    def as_dict(self):
        d = asdict(self)
        d.update({"name": self.protein.name, "organism": self.protein.organism,
                  "accession": self.protein.accession, "pdb_id": self.protein.pdb_id})
        return d
