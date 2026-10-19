"""Fetch and inspect publicly deposited PDB structures."""
import io
import requests
from Bio.PDB import PDBParser


def fetch_pdb(pdb_id: str, timeout: int = 25) -> str:
    if not pdb_id or len(pdb_id) != 4 or not pdb_id.isalnum():
        raise ValueError("PDB ID must be four letters/digits")
    r = requests.get(f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb", timeout=timeout)
    r.raise_for_status()
    if not ("ATOM  " in r.text or "HETATM" in r.text):
        raise ValueError("No atomic coordinates found in PDB response")
    return r.text


def binding_neighborhood(pdb_text: str, radius_angstrom: float = 4.0) -> list[dict]:
    """Residues near existing lanthanide HETATM ions; NOT hypothetical metal docking."""
    from numpy.linalg import norm
    structure = PDBParser(QUIET=True).get_structure("protein", io.StringIO(pdb_text))
    model = next(structure.get_models())
    atoms = list(model.get_atoms())
    # PDB element symbol may be absent; restrict to explicitly labelled lanthanide residue names.
    symbols = {"LA", "CE", "PR", "ND", "SM", "EU", "GD", "TB", "DY", "HO", "ER", "TM", "YB", "LU"}
    ions = [a for a in atoms if a.parent.id[0] != " " and a.parent.resname.strip().upper() in symbols]
    out = []
    for ion in ions:
        residues = {}
        for atom in atoms:
            residue = atom.parent
            if residue.id[0] != " ":
                continue
            dist = float(norm(atom.coord - ion.coord))
            if dist <= radius_angstrom:
                chain = residue.parent.id
                key = (chain, residue.id[1], residue.resname)
                residues[key] = min(dist, residues.get(key, 1e9))
        out.append({"metal": ion.parent.resname, "chain": ion.parent.parent.id,
                    "site": str(ion.parent.id[1]),
                    "neighbors": [{"chain": c, "residue_number": n, "residue": r, "minimum_atom_distance_A": round(d, 2)}
                                  for (c, n, r), d in sorted(residues.items())]})
    return out
