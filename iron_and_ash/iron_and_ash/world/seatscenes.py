"""Loader for the hand-authored local scenes at the great seats.

Reads ``data/seats.json`` and turns each seat into a set of :class:`Location`
and :class:`NPCDef` objects (the same types used by the Winterfell scene in
``world.data``), plus a province -> entry-location map so the overworld knows
where to drop the player when they arrive at a seat.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple

from .models import Location, NPCDef

SEATS_FILE = Path(__file__).resolve().parents[1] / "data" / "seats.json"


@lru_cache(maxsize=1)
def _load() -> Tuple[Dict[str, Location], Dict[str, NPCDef], Dict[str, str], Dict[str, str]]:
    locations: Dict[str, Location] = {}
    npcs: Dict[str, NPCDef] = {}
    province_entry: Dict[str, str] = {}
    loc_province: Dict[str, str] = {}

    raw = json.loads(SEATS_FILE.read_text(encoding="utf-8"))
    for province_id, scene in raw.items():
        province_entry[province_id] = scene["entry"]
        for loc in scene["locations"]:
            locations[loc["id"]] = Location(
                id=loc["id"], name=loc["name"], region=loc["region"],
                description=loc["description"], exits=dict(loc["exits"]),
                npcs=list(loc.get("npcs", [])),
                travel_days=int(loc.get("travel_days", 0)),
            )
            loc_province[loc["id"]] = province_id
        for npc in scene["npcs"]:
            npcs[npc["id"]] = NPCDef(
                id=npc["id"], name=npc["name"], title=npc["title"],
                home_location=npc["home_location"], faction=npc.get("faction"),
                description=npc["description"],
                base_disposition=int(npc.get("base_disposition", 0)),
            )
    return locations, npcs, province_entry, loc_province


SCENE_LOCATIONS, SCENE_NPCS, PROVINCE_ENTRY, LOC_PROVINCE = _load()
