"""In-game lore codex / browser.

Browses the structured lore library in ``data/lore`` (loaded via ``world.lore``)
by category, entry, and free-text search. When a game is in progress the codex
also marks which entries the character has *studied* - lore learned in play from
maesters and storytellers, tracked through the memory system.
"""
from __future__ import annotations

import json
from typing import Optional, Set

from ..ui.console import UI
from ..world import lore

# world.flags key holding the JSON list of studied lore ids
STUDIED_FLAG = "lore_studied"


def studied_ids(world) -> Set[str]:
    """The set of lore entry ids this character has learned in play."""
    if world is None:
        return set()
    raw = world.flags.get(STUDIED_FLAG, "[]")
    try:
        return set(json.loads(raw))
    except (TypeError, ValueError):
        return set()


def mark_studied(world, entry_id: str) -> None:
    ids = studied_ids(world)
    ids.add(entry_id)
    world.flags[STUDIED_FLAG] = json.dumps(sorted(ids))


def open_codex(ui: UI, world=None) -> None:
    """Browse the lore library. ``world`` (optional) enables study markers."""
    while True:
        known = studied_ids(world)
        options = list(lore.CATEGORIES.values()) + ["Search the codex"]
        if known:
            total = len(lore.load_lore())
            ui.print(f"[dim]Your studies: {len(known)} of {total} entries learned in your travels.[/dim]")
        choice = ui.menu("The Maester's Codex", options, allow_back=True)
        if choice == -1:
            return
        if choice == len(options) - 1:
            _search(ui, world)
            continue
        category = list(lore.CATEGORIES.keys())[choice]
        _browse_category(ui, category, world)


def _browse_category(ui: UI, category: str, world) -> None:
    entries = lore.entries_in(category)
    while True:
        known = studied_ids(world)
        labels = [
            f"{'* ' if e.id in known else ''}{e.name} - {e.summary}"
            for e in entries
        ]
        idx = ui.menu(lore.CATEGORIES[category], labels, allow_back=True)
        if idx == -1:
            return
        show_entry(ui, entries[idx])


def _search(ui: UI, world) -> None:
    query = ui.ask("Search for (name, place, tag, or phrase)")
    results = lore.search(query)
    if not results:
        ui.print(f"[dim]The codex holds nothing on '{query}'.[/dim]")
        return
    labels = [f"{e.name} ({lore.CATEGORIES[e.category]})" for e in results[:12]]
    idx = ui.menu(f"Entries touching on '{query}'", labels, allow_back=True)
    if idx == -1:
        return
    show_entry(ui, results[idx])


def show_entry(ui: UI, entry: lore.LoreEntry) -> None:
    """Render one lore entry as a fact sheet plus its full prose."""
    parts = []
    if entry.facts:
        parts.append("\n".join(f"[bold]{k}:[/bold] {v}" for k, v in entry.facts.items()))
    parts.append(entry.full_text())
    ui.panel("\n\n".join(parts), title=entry.name)
