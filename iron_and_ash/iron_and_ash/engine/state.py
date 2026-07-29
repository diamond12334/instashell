"""The live game state that ties the systems together."""
from __future__ import annotations

from dataclasses import dataclass

from ..character.models import Character
from ..memory.store import MemoryStore
from ..world.models import WorldState


@dataclass
class GameState:
    """Everything a running game needs in memory.

    The ``memory`` store writes straight through to the save database, while
    ``character`` and ``world`` are serialised on save. ``slot`` is the save-slot
    name so autosave knows where to write.
    """

    character: Character
    world: WorldState
    memory: MemoryStore
    slot: str
    running: bool = True

    def current_day(self) -> int:
        return self.world.day
