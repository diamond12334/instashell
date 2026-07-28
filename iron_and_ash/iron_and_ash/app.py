"""Main menu and application orchestration."""
from __future__ import annotations

import sys

from .character.creation import create_character
from .character import data as cdata
from .engine.codex import open_codex
from .engine.game import Game
from .memory import Event, EventType
from .persistence.saves import SaveManager
from .ui.console import UI
from .world import data as wdata


TITLE_ART = r"""
 ___                    ___      _         _
|_ _|_ __ ___  _ __    ( _ )    /_\   ___ | |__
 | || '__/ _ \| '_ \   / _ \/\ //_\\ / __|| '_ \
 | || | | (_) | | | | | (_>  </  _  \\__ \| | | |
|___|_|  \___/|_| |_|  \___/\/\_/ \_/|___/|_| |_|
        A Song of Ice and Fire  -  Text RPG
"""


class App:
    def __init__(self, ui: UI | None = None) -> None:
        self.ui = ui or UI()
        self.saves = SaveManager()

    def run(self) -> None:
        self.ui.print(TITLE_ART, style="bold cyan")
        self.ui.print("[dim]A transformative fan project. Winter is coming.[/dim]\n")
        while True:
            has_saves = bool(self.saves.list_saves())
            options = ["New Game"]
            actions = ["new"]
            if has_saves:
                options += ["Continue (most recent)", "Load Game", "Delete Save"]
                actions += ["continue", "load", "delete"]
            options += ["Lore Codex", "Quit"]
            actions += ["codex", "quit"]

            idx = self.ui.menu("Main Menu", options)
            action = actions[idx]
            if action == "new":
                self._new_game()
            elif action == "continue":
                self._continue()
            elif action == "load":
                self._load()
            elif action == "delete":
                self._delete()
            elif action == "codex":
                open_codex(self.ui)
            elif action == "quit":
                self.ui.print("May your road be smooth and your winters short. Farewell.")
                return

    # -- menu actions ---------------------------------------------------------
    def _new_game(self) -> None:
        slot = self._ask_slot_name()
        if slot is None:
            return
        character = create_character(self.ui)
        world = wdata.new_world_state()
        character.location = wdata.STARTING_LOCATION
        gs = self.saves.new_game(slot, character, world)
        # opening milestone - the first thing the world remembers
        gs.memory.record(Event(
            game_day=0, type=EventType.MILESTONE,
            summary=f"{character.name} of {character.house} began their tale at Winterfell.",
            location=character.location, importance=4,
        ))
        self.saves.save_game(gs)
        self._opening_scene(gs)
        Game(self.ui, gs, self.saves).run()

    def _ask_slot_name(self) -> str | None:
        existing = {s.slot for s in self.saves.list_saves()}
        name = self.ui.ask("Name this save (e.g. your character or a keyword)", default="winterfell")
        slot = name.strip()
        if slot in existing:
            if not self.ui.confirm(f"Slot '{slot}' exists and will be overwritten. Continue?", default=False):
                return None
        return slot

    def _opening_scene(self, gs) -> None:
        c = gs.character
        self.ui.panel(
            f"The year turns cold as {c.name} of {c.house} comes to Winterfell, "
            f"seat of the Starks and heart of the North. Whatever brought you here - "
            f"blood, coin, oath, or exile - the grey walls care nothing for it. "
            f"They have stood ten thousand years, and they will judge you by your "
            f"deeds alone.\n\n[dim]Faith: {cdata.RELIGIONS[c.religion]}  -  "
            f"Born: {cdata.REGIONS[c.region].name}[/dim]",
            title="Winterfell", style="cyan",
        )

    def _continue(self) -> None:
        slot = self.saves.last_slot()
        if not slot:
            self.ui.print("There is nothing to continue.")
            return
        self._launch(slot)

    def _load(self) -> None:
        infos = self.saves.list_saves()
        if not infos:
            self.ui.print("No saved games found.")
            return
        labels = [
            f"{i.character_name} of {i.house}  -  Day {i.in_game_day}  -  {i.notable_event}"
            for i in infos
        ]
        idx = self.ui.menu("Load which tale?", labels, allow_back=True)
        if idx == -1:
            return
        self._launch(infos[idx].slot)

    def _delete(self) -> None:
        infos = self.saves.list_saves()
        if not infos:
            self.ui.print("No saved games to delete.")
            return
        labels = [f"{i.character_name} of {i.house} (slot '{i.slot}')" for i in infos]
        idx = self.ui.menu("Delete which save?", labels, allow_back=True)
        if idx == -1:
            return
        slot = infos[idx].slot
        if self.ui.confirm(f"Permanently delete '{slot}'? This cannot be undone.", default=False):
            self.saves.delete_save(slot)
            self.ui.print(f"[red]Save '{slot}' has been deleted.[/red]")

    def _launch(self, slot: str) -> None:
        try:
            gs = self.saves.load_game(slot)
        except Exception as exc:  # pragma: no cover - defensive
            self.ui.print(f"[red]Could not load '{slot}': {exc}[/red]")
            return
        self.ui.print(f"[green]Welcome back, {gs.character.name}. Your tale continues on day {gs.world.day}.[/green]")
        Game(self.ui, gs, self.saves).run()


def main() -> None:
    # Older Windows consoles default to legacy code pages; never let an
    # unprintable character crash the game.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        App().run()
    except (KeyboardInterrupt, EOFError):
        print("\nUntil next time. Winter is coming.")


if __name__ == "__main__":
    main()
