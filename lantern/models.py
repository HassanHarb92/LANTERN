from dataclasses import dataclass, asdict, field
from typing import Optional

@dataclass
class Protein:
    accession: str
    name: str
    organism: str
    sequence: str = ""
    pdb_id: Optional[str] = None
    # Every structure UniProt cross-references for this entry, as
    # {id, method, resolution_A}. `pdb_id` is whichever one
    # uniprot.choose_structure picked; the rest are kept so a page can say
    # what was deposited and not measured, instead of presenting one
    # structure as though it were the only one.
    pdb_options: list[dict] = field(default_factory=list)
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
    # Residue counts at EF-loop position 9, the position that actually
    # discriminates. Reported rather than folded into the score: it is
    # evidence for a reader, not a term in the arithmetic.
    position_9: dict[str, int] = field(default_factory=dict)

    def as_dict(self):
        d = asdict(self)
        d.update({"name": self.protein.name, "organism": self.protein.organism,
                  "accession": self.protein.accession, "pdb_id": self.protein.pdb_id})
        return d
