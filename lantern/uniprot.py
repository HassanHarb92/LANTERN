"""Live protein lookup. Calls only the public UniProt and InterPro APIs."""
import requests
from .models import Protein

BASE = "https://rest.uniprot.org/uniprotkb/search"
INTERPRO = "https://www.ebi.ac.uk/interpro/api/protein/uniprot/entry"
FIELDS = "accession,protein_name,organism_name,sequence"

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


def _to_protein(item: dict, source: str, notes: str) -> Protein:
    accession = item.get("primaryAccession", "")
    description = item.get("proteinDescription", {})
    recommended = description.get("recommendedName", {})
    submitted = description.get("submissionNames", [])
    name = (recommended.get("fullName", {}).get("value")
            or (submitted[0].get("fullName", {}).get("value") if submitted else None)
            or accession)
    return Protein(accession=accession, name=name,
                   organism=item.get("organism", {}).get("scientificName", "Unknown"),
                   sequence=item.get("sequence", {}).get("value", ""),
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
