"""Fetch and inspect publicly deposited PDB structures."""
import io
from pathlib import Path

import requests
from Bio.PDB import PDBParser, MMCIFParser

# Structures prefetched by scripts/prefetch_structures.py, so the demo runs
# without a network. Cached files are verbatim RCSB downloads, never edited.
STRUCTURE_CACHE = Path(__file__).resolve().parent.parent / "data" / "structures"

# Verified PDB chemical-component codes for rare-earth ions, mapped to element.
# Several elements carry two codes that must be merged, erbium is ER3 with no
# plain ER, and yttrium is YT3. Matching on element symbol instead would both
# miss sites and pull in unrelated organic components that happen to be called
# LA3, ND3, TM3, SC or Y.
REE_LIGAND_CODES = {
    "LA": "La", "CE": "Ce", "PR": "Pr", "ND": "Nd", "SM": "Sm",
    "EU": "Eu", "EU3": "Eu", "GD": "Gd", "GD3": "Gd", "TB": "Tb",
    "DY": "Dy", "HO": "Ho", "HO3": "Ho", "ER3": "Er",
    "YB": "Yb", "YB2": "Yb", "LU": "Lu", "YT3": "Y",
}

# Lanthanides are hard acids: first-shell donors are overwhelmingly O, with
# occasional N and rare S. Counting every nearby atom instead would include
# carboxylate carbons, which sit only ~0.4 A behind their own oxygens.
DONOR_ELEMENTS = {"O", "N", "S"}
WATER_RESNAMES = {"HOH", "DOD", "WAT"}

# Ln-O first-shell distances cluster near 2.3-2.6 A. 3.2 A admits the whole
# first shell without reaching the second.
FIRST_SHELL_ANGSTROM = 3.2


def _valid_id(pdb_id: str) -> str:
    if not pdb_id or len(pdb_id) != 4 or not pdb_id.isalnum():
        raise ValueError("PDB ID must be four letters/digits")
    return pdb_id.upper()


def cached_structure(pdb_id: str) -> tuple[str, str] | None:
    """Return a prefetched structure, or None if it was never cached."""
    code = _valid_id(pdb_id)
    for fmt in ("pdb", "cif"):
        path = STRUCTURE_CACHE / f"{code}.{fmt}"
        if path.exists():
            return path.read_text(), fmt
    return None


def fetch_structure(pdb_id: str, timeout: int = 25,
                    use_cache: bool = True) -> tuple[str, str]:
    """Return (coordinate text, format) for a PDB entry, preferring mmCIF.

    Checks the local prefetch cache first so the bundled demo works offline,
    then falls back to RCSB.

    RCSB does not generate legacy .pdb files for large structures: 6EK0, 7K00
    and 3J3Q all answer 404 for .pdb and 200 for .cif. Trying .pdb first and
    falling back keeps small entries in the simpler format while making large
    ones work at all.
    """
    code = _valid_id(pdb_id)
    if use_cache:
        hit = cached_structure(code)
        if hit is not None:
            return hit
    errors = []
    for suffix, fmt in (("pdb", "pdb"), ("cif", "cif")):
        try:
            r = requests.get(f"https://files.rcsb.org/download/{code}.{suffix}", timeout=timeout)
            r.raise_for_status()
        except requests.RequestException as exc:
            errors.append(f"{suffix}: {type(exc).__name__}")
            continue
        text = r.text
        if fmt == "pdb" and not ("ATOM  " in text or "HETATM" in text):
            errors.append("pdb: no coordinate records")
            continue
        if fmt == "cif" and "_atom_site." not in text:
            errors.append("cif: no coordinate records")
            continue
        return text, fmt
    raise ValueError(f"No coordinates retrievable for {code} ({'; '.join(errors)})")


def fetch_pdb(pdb_id: str, timeout: int = 25) -> str:
    """Legacy-format coordinates only. Prefer fetch_structure, which falls back
    to mmCIF for entries RCSB does not publish as .pdb."""
    text, fmt = fetch_structure(pdb_id, timeout)
    if fmt != "pdb":
        raise ValueError(f"{pdb_id.upper()} is not available in legacy PDB format; use fetch_structure")
    return text


def _parse(text: str, fmt: str):
    parser = MMCIFParser(QUIET=True) if fmt == "cif" else PDBParser(QUIET=True)
    return parser.get_structure("protein", io.StringIO(text))


def binding_neighborhood(coordinate_text: str, fmt: str = "pdb",
                         radius_angstrom: float = FIRST_SHELL_ANGSTROM) -> list[dict]:
    """First-shell donor atoms around rare-earth ions already present in the
    deposited coordinates. This describes an experimentally observed site; it
    is not hypothetical metal docking.

    Waters are included and labelled. They are genuine first-shell donors --
    every Nd site in 8FNS has two -- and excluding them understates the
    coordination number, which is the descriptor that actually separates
    lanthanide sites from calcium sites.
    """
    from numpy.linalg import norm

    model = next(_parse(coordinate_text, fmt).get_models())
    atoms = list(model.get_atoms())
    ions = [a for a in atoms
            if a.parent.id[0] != " " and a.parent.resname.strip().upper() in REE_LIGAND_CODES]

    sites = []
    for ion in ions:
        resname = ion.parent.resname.strip().upper()
        donors = []
        for atom in atoms:
            if atom is ion:
                continue
            if (atom.element or "").strip().upper() not in DONOR_ELEMENTS:
                continue
            distance = float(norm(atom.coord - ion.coord))
            if distance > radius_angstrom:
                continue
            residue = atom.parent
            residue_name = residue.resname.strip().upper()
            if residue_name in WATER_RESNAMES:
                kind = "water"
            elif residue.id[0] == " ":
                kind = "protein"
            else:
                kind = "ligand"
            donors.append({"kind": kind, "chain": residue.parent.id,
                           "residue_number": residue.id[1], "residue": residue.resname,
                           "atom": atom.get_id(), "element": (atom.element or "").strip().upper(),
                           "distance_A": round(distance, 2)})

        donors.sort(key=lambda d: d["distance_A"])
        counts = {k: sum(1 for d in donors if d["kind"] == k) for k in ("protein", "water", "ligand")}
        sites.append({
            "metal": ion.parent.resname.strip(),
            "element": REE_LIGAND_CODES[resname],
            "chain": ion.parent.parent.id,
            "site": str(ion.parent.id[1]),
            "coordination_number": len(donors),
            "protein_donor_count": counts["protein"],
            "water_donor_count": counts["water"],
            "other_ligand_donor_count": counts["ligand"],
            "mean_donor_distance_A": round(sum(d["distance_A"] for d in donors) / len(donors), 2) if donors else None,
            "donors": donors,
        })
    return sites
