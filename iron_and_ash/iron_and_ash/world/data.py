"""The starting world: the North around Winterfell.

A compact but real region for the vertical slice - six connected locations,
three factions, and a handful of NPCs who will remember the player. All names
and prose are original to this fan project; the geography echoes the source
without quoting it. New regions can be added by extending these dicts.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from . import localgen, seatscenes
from .models import Faction, Location, NPCDef, NPCState, WorldState

STARTING_LOCATION = "winterfell_yard"

FACTIONS: Dict[str, Faction] = {
    f.id: f for f in [
        Faction("north_lords", "The Northern Lords",
                "The bannermen of Winterfell, hard men of the First Men's blood."),
        Faction("free_folk", "The Free Folk",
                "Wildlings beyond the Wall who kneel to no southron king."),
        Faction("nights_watch", "The Night's Watch",
                "The black brothers who guard the Wall against the cold."),
    ]
}

LOCATIONS: Dict[str, Location] = {
    loc.id: loc for loc in [
        Location(
            "winterfell_yard", "The Yard of Winterfell", "north",
            "Grey granite walls rise about a broad training yard where the ring of "
            "steel never truly fades. Hot springs keep the stones warm even as snow "
            "drifts past the battlements. The great keep looms to the north.",
            exits={"the great hall": "winterfell_hall",
                   "the godswood": "winterfell_godswood",
                   "out to winter town": "winter_town"},
            npcs=["master_at_arms"],
        ),
        Location(
            "winterfell_hall", "The Great Hall", "north",
            "Long trestle tables run beneath banners of grey and white. A fire the "
            "size of a cart pit roars in the hearth, and the high seat waits cold "
            "and empty at the far end.",
            exits={"back to the yard": "winterfell_yard"},
            npcs=["maester"],
        ),
        Location(
            "winterfell_godswood", "The Godswood", "north",
            "Three acres of ancient wood, silent but for wind in the leaves. At its "
            "heart a weirwood watches with carved red eyes, its face weeping sap the "
            "colour of old blood. The old gods are close here.",
            exits={"back to the yard": "winterfell_yard"},
            npcs=["septa_or_woodswitch"],
        ),
        Location(
            "winter_town", "Winter Town", "north",
            "A huddle of houses below the castle walls, most shuttered and empty in "
            "the warm years, filling only when winter drives the smallfolk to shelter. "
            "A market square holds a few stubborn stalls.",
            exits={"the market": "winter_town",
                   "back to the castle": "winterfell_yard",
                   "the kingsroad north": "wolfswood_road",
                   "the winesink": "winter_town_inn"},
            npcs=["merchant"],
        ),
        Location(
            "winter_town_inn", "The Smoking Log", "north",
            "A low, smoky common room that smells of tallow, wet wool, and barley "
            "beer. Travellers trade rumours here more freely than coin.",
            exits={"back outside": "winter_town"},
            npcs=["ranger"],
        ),
        Location(
            "wolfswood_road", "The Wolfswood Road", "north",
            "The kingsroad narrows here where the Wolfswood crowds close on either "
            "side, dark with pine and old snow. Something watches from the treeline - "
            "or perhaps that is only the wind.",
            exits={"into the trees": "wolfswood_road",
                   "back toward winter town": "winter_town"},
            npcs=["wildling"],
            travel_days=2,
        ),
    ]
}

NPCS: Dict[str, NPCDef] = {
    n.id: n for n in [
        NPCDef("master_at_arms", "Ser Ormund Cassel", "Master-at-Arms",
               "winterfell_yard", "north_lords",
               "A broad, greying knight with a broken nose and a soldier's patience. "
               "He runs the yard and judges every sword that enters it.", 5),
        NPCDef("maester", "Maester Wyllis", "Maester of Winterfell",
               "winterfell_hall", "north_lords",
               "A stooped man in grey robes, his chain of many metals soft against "
               "his chest. He keeps the ravens, the records, and more secrets than either.", 0),
        NPCDef("septa_or_woodswitch", "Old Nan of the Wood", "Woods Witch",
               "winterfell_godswood", None,
               "A wrinkled crone who tends the godswood and speaks to the weirwood as "
               "to an old friend. Her eyes miss nothing.", 0),
        NPCDef("merchant", "Tobbot Flint", "Market Trader",
               "winter_town", "north_lords",
               "A round, shrewd man with cold-chapped hands and a warm smile for "
               "anyone with silver. He knows the price of everything.", 0),
        NPCDef("ranger", "Qorin the Black", "Ranger of the Night's Watch",
               "winter_town_inn", "nights_watch",
               "A lean, hard-bitten ranger in weathered black, down from the Wall on "
               "some errand he keeps to himself. He drinks alone and watches the door.", 0),
        NPCDef("wildling", "Ygga Snowhair", "Free Folk Raider",
               "wolfswood_road", "free_folk",
               "A wildling woman with white-blond hair and a spear taller than she is. "
               "She is south of the Wall for reasons of her own, and wary of kneelers.", -10),
    ]
}


# ids of the original hand-authored Winterfell scene, before other seats merge in
_WINTERFELL_LOCATION_IDS = set(LOCATIONS)

# fold in the hand-authored scenes for the other great seats
LOCATIONS.update(seatscenes.SCENE_LOCATIONS)
NPCS.update(seatscenes.SCENE_NPCS)


def new_world_state(era: str = "agot") -> WorldState:
    """Build the initial mutable world overlay from the static definitions."""
    ws = WorldState(day=0, era=era)
    for npc in NPCS.values():
        ws.npcs[npc.id] = NPCState(id=npc.id, location=npc.home_location)
    for fac in FACTIONS:
        ws.faction_reputation.setdefault(fac, 0)
    return ws


def npcs_at(location_id: str, world: WorldState) -> List[str]:
    """Ids of living NPCs currently at a location (respecting the save overlay)."""
    present: List[str] = []
    for npc_id, state in world.npcs.items():
        if state.alive and state.location == location_id:
            present.append(npc_id)
    return present


# ---------------------------------------------------------------------------
# scene resolver: authored (static) + generated (from the save) locations & NPCs
# ---------------------------------------------------------------------------
def province_of_location(location_id: str) -> Optional[str]:
    """Which strategic province a local location belongs to."""
    if location_id in _WINTERFELL_LOCATION_IDS:
        return "winterfell"
    if location_id in seatscenes.LOC_PROVINCE:
        return seatscenes.LOC_PROVINCE[location_id]
    if location_id.startswith("gen:"):
        return location_id.split(":")[1]
    return None


def get_location(location_id: str, world: Optional[WorldState] = None) -> Optional[Location]:
    """Resolve a location id to its definition (authored or generated)."""
    if location_id in LOCATIONS:
        return LOCATIONS[location_id]
    if location_id.startswith("gen:") and world is not None:
        pid = location_id.split(":")[1]
        return localgen.scene_for_province(world, pid).locations.get(location_id)
    return None


def get_npc(npc_id: str, world: Optional[WorldState] = None) -> Optional[NPCDef]:
    """Resolve an NPC id to its definition (authored or generated)."""
    if npc_id in NPCS:
        return NPCS[npc_id]
    if npc_id.startswith("gnpc:") and world is not None:
        pid = npc_id.split(":")[1]
        return localgen.scene_for_province(world, pid).npcs.get(npc_id)
    return None


def entry_for_province(world: WorldState, province_id: str) -> str:
    """The local location a traveller arrives at when reaching a province."""
    if province_id == "winterfell":
        return STARTING_LOCATION
    if province_id in seatscenes.PROVINCE_ENTRY:
        return seatscenes.PROVINCE_ENTRY[province_id]
    return localgen.entry_for_province(world, province_id)


def ensure_local(world: WorldState, location_id: str) -> None:
    """Make sure a generated scene's NPCs are placed in the world.

    Authored scenes (Winterfell, the great seats) are placed at world creation;
    generated scenes are populated lazily the first time the player arrives.
    """
    if not location_id.startswith("gen:"):
        return
    pid = province_of_location(location_id)
    if pid is None:
        return
    scene = localgen.scene_for_province(world, pid)
    for npc_id, npc in scene.npcs.items():
        if npc_id not in world.npcs:
            world.npcs[npc_id] = NPCState(id=npc_id, location=npc.home_location)
