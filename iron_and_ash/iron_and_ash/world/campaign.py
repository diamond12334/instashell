"""The campaign layer: seeding the map, wars, and the daily strategic tick.

This is the conductor that drives :mod:`world.military` across the whole map. It
seeds the canonical holdings and who controls what, declares wars (mustering
hosts on both sides), and each day advances every army, fights battles where
enemies meet, shifts control of conquered provinces, and lets bandits and outlaws
boil up out of devastated, lawless country. Information reaches the player through
a fog of war: they learn of doings in provinces they have discovered, plus
realm-shaking news that any raven would carry.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from ..memory import Event, EventType, MemoryStore
from . import geography, holdings, mapdata, military
from .models import WorldState

# map factions to their capital province, for mustering
FACTION_CAPITAL: Dict[str, str] = {
    "north_lords": "winterfell",
    "riverlands_lords": "riverrun",
    "arryn": "the_eyrie",
    "lannister": "casterly_rock",
    "tyrell": "highgarden",
    "baratheon": "storms_end",
    "martell": "sunspear",
    "greyjoy": "pyke",
    "iron_throne": "kings_landing",
    "nights_watch": "the_wall",
    "free_folk": "beyond_wall",
    "braavos": "braavos",
    "pentos": "pentos",
    "volantis": "volantis",
}

FACTION_NAMES: Dict[str, str] = {
    "north_lords": "House Stark", "riverlands_lords": "House Tully",
    "arryn": "House Arryn", "lannister": "House Lannister",
    "tyrell": "House Tyrell", "baratheon": "House Baratheon",
    "martell": "House Martell", "greyjoy": "House Greyjoy",
    "iron_throne": "the Iron Throne", "nights_watch": "the Night's Watch",
    "free_folk": "the Free Folk", "braavos": "Braavos",
    "pentos": "Pentos", "volantis": "Volantis", "bandit": "brigands",
    "outlaw": "outlaws", "player": "your household",
}

MAX_ARMIES = 40   # ceiling so the sim can't run away


def faction_name(faction: str) -> str:
    return FACTION_NAMES.get(faction, faction.replace("_", " ").title())


# ---------------------------------------------------------------------------
# seeding
# ---------------------------------------------------------------------------
def ensure_map(world: WorldState, start_province: str = "winterfell") -> None:
    """Idempotently seed the strategic map into a save that lacks it."""
    if world.map_ready:
        return
    for pid, prov in mapdata.PROVINCES.items():
        world.province_control.setdefault(pid, prov.faction)
        world.devastation.setdefault(pid, 0)
        if prov.seat:
            hid = f"seat_{pid}"
            if hid not in world.holdings:
                world.holdings[hid] = holdings.generate_holding(
                    hid, pid, faction_name(prov.faction),
                    kind=prov.seat_kind or "castle", name=prov.seat,
                )
    world.player_province = start_province
    world.discover(start_province)
    for nbr in geography.neighbors(start_province):
        world.discover(nbr)
    world.map_ready = True


# ---------------------------------------------------------------------------
# wars
# ---------------------------------------------------------------------------
def declare_war(world: WorldState, memory: MemoryStore, attacker: str,
                defender: str, cause: str,
                rng: Optional[random.Random] = None) -> List[str]:
    """Open a war: record it, raise the temperature, and muster a host on each
    side marching toward the other's seat.
    """
    rng = rng or random
    world.wars.append({"attacker": attacker, "defender": defender,
                       "cause": cause, "start_day": world.day})
    world.war_intensity = min(100, world.war_intensity + 40)

    lines = [f"War! {faction_name(attacker)} takes up arms against "
             f"{faction_name(defender)} - {cause}."]
    atk_cap = FACTION_CAPITAL.get(attacker)
    def_cap = FACTION_CAPITAL.get(defender)
    if atk_cap and len(world.living_armies()) < MAX_ARMIES:
        host = military.muster_host(
            world, attacker, atk_cap,
            name=f"the host of {faction_name(attacker)}",
            commander="the Lord Commander", leadership=rng.randint(2, 4),
            strength_hint=rng.randint(2500, 6000),
        )
        host.orders_target = def_cap
        host.orders_intent = "march"
        world.armies[host.id] = host
    if def_cap and len(world.living_armies()) < MAX_ARMIES:
        host = military.muster_host(
            world, defender, def_cap,
            name=f"the host of {faction_name(defender)}",
            commander="the Lord Commander", leadership=rng.randint(2, 4),
            strength_hint=rng.randint(2500, 6000),
        )
        host.orders_target = atk_cap
        host.orders_intent = "march"
        world.armies[host.id] = host

    memory.record(Event(game_day=world.day, type=EventType.WORLD,
                        summary=lines[0], importance=5,
                        data={"war": True, "attacker": attacker, "defender": defender}))
    return lines


def maybe_random_war(world: WorldState, memory: MemoryStore,
                     rng: random.Random) -> List[str]:
    """A small chance, in quiet times, that some quarrel flares into open war."""
    if world.wars or world.war_intensity > 20:
        return []
    if rng.random() > 0.02:
        return []
    causes = ["a disputed succession", "an insult unavenged", "a broken betrothal",
              "raids across the border", "an unpaid debt of blood"]
    pairs = [("lannister", "riverlands_lords"), ("baratheon", "iron_throne"),
             ("greyjoy", "north_lords"), ("tyrell", "martell"),
             ("arryn", "lannister")]
    atk, dfn = rng.choice(pairs)
    return declare_war(world, memory, atk, dfn, rng.choice(causes), rng)


# ---------------------------------------------------------------------------
# the daily strategic tick
# ---------------------------------------------------------------------------
def strategic_tick(world: WorldState, memory: MemoryStore, days: int,
                   rng: Optional[random.Random] = None) -> List[str]:
    """Advance the whole military map by ``days``; return news the player learns."""
    if not world.map_ready:
        return []
    rng = rng or random
    news: List[str] = []

    # 1. advance every army (logistics, finances, morale, movement)
    for army in list(world.living_armies()):
        for line in military.tick_army(world, army, days, rng):
            _broadcast(world, memory, news, army.province, line, importance=2)

    # 2. battles wherever hostile armies now share a province
    for pid in list(mapdata.PROVINCES):
        _resolve_province_battles(world, memory, news, pid, rng)

    # 3. lawlessness: bandits/outlaws form in devastated or war-torn country
    _spawn_lawlessness(world, memory, news, rng, days)

    # 4. random wars, and cool-down of intensity/devastation in peace
    news += maybe_random_war(world, memory, rng)
    _cool_down(world, days)
    _close_finished_wars(world, memory, news)

    # cull the dead
    world.armies = {aid: a for aid, a in world.armies.items()
                    if not a.disbanded and a.strength() > 0}
    return news


def _resolve_province_battles(world: WorldState, memory: MemoryStore,
                              news: List[str], province: str,
                              rng: random.Random) -> None:
    guard = 0
    while guard < 6:
        guard += 1
        armies = world.armies_in(province)
        if len(armies) < 2:
            return
        armies.sort(key=lambda a: -a.combat_power())
        attacker = armies[0]
        defender = next((a for a in armies[1:] if a.is_hostile_to(attacker.allegiance)
                         and attacker.is_hostile_to(a.allegiance)), None)
        if defender is None:
            return
        _, lines = military.resolve_battle(world, attacker, defender, rng)
        world.devastation[province] = min(100, world.devastation.get(province, 0) + 15)
        world.war_intensity = min(100, world.war_intensity + 3)
        winner = attacker if not attacker.disbanded else defender
        for line in lines:
            _broadcast(world, memory, news, province, line, importance=4, always=True)
        # occupation: a victorious host seizes an enemy province
        if (winner.kind == "host" and not winner.disbanded
                and world.control_of(province) != winner.allegiance
                and not any(a.allegiance == world.control_of(province)
                            for a in world.armies_in(province))):
            old = world.control_of(province)
            world.province_control[province] = winner.allegiance
            seat = _seat_of(world, province)
            if seat:
                seat.holder_house = faction_name(winner.allegiance)
            _broadcast(world, memory, news, province,
                       f"{faction_name(winner.allegiance)} seizes "
                       f"{mapdata.PROVINCES[province].name} from {faction_name(old)}.",
                       importance=4, always=True)


def _spawn_lawlessness(world: WorldState, memory: MemoryStore, news: List[str],
                       rng: random.Random, days: int) -> None:
    if len(world.living_armies()) >= MAX_ARMIES:
        return
    for pid, dev in list(world.devastation.items()):
        pressure = dev + world.war_intensity // 2
        if pressure <= 20:
            continue
        # already crawling with brigands? don't stack endlessly
        if any(a.kind in ("bandits", "outlaws") for a in world.armies_in(pid)):
            continue
        chance = min(0.5, pressure / 300.0) * days
        if rng.random() < chance:
            band = military.form_bandits(world, pid, intensity=pressure, rng=rng)
            world.armies[band.id] = band
            _broadcast(world, memory, news, pid,
                       f"{band.name} ({band.strength()} strong) rises in "
                       f"{mapdata.PROVINCES[pid].name}, preying on the roads.",
                       importance=3)
            if len(world.living_armies()) >= MAX_ARMIES:
                return


def _cool_down(world: WorldState, days: int) -> None:
    world.war_intensity = max(0, world.war_intensity - days)
    for pid in list(world.devastation):
        if world.devastation[pid] > 0 and not world.armies_in(pid):
            world.devastation[pid] = max(0, world.devastation[pid] - days)


def _close_finished_wars(world: WorldState, memory: MemoryStore,
                         news: List[str]) -> None:
    still = []
    for war in world.wars:
        atk_hosts = any(a.kind == "host" and a.allegiance == war["attacker"]
                        for a in world.living_armies())
        def_hosts = any(a.kind == "host" and a.allegiance == war["defender"]
                        for a in world.living_armies())
        if atk_hosts or def_hosts or (world.day - war["start_day"] < 10):
            still.append(war)
        else:
            line = (f"The war between {faction_name(war['attacker'])} and "
                    f"{faction_name(war['defender'])} guts itself out; the hosts are spent.")
            news.append(line)
            memory.record(Event(game_day=world.day, type=EventType.WORLD,
                                summary=line, importance=4))
    world.wars = still


# ---------------------------------------------------------------------------
# player forces
# ---------------------------------------------------------------------------
def muster_player_levies(world: WorldState, character, rng: Optional[random.Random] = None) -> Optional[military.Army]:
    """Raise the player's own host from the levies of their holdings."""
    rng = rng or random
    own = [h for h in world.holdings.values() if h.owner_is_player]
    if not own:
        return None
    total_levy = sum(h.levy_potential() for h in own)
    if total_levy < 10:
        return None
    province = own[0].province
    s = total_levy
    comp = {"levies": int(s * 0.6), "light_infantry": int(s * 0.2),
            "archers": int(s * 0.15), "men_at_arms": int(s * 0.05)}
    army = military.Army(
        id=military._next_id(world, "player_host"),
        name=f"the levies of {character.house}",
        kind="host", allegiance="player", commander=character.name,
        leadership=2 + character.attributes.modifier("presence"),
        province=province, home_province=province, composition=comp,
        morale=65, coffers=character.gold,
    )
    military._provision(army, rng, 15, 30)
    world.armies[army.id] = army
    return army


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _seat_of(world: WorldState, province: str) -> Optional[holdings.Holding]:
    return world.holdings.get(f"seat_{province}")


def _broadcast(world: WorldState, memory: MemoryStore, news: List[str],
               province: str, text: str, importance: int, always: bool = False) -> None:
    """Record big news to memory, and surface to the player only what they'd learn.

    The player learns of events in provinces they have discovered or that neighbour
    where they stand; ``always`` news (major battles, wars, conquests) reaches them
    by raven wherever they are.
    """
    near = (province in world.discovered
            or province in geography.neighbors(world.player_province)
            or province == world.player_province)
    if always or near:
        news.append(text)
    if importance >= 3:
        memory.record(Event(game_day=world.day, type=EventType.WORLD,
                            summary=text, location=province, importance=importance))
