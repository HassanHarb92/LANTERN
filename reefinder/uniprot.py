"""Live UniProt lookup. Calls only the public UniProt API."""
import requests
from .models import Protein

BASE = "https://rest.uniprot.org/uniprotkb/search"
ALLOWED_QUERIES = {
    "lanmodulin": "protein_name:lanmodulin",
    "calmodulin": "protein_name:calmodulin AND reviewed:true",
    "ef-hand": "keyword:KW-0254 AND reviewed:true",
}

def search_proteins(topic: str = "lanmodulin", limit: int = 20, timeout: int = 25) -> list[Protein]:
    if topic not in ALLOWED_QUERIES:
        raise ValueError("Allowed topics: " + ", ".join(ALLOWED_QUERIES))
    size = max(1, min(int(limit), 50))
    response = requests.get(BASE, params={"query": ALLOWED_QUERIES[topic], "format": "json", "size": size},
                            timeout=timeout, headers={"User-Agent": "REE-Finder-hackathon/0.1"})
    response.raise_for_status()
    proteins = []
    for item in response.json().get("results", []):
        accession = item.get("primaryAccession", "")
        seq = item.get("sequence", {}).get("value", "")
        pd = item.get("proteinDescription", {})
        rec = pd.get("recommendedName", {})
        sub = pd.get("submissionNames", [])
        name = rec.get("fullName", {}).get("value") or (sub[0].get("fullName", {}).get("value") if sub else None) or accession
        proteins.append(Protein(accession=accession, name=name,
                                organism=item.get("organism", {}).get("scientificName", "Unknown"),
                                sequence=seq, source="UniProt live API", evidence="database record; binding not established",
                                source_url=f"https://www.uniprot.org/uniprotkb/{accession}/entry",
                                notes="Automated search result. Evaluate evidence before biological conclusions."))
    return proteins
