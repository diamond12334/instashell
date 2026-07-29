"""Character data models.

These pydantic models are the single source of truth for who the player is.
They serialise cleanly to JSON (via ``model_dump``) which is exactly how the
save system stores the character inside the save database.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..compat import BaseModel, Field


ATTRIBUTES = ["might", "agility", "cunning", "presence", "will", "lore"]

ATTRIBUTE_LABELS = {
    "might": "Might",
    "agility": "Agility",
    "cunning": "Cunning",
    "presence": "Presence",
    "will": "Will",
    "lore": "Lore",
}


class Attributes(BaseModel):
    """The six core attributes. Rolled by point-buy at creation."""

    might: int = 4
    agility: int = 4
    cunning: int = 4
    presence: int = 4
    will: int = 4
    lore: int = 4

    def total(self) -> int:
        return sum(getattr(self, a) for a in ATTRIBUTES)

    def modifier(self, attribute: str) -> int:
        """A d20-style modifier derived from the attribute score."""
        return (getattr(self, attribute) - 4)


class Character(BaseModel):
    """The player character in full.

    Identity, origin, mechanical stats, skills, traits, holdings and progression
    all live here. ``location`` is the id of the character's current location so
    the world can place them on load.
    """

    # identity
    name: str
    gender: str = "unspecified"
    house: str = "None"
    house_words: str = ""
    sigil: str = ""
    appearance: str = ""
    origin: str            # id into character.data.ORIGINS
    region: str            # id into world regions
    religion: str
    background: str        # id into character.data.BACKGROUNDS

    # mechanics
    attributes: Attributes = Field(default_factory=Attributes)
    skills: Dict[str, int] = Field(default_factory=dict)
    traits: List[str] = Field(default_factory=list)

    # state
    max_health: int = 20
    health: int = 20
    gold: int = 0
    inventory: List[str] = Field(default_factory=list)
    titles: List[str] = Field(default_factory=list)
    location: str = ""

    # progression
    level: int = 1
    xp: int = 0

    def skill(self, name: str) -> int:
        return self.skills.get(name, 0)

    def check_bonus(self, attribute: str, skill: Optional[str] = None) -> int:
        """Total bonus for a skill check: attribute modifier + skill rank."""
        bonus = self.attributes.modifier(attribute)
        if skill:
            bonus += self.skill(skill)
        return bonus

    def xp_to_next(self) -> int:
        return self.level * 100

    def grant_xp(self, amount: int) -> List[str]:
        """Add XP; return a list of level-up messages (possibly empty)."""
        messages: List[str] = []
        self.xp += amount
        while self.xp >= self.xp_to_next():
            self.xp -= self.xp_to_next()
            self.level += 1
            self.max_health += 4
            self.health = self.max_health
            messages.append(f"You have grown stronger - you are now level {self.level}.")
        return messages

    def is_alive(self) -> bool:
        return self.health > 0
