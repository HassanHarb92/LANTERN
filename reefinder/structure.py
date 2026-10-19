"""Fetch and inspect publicly deposited PDB structures."""
import io
from pathlib import Path

import requests
from Bio.PDB import PDBParser, MMCIFParser

# Structures prefetched by scripts/prefetch_structures.py, so the demo runs
# without a network. Cached files are verbatim RCSB downloads, never edited.
STRUCTURE_CACHE = Path(__file__).resolve().parent.parent / "data" / "structures"

# Verified PDB chemical-component codes for *bare* rare-earth ions, mapped to
# element. Several elements carry two codes that must be merged, erbium is ER3
# with no plain ER, and yttrium has two: YT3 and Y1. Matching on element symbol
# instead would both miss sites and pull in unrelated organic components that
# happen to be called LA3, ND3, TM3, SC or Y.
#
# This list is complete as of 2026-10-19, established by enumerating every
# chemical component whose formula contains a lanthanide, Y or Sc (RCSB
# chemical formula search, match_subset) rather than by guessing codes --
# which is how Y1 came to be missing for 19 entries.
REE_LIGAND_CODES = {
    "LA": "La", "CE": "Ce", "PR": "Pr", "ND": "Nd", "SM": "Sm",
    "EU": "Eu", "EU3": "Eu", "GD": "Gd", "GD3": "Gd", "TB": "Tb",
    "DY": "Dy", "HO": "Ho", "HO3": "Ho", "ER3": "Er",
    "YB": "Yb", "YB2": "Yb", "LU": "Lu", "YT3": "Y", "Y1": "Y",
}

# The other eight rare-earth-containing components in the PDB, deliberately
# excluded: in every one the metal arrives pre-chelated by a synthetic cage,
# a polyoxometalate, a buffer molecule or fluoride, so its first shell is the
# reagent's donors and not the protein's. Including them would inflate the
# corpus with sites that teach the opposite of what this project is looking
# for. Kept by name so M2 can report *why* an entry was dropped.
#
# Note the absence of any bare Sc code: scandium appears in the PDB only as
# ScF4, so "no scandium entries" is a fact about the ion's chemistry here,
# not an omission in the list above.
CHELATED_REE_CODES = {
    "7MT": "Tb-Xo4 crystallophore (nucleating/phasing agent)",
    "WRT": "TbXo4-OH, same crystallophore family",
    "7PR": "praseodymium triacetate",
    "JGH": "Ce-substituted Keggin polyoxometalate",
    "K93": "Lu(III) macrocyclic cage complex",
    "T7K": "neutral Yb(III) caged complex",
    "YBT": "yttrium bis-tris, i.e. a buffer component",
    "SFL": "scandium tetrafluoride",
}

# Calcium, scanned only on request. It is not a rare earth; it is the ion the
# whole project has to discriminate against, and the clearest evidence is a
# structure containing both (9PI2: Nd3+ in EF1-3, Ca2+ in EF4, one crystal).
CONTRAST_LIGAND_CODES = {"CA": "Ca"}
ALL_METAL_CODES = {**REE_LIGAND_CODES, **CONTRAST_LIGAND_CODES}

# Lanthanides are hard acids: first-shell donors are overwhelmingly O, with
# occasional N and rare S. Counting every nearby atom instead would include
# carboxylate carbons, which sit only ~0.4 A behind their own oxygens.
DONOR_ELEMENTS = {"O", "N", "S"}
WATER_RESNAMES = {"HOH", "DOD", "WAT"}

# Donor-atom chemistry. Which *kind* of oxygen coordinates the ion separates
# lanthanide from calcium sites far better than how many do: across a 283-site
# Ln vs 1602-site Ca survey, side-chain carboxylate O outnumbers backbone
# carbonyl O 9.9:1 at lanthanide sites and only 1.4:1 at calcium sites. The
# mechanism is charge -- a neutral backbone carbonyl adds nothing to pocket
# charge, and pocket charge is the published determinant of Ln/Ca selectivity
# (Nikolova & Dudev, Int J Mol Sci 2023, 24, 6297).
CARBOXYLATE_ATOMS = {("ASP", "OD1"), ("ASP", "OD2"),
                     ("GLU", "OE1"), ("GLU", "OE2")}
SIDECHAIN_AMIDE_ATOMS = {("ASN", "OD1"), ("GLN", "OE1")}
HYDROXYL_ATOMS = {("SER", "OG"), ("THR", "OG1"), ("TYR", "OH")}
BACKBONE_CARBONYL_ATOMS = {"O", "OXT"}

# Ln-O first-shell distances cluster near 2.3-2.6 A. 3.2 A admits the whole
# first shell without reaching the second.
FIRST_SHELL_ANGSTROM = 3.2

