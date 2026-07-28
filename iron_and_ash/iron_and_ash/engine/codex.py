"""In-game lore codex / browser.

Reads the same structured lore data used by character creation and the world, so
the codex never drifts out of sync with the game's content.
"""
from __future__ import annotations

from ..character import data as cdata
from ..ui.console import UI
from ..world import data as wdata


def open_codex(ui: UI) -> None:
    while True:
        choice = ui.menu(
            "The Maester's Codex",
            ["The Great Houses", "The Regions of Westeros", "The Faiths",
             "Factions of the North", "Backgrounds & Callings"],
            allow_back=True,
        )
        if choice == -1:
            return
        if choice == 0:
            rows = [(h.name, h.words, cdata.REGIONS[h.region].name) for h in cdata.GREAT_HOUSES.values()]
            ui.table(["House", "Words", "Seat"], rows, title="The Great Houses")
        elif choice == 1:
            rows = [(r.name, cdata.RELIGIONS[r.default_religion], r.blurb) for r in cdata.REGIONS.values()]
            ui.table(["Region", "Common Faith", "Description"], rows, title="Regions")
        elif choice == 2:
            rows = [(name,) for name in cdata.RELIGIONS.values()]
            ui.table(["Faith"], rows, title="The Faiths of the World")
        elif choice == 3:
            rows = [(f.name, f.description) for f in wdata.FACTIONS.values()]
            ui.table(["Faction", "About"], rows, title="Factions")
        elif choice == 4:
            rows = [(b.name, b.blurb) for b in cdata.BACKGROUNDS.values()]
            ui.table(["Background", "About"], rows, title="Backgrounds")
