"""Live protein lookup. Calls only the public UniProt and InterPro APIs."""
import requests
from .models import Protein

BASE = "https://rest.uniprot.org/uniprotkb/search"
INTERPRO = "https://www.ebi.ac.uk/interpro/api/protein/uniprot/entry"

# xref_pdb is what connects a live search result to the half of this platform
# that measures things. Without it every live hit arrives with pdb_id None, so
# discover reports "no deposited structure and no prediction" for proteins
# whose coordinates UniProt is cross-referencing in the same record -- C5B164
# is the canonical case: the search finds lanmodulin, UniProt lists 8FNS at
# 1.01 A, and the page used to say the coordination number was unknown.
FIELDS = "accession,protein_name,organism_name,sequence,xref_pdb"

# Topics answerable by a single UniProt search.
ALLOWED_QUERIES = {
    "lanmodulin": "protein_name:lanmodulin",
    "calmodulin": "protein_name:calmodulin AND reviewed:true",
}

# Topics UniProt search cannot express. The lanmodulin family is an NCBIfam
# entry, and UniProt records no NCBIfam cross-reference for its members --
# xref:ncbifam-NF053806 returns zero hits, and C5B164's only family handles are
# generic EF-hand ones shared with hundreds of thousands of calcium proteins.
# Membership therefore has to come from InterPro, after which sequences are
# fetched from UniProt by accession.
#
# An "ef-hand" topic previously mapped to keyword KW-0254. That keyword is
# Endocytosis, so the option returned 755 irrelevant proteins; it is withdrawn
# rather than repaired, because no UniProt keyword denotes the EF-hand domain.
INTERPRO_FAMILIES = {
    "lanm-family": ("ncbifam", "NF053806"),
}

TOPICS = tuple(ALLOWED_QUERIES) + tuple(INTERPRO_FAMILIES)

# UniProt is queried over GET, so accession batches are kept short enough that
# the assembled URL stays well inside normal length limits.
_ACCESSION_BATCH = 50


def _resolution(value) -> float | None:
    """"1.01 A" -> 1.01. None for the "-" an NMR entry carries.

    None means "this entry states no resolution", which is a real answer and
    the same one `structure.resolution_from_coordinates` gives for the same
    entries. It must not become a large number: that would sort NMR entries
    last rather than out of the comparison.
    """
    try:
        return float(str(value).split()[0])
    except (ValueError, IndexError):
        return None


def pdb_cross_references(item: dict) -> list[dict]:
    """The deposited structures UniProt lists for one entry.

    Method and resolution come from the cross-reference itself, so knowing
    what was deposited costs no extra request -- which is what makes it
    affordable to do this for every hit in a search.
    """
    options = []
    for xref in item.get("uniProtKBCrossReferences", []):
        if xref.get("database") != "PDB":
            continue
        properties = {p.get("key"): p.get("value")
                      for p in xref.get("properties", [])}
        options.append({"id": (xref.get("id") or "").upper(),
                        "method": properties.get("Method") or "unknown",
                        "resolution_A": _resolution(properties.get("Resolution")),
                        "chains": properties.get("Chains") or ""})
    return [o for o in options if o["id"]]


# Why resolution decides, said once here and repeated to the user by
# choose_structure. geometry-v2 weighs a call's reliability against the
# resolution of the entry it measured, so taking the sharpest coordinates is
# the choice that makes the measurement downstream worth the most. It is not a
# judgement about which structure is most relevant: a cross-reference says
# nothing about which metal is in the file, so a lower-resolution entry holding
# the lanthanide a user asked about could easily be the better one to look at.
# That is why the alternatives are carried rather than discarded.
RESOLUTION_IS_THE_RULE = (
    "Chosen on resolution, because the geometry score weighs how far to trust "
    "a call against the resolution of the entry it measured. A cross-reference "
    "does not say which metal is in which file, so this is not a judgement "
    "about which structure is most relevant to your ion."
)


