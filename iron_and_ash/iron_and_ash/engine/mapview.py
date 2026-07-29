"""The interactive strategic map: view, travel, and meet what you find.

This is the overworld. It renders an ASCII map of the known world with the
player's position and any forces they can see (subject to fog of war), lets them
travel province to province, inspect holdings and armies, found their own seat,
muster their levies, and - when they share a province with a lord or an army -
hand off to :mod:`narrative.reactions` for the meeting.
"""
from __future__ import annotations

from typing import List, Optional

from ..narrative import reactions
from ..persistence.saves import SaveManager
from ..ui.console import UI
from ..world import campaign, geography, holdings, mapdata
from ..world import data as wdata
from ..world import reactivity
from ..world.military import Army
from .state import GameState

# short map labels (<=4 chars) keyed by province id
ABBREV = {
    "beyond_wall": "BWal", "the_wall": "Wall", "the_gift": "Gift",
    "bear_island": "Bear", "the_dreadfort": "Drea", "winterfell": "Wint",
    "white_harbor": "WHrb", "barrowlands": "Barr", "moat_cailin": "Moat",
    "pyke": "Pyke", "the_twins": "Twin", "riverrun": "Rvrn", "harrenhal": "Harr",
    "the_eyrie": "Eyri", "gulltown": "Gull", "casterly_rock": "Cast",
    "lannisport": "Lann", "kings_landing": "KLnd", "dragonstone": "Drgn",
    "highgarden": "High", "oldtown": "Oldt", "the_arbor": "Arbr",
    "storms_end": "Strm", "sunspear": "Suns", "braavos": "Braa",
    "pentos": "Pent", "volantis": "Volt",
}
_CELL_W = 6


def open_map(ui: UI, gs: GameState, saves: SaveManager) -> None:
    """Enter the overworld. Returns to local play when the player leaves."""
    campaign.ensure_map(gs.world, gs.world.player_province or "winterfell")
    if not gs.world.player_province:
        gs.world.player_province = "winterfell"
    while True:
        prov = mapdata.PROVINCES[gs.world.player_province]
        _province_view(ui, gs, prov)
        action = _province_menu(ui, gs, prov)
        if action == "exit":
            # leaving the map drops you into the local scene of where you stand
            if wdata.province_of_location(gs.character.location) != gs.world.player_province:
                gs.character.location = wdata.entry_for_province(gs.world, gs.world.player_province)
                wdata.ensure_local(gs.world, gs.character.location)
            return
        if action == "handled":
            saves.save_game(gs)


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
def render_map(ui: UI, gs: GameState) -> None:
    world = gs.world
    rows: List[List[str]] = [[" " * _CELL_W for _ in range(mapdata.GRID_COLS)]
                             for _ in range(mapdata.GRID_ROWS)]
    for pid, prov in mapdata.PROVINCES.items():
        rows[prov.row][prov.col] = _cell(world, pid)
    ui.heading(f"The Known World  -  Day {world.day}")
    lines = ["".join(r) for r in rows]
    ui.panel("\n".join(lines), title="Map of Westeros and the Free Cities")
    ui.print("[dim]@ you   # holding   ! hostile force   x armed force   . known land[/dim]")


def _cell(world, pid: str) -> str:
    prov = mapdata.PROVINCES[pid]
    if not world.is_discovered(pid):
        return _pad("  .")     # land seen from afar; details unknown
    marker = "."
    armies = world.armies_in(pid)
    seat = world.holdings.get(f"seat_{pid}")
    if pid == world.player_province:
        marker = "@"
    elif armies:
        hostile = any(a.kind in ("bandits", "outlaws") or a.allegiance != "player"
                      and world.reputation(a.allegiance) <= -40 for a in armies)
        marker = "!" if hostile else "x"
    elif seat:
        marker = "#"
    return _pad(marker + ABBREV.get(pid, pid[:4]))


def _pad(token: str) -> str:
    return (token + " " * _CELL_W)[:_CELL_W]


