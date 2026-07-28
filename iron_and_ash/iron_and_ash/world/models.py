"""World models: static definitions and the mutable world state.

Static geography, factions and NPCs are declared as data in ``world.data``. The
*mutable* overlay - the in-game date, faction standing, which NPCs are alive and
where they are, and story flags - lives in :class:`WorldState`, which is part of
every save.
"""
from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional

from pydantic import BaseModel, Field

from .holdings import Holding
from .military import Army


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

    # -- strategic map layer (all default-empty so old saves load unchanged) --
    player_province: str = ""
    discovered: List[str] = Field(default_factory=list)     # fog of war
    holdings: Dict[str, Holding] = Field(default_factory=dict)
    armies: Dict[str, Army] = Field(default_factory=dict)
    province_control: Dict[str, str] = Field(default_factory=dict)
    devastation: Dict[str, int] = Field(default_factory=dict)  # province -> 0-100
    next_entity_seq: int = 0
    war_intensity: int = 0                                  # 0-100, drives spawns
    wars: List[dict] = Field(default_factory=list)
    map_ready: bool = False

    def reputation(self, faction_id: str) -> int:
        return self.faction_reputation.get(faction_id, 0)

    def adjust_reputation(self, faction_id: str, delta: int) -> int:
        val = max(-100, min(100, self.reputation(faction_id) + delta))
        self.faction_reputation[faction_id] = val
        return val

    # -- strategic-map helpers ------------------------------------------------
    def is_discovered(self, province_id: str) -> bool:
        return province_id in self.discovered

    def discover(self, province_id: str) -> None:
        if province_id and province_id not in self.discovered:
            self.discovered.append(province_id)

    def control_of(self, province_id: str) -> Optional[str]:
        return self.province_control.get(province_id)

    def living_armies(self) -> List[Army]:
        return [a for a in self.armies.values() if not a.disbanded and a.strength() > 0]

    def armies_in(self, province_id: str) -> List[Army]:
        return [a for a in self.living_armies() if a.province == province_id]

    def holdings_in(self, province_id: str) -> List[Holding]:
        return [h for h in self.holdings.values() if h.province == province_id]
