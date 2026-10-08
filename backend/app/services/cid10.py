"""CID-10 catalogue (DATASUS, pt-BR) — in-memory lookup for diagnosis pickers.

The dataset is a plain JSON file shipped with the app (12,451 subcategory codes,
`code` formatted as the clinician writes it, e.g. "A00.0"). It is loaded once and
kept in memory; searching is a filtered scan, which is plenty for 12k rows.
Swapping/adding CID-11 later only means dropping another file and pointing the
loader at it.
"""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parents[1] / "data" / "cid10.json"


@lru_cache(maxsize=1)
def _entries() -> list[dict]:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def _norm(text: str) -> str:
    """Lowercase, strip accents — so "hipertensao" finds "Hipertensão"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


@lru_cache(maxsize=512)
def search(query: str, limit: int = 20) -> list[dict]:
    q = query.strip()
    if not q:
        return []
    nq = _norm(q)
    exact: list[dict] = []
    prefix: list[dict] = []
    contains: list[dict] = []
    seen: set[str] = set()
    for e in _entries():
        code = e["code"]
        if code in seen:
            continue
        if code.lower() == nq:
            exact.append(e)
        elif code.lower().startswith(nq):
            prefix.append(e)
        elif nq in _norm(e["description"]):
            contains.append(e)
        else:
            continue
        seen.add(code)
        if len(exact) + len(prefix) + len(contains) > limit * 4:
            break
    return (exact + prefix + contains)[:limit]
