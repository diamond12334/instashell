"""Event vocabulary for the memory system.

Everything the world should *remember* becomes an :class:`Event`. Events are
append-only: once written they are never mutated or deleted, which is what makes
the memory "infinite" - the raw record is always there to be recalled or
re-summarised.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from ..compat import BaseModel, Field


class EventType(str, Enum):
    """Kinds of remembered happenings.

    ``importance`` on an event is a 1-5 hint used by the summariser and the
    working-memory view; these types are the stable, queryable categories.
    """

    WORLD = "world"            # background world advancement (wars, seasons)
    TRAVEL = "travel"          # the player moved
    DIALOGUE = "dialogue"      # a conversation happened
    FAVOR = "favor"            # the player helped someone
    SLIGHT = "slight"          # the player wronged someone
    OATH = "oath"              # an oath sworn
    OATH_BROKEN = "oath_broken"
    COMBAT = "combat"
    DEATH = "death"            # someone died
    ALLIANCE = "alliance"
    BETRAYAL = "betrayal"
    MARRIAGE = "marriage"
    DISCOVERY = "discovery"    # learned lore / found something
    QUEST = "quest"            # quest state change
    MILESTONE = "milestone"    # character growth / title / land


class Event(BaseModel):
    """A single remembered happening.

    ``game_day`` anchors the event on the in-world calendar; ``actors`` lists the
    ids of NPCs/factions involved so the store can answer "what has passed
    between me and X". ``data`` carries structured detail for future systems (or
    an LLM narration layer) without needing a schema change.
    """

    game_day: int
    type: EventType
    summary: str
    actors: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    importance: int = 2  # 1 = trivial, 5 = era-defining
    data: Dict[str, Any] = Field(default_factory=dict)

    # populated by the store on write / read
    id: Optional[int] = None

    def actor_line(self) -> str:
        return ", ".join(self.actors) if self.actors else "-"
