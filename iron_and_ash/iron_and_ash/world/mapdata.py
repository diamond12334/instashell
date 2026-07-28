"""The strategic map: provinces, terrain, and how they connect.

This is the world at the *strategic* scale - one node per notable seat or
territory across Westeros and the nearer Free Cities of Essos - as opposed to
the fine-grained local locations of Winterfell in ``world.data``. Everything
here is static data; the mutable overlay (who controls what, who is where) lives
in :class:`~iron_and_ash.world.models.WorldState`.

Coordinates are (row, col) cells on a rendering grid, north at the top and Essos
to the east. Adjacency is authored by hand so armies march along plausible roads
and sea-lanes rather than straight lines across the map.
"""
from __future__ import annotations

from typing import Dict, List, NamedTuple, Tuple


class Terrain(NamedTuple):
    id: str
    name: str
    move_days: int      # base days to march into this province
    attrition: int      # supply drain per day of occupation (per 1000 men)
    forage: int         # supplies foraged per day here (per 1000 men)
    defense_bonus: int  # % bonus to a defender fighting here


TERRAIN: Dict[str, Terrain] = {
    t.id: t for t in [
        Terrain("plains", "plains", 3, 2, 5, 0),
        Terrain("hills", "hills", 4, 3, 3, 15),
        Terrain("mountains", "mountains", 6, 4, 1, 40),
        Terrain("forest", "forest", 5, 3, 3, 20),
        Terrain("swamp", "swamp", 6, 5, 2, 30),
        Terrain("tundra", "frozen waste", 6, 5, 1, 10),
        Terrain("desert", "desert", 6, 6, 0, 25),
        Terrain("coast", "coastland", 3, 2, 4, 5),
        Terrain("river", "river country", 3, 2, 5, 10),
        Terrain("sea", "open sea", 5, 0, 0, 0),
    ]
}


class Province(NamedTuple):
    id: str
    name: str
    region: str          # matches character.data.REGIONS ids where applicable
    terrain: str
    row: int
    col: int
    faction: str         # default controlling faction id
    seat: str            # name of the canonical seat/holding, "" if none
    seat_kind: str       # holding kind for the seat: castle/city/town/keep/""
    blurb: str


# The strategic provinces. A curated, recognisable slice of the known world.
PROVINCES: Dict[str, Province] = {
    p.id: p for p in [
        # --- Beyond the Wall & the North ---
        Province("beyond_wall", "The Haunted Forest", "beyond_wall", "tundra", 0, 4,
                 "free_folk", "", "", "The frozen wilds beyond the Wall, home to the free folk and worse."),
        Province("the_wall", "The Wall", "north", "tundra", 1, 4,
                 "nights_watch", "Castle Black", "castle", "Seven hundred feet of ice, held by the black brothers."),
        Province("the_gift", "The Gift", "north", "hills", 2, 4,
                 "nights_watch", "Queenscrown", "keep", "Lands given to the Watch, emptier every year."),
        Province("bear_island", "Bear Island", "north", "forest", 3, 2,
                 "north_lords", "Mormont Keep", "keep", "A cold, remote isle of gnarled oak and fierce folk."),
        Province("the_dreadfort", "The Dreadfort", "north", "hills", 3, 6,
                 "north_lords", "The Dreadfort", "castle", "The grim seat of the Boltons, and its darker cellars."),
        Province("winterfell", "Winterfell", "north", "forest", 4, 4,
                 "north_lords", "Winterfell", "castle", "The ancient seat of House Stark, warmed by the earth itself."),
        Province("white_harbor", "White Harbor", "north", "coast", 4, 6,
                 "north_lords", "New Castle", "city", "The North's only true city, white-walled and wealthy."),
        Province("barrowlands", "The Barrowlands", "north", "plains", 5, 3,
                 "north_lords", "Barrowton", "town", "Rolling grave-barrows of the First Men kings."),
        Province("moat_cailin", "Moat Cailin", "north", "swamp", 6, 4,
                 "north_lords", "Moat Cailin", "castle", "The ruined gateway to the North through the Neck's bogs."),
        # --- Iron Islands & Riverlands ---
        Province("pyke", "Pyke", "iron_islands", "coast", 7, 1,
                 "greyjoy", "Pyke", "castle", "The Greyjoy stronghold, crumbling into the sea that made it."),
        Province("the_twins", "The Twins", "riverlands", "river", 7, 4,
                 "riverlands_lords", "The Twins", "castle", "The Freys' toll-bridge over the Green Fork."),
        Province("riverrun", "Riverrun", "riverlands", "river", 8, 4,
                 "riverlands_lords", "Riverrun", "castle", "Seat of House Tully, moated by two rivers."),
        Province("harrenhal", "Harrenhal", "riverlands", "river", 9, 5,
                 "riverlands_lords", "Harrenhal", "castle", "The greatest castle ever built, and the most cursed."),
        # --- Vale ---
        Province("the_eyrie", "The Vale of Arryn", "vale", "mountains", 7, 7,
                 "arryn", "The Eyrie", "castle", "A mountain-walled kingdom guarded by the Bloody Gate."),
        Province("gulltown", "Gulltown", "vale", "coast", 8, 8,
                 "arryn", "Gulltown", "city", "The Vale's port, and its purse."),
        # --- Westerlands ---
        Province("casterly_rock", "Casterly Rock", "westerlands", "hills", 9, 2,
                 "lannister", "Casterly Rock", "castle", "The hollow golden mountain of the Lannisters."),
        Province("lannisport", "Lannisport", "westerlands", "coast", 10, 2,
                 "lannister", "Lannisport", "city", "A great port beneath the Rock, thick with gold."),
        # --- Crownlands ---
        Province("kings_landing", "King's Landing", "crownlands", "coast", 10, 6,
                 "iron_throne", "The Red Keep", "city", "The stinking, teeming capital and the Iron Throne."),
        Province("dragonstone", "Dragonstone", "crownlands", "coast", 10, 8,
                 "iron_throne", "Dragonstone", "castle", "The smoking island fortress of the old dragonlords."),
        # --- Reach ---
        Province("highgarden", "Highgarden", "reach", "plains", 12, 3,
                 "tyrell", "Highgarden", "castle", "The rich, chivalrous heart of the Reach."),
        Province("oldtown", "Oldtown", "reach", "coast", 14, 2,
                 "tyrell", "The Hightower", "city", "The oldest city in Westeros, seat of the Citadel."),
        Province("the_arbor", "The Arbor", "reach", "coast", 15, 2,
                 "tyrell", "Ryamsport", "town", "An island of vineyards making the realm's finest wine."),
        # --- Stormlands ---
        Province("storms_end", "Storm's End", "stormlands", "coast", 12, 7,
                 "baratheon", "Storm's End", "castle", "The drum tower that has defied the very gods."),
        # --- Dorne ---
        Province("sunspear", "Sunspear", "dorne", "desert", 15, 7,
                 "martell", "Sunspear", "castle", "The sandstone seat of the unbowed Martells."),
        # --- Essos: the nearer Free Cities ---
        Province("braavos", "Braavos", "essos", "coast", 6, 11,
                 "braavos", "The Sealord's Palace", "city", "The secret city of escaped slaves, richest of the Free Cities."),
        Province("pentos", "Pentos", "essos", "coast", 10, 11,
                 "pentos", "The Prince's Manse", "city", "A city of spice and cheese magisters across the narrow sea."),
        Province("volantis", "Volantis", "essos", "coast", 16, 12,
                 "volantis", "The Black Walls", "city", "The eldest daughter of Valyria, first city of the slave trade."),
    ]
}


