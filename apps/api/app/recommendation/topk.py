"""Top-K selection, O(n log k) via heapq.nlargest (V2 §10.2 — 'heap /
priority queue' is a named required DSA concept). heapq.nlargest already
maintains a k-sized heap internally; this wrapper exists so call sites
work with plain (score, item) pairs instead of hand-rolling heap-tuple
comparisons everywhere.
"""

import heapq
from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")


def top_k(scored_items: Iterable[tuple[float, T]], k: int) -> list[tuple[float, T]]:
    return heapq.nlargest(k, scored_items, key=lambda pair: pair[0])