def choose_structure(options: list[dict]) -> tuple[str | None, str]:
    """Which of an entry's deposited structures to measure, and why.

    Returns the PDB id and a sentence stating the rule that picked it, so the
    choice can be shown to the user rather than made on their behalf in
    silence. Entries stating no resolution -- NMR, cryo-EM without one -- are
    not ranked against those that do; they are the fallback, taken in PDB id
    order so the same search returns the same structure twice running.
    """
    if not options:
        return None, ""
    n = len(options)
    measured = [o for o in options if o["resolution_A"] is not None]
    if measured:
        best = min(measured, key=lambda o: (o["resolution_A"], o["id"]))
        return best["id"], (
            f"{best['id']} measured, the sharpest of the {n} structure(s) "
            f"UniProt lists for this entry ({best['resolution_A']} Å, "
            f"{best['method']}). {RESOLUTION_IS_THE_RULE}")
    first = min(options, key=lambda o: o["id"])
    methods = ", ".join(sorted({o["method"] for o in options}))
    return first["id"], (
        f"{first['id']} measured. None of the {n} structure(s) UniProt lists "
        f"for this entry states a resolution ({methods}), so the lowest PDB id "
        "was taken and the choice between them is arbitrary.")


def _to_protein(item: dict, source: str, notes: str) -> Protein:
    accession = item.get("primaryAccession", "")
    description = item.get("proteinDescription", {})
    recommended = description.get("recommendedName", {})
    submitted = description.get("submissionNames", [])
    name = (recommended.get("fullName", {}).get("value")
            or (submitted[0].get("fullName", {}).get("value") if submitted else None)
            or accession)
    options = pdb_cross_references(item)
    pdb_id, _ = choose_structure(options)
    return Protein(accession=accession, name=name,
                   organism=item.get("organism", {}).get("scientificName", "Unknown"),
                   sequence=item.get("sequence", {}).get("value", ""),
                   pdb_id=pdb_id, pdb_options=options,
                   source=source, evidence="database record; binding not established",
                   source_url=f"https://www.uniprot.org/uniprotkb/{accession}/entry",
                   notes=notes)


def _get_json(url: str, params: dict, timeout: int, accept_json: bool = False) -> dict:
    headers = {"Accept": "application/json"} if accept_json else {}
    response = requests.get(url, params=params, timeout=timeout, headers=headers)
    response.raise_for_status()
    return response.json()


def family_accessions(database: str, entry: str, limit: int, timeout: int = 25) -> list[str]:
    """UniProt accessions belonging to an InterPro member-database entry."""
    accessions, url = [], f"{INTERPRO}/{database}/{entry}/"
    params = {"page_size": min(200, max(limit, 1))}
    while url and len(accessions) < limit:
        payload = _get_json(url, params, timeout, accept_json=True)
        for result in payload.get("results", []):
            accessions.append(result["metadata"]["accession"])
        url, params = payload.get("next"), {}  # `next` already carries its query string
    return accessions[:limit]


def fetch_by_accessions(accessions: list[str], timeout: int = 25,
                        source: str = "UniProt live API", notes: str = "") -> list[Protein]:
    """Fetch full records for an explicit accession list, preserving its order."""
    found = {}
    for start in range(0, len(accessions), _ACCESSION_BATCH):
        batch = accessions[start:start + _ACCESSION_BATCH]
        payload = _get_json(BASE, {"query": " OR ".join(f"accession:{a}" for a in batch),
                                   "format": "json", "fields": FIELDS,
                                   "size": len(batch)}, timeout)
        for item in payload.get("results", []):
            protein = _to_protein(item, source, notes)
            found[protein.accession] = protein
    # Demerged or withdrawn accessions simply return nothing; dropping them
    # silently would overstate coverage, so the caller sees a shorter list.
    return [found[a] for a in accessions if a in found]


def search_proteins(topic: str = "lanmodulin", limit: int = 20, timeout: int = 25) -> list[Protein]:
    if topic not in TOPICS:
        raise ValueError("Allowed topics: " + ", ".join(TOPICS))
    size = max(1, min(int(limit), 200))

    if topic in INTERPRO_FAMILIES:
        database, entry = INTERPRO_FAMILIES[topic]
        accessions = family_accessions(database, entry, size, timeout)
        return fetch_by_accessions(
            accessions, timeout,
            source=f"InterPro {database.upper()} {entry} membership; sequences from UniProt",
            notes=("Family member retrieved from InterPro. Most of this family is "
                   "uncharacterized; membership is not evidence of metal binding."))

    payload = _get_json(BASE, {"query": ALLOWED_QUERIES[topic], "format": "json",
                               "fields": FIELDS, "size": size}, timeout)
    return [_to_protein(item, "UniProt live API",
                        "Automated search result. Evaluate evidence before biological conclusions.")
            for item in payload.get("results", [])]
