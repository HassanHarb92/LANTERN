"""Pure-Python Okapi BM25 over title + abstract.

Lexical on purpose: a hit is always a paper that literally contains the query words, and the score has no model behind it.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from .types import Paper

# Deliberately small. "in", "as", "no", "he" are left out because they are also element symbols (In, As, No, He).
STOPWORDS = frozenset(
    "a an and are be by for from has have is it its of on or that the their this to was were with which".split())
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric runs minus stopwords: "EF-hand" -> ef, hand; "Ce3+" -> ce3; digits are kept."""
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


class BM25Index:
    def __init__(self, papers: list[Paper], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.papers = list(papers)
        self._tf = [Counter(tokenize(p.title + " " + p.abstract)) for p in self.papers]
        self._len = [sum(c.values()) for c in self._tf]
        n = len(self.papers)
        self._avg = (sum(self._len) / n) if n else 0.0
        df: Counter = Counter()
        for c in self._tf:
            df.update(c.keys())
        # The +1 form keeps idf positive even for terms in most documents, so any literal match scores above 0.
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query: str, k: int = 5) -> list[tuple[Paper, float]]:
        terms = tokenize(query)
        if not self.papers or not terms:
            return []
        scored = []
        for i, tf in enumerate(self._tf):
            norm = 1 - self.b + self.b * (self._len[i] / self._avg) if self._avg else 1.0
            s = 0.0
            for t in terms:
                f = tf.get(t, 0)
                if f:
                    s += self._idf[t] * f * (self.k1 + 1) / (f + self.k1 * norm)
            if s > 0:
                scored.append((self.papers[i], s))
        scored.sort(key=lambda ps: (-ps[1], ps[0].cid))
        return scored[:k]
