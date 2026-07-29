"""Structured lore: loader and query API over the JSON files in ``data/lore``.

Lore is pure data - every entry lives in a JSON file named after its category,
so expanding the world's lore means editing data, never code. The loader
validates entries through pydantic and caches the result.

Entry schema (per JSON object):
    id       unique string id
    name     display name
    summary  one-line description
    body     list of paragraphs (joined for display)
    facts    optional {label: value} dict shown as a fact sheet
    tags     optional list of lowercase search tags
"""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from ..compat import BaseModel, Field

LORE_DIR = Path(__file__).resolve().parents[1] / "data" / "lore"

# category id -> title shown in the codex, in menu order
CATEGORIES: Dict[str, str] = {
    "houses": "The Great and Noble Houses",
    "history": "Histories and Ages of the World",
    "religions": "The Faiths",
    "places": "Castles, Cities, and Wonders",
    "legends": "Legends and Creatures",
    "orders": "Orders and Institutions",
    "customs": "Laws and Customs",
}


class LoreEntry(BaseModel):
    id: str
    name: str
    summary: str
    body: List[str]
    facts: Dict[str, str] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    category: str = ""  # filled by the loader from the file name

    def full_text(self) -> str:
        return "\n\n".join(self.body)


@lru_cache(maxsize=1)
def load_lore() -> Dict[str, LoreEntry]:
    """All lore entries keyed by id. Cached for the life of the process."""
    entries: Dict[str, LoreEntry] = {}
    for category in CATEGORIES:
        path = LORE_DIR / f"{category}.json"
        if not path.exists():
            continue
        for raw in json.loads(path.read_text(encoding="utf-8")):
            entry = LoreEntry.model_validate({**raw, "category": category})
            if entry.id in entries:
                raise ValueError(f"Duplicate lore id: {entry.id}")
            entries[entry.id] = entry
    return entries


def entries_in(category: str) -> List[LoreEntry]:
    return [e for e in load_lore().values() if e.category == category]


def get(entry_id: str) -> Optional[LoreEntry]:
    return load_lore().get(entry_id)


def search(query: str) -> List[LoreEntry]:
    """Case-insensitive search across names, summaries, tags, and body text.

    Name/summary/tag hits rank above body-only hits.
    """
    q = query.strip().lower()
    if not q:
        return []
    strong: List[LoreEntry] = []
    weak: List[LoreEntry] = []
    for entry in load_lore().values():
        haystack_strong = " ".join([entry.name, entry.summary, *entry.tags]).lower()
        if q in haystack_strong:
            strong.append(entry)
        elif q in entry.full_text().lower():
            weak.append(entry)
    return strong + weak


def random_entry(exclude_ids: Optional[set] = None,
                 categories: Optional[List[str]] = None,
                 rng: Optional[random.Random] = None) -> Optional[LoreEntry]:
    """A random lore entry, for NPCs who teach the player something new."""
    rng = rng or random
    pool = [
        e for e in load_lore().values()
        if (not exclude_ids or e.id not in exclude_ids)
        and (not categories or e.category in categories)
    ]
    return rng.choice(pool) if pool else None
