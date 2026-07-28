"""World models: static definitions and the mutable world state.

Static geography, factions and NPCs are declared as data in ``world.data``. The
*mutable* overlay - the in-game date, faction standing, which NPCs are alive and
where they are, and story flags - lives in :class:`WorldState`, which is part of
every save.
"""
from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional

from pydantic import BaseModel, Field


class Location(NamedTuple):
    id: str
    name: str
    region: str
    description: str
    exits: Dict[str, str]      # direction/label -> location id
    npcs: List[str]            # npc ids present by default
    travel_days: int = 1       # days it costs to arrive here


class Faction(NamedTuple):
    id: str
    name: str
    description: str


class NPCDef(NamedTuple):
    id: str
    name: str
    title: str
    home_location: str
    faction: Optional[str]
    description: str
    base_disposition: int = 0


class NPCState(BaseModel):
    """The mutable state of an NPC within a save."""

    id: str
    alive: bool = True
    location: str
    age_offset: int = 0        # days aged since game start (for flavour/aging)


class WorldState(BaseModel):
    """Everything about the living world that a save must remember."""

    day: int = 0
    era: str = "agot"
    faction_reputation: Dict[str, int] = Field(default_factory=dict)
    npcs: Dict[str, NPCState] = Field(default_factory=dict)
    flags: Dict[str, str] = Field(default_factory=dict)
    quests: Dict[str, str] = Field(default_factory=dict)   # quest id -> stage
    # days-since-start markers used by world reactivity so ripples fire once
    pending_ripples: List[dict] = Field(default_factory=list)

    def reputation(self, faction_id: str) -> int:
        return self.faction_reputation.get(faction_id, 0)

    def adjust_reputation(self, faction_id: str, delta: int) -> int:
        val = max(-100, min(100, self.reputation(faction_id) + delta))
        self.faction_reputation[faction_id] = val
        return val
