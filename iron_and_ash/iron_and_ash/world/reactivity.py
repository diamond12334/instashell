"""World reactivity: the world lives and reacts between and within sessions.

Two responsibilities:

* **Advancement** - as in-game days pass (travel, resting), background history
  ticks forward: seasons turn, distant wars grind on, and NPCs age. These are
  recorded as low-importance WORLD events so they enter the permanent memory.
* **Ripples** - consequences the player set in motion. When the player helps or
  wrongs someone, a delayed ripple can be scheduled; when its day arrives it
  fires (aid arrives, an enemy moves) and is recorded as a remembered event.

This keeps the world feeling like it remembers and responds long after the
triggering act, which is the point of the memory system.
"""
from __future__ import annotations

import random
from typing import List, Optional

from ..memory import Event, EventType, MemoryStore
from . import data
from .models import WorldState

# Flavourful background beats. Kept deliberately generic so they read as the
# world turning, not as scripted plot the player must chase.
_WORLD_BEATS = [
    "Ravens carry word that the harvest was thin in the Riverlands this year.",
    "Talk in the yard says the King is hunting again while the realm's debts grow.",
    "A cold wind out of the north sets the old folk muttering that summer is ending.",
    "Merchants report bandits thick on the kingsroad south of the Neck.",
    "Whispers from White Harbor tell of strange ships flying no known banner.",
    "The maesters of the Citadel have sent a white raven, some say. Winter comes.",
]


def advance_time(world: WorldState, memory: MemoryStore, days: int,
                 season_len: int = 90) -> List[str]:
    """Advance the calendar by ``days`` and return narration lines for anything
    noteworthy that happened while time passed.
    """
    lines: List[str] = []
    start = world.day
    world.day += days
    for state in world.npcs.values():
        state.age_offset += days

    # a background beat roughly every couple of weeks of travel
    if days >= 1 and random.random() < min(0.6, 0.15 * days):
        beat = random.choice(_WORLD_BEATS)
        memory.record(Event(game_day=world.day, type=EventType.WORLD,
                             summary=beat, importance=1))
        lines.append(beat)

    # season turn
    if (start // season_len) != (world.day // season_len):
        season_no = world.day // season_len
        note = f"The turning of the season is felt across the North (season {season_no})."
        memory.record(Event(game_day=world.day, type=EventType.WORLD,
                            summary=note, importance=2))
        lines.append(note)

    lines.extend(_fire_ripples(world, memory))
    return lines


def schedule_ripple(world: WorldState, *, delay_days: int, kind: str,
                    faction: Optional[str] = None, npc: Optional[str] = None,
                    text: str = "") -> None:
    """Queue a delayed consequence to fire on a future day."""
    world.pending_ripples.append({
        "fire_day": world.day + delay_days,
        "kind": kind,
        "faction": faction,
        "npc": npc,
        "text": text,
    })


def _fire_ripples(world: WorldState, memory: MemoryStore) -> List[str]:
    lines: List[str] = []
    still_pending = []
    for ripple in world.pending_ripples:
        if ripple["fire_day"] > world.day:
            still_pending.append(ripple)
            continue
        text = ripple.get("text") or "A consequence of your deeds comes to pass."
        actors = [ripple["npc"]] if ripple.get("npc") else []
        etype = EventType.WORLD
        if ripple["kind"] == "aid":
            etype = EventType.ALLIANCE
        elif ripple["kind"] == "reprisal":
            etype = EventType.SLIGHT
        memory.record(Event(game_day=world.day, type=etype, summary=text,
                            actors=actors, importance=3))
        if ripple.get("faction"):
            delta = 6 if ripple["kind"] == "aid" else -8
            world.adjust_reputation(ripple["faction"], delta)
        lines.append(text)
    world.pending_ripples = still_pending
    return lines
