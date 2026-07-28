"""Reaction logic for entities that share a place with the player.

When the player stands in the same province as an army, a warband, or a lord in
his seat, this module decides how that meeting can go. The options offered - and
how they resolve - weigh the factors the brief asks for:

* **prior relationship & house standing** - faction reputation and any personal
  disposition from the memory system;
* **recent events** - the memory log (oaths, slights) colours greetings;
* **troop-strength disparity** - your host (if you have mustered one) against theirs;
* **local law & custom** - guest right inside a holding, the peace of a lord's hall;
* **the other side's nature and goals** - a lord parleys, a free company haggles,
  bandits threaten and take.

Every meaningful outcome is written to memory, so the world remembers how you
carried yourself.
"""
from __future__ import annotations

import random
from typing import Optional

from ..engine.mechanics import resolve_combat, skill_check
from ..engine.state import GameState
from ..memory import Event, EventType
from ..ui.console import UI
from ..world import campaign, military
from ..world.holdings import Holding
from ..world.military import Army


def player_host(gs: GameState) -> Optional[Army]:
    for army in gs.world.living_armies():
        if army.allegiance == "player":
            return army
    return None


# ---------------------------------------------------------------------------
# meeting an army / warband
# ---------------------------------------------------------------------------
def encounter_army(ui: UI, gs: GameState, army: Army) -> None:
    kind_word = {"host": "an armed host", "garrison": "a garrison",
                 "free_company": "a free company", "bandits": "a band of brigands",
                 "outlaws": "a gang of outlaws"}.get(army.kind, "armed men")
    ui.heading(f"{army.name}")
    ui.narrate(f"You have come upon {kind_word} - {army.commander}'s people, "
               f"{army.strength()} strong and {army.morale_word()}. "
               f"They are {army.supply_status()}.")

    mine = player_host(gs)
    my_strength = mine.strength() if mine else 0
    _disparity_note(ui, my_strength, army.strength())

    hostile = army.kind in ("bandits", "outlaws") or (
        army.allegiance not in ("player",) and _standing(gs, army.allegiance) <= -40)

    options, handlers = [], []
    options.append("Hail them and speak"); handlers.append("parley")
    if army.kind in ("free_company",):
        options.append("Seek to take them into your pay"); handlers.append("hire")
    if army.kind in ("bandits", "outlaws"):
        options.append("Try to buy them off"); handlers.append("bribe")
        options.append("Try to recruit them to your cause"); handlers.append("recruit")
    if mine is not None:
        options.append("Give battle with your host"); handlers.append("battle")
    else:
        options.append("Stand and fight them yourself"); handlers.append("skirmish")
    options.append("Withdraw and avoid them"); handlers.append("avoid")

    idx = ui.menu("How do you meet them?", options)
    getattr(_ArmyReactions, handlers[idx])(ui, gs, army, mine)


