"""scholarbud: literature collection and search adapted from ScholarMap.

Kept in its own subpackage so the boundary with the ScholarMap project stays visible. Provenance and what was changed are in
README.md in this folder. Nothing here imports the rest of LANTERN except through `lantern.scholarbud.types`.
"""
from .types import Paper

__all__ = ["Paper"]
from .bm25 import BM25Index
from .crossref import search, search_chemrxiv
from .library import Library

__all__ += ["search", "search_chemrxiv", "Library", "BM25Index"]
