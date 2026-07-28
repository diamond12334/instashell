"""Core mechanics: skill checks and simple text combat.

Deterministic given a random seed, so tests can pin outcomes. Skill checks use a
d20 + bonus vs. difficulty; traits nudge the odds where they logically apply.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from ..character.models import Character

# named difficulty tiers
DIFFICULTY = {
    "trivial": 6,
    "easy": 9,
    "moderate": 12,
    "hard": 16,
    "daunting": 20,
}


@dataclass
class CheckResult:
    success: bool
    roll: int
    total: int
    difficulty: int
    critical: bool = False

    def describe(self) -> str:
        edge = " (a critical!)" if self.critical else ""
        verdict = "success" if self.success else "failure"
        return f"[d20={self.roll} + bonus = {self.total} vs {self.difficulty}] {verdict}{edge}"


def skill_check(char: Character, attribute: str, skill: Optional[str],
                difficulty: str = "moderate", rng: Optional[random.Random] = None,
                trait_mods: int = 0) -> CheckResult:
    rng = rng or random
    dc = DIFFICULTY.get(difficulty, 12)
    roll = rng.randint(1, 20)
    bonus = char.check_bonus(attribute, skill) + trait_mods
    # trait flavour: the craven falter under pressure, the silver-tongued persuade
    if "craven" in char.traits and attribute in ("might", "will"):
        bonus -= 2
    if "silver_tongue" in char.traits and attribute == "presence":
        bonus += 2
    total = roll + bonus
    crit = roll == 20 or roll == 1
    success = (roll == 20) or (roll != 1 and total >= dc)
    return CheckResult(success=success, roll=roll, total=total, difficulty=dc, critical=crit)


@dataclass
class CombatResult:
    victory: bool
    rounds: int
    damage_taken: int
    log: list


def resolve_combat(char: Character, foe_name: str, foe_might: int, foe_health: int,
                   rng: Optional[random.Random] = None) -> CombatResult:
    """A compact, readable duel resolved in rounds.

    Not a full tactical layer yet - it uses the character's Might/Agility and
    swordsmanship so the stat build matters, and returns a blow-by-blow log.
    """
    rng = rng or random
    log: list = []
    hp = char.health
    foe_hp = foe_health
    rounds = 0
    atk_bonus = char.attributes.modifier("might") + char.skill("swordsmanship")
    defense = 10 + char.attributes.modifier("agility")
    if "craven" in char.traits:
        atk_bonus -= 1
    while hp > 0 and foe_hp > 0 and rounds < 30:
        rounds += 1
        # player strikes
        if rng.randint(1, 20) + atk_bonus >= 10 + (foe_might // 2):
            dmg = rng.randint(3, 7) + max(0, char.attributes.modifier("might"))
            foe_hp -= dmg
            log.append(f"You land a blow on {foe_name} ({dmg} damage).")
        else:
            log.append(f"{foe_name} turns your stroke aside.")
        if foe_hp <= 0:
            break
        # foe strikes
        if rng.randint(1, 20) + foe_might >= defense:
            dmg = rng.randint(2, 6) + foe_might // 3
            hp -= dmg
            log.append(f"{foe_name} wounds you ({dmg} damage).")
        else:
            log.append(f"You dodge {foe_name}'s attack.")
    victory = foe_hp <= 0 and hp > 0
    return CombatResult(victory=victory, rounds=rounds,
                        damage_taken=char.health - max(hp, 0), log=log)