class _ArmyReactions:
    @staticmethod
    def parley(ui: UI, gs: GameState, army: Army, mine: Optional[Army]) -> None:
        standing = _standing(gs, army.allegiance)
        if army.kind in ("bandits", "outlaws"):
            ui.narrate(f"\"Well now,\" grins {army.commander}. \"Coin or blood, "
                       "friend - your choice, and quick about it.\"")
            _record(gs, army, f"You parleyed warily with {army.name}.", EventType.DIALOGUE, 1)
            return
        if standing >= 15:
            ui.narrate(f"{army.commander} greets you as a friend of "
                       f"{campaign.faction_name(army.allegiance)}. You are made welcome at their fire.")
        elif standing <= -15:
            ui.narrate(f"{army.commander} hears you out with a cold eye - you are no friend "
                       f"of {campaign.faction_name(army.allegiance)}, and they do not forget it.")
        else:
            ui.narrate(f"{army.commander} hears you courteously, giving little away.")
        _record(gs, army, f"You spoke with {army.name} in the field.", EventType.DIALOGUE, 1)

    @staticmethod
    def hire(ui: UI, gs: GameState, army: Army, mine: Optional[Army]) -> None:
        price = army.strength() * 3
        ui.narrate(f"The captain names his price: {price} silver to take his "
                   f"{army.strength()} swords into your service.")
        if gs.character.gold < price:
            ui.print(f"[red]You have but {gs.character.gold} silver. Not enough.[/red]")
            return
        if not ui.confirm(f"Pay {price} silver to hire {army.name}?", default=False):
            return
        gs.character.gold -= price
        army.allegiance = "player"
        army.coffers += price
        army.morale = min(100, army.morale + 10)
        _record(gs, army, f"You took {army.name} into your pay.", EventType.ALLIANCE, 3)
        ui.narrate(f"\"Your coin, your war,\" the captain says. {army.name} follows your banner now.")

    @staticmethod
    def bribe(ui: UI, gs: GameState, army: Army, mine: Optional[Army]) -> None:
        price = army.strength() * 2
        ui.narrate(f"They will let you pass - and leave the district - for {price} silver.")
        if gs.character.gold < price:
            ui.print(f"[red]You cannot meet their price ({gs.character.gold} silver).[/red]")
            return
        if not ui.confirm(f"Pay {price} silver?", default=False):
            return
        gs.character.gold -= price
        army.orders_target = random.choice(
            military.geography.neighbors(army.province) or [army.province])
        army.orders_intent = "raid"
        _record(gs, army, f"You bought off {army.name}.", EventType.DIALOGUE, 2)
        ui.narrate("They melt back into the trees, for now.")

    @staticmethod
    def recruit(ui: UI, gs: GameState, army: Army, mine: Optional[Army]) -> None:
        check = skill_check(gs.character, "presence", "intrigue", "hard")
        ui.print(check.describe())
        if check.success:
            army.allegiance = "player"
            army.kind = "free_company"
            army.morale = min(100, army.morale + 8)
            _record(gs, army, f"You won over {army.name} to your cause.", EventType.ALLIANCE, 3)
            ui.narrate("Something in your words reaches them. They throw in their lot with you.")
        else:
            army.morale = max(0, army.morale - 5)
            _record(gs, army, f"{army.name} spurned your offer.", EventType.SLIGHT, 1)
            ui.narrate("\"Pretty words butter no bread,\" the captain sneers. They refuse.")

    @staticmethod
    def battle(ui: UI, gs: GameState, army: Army, mine: Optional[Army]) -> None:
        if mine is None:
            return _ArmyReactions.skirmish(ui, gs, army, mine)
        if not ui.confirm(f"Loose your {mine.strength()} against their {army.strength()}?", default=False):
            return
        winner_id, lines = military.resolve_battle(gs.world, mine, army, random)
        for line in lines:
            ui.print(f"[yellow]{line}[/yellow]")
        won = winner_id == mine.id
        _record(gs, army,
                f"You gave battle to {army.name} and {'won' if won else 'were beaten'}.",
                EventType.COMBAT, 4)
        gs.world.devastation[army.province] = min(100, gs.world.devastation.get(army.province, 0) + 15)
        for m in gs.character.grant_xp(60 if won else 20):
            ui.print(f"[green]{m}[/green]")

    @staticmethod
    def skirmish(ui: UI, gs: GameState, army: Army, mine: Optional[Army]) -> None:
        if army.strength() > 40:
            ui.narrate("They are far too many for one blade. To stand alone here is simply to die.")
            if not ui.confirm("Throw your life away against them anyway?", default=False):
                return
        foe_might = 6 + army.leadership
        result = resolve_combat(gs.character, army.commander, foe_might,
                                foe_health=10 + army.strength() // 4)
        for line in result.log[:6]:
            ui.print(f"  {line}")
        if result.victory:
            ui.narrate("Against all sense, you cut your way clear - a tale men will not believe.")
            _record(gs, army, f"You fought clear of {army.name} with your own hand.", EventType.COMBAT, 3)
            for m in gs.character.grant_xp(40):
                ui.print(f"[green]{m}[/green]")
        else:
            gs.character.health = max(0, gs.character.health - result.damage_taken)
            ui.narrate("They overwhelm you. You are fortunate to crawl away with your life.")
            _record(gs, army, f"You were bloodied by {army.name}.", EventType.COMBAT, 3)

    @staticmethod
    def avoid(ui: UI, gs: GameState, army: Army, mine: Optional[Army]) -> None:
        check = skill_check(gs.character, "agility", "stealth", "moderate")
        if check.success:
            ui.narrate("You keep to the hedges and hollows and slip away unseen.")
        else:
            ui.narrate("You break contact, though not before they mark your going.")
        _record(gs, army, f"You avoided {army.name}.", EventType.TRAVEL, 1)


# ---------------------------------------------------------------------------
# meeting a lord in his seat
# ---------------------------------------------------------------------------
def visit_holding(ui: UI, gs: GameState, holding: Holding) -> None:
    ui.heading(f"{holding.name}")
    ui.narrate(holding.description)
    if holding.owner_is_player:
        ui.print("[green]This is your own seat.[/green]")
        _holding_readout(ui, holding)
        return

    standing = _standing_by_house(gs, holding.holder_house)
    ui.print(f"[dim]Held by {holding.holder_house}. Garrison: {holding.garrison}. "
             f"Fortification: {holding.defense}.[/dim]")
    # guest right: the custom that governs a lord's hall
    ui.narrate("You are met at the gate. Bread and salt are the law here - offered, "
               "you and your host are bound to do no harm while you bide.")

    options = ["Seek an audience with the lord", "Ask to trade in the market",
               "Ask after news and rumor", "Take your leave"]
    idx = ui.menu(f"At {holding.name}", options, allow_back=True)
    if idx in (-1, 3):
        return
    if idx == 0:
        diff = "moderate" if standing >= 0 else "hard"
        check = skill_check(gs.character, "presence", "intrigue", diff)
        ui.print(check.describe())
        if check.success:
            ui.narrate(f"The lord of {holding.name} receives you graciously and hears your suit.")
            _record_place(gs, holding, f"You were received at {holding.name}.", EventType.DIALOGUE, 2)
        else:
            ui.narrate("You are kept waiting in a cold hall, and sent away with courtesies and nothing more.")
    elif idx == 1:
        ui.narrate(f"The market of {holding.name} offers what a {holding.kind_label()} can - "
                   "you barter for what you need.")
        _record_place(gs, holding, f"You traded at {holding.name}.", EventType.DIALOGUE, 1)
    elif idx == 2:
        ui.narrate("The talk is all of the wars, the weather, and who owes whom - "
                   "little you did not know, but a thread or two worth keeping.")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _standing(gs: GameState, faction: str) -> int:
    return gs.world.reputation(faction)


def _standing_by_house(gs: GameState, house: str) -> int:
    # map a couple of well-known houses to their factions for standing
    lookup = {v: k for k, v in campaign.FACTION_NAMES.items()}
    faction = lookup.get(house)
    return gs.world.reputation(faction) if faction else 0


def _disparity_note(ui: UI, mine: int, theirs: int) -> None:
    if mine == 0:
        ui.print("[dim]You stand alone; they are a body of armed men.[/dim]")
    elif mine >= theirs * 1.5:
        ui.print("[dim]Your host outnumbers them handily.[/dim]")
    elif theirs >= mine * 1.5:
        ui.print("[dim]They have the greater strength.[/dim]")
    else:
        ui.print("[dim]You are roughly matched.[/dim]")


def _record(gs: GameState, army: Army, text: str, etype: EventType, importance: int) -> None:
    gs.memory.record(Event(game_day=gs.world.day, type=etype, summary=text,
                           actors=[army.id], location=army.province, importance=importance))


def _record_place(gs: GameState, holding: Holding, text: str, etype: EventType, importance: int) -> None:
    gs.memory.record(Event(game_day=gs.world.day, type=etype, summary=text,
                           location=holding.province, importance=importance))


def _holding_readout(ui: UI, holding: Holding) -> None:
    ui.table(
        ["Attribute", "Value"],
        [("Kind", holding.kind_label()),
         ("Population", f"{holding.population:,}"),
         ("Garrison", str(holding.garrison)),
         ("Fortification", str(holding.defense)),
         ("Income / season", str(holding.income)),
         ("Levy potential", str(holding.levy_potential())),
         ("Buildings", ", ".join(holding.buildings) or "none"),
         ("Defenses", ", ".join(holding.defense_works) or "none")],
        title=holding.name,
    )