# Burial shell. 8 A around the ion reaches roughly two residue layers past the
# first shell, which is the scale the Dudev selectivity argument operates on:
# a buried site cannot reorganise solvent to pay the desolvation penalty that
# discriminates Ln3+ from Ca2+.
BURIAL_RADIUS_ANGSTROM = 8.0

# Residues whose side chains carry formal charge at pH ~7, used for the
# second-shell charge count. First-shell charge is counted from donor
# chemistry instead -- see site_net_charge().
ANIONIC_RESIDUES = {"ASP", "GLU"}
CATIONIC_RESIDUES = {"LYS", "ARG"}


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


def _donor_class(donor: dict) -> str:
    """Chemical class of one first-shell donor atom."""
    if donor["kind"] != "protein":
        return donor["kind"]  # water / ligand
    key = (donor["residue"].strip().upper(), donor["atom"].strip().upper())
    if key in CARBOXYLATE_ATOMS:
        return "carboxylate"
    if key in SIDECHAIN_AMIDE_ATOMS:
        return "sidechain_amide"
    if key in HYDROXYL_ATOMS:
        return "hydroxyl"
    if donor["atom"].strip().upper() in BACKBONE_CARBONYL_ATOMS:
        return "backbone_carbonyl"
    return "other"


def donor_chemistry(donors: list[dict]) -> dict:
    """Classify a first shell by donor chemistry.

    Reports the two counts that actually separate lanthanide from calcium
    sites -- side-chain carboxylate O and backbone carbonyl O -- plus how many
    carboxylates are bidentate, which is a further 2.1x enrichment at Ln sites
    (55.8% vs 26.2%). Their ratio is deliberately *not* reduced to a single
    number per site: a site with zero backbone carbonyls is the interesting
    case, and dividing by it would discard exactly that signal. Aggregate the
    counts across sites instead.
    """
    classes = [_donor_class(d) for d in donors]
    counts = {name: classes.count(name) for name in
              ("carboxylate", "backbone_carbonyl", "sidechain_amide",
               "hydroxyl", "water", "ligand", "other")}

    # A carboxylate is bidentate when the same residue donates both its oxygens.
    carboxylate_residues: dict[tuple, set] = {}
    for donor, cls in zip(donors, classes):
        if cls != "carboxylate":
            continue
        key = (donor["chain"], donor["residue_number"], donor["residue"])
        carboxylate_residues.setdefault(key, set()).add(donor["atom"])
    bidentate = sum(1 for atoms in carboxylate_residues.values() if len(atoms) >= 2)

    glu = sum(1 for d, c in zip(donors, classes)
              if c == "carboxylate" and d["residue"].strip().upper() == "GLU")
    asp = counts["carboxylate"] - glu
    return {
        **counts,
        "carboxylate_residues": len(carboxylate_residues),
        "bidentate_carboxylates": bidentate,
        "monodentate_carboxylates": len(carboxylate_residues) - bidentate,
        "glu_carboxylate_O": glu,
        "asp_carboxylate_O": asp,
    }


def site_net_charge(chemistry: dict) -> dict:
    """Formal charge of the first shell, for the Dudev selectivity rule.

    Nikolova & Dudev (IJMS 2023, 24, 6297, DFT/PCM): "buried active centers
    with net charge of -4 or -3 are characterized by higher Ln3+ over Ca2+
    selectivity, whereas it is the opposite for sites with overall charge of
    -1." Charge and burial are a conjunction in that sentence, so both are
    computed and neither is reported alone.

    Counts carboxylate *residues*, not carboxylate oxygens. A bidentate Glu
    donates two oxygens and still carries one negative charge; counting atoms
    would double it and push every bidentate-rich lanthanide site into a
    charge class it does not occupy.

    Backbone carbonyls, side-chain amides, hydroxyls and waters are neutral.
    `unassigned_donors` counts first-shell donors whose charge this function
    does not model -- non-water heteroatom ligands, and anything `other`
    (His N, Cys S). When it is non-zero the charge is a model of part of the
    shell, not of the shell, and callers should say so rather than round it.
    """
    return {
        "net_charge": -chemistry["carboxylate_residues"],
        "anionic_groups": chemistry["carboxylate_residues"],
        "neutral_donors": (chemistry["backbone_carbonyl"]
                           + chemistry["sidechain_amide"]
                           + chemistry["hydroxyl"] + chemistry["water"]),
        "unassigned_donors": chemistry["ligand"] + chemistry["other"],
    }