# ---------------------------------------------------------------------------
# province view
# ---------------------------------------------------------------------------
def _province_view(ui: UI, gs: GameState, prov) -> None:
    world = gs.world
    ui.rule(f"{prov.name}  -  Day {world.day}")
    ui.narrate(prov.blurb)
    control = world.control_of(prov.id)
    dev = world.devastation.get(prov.id, 0)
    ui.print(f"[cyan]Held by:[/cyan] {campaign.faction_name(control) if control else 'no one'}"
             f"   [cyan]Terrain:[/cyan] {mapdata.TERRAIN[prov.terrain].name}"
             + (f"   [red]Devastation: {dev}%[/red]" if dev > 0 else ""))

    for h in world.holdings_in(prov.id):
        who = "yours" if h.owner_is_player else h.holder_house
        ui.print(f"  [green]#[/green] {h.name} ({h.kind_label()}, held by {who})")

    forces = world.armies_in(prov.id)
    if forces:
        ui.print("[yellow]Forces here:[/yellow]")
        for a in forces:
            ui.print("  " + _army_tooltip(world, a, close=True))


def _army_tooltip(world, army: Army, close: bool) -> str:
    """A marker's tooltip. Full detail if the player stands with it (close),
    otherwise only what a distant observer could tell - fog of war.
    """
    banner = campaign.faction_name(army.allegiance)
    if close:
        return (f"[bold]{army.name}[/bold] ({banner}) - {army.strength()} men "
                f"[{army.composition_line()}]; morale {army.morale_word()}, "
                f"{army.supply_status()}; orders: {army.orders_intent}.")
    return (f"{army.name} ({banner}) - {_strength_descr(army.strength())}, "
            f"bearing {'no banner you know' if army.kind in ('bandits','outlaws') else banner}.")


def _strength_descr(n: int) -> str:
    if n < 50:
        return "a small band"
    if n < 200:
        return "a couple hundred men"
    if n < 1000:
        return "several hundred men"
    if n < 3000:
        return "a few thousand men"
    return "a great host"


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------
def _province_menu(ui: UI, gs: GameState, prov) -> str:
    world = gs.world
    options: List[str] = []
    handlers: List = []

    for a in world.armies_in(prov.id):
        if a.allegiance == "player":
            continue  # your own host is handled through "command your host"
        options.append(f"Approach {a.name}")
        handlers.append(("army", a.id))
    for h in world.holdings_in(prov.id):
        options.append(f"Visit {h.name}")
        handlers.append(("holding", h.id))
    for nbr in geography.neighbors(prov.id):
        name = mapdata.PROVINCES[nbr].name
        days = geography.travel_days(nbr)
        known = "" if world.is_discovered(nbr) else " (uncharted)"
        options.append(f"Travel to {name} ({days}d){known}")
        handlers.append(("travel", nbr))

    options += ["View the full map", "Found a holding here", "Muster / command your host",
                "Rest a day", "Leave the map (return to local play)"]
    handlers += [("map", None), ("found", None), ("host", None),
                 ("rest", None), ("exit", None)]

    idx = ui.menu("The realm", options)
    kind, arg = handlers[idx]

    if kind == "army":
        army = world.armies.get(arg)
        if army:
            reactions.encounter_army(ui, gs, army)
        return "handled"
    if kind == "holding":
        holding = world.holdings.get(arg)
        if holding:
            reactions.visit_holding(ui, gs, holding)
        return "handled"
    if kind == "travel":
        _travel(ui, gs, arg)
        return "handled"
    if kind == "map":
        render_map(ui, gs)
        return "handled"
    if kind == "found":
        _found_holding(ui, gs, prov)
        return "handled"
    if kind == "host":
        _manage_host(ui, gs)
        return "handled"
    if kind == "rest":
        _advance(ui, gs, 1)
        return "handled"
    return "exit"


