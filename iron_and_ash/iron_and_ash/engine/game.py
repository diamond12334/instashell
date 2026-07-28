"""The in-game loop: exploration, action, and the systems tied together."""
from __future__ import annotations

from typing import List

from ..character import data as cdata
from ..character.models import ATTRIBUTE_LABELS, ATTRIBUTES
from ..memory import Event, EventType
from ..narrative import talk_to
from ..persistence.saves import SaveManager
from ..ui.console import UI
from ..world import data as wdata
from ..world import reactivity
from .codex import open_codex
from .state import GameState


class Game:
    def __init__(self, ui: UI, gs: GameState, saves: SaveManager) -> None:
        self.ui = ui
        self.gs = gs
        self.saves = saves

    def run(self) -> None:
        self._on_enter_location(first=True)
        while self.gs.running and self.gs.character.is_alive():
            self._describe_location()
            self._action_menu()
        if not self.gs.character.is_alive():
            self.ui.panel("Your watch has ended. Death comes for us all, and it has "
                          "come for you.", title="You Have Died", style="red")
            self.saves.save_game(self.gs)

    # -- location -------------------------------------------------------------
    def _describe_location(self) -> None:
        loc = wdata.LOCATIONS[self.gs.character.location]
        self.ui.rule(f"{loc.name}  -  Day {self.gs.world.day}")
        self.ui.narrate(loc.description)
        present = wdata.npcs_at(loc.id, self.gs.world)
        if present:
            names = ", ".join(wdata.NPCS[n].name for n in present)
            self.ui.print(f"[cyan]Here you see:[/cyan] {names}")

    def _on_enter_location(self, first: bool = False) -> None:
        loc = wdata.LOCATIONS[self.gs.character.location]
        if not first:
            self.gs.memory.record(Event(
                game_day=self.gs.world.day, type=EventType.TRAVEL,
                summary=f"You travelled to {loc.name}.",
                location=loc.id, importance=1))

    def _action_menu(self) -> None:
        loc = wdata.LOCATIONS[self.gs.character.location]
        present = wdata.npcs_at(loc.id, self.gs.world)
        actions: List[str] = []
        handlers: List = []

        for npc_id in present:
            actions.append(f"Speak with {wdata.NPCS[npc_id].name}")
            handlers.append(("talk", npc_id))
        for label, dest in loc.exits.items():
            if dest == loc.id:
                continue  # a self-loop 'explore' exit; skip to keep the menu clean
            dest_name = wdata.LOCATIONS[dest].name
            actions.append(f"Travel: {label} -> {dest_name}")
            handlers.append(("travel", dest))

        actions += ["Rest a while", "View character", "Journal (memory)",
                    "Inventory", "Lore codex", "Save game", "Quit to main menu"]
        handlers += [("rest", None), ("status", None), ("journal", None),
                     ("inventory", None), ("codex", None), ("save", None), ("quit", None)]

        idx = self.ui.menu("What do you do?", actions)
        kind, arg = handlers[idx]
        getattr(self, f"_do_{kind}")(arg)

    # -- actions --------------------------------------------------------------
    def _do_talk(self, npc_id: str) -> None:
        talk_to(self.ui, self.gs, npc_id)
        self.saves.save_game(self.gs)  # autosave after meaningful interaction

    def _do_travel(self, dest: str) -> None:
        loc = wdata.LOCATIONS[dest]
        days = max(1, loc.travel_days)
        self.ui.print(f"[dim]You travel to {loc.name} ({days} day(s) on the road)...[/dim]")
        lines = reactivity.advance_time(self.gs.world, self.gs.memory, days)
        for line in lines:
            self.ui.print(f"[yellow]* {line}[/yellow]")
        self.gs.character.location = dest
        self._maybe_summarize()
        self._on_enter_location()
        self.saves.save_game(self.gs)  # autosave on travel

    def _do_rest(self, _arg) -> None:
        lines = reactivity.advance_time(self.gs.world, self.gs.memory, 1)
        healed = min(self.gs.character.max_health,
                     self.gs.character.health + 5) - self.gs.character.health
        self.gs.character.health += healed
        self.ui.narrate(f"You rest, and the day passes. You recover {healed} vigour.")
        for line in lines:
            self.ui.print(f"[yellow]* {line}[/yellow]")
        self.saves.save_game(self.gs)

    def _do_status(self, _arg) -> None:
        c = self.gs.character
        attr_line = "  ".join(f"{ATTRIBUTE_LABELS[a]} {getattr(c.attributes, a)}" for a in ATTRIBUTES)
        skills = ", ".join(f"{cdata.SKILLS.get(s, s)} +{v}" for s, v in c.skills.items()) or "none"
        traits = ", ".join(cdata.TRAITS[t].name for t in c.traits if t in cdata.TRAITS) or "none"
        titles = ", ".join(c.titles) or "none"
        body = (
            f"[bold]{c.name}[/bold] of {c.house}\n"
            f"{cdata.REGIONS[c.region].name}, faith of {cdata.RELIGIONS[c.religion]}\n"
            f"Level {c.level}  (XP {c.xp}/{c.xp_to_next()})   Health {c.health}/{c.max_health}   "
            f"Gold {c.gold}\n\n"
            f"{attr_line}\n"
            f"Skills: {skills}\n"
            f"Traits: {traits}\n"
            f"Titles: {titles}\n"
            f"Motto: {c.house_words or '(none)'}"
        )
        self.ui.panel(body, title="Your Character")
        self._reputation_table()

    def _reputation_table(self) -> None:
        rows = []
        for fid, faction in wdata.FACTIONS.items():
            rep = self.gs.world.reputation(fid)
            rows.append((faction.name, _rep_word(rep), str(rep)))
        self.ui.table(["Faction", "Standing", "Value"], rows, title="Reputation")

    def _do_journal(self, _arg) -> None:
        wm = self.gs.memory.working_memory()
        self.ui.heading(f"Journal - {self.gs.memory.event_count()} things remembered")
        if wm["summaries"]:
            self.ui.print("[bold]Chronicles of ages past:[/bold]")
            for s in wm["summaries"]:
                self.ui.print(f"  [italic]{s['title']}[/italic]: {s['text']}")
        if wm["landmarks"]:
            self.ui.print("\n[bold]Deeds that still echo:[/bold]")
            for e in wm["landmarks"]:
                self.ui.print(f"  (day {e.game_day}) {e.summary}")
        self.ui.print("\n[bold]Of late:[/bold]")
        for e in wm["recent"]:
            self.ui.print(f"  (day {e.game_day}) {e.summary}")

    def _do_inventory(self, _arg) -> None:
        c = self.gs.character
        if c.inventory:
            self.ui.table(["Possessions"], [(item,) for item in c.inventory])
        else:
            self.ui.print("You carry nothing of note.")
        self.ui.print(f"Silver: {c.gold}")

    def _do_codex(self, _arg) -> None:
        open_codex(self.ui, self.gs.world)

    def _do_save(self, _arg) -> None:
        self.saves.save_game(self.gs)
        self.ui.print(f"[green]Game saved to slot '{self.gs.slot}'.[/green]")

    def _do_quit(self, _arg) -> None:
        if self.ui.confirm("Quit to the main menu? (Your progress is saved.)", default=True):
            self.saves.save_game(self.gs)
            self.gs.running = False

    # -- memory upkeep --------------------------------------------------------
    def _maybe_summarize(self) -> None:
        """Periodically fold old events into a chronicle summary.

        Every ~30 in-game days of history beyond the last summary, compress the
        older events into a narrative digest. Raw events remain in the log.
        """
        summaries = self.gs.memory.summaries()
        last_end = max((s["span_end_day"] for s in summaries), default=0)
        if self.gs.world.day - last_end >= 30:
            up_to = self.gs.world.day - 15  # leave recent events out of the digest
            n = len(summaries) + 1
            title = _chronicle_title(n)
            created = self.gs.memory.summarize_period(title, up_to_day=up_to)
            if created:
                self.ui.print(f"[dim]The maesters record a new chapter: {created['title']}.[/dim]")


def _rep_word(rep: int) -> str:
    if rep >= 40:
        return "Honoured"
    if rep >= 15:
        return "Friendly"
    if rep <= -40:
        return "Hated"
    if rep <= -15:
        return "Distrusted"
    return "Neutral"


def _chronicle_title(n: int) -> str:
    names = ["The First Chronicle", "The Second Chronicle", "The Third Chronicle",
             "The Fourth Chronicle", "The Fifth Chronicle"]
    return names[n - 1] if 1 <= n <= len(names) else f"Chronicle {n}"
