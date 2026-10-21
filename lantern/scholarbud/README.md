# scholarbud

Literature collection and lexical search for LANTERN, adapted from the ScholarMap project (author Hassan Harb). ScholarMap
has no licence file; it is used here with the project owner's go-ahead.

## What was adapted

- `crossref.py`: the Crossref and ChemRxiv path from ScholarMap `collect.py` (`_crossref_paper`, the ChemRxiv DOI-prefix
  filter 10.26434). Rewritten to return `Paper` records, with an injectable HTTP session so tests run offline, one retry
  on 429/5xx, and a `LiteratureError` on failure instead of a silent empty list.
- `library.py`: the dedup idea from `library_db.py` (SQLite, canonical id of DOI, then arXiv id, then title hash; upsert
  merges and keeps the richer abstract). DOIs are also matched case-insensitively.
- `bm25.py`: new, pure Python Okapi BM25 (k1=1.5, b=0.75) over title and abstract. No numpy.

## What was left out, and why

Argo (LLM gateway), FAISS and torch (embedding search), LLM-extracted knowledge items, and the Streamlit UI. Our contract is
that no model-written fact is indexed: every field in the library is what the source deposited, and search is lexical so a
hit always contains the query words. Embeddings and LLM extraction would put model output between the source and the
critic.

## Limits of the source

chemrxiv.org is behind Cloudflare and refuses scripted clients, so only Crossref abstracts are available for ChemRxiv.
About 479 ChemRxiv full texts are reachable via Europe PMC (mostly COVID-era); this package is abstract-only by design.

Set `LANTERN_MAILTO` to put a contact address in the Crossref User-Agent (polite pool). No address is hard-coded.