def _burial(model, ion, radius_angstrom: float = BURIAL_RADIUS_ANGSTROM) -> dict:
    """How enclosed one ion is, by two independent measures.

    Solvent accessibility is computed with waters and non-metal heteroatoms
    removed. Leaving them in would be backwards: an exposed site attracts
    *more* ordered waters, so each one would shield the ion and make the most
    solvent-exposed sites score as the most buried.

    The heavy-atom count is reported alongside because SASA depends on the
    radius assigned to an element the table may not know, while a count does
    not. Two measures that can be checked against each other beat one that
    cannot.
    """
    from numpy.linalg import norm

    neighbours = sum(
        1 for atom in model.get_atoms()
        if atom is not ion
        and atom.parent.id[0] == " "
        and (atom.element or "").strip().upper() != "H"
        and float(norm(atom.coord - ion.coord)) <= radius_angstrom)
    charged = {"anionic": 0, "cationic": 0}
    for residue in model.get_residues():
        name = residue.resname.strip().upper()
        if name not in ANIONIC_RESIDUES and name not in CATIONIC_RESIDUES:
            continue
        if any(float(norm(a.coord - ion.coord)) <= radius_angstrom for a in residue):
            charged["anionic" if name in ANIONIC_RESIDUES else "cationic"] += 1
    return {
        "protein_atoms_within_8A": neighbours,
        "shell_anionic_residues": charged["anionic"],
        "shell_cationic_residues": charged["cationic"],
        "shell_net_charge": charged["cationic"] - charged["anionic"],
    }


def _sasa_by_ion(model, table: dict) -> dict:
    """Solvent-accessible surface area of every metal ion in the model.

    Returns {} if SASA cannot be computed, rather than failing the whole
    analysis -- burial is one descriptor among several and the atom count
    survives on its own.
    """
    import copy

    try:
        from Bio.PDB.SASA import ShrakeRupley
    except ImportError:                                   # pragma: no cover
        return {}
    stripped = copy.deepcopy(model)
    for chain in list(stripped):
        for residue in list(chain):
            if residue.id[0] == " ":
                continue
            if residue.resname.strip().upper() not in table:
                chain.detach_child(residue.id)
    try:
        ShrakeRupley().compute(stripped, level="A")
    except Exception:                                     # pragma: no cover
        return {}
    out = {}
    for chain in stripped:
        for residue in chain:
            if residue.id[0] == " ":
                continue
            if residue.resname.strip().upper() not in table:
                continue
            atoms = [a for a in residue if (a.element or "").strip().upper() != "H"]
            if atoms:
                # float() deliberately: Bio.PDB hands back numpy scalars, and a
                # numpy float in a site dict survives every in-process check and
                # then fails at json.dump() in whatever writes the sites out.
                out[(chain.id, residue.id[1])] = round(
                    float(max(a.sasa for a in atoms)), 2)
    return out


def binding_neighborhood(coordinate_text: str, fmt: str = "pdb",
                         radius_angstrom: float = FIRST_SHELL_ANGSTROM,
                         metals: dict[str, str] | None = None) -> list[dict]:
    """First-shell donor atoms around rare-earth ions already present in the
    deposited coordinates. This describes an experimentally observed site; it
    is not hypothetical metal docking.

    Waters are included and labelled. They are genuine first-shell donors --
    every Nd site in 8FNS has two -- and excluding them understates the
    coordination number, which is the descriptor that actually separates
    lanthanide sites from calcium sites.

    Pass metals=ALL_METAL_CODES to include Ca2+ sites as a contrast set.
    """
    from numpy.linalg import norm

    table = REE_LIGAND_CODES if metals is None else metals
    model = next(_parse(coordinate_text, fmt).get_models())
    atoms = list(model.get_atoms())
    ions = [a for a in atoms
            if a.parent.id[0] != " " and a.parent.resname.strip().upper() in table]

    # Once per model, not once per ion: ShrakeRupley rolls a probe over every
    # atom in the structure, so calling it per site would repeat the whole
    # calculation for each ion in it.
    sasa = _sasa_by_ion(model, table) if ions else {}

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
        chemistry = donor_chemistry(donors)
        burial = _burial(model, ion, BURIAL_RADIUS_ANGSTROM)
        burial["metal_sasa_A2"] = sasa.get((ion.parent.parent.id, ion.parent.id[1]))
        sites.append({
            "metal": ion.parent.resname.strip(),
            "element": table[resname],
            "chain": ion.parent.parent.id,
            "site": str(ion.parent.id[1]),
            "coordination_number": len(donors),
            "protein_donor_count": counts["protein"],
            "water_donor_count": counts["water"],
            "other_ligand_donor_count": counts["ligand"],
            "mean_donor_distance_A": round(sum(d["distance_A"] for d in donors) / len(donors), 2) if donors else None,
            "chemistry": chemistry,
            "charge": site_net_charge(chemistry),
            "burial": burial,
            "donors": donors,
        })
    return sites