# Authored adjacency (undirected). Sea-lanes included; crossings cost more via
# the sea terrain of an intervening leg, approximated by the destination.
_EDGES: List[Tuple[str, str]] = [
    ("beyond_wall", "the_wall"),
    ("the_wall", "the_gift"),
    ("the_gift", "winterfell"),
    ("winterfell", "white_harbor"),
    ("winterfell", "the_dreadfort"),
    ("winterfell", "barrowlands"),
    ("winterfell", "bear_island"),
    ("the_dreadfort", "white_harbor"),
    ("barrowlands", "moat_cailin"),
    ("moat_cailin", "the_twins"),
    ("bear_island", "pyke"),
    ("the_twins", "riverrun"),
    ("the_twins", "the_eyrie"),
    ("riverrun", "harrenhal"),
    ("riverrun", "casterly_rock"),
    ("harrenhal", "kings_landing"),
    ("the_eyrie", "gulltown"),
    ("the_eyrie", "harrenhal"),
    ("gulltown", "kings_landing"),
    ("casterly_rock", "lannisport"),
    ("casterly_rock", "highgarden"),
    ("lannisport", "highgarden"),
    ("kings_landing", "storms_end"),
    ("kings_landing", "dragonstone"),
    ("kings_landing", "highgarden"),
    ("highgarden", "oldtown"),
    ("highgarden", "storms_end"),
    ("oldtown", "the_arbor"),
    ("oldtown", "sunspear"),
    ("storms_end", "sunspear"),
    ("pyke", "lannisport"),
    # sea-lanes across the narrow sea
    ("gulltown", "braavos"),
    ("dragonstone", "pentos"),
    ("kings_landing", "pentos"),
    ("braavos", "pentos"),
    ("pentos", "volantis"),
    ("sunspear", "volantis"),
]


def _build_adjacency() -> Dict[str, List[str]]:
    adj: Dict[str, List[str]] = {pid: [] for pid in PROVINCES}
    for a, b in _EDGES:
        adj[a].append(b)
        adj[b].append(a)
    return adj


ADJACENCY: Dict[str, List[str]] = _build_adjacency()

# Rendering grid extent (rows, cols), with a little margin.
GRID_ROWS = max(p.row for p in PROVINCES.values()) + 1
GRID_COLS = max(p.col for p in PROVINCES.values()) + 1