def _travel(ui: UI, gs: GameState, dest: str) -> None:
    days = geography.travel_days(dest)
    ui.print(f"[dim]You set out for {mapdata.PROVINCES[dest].name} "
             f"({days} days on the road)...[/dim]")
    _advance(ui, gs, days)
    gs.world.player_province = dest
    gs.world.discover(dest)
    for nbr in geography.neighbors(dest):
        gs.world.discover(nbr)
    # arriving drops you at the local scene of the seat you have reached
    gs.character.location = wdata.entry_for_province(gs.world, dest)
    wdata.ensure_local(gs.world, gs.character.location)
    entry = wdata.get_location(gs.character.location, gs.world)
    if entry:
        ui.print(f"[green]You arrive at {entry.name}.[/green]")


def _advance(ui: UI, gs: GameState, days: int) -> None:
    lines = reactivity.advance_time(gs.world, gs.memory, days)
    for line in lines:
        ui.print(f"[yellow]* {line}[/yellow]")


def _found_holding(ui: UI, gs: GameState, prov) -> None:
    cost = 200
    ui.print(f"[dim]Founding a new seat takes coin, hands, and a claim. "
             f"Cost: {cost} silver. You have {gs.character.gold}.[/dim]")
    if gs.character.gold < cost:
        ui.print("[red]You lack the silver to raise even a holdfast.[/red]")
        return
    kinds = ["keep", "castle", "town"]
    ki = ui.menu("What will you raise?", [k.title() for k in kinds], allow_back=True)
    if ki == -1:
        return
    name = ui.ask("Name your new seat", default=holdings.generate_holding_name(kinds[ki]))
    independent = ui.confirm("Hold it independently, sworn to no liege?", default=False)
    gs.character.gold -= cost
    gs.world.next_entity_seq += 1
    hid = f"holding_{gs.world.next_entity_seq}"
    holding = holdings.generate_holding(
        hid, prov.id, gs.character.house, kind=kinds[ki], name=name,
        owner_is_player=True, independent=independent, founded_day=gs.world.day,
    )
    gs.world.holdings[hid] = holding
    if not gs.character.titles:
        gs.character.titles.append(f"Lord of {name}")
    elif f"Lord of {name}" not in gs.character.titles:
        gs.character.titles.append(f"Lord of {name}")
    from ..memory import Event, EventType
    gs.memory.record(Event(
        game_day=gs.world.day, type=EventType.MILESTONE,
        summary=f"You founded {name}, a {holding.kind_label()} in {prov.name}, "
                f"seat of {gs.character.house}.",
        location=prov.id, importance=5))
    ui.panel(f"{name} rises in {prov.name} - the seat of {gs.character.house}, and yours.\n"
             f"Population {holding.population:,}, garrison {holding.garrison}, "
             f"income {holding.income}/season, and {holding.levy_potential()} levies at need.",
             title="A Seat of Your Own")


def _manage_host(ui: UI, gs: GameState) -> None:
    host = reactions.player_host(gs)
    if host is None:
        own = [h for h in gs.world.holdings.values() if h.owner_is_player]
        if not own:
            ui.print("[dim]You hold no lands from which to raise men. Found a holding first.[/dim]")
            return
        levy = sum(h.levy_potential() for h in own)
        if not ui.confirm(f"Call your banners? You can raise about {levy} levies.", default=False):
            return
        host = campaign.muster_player_levies(gs.world, gs.character)
        if host is None:
            ui.print("[red]Your lands cannot raise a host worth the name.[/red]")
            return
        ui.narrate(f"Your banners go up. {host.strength()} men gather to {gs.character.house}.")
        return
    # manage an existing host
    ui.print(_army_tooltip(gs.world, host, close=True))
    options = ["Order a march to another province", "Disband the host", "Never mind"]
    idx = ui.menu("Your host", options, allow_back=True)
    if idx == 0:
        dests = geography.neighbors(host.province) or list(mapdata.PROVINCES)
        di = ui.menu("March to", [mapdata.PROVINCES[d].name for d in dests], allow_back=True)
        if di != -1:
            host.orders_target = dests[di]
            host.orders_intent = "march"
            ui.print(f"[green]Your host makes ready to march on {mapdata.PROVINCES[dests[di]].name}.[/green]")
    elif idx == 1:
        if ui.confirm("Disband your host and send the men home?", default=False):
            host.disbanded = True
            ui.print("[dim]The banners come down; the levies return to their fields.[/dim]")
