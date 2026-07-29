"""Choosing where a new character's tale begins.

Three ways to start, mirroring the request:

* the default, at Winterfell;
* at any famous seat in the realm - you begin walking its streets and halls;
* by founding your **own** seat, where you choose the castle's kind and tune its
  size, defenses, levy strength, and prosperity yourself.

Whichever is chosen, this seeds the strategic map, sets the character's local
location and strategic province, and (for a custom hold) creates the holding,
attaches it to the character's house, and grants the title.
"""
from __future__ import annotations

from typing import List, Tuple

from ..ui.console import UI
from ..world import campaign, data as wdata, holdings, mapdata
from ..character.models import Character
from ..world.models import WorldState

# tiers offered when tuning a custom holding: label -> value
_SIZE = [("A modest holdfast", "keep", 400),
         ("A strong castle", "castle", 2000),
         ("A bustling town", "town", 6000),
         ("A great city", "city", 60000)]
_DEFENSE = [("Lightly held (wooden walls)", 2),
            ("Stoutly walled (stone)", 5),
            ("Strongly fortified (double walls)", 8),
            ("Nigh impregnable", 12)]
_LEVY = [("Few swords (about 150)", 150),
         ("A fair muster (about 500)", 500),
         ("Many banners (about 1200)", 1200),
         ("A great host (about 3000)", 3000)]
_PROSPERITY = [("Poor", 15), ("Modest", 60), ("Rich", 200), ("Opulent", 600)]


def choose_start(ui: UI, character: Character, world: WorldState) -> None:
    ui.rule("Where does your tale begin?")
    mode = ui.menu(
        "Choose your beginning",
        ["At Winterfell, in the North (the classic start)",
         "At a famous seat of the realm",
         "Found your own seat, built to your design"],
    )
    if mode == 0:
        _begin_at(character, world, "winterfell")
        return
    if mode == 1:
        _begin_at_famous_seat(ui, character, world)
        return
    _found_custom(ui, character, world)


def _begin_at(character: Character, world: WorldState, province_id: str) -> None:
    campaign.ensure_map(world, province_id)
    character.location = wdata.entry_for_province(world, province_id)
    wdata.ensure_local(world, character.location)


def _begin_at_famous_seat(ui: UI, character: Character, world: WorldState) -> None:
    seats = _seat_provinces()
    labels = [f"{p.seat} - {mapdata.PROVINCES[p.id].name} ({p.region.replace('_', ' ').title()}, "
              f"{campaign.faction_name(p.faction)})" for p in seats]
    idx = ui.menu("Choose a seat to begin at", labels)
    prov = seats[idx]
    ui.narrate(prov.blurb)
    _begin_at(character, world, prov.id)


def _found_custom(ui: UI, character: Character, world: WorldState) -> None:
    # found in lands without a famous seat of their own, so your hold is the seat
    provinces = [p for p in mapdata.PROVINCES.values()
                 if p.id not in wdata.seatscenes.PROVINCE_ENTRY and p.id != "winterfell"]
    prov_labels = [f"{mapdata.PROVINCES[p.id].name} ({p.region.replace('_', ' ').title()})"
                   for p in provinces]
    pi = ui.menu("In which land will you raise your seat?", prov_labels)
    province = provinces[pi]

    name = ui.ask("Name your seat", default=holdings.generate_holding_name("castle"))
    ki = ui.menu("How grand a seat?", [s[0] for s in _SIZE])
    di = ui.menu("How well defended?", [d[0] for d in _DEFENSE])
    li = ui.menu("How many swords can it call?", [l[0] for l in _LEVY])
    pi2 = ui.menu("How prosperous?", [p[0] for p in _PROSPERITY])
    independent = ui.confirm("Hold it independently, sworn to no liege?", default=False)

    _size_label, kind, population = _SIZE[ki]
    defense = _DEFENSE[di][1]
    levy = _LEVY[li][1]
    income = _PROSPERITY[pi2][1]

    campaign.ensure_map(world, province.id)
    hid = "player_seat"
    holding = holdings.generate_holding(
        hid, province.id, character.house, kind=kind, name=name,
        owner_is_player=True, independent=independent, founded_day=0,
    )
    # apply the player's own design over the generated flavour
    holding.population = population
    holding.defense = defense
    holding.income = income
    holding.levy_override = levy
    holding.garrison = max(holding.garrison, levy // 10)
    world.holdings[hid] = holding

    title = f"Lord of {name}"
    if title not in character.titles:
        character.titles.append(title)

    character.location = wdata.entry_for_province(world, province.id)
    wdata.ensure_local(world, character.location)

    ui.panel(
        f"{name} rises in {mapdata.PROVINCES[province.id].name}, the seat of {character.house}.\n"
        f"A {holding.kind_label()} of {population:,} souls, {_DEFENSE[di][0].lower()}, "
        f"raising some {levy} swords at need, and {_PROSPERITY[pi2][0].lower()} in its coffers.\n"
        f"You begin your tale as its lord.",
        title="A Seat of Your Own",
    )


def _seat_provinces():
    return [p for p in mapdata.PROVINCES.values()
            if p.seat and p.seat_kind in ("castle", "city", "town", "keep")]
